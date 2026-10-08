import unittest
from typing import Any

from clean_transcript import SAME_LANGUAGE_INSTRUCTION, build_cleanup_messages, clean_transcript

TASK_CONFIG = {
    "system_message_template": "You edit text. {language_instruction}",
    "model": "gpt-6-luna",
    "temperature": 0.3,
    "max_tokens": 2000,
}


def recording_chat(reply: str, calls: list[dict[str, Any]]) -> Any:
    def complete_chat(**kwargs: Any) -> str:
        calls.append(kwargs)
        return reply
    return complete_chat


class BuildCleanupMessagesTest(unittest.TestCase):
    def test_system_message_keeps_transcript_language(self) -> None:
        messages = build_cleanup_messages("salut", TASK_CONFIG)
        self.assertEqual(messages[0]["content"], f"You edit text. {SAME_LANGUAGE_INSTRUCTION}")

    def test_user_message_ends_with_transcript(self) -> None:
        messages = build_cleanup_messages("um so hello", TASK_CONFIG)
        self.assertTrue(messages[1]["content"].endswith("um so hello"))

    def test_empty_transcript_still_builds_two_messages(self) -> None:
        self.assertEqual(len(build_cleanup_messages("", TASK_CONFIG)), 2)


class CleanTranscriptTest(unittest.TestCase):
    def test_returns_completion_text(self) -> None:
        chat = recording_chat("Hello.", [])
        self.assertEqual(clean_transcript("um hello", TASK_CONFIG, complete_chat=chat), "Hello.")

    def test_uses_task_model(self) -> None:
        calls: list[dict[str, Any]] = []
        clean_transcript("um hello", TASK_CONFIG, complete_chat=recording_chat("Hello.", calls))
        self.assertEqual(calls[0]["model"], "gpt-6-luna")


if __name__ == "__main__":
    unittest.main()
