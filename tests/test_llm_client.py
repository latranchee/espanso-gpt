import unittest

from llm_client import THINKING_EFFORT, _build_openai_args

MESSAGES = [{"role": "user", "content": "hi"}]


class BuildOpenaiArgsTest(unittest.TestCase):
    def test_reasoning_model_defaults_to_thinking_effort(self) -> None:
        self.assertEqual(_build_openai_args("gpt-6-luna", MESSAGES, 0.3, 2000)["reasoning_effort"], THINKING_EFFORT)

    def test_default_effort_omits_temperature(self) -> None:
        self.assertNotIn("temperature", _build_openai_args("gpt-6-luna", MESSAGES, 0.3, 2000))

    def test_effort_override_is_sent(self) -> None:
        args = _build_openai_args("gpt-6-luna", MESSAGES, 0.3, 2000, reasoning_effort="none")
        self.assertEqual(args["reasoning_effort"], "none")

    def test_no_effort_reenables_temperature(self) -> None:
        args = _build_openai_args("gpt-6-luna", MESSAGES, 0.3, 2000, reasoning_effort="none")
        self.assertEqual(args["temperature"], 0.3)

    def test_classic_model_ignores_effort(self) -> None:
        args = _build_openai_args("gpt-4o-mini", MESSAGES, 0.3, 2000, reasoning_effort="none")
        self.assertNotIn("reasoning_effort", args)


if __name__ == "__main__":
    unittest.main()
