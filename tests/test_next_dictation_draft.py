import unittest

from next_dictation_draft import (
    EMPTY_DRAFT,
    DictationDraft,
    close_live_speech,
    discard_live_speech,
    next_dictation_draft,
    normalize_whitespace,
    open_live_speech,
    polish_draft,
    render_draft,
)
from stream_transcription import TranscriptEvent

STREAM = 1
OTHER_STREAM = 2


def hear(draft: DictationDraft, kind: str, text: str, stream_id: int = STREAM) -> DictationDraft:
    return next_dictation_draft(draft, stream_id, TranscriptEvent(kind, text))[0]


def opened(*stream_ids: int) -> DictationDraft:
    draft = EMPTY_DRAFT
    for stream_id in stream_ids:
        draft = open_live_speech(draft, stream_id)
    return draft


class NormalizeWhitespaceTest(unittest.TestCase):
    def test_newlines_become_spaces(self) -> None:
        self.assertEqual(normalize_whitespace("Hi.\n\nBye."), "Hi. Bye.")

    def test_empty_stays_empty(self) -> None:
        self.assertEqual(normalize_whitespace("  "), "")


class RenderDraftTest(unittest.TestCase):
    def test_empty_draft_renders_nothing(self) -> None:
        self.assertEqual(render_draft(opened(STREAM)), "")

    def test_interim_is_rendered(self) -> None:
        self.assertEqual(render_draft(hear(opened(STREAM), "interim", "So I think")), "So I think")

    def test_locked_chunk_and_interim_are_joined_with_space(self) -> None:
        draft = hear(hear(opened(STREAM), "chunk_final", "We should."), "interim", "Send it")
        self.assertEqual(render_draft(draft), "We should. Send it")

    def test_earlier_stream_renders_first(self) -> None:
        draft = hear(hear(opened(STREAM, OTHER_STREAM), "interim", "second", OTHER_STREAM), "interim", "first")
        self.assertEqual(render_draft(draft), "first second")


class NextDictationDraftTest(unittest.TestCase):
    def test_chunk_final_replaces_interim(self) -> None:
        draft = hear(hear(opened(STREAM), "interim", "we sh-"), "chunk_final", "we should.")
        self.assertEqual(render_draft(draft), "we should.")

    def test_utterance_final_commits_stitched_text(self) -> None:
        draft = hear(hear(opened(STREAM), "chunk_final", "a."), "utterance_final", "a. b.")
        self.assertEqual(draft.utterances, ("a. b.",))

    def test_utterance_final_returns_its_index(self) -> None:
        draft = hear(opened(STREAM), "utterance_final", "first.")
        self.assertEqual(next_dictation_draft(draft, STREAM, TranscriptEvent("utterance_final", "x."))[1], 1)

    def test_utterance_final_clears_live_text(self) -> None:
        draft = hear(hear(opened(STREAM), "interim", "a"), "utterance_final", "a.")
        self.assertEqual(draft.live[0].interim, "")

    def test_empty_utterance_final_falls_back_to_locked_chunks(self) -> None:
        draft = hear(hear(opened(STREAM), "chunk_final", "kept."), "utterance_final", "")
        self.assertEqual(draft.utterances, ("kept.",))

    def test_silent_utterance_commits_nothing(self) -> None:
        self.assertEqual(hear(opened(STREAM), "utterance_final", "").utterances, ())

    def test_unknown_stream_is_ignored(self) -> None:
        self.assertEqual(hear(opened(STREAM), "interim", "ghost", OTHER_STREAM), opened(STREAM))


class CloseLiveSpeechTest(unittest.TestCase):
    def test_leftover_live_text_is_committed(self) -> None:
        draft = hear(opened(STREAM), "interim", "cut off")
        self.assertEqual(close_live_speech(draft, STREAM)[0].utterances, ("cut off",))

    def test_empty_stream_commits_nothing(self) -> None:
        self.assertIsNone(close_live_speech(opened(STREAM), STREAM)[1])

    def test_stream_slot_is_removed(self) -> None:
        self.assertEqual(close_live_speech(opened(STREAM), STREAM)[0].live, ())


class DiscardLiveSpeechTest(unittest.TestCase):
    def test_live_text_disappears(self) -> None:
        draft = hear(opened(STREAM), "interim", "oops")
        self.assertEqual(render_draft(discard_live_speech(draft, STREAM)), "")


class PolishDraftTest(unittest.TestCase):
    def test_replaces_all_utterances_with_the_polished_text(self) -> None:
        draft = DictationDraft(utterances=("um hi.", "so yeah."))
        self.assertEqual(polish_draft(draft, "Hi.").utterances, ("Hi.",))

    def test_keeps_live_speech(self) -> None:
        draft = opened(STREAM)
        self.assertEqual(polish_draft(draft, "Hi.").live, draft.live)

    def test_ignores_empty_polish(self) -> None:
        draft = DictationDraft(utterances=("hi.",))
        self.assertEqual(polish_draft(draft, " \n"), draft)

    def test_flattens_polished_newlines(self) -> None:
        self.assertEqual(polish_draft(EMPTY_DRAFT, "A.\n\nB.").utterances, ("A. B.",))


if __name__ == "__main__":
    unittest.main()
