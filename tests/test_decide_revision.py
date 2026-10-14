import unittest
from typing import Any

from decide_revision import DECISION_MODEL, DECISIONS_URL, decide_revision, extract_revision_probability


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any], text: str = "") -> None:
        self.status_code = status_code
        self.ok = status_code < 400
        self.text = text
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def decision_payload(probability: float) -> dict[str, Any]:
    return {"answers": [{"type": "predicate", "name": "needs_revision", "probability": probability}]}


def recording_post(response: FakeResponse, calls: list[dict[str, Any]]) -> Any:
    def post(url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"url": url, **kwargs})
        return response
    return post


class ExtractRevisionProbabilityTest(unittest.TestCase):
    def test_reads_predicate_probability(self) -> None:
        self.assertEqual(extract_revision_probability(decision_payload(0.96)), 0.96)

    def test_refusal_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            extract_revision_probability({"answers": [{"type": "refusal", "name": "needs_revision"}]})

    def test_missing_answer_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            extract_revision_probability({})


class DecideRevisionTest(unittest.TestCase):
    def test_likely_revision_is_true(self) -> None:
        post = recording_post(FakeResponse(200, decision_payload(0.96)), [])
        self.assertTrue(decide_revision("So I think we should. We should.", post=post))

    def test_clean_transcript_is_false(self) -> None:
        post = recording_post(FakeResponse(200, decision_payload(0.04)), [])
        self.assertFalse(decide_revision("Okay, this is a test.", post=post))

    def test_threshold_probability_counts_as_revision(self) -> None:
        post = recording_post(FakeResponse(200, decision_payload(0.5)), [])
        self.assertTrue(decide_revision("x", post=post))

    def test_posts_to_shush_decisions_route(self) -> None:
        calls: list[dict[str, Any]] = []
        decide_revision("x", post=recording_post(FakeResponse(200, decision_payload(0.0)), calls))
        self.assertEqual(calls[0]["url"], DECISIONS_URL)

    def test_sends_luna_model(self) -> None:
        calls: list[dict[str, Any]] = []
        decide_revision("x", post=recording_post(FakeResponse(200, decision_payload(0.0)), calls))
        self.assertEqual(calls[0]["json"]["model"], DECISION_MODEL)

    def test_sends_transcript_as_input(self) -> None:
        calls: list[dict[str, Any]] = []
        decide_revision("dictated", post=recording_post(FakeResponse(200, decision_payload(0.0)), calls))
        self.assertEqual(calls[0]["json"]["input"], "dictated")

    def test_http_error_raises(self) -> None:
        post = recording_post(FakeResponse(403, {}, "no access"), [])
        with self.assertRaises(RuntimeError):
            decide_revision("x", post=post)


if __name__ == "__main__":
    unittest.main()
