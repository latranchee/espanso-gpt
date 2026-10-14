#!/usr/bin/env python3
from dataclasses import dataclass, replace

from stream_transcription import TranscriptEvent


@dataclass(frozen=True)
class LiveSpeech:
    stream_id: int
    locked_chunks: tuple[str, ...] = ()
    interim: str = ""


@dataclass(frozen=True)
class DictationDraft:
    utterances: tuple[str, ...] = ()
    live: tuple[LiveSpeech, ...] = ()


EMPTY_DRAFT = DictationDraft()


def normalize_whitespace(text: str) -> str:
    # Typed newlines are Enter keys, which would send the message in chat apps.
    return " ".join(text.split())


def render_live_speech(speech: LiveSpeech) -> str:
    return " ".join(part for part in (*speech.locked_chunks, speech.interim) if part)


def render_draft(draft: DictationDraft) -> str:
    parts = (*draft.utterances, *(render_live_speech(speech) for speech in draft.live))
    return " ".join(part for part in parts if part)


def open_live_speech(draft: DictationDraft, stream_id: int) -> DictationDraft:
    # Reserved up front so a stream that started earlier always renders before a later one.
    return replace(draft, live=(*draft.live, LiveSpeech(stream_id)))


def find_live_speech(draft: DictationDraft, stream_id: int) -> LiveSpeech | None:
    return next((speech for speech in draft.live if speech.stream_id == stream_id), None)


def replace_live_speech(draft: DictationDraft, speech: LiveSpeech) -> DictationDraft:
    live = tuple(speech if current.stream_id == speech.stream_id else current for current in draft.live)
    return replace(draft, live=live)


def discard_live_speech(draft: DictationDraft, stream_id: int) -> DictationDraft:
    return replace(draft, live=tuple(speech for speech in draft.live if speech.stream_id != stream_id))


def commit_utterance(draft: DictationDraft, text: str) -> tuple[DictationDraft, int | None]:
    if not text:
        return draft, None
    return replace(draft, utterances=(*draft.utterances, text)), len(draft.utterances)


def next_dictation_draft(
    draft: DictationDraft, stream_id: int, event: TranscriptEvent
) -> tuple[DictationDraft, int | None]:
    speech = find_live_speech(draft, stream_id)
    if speech is None:
        return draft, None
    text = normalize_whitespace(event.text)

    if event.kind == "interim":
        return replace_live_speech(draft, replace(speech, interim=text)), None
    if event.kind == "chunk_final":
        locked_chunks = (*speech.locked_chunks, text) if text else speech.locked_chunks
        return replace_live_speech(draft, replace(speech, locked_chunks=locked_chunks, interim="")), None
    if event.kind == "utterance_final":
        cleared = replace_live_speech(draft, LiveSpeech(stream_id))
        return commit_utterance(cleared, text or render_live_speech(speech))
    return draft, None


def close_live_speech(draft: DictationDraft, stream_id: int) -> tuple[DictationDraft, int | None]:
    speech = find_live_speech(draft, stream_id)
    leftover = render_live_speech(speech) if speech else ""
    return commit_utterance(discard_live_speech(draft, stream_id), leftover)


def polish_draft(draft: DictationDraft, polished: str) -> DictationDraft:
    text = normalize_whitespace(polished)
    if not text:
        return draft
    return replace(draft, utterances=(text,))
