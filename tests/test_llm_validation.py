"""Tests for the LLM output validator.

The LLM hallucinates course codes regularly — defense in depth is
non-negotiable per the spec. These tests verify that:
* hallucinated codes are dropped (with a warning),
* codes from outside the candidate list are dropped,
* the deterministic order is preserved when the LLM omits a candidate.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from capstone.llm.reasoner import LLMReasoner
from capstone.ranker import CourseScore
from capstone.transcript.models import Transcript


def _candidate(cid: str, title: str = "x") -> CourseScore:
    return CourseScore(
        course_id=cid,
        title=title,
        credits=5.0,
        criticality_score=0.5,
        availability_score=0.5,
        progress_score=0.5,
    )


def _mock_backend(response: dict):
    backend = MagicMock()
    backend.model = "test-model"
    backend.generate_json.return_value = response
    return backend


class TestLLMValidation:
    def test_drops_hallucinated_course(self, fixture_db):
        candidates = [_candidate("CSS 360"), _candidate("CSS 430")]
        # LLM emits a real-looking but fake course
        backend = _mock_backend({
            "recommendations": [
                {"course_id": "CSS 999", "rank": 1, "reasoning": "fake"},
                {"course_id": "CSS 360", "rank": 2, "reasoning": "real"},
            ],
        })
        r = LLMReasoner(backend, fixture_db)
        ranked, warnings = r.rerank(candidates, Transcript(major="CSSE"))
        ids = [c.course_id for c in ranked]
        assert "CSS 999" not in ids
        assert any("hallucinated" in w.lower() for w in warnings)

    def test_drops_off_list_real_courses(self, fixture_db):
        """LLM picks a course that exists but wasn't in the candidate list.

        That's still wrong (the candidate filter exists for a reason) — so
        it should be dropped with a clear warning.
        """
        candidates = [_candidate("CSS 360")]
        backend = _mock_backend({
            "recommendations": [
                # CSS 422 exists in fixture_db but isn't a candidate here.
                {"course_id": "CSS 422", "rank": 1, "reasoning": "exists but off-list"},
                {"course_id": "CSS 360", "rank": 2, "reasoning": "ok"},
            ],
        })
        r = LLMReasoner(backend, fixture_db)
        ranked, warnings = r.rerank(candidates, Transcript(major="CSSE"))
        ids = [c.course_id for c in ranked]
        assert ids == ["CSS 360"]
        assert any("exists but wasn't in the candidate" in w for w in warnings)

    def test_preserves_candidates_omitted_by_llm(self, fixture_db):
        candidates = [_candidate("CSS 360"), _candidate("CSS 430"), _candidate("CSS 422")]
        backend = _mock_backend({
            "recommendations": [
                {"course_id": "CSS 430", "rank": 1, "reasoning": "ranked first"},
            ],
        })
        r = LLMReasoner(backend, fixture_db)
        ranked, _ = r.rerank(candidates, Transcript(major="CSSE"))
        ids = [c.course_id for c in ranked]
        # CSS 430 first, then the deterministic order for the remainder.
        assert ids[0] == "CSS 430"
        assert set(ids) == {"CSS 360", "CSS 430", "CSS 422"}

    def test_attaches_reasoning_to_picks(self, fixture_db):
        candidates = [_candidate("CSS 360")]
        backend = _mock_backend({
            "recommendations": [
                {"course_id": "CSS 360", "rank": 1,
                 "reasoning": "Unlocks the capstone sequence."},
            ],
        })
        r = LLMReasoner(backend, fixture_db)
        ranked, _ = r.rerank(candidates, Transcript(major="CSSE"))
        assert ranked[0].reasoning == "Unlocks the capstone sequence."

    def test_falls_back_when_llm_raises(self, fixture_db):
        candidates = [_candidate("CSS 360"), _candidate("CSS 430")]
        backend = MagicMock()
        backend.generate_json.side_effect = RuntimeError("model not loaded")
        r = LLMReasoner(backend, fixture_db)
        ranked, warnings = r.rerank(candidates, Transcript(major="CSSE"))
        assert ranked == candidates
        assert any("LLM error" in w for w in warnings)
