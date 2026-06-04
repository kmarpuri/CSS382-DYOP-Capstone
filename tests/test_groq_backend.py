"""Tests for the GroqBackend hosted LLM backend.

These mock the Groq SDK so the suite runs offline. The on-the-wire
verification was done manually against the real free-tier API.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from capstone.llm.backend import GroqBackend, OllamaBackend, default_backend
from capstone.llm.redact import REDACTED_FIELDS, redact_for_external
from capstone.transcript.models import (
    CompletedCourse,
    TransferCredit,
    Transcript,
)


# ── Backend init / config ─────────────────────────────────────────


class TestGroqBackendInit:
    def test_requires_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            GroqBackend()

    def test_picks_up_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key-123")
        b = GroqBackend()
        assert b._api_key == "test-key-123"

    def test_default_model_is_llama_70b(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "x")
        monkeypatch.delenv("CAPSTONE_LLM_MODEL", raising=False)
        assert GroqBackend().model == "llama-3.3-70b-versatile"

    def test_model_override_via_env(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "x")
        monkeypatch.setenv("CAPSTONE_LLM_MODEL", "gemma2-9b-it")
        assert GroqBackend().model == "gemma2-9b-it"

    def test_requires_redaction_flag(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "x")
        assert GroqBackend().requires_redaction is True
        # Ollama, by contrast, does NOT require redaction
        # (instantiation needs Ollama installed, so just check the class attr)
        assert OllamaBackend.requires_redaction is False


# ── Backend selection ─────────────────────────────────────────────


class TestDefaultBackendSelection:
    def test_explicit_groq(self, monkeypatch):
        monkeypatch.setenv("CAPSTONE_LLM_BACKEND", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "x")
        b = default_backend()
        assert isinstance(b, GroqBackend)

    def test_explicit_unknown_raises(self, monkeypatch):
        monkeypatch.setenv("CAPSTONE_LLM_BACKEND", "magic-cloud-9000")
        with pytest.raises(RuntimeError, match="Unknown LLM backend"):
            default_backend()

    def test_groq_key_picks_groq(self, monkeypatch):
        monkeypatch.delenv("CAPSTONE_LLM_BACKEND", raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "x")
        b = default_backend()
        assert isinstance(b, GroqBackend)


# ── generate_json round-trip (mocked) ─────────────────────────────


class TestGenerateJson:
    def test_parses_valid_json_response(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "x")

        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = (
            '{"recommendations":[{"course_id":"CSS 360","rank":1,"reasoning":"ok"}],'
            '"warnings":[]}'
        )

        with patch("groq.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.return_value = fake_response
            backend = GroqBackend()
            out = backend.generate_json("sys", "prompt")

        assert out == {
            "recommendations": [{"course_id": "CSS 360", "rank": 1, "reasoning": "ok"}],
            "warnings": [],
        }

    def test_retries_on_non_json(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "x")

        bad = MagicMock()
        bad.choices = [MagicMock()]
        bad.choices[0].message.content = "not json"

        good = MagicMock()
        good.choices = [MagicMock()]
        good.choices[0].message.content = '{"ok":true}'

        with patch("groq.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.side_effect = [bad, good]
            out = GroqBackend().generate_json("sys", "prompt", max_retries=1)

        assert out == {"ok": True}

    def test_raises_after_max_retries(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "x")
        bad = MagicMock()
        bad.choices = [MagicMock()]
        bad.choices[0].message.content = "definitely not json"

        with patch("groq.Groq") as MockGroq:
            MockGroq.return_value.chat.completions.create.return_value = bad
            with pytest.raises(RuntimeError, match="Groq failed to produce valid JSON"):
                GroqBackend().generate_json("sys", "prompt", max_retries=0)


# ── Redaction ─────────────────────────────────────────────────────


class TestRedaction:
    def _build_transcript(self) -> Transcript:
        return Transcript(
            student_name="Krish Marpuri",
            student_id="2429082",
            major="CSSE",
            class_standing="JUNIOR",
            cumulative_gpa=3.55,
            completed=[
                CompletedCourse(
                    course_id="CSS 142",
                    title="Intro",
                    credits=5.0,
                    grade="3.8",
                    quarter="AUT",
                    year=2024,
                ),
            ],
            transfer_credits=[
                TransferCredit(
                    course_id="CHEM 142",
                    title="Chem",
                    credits=5.0,
                    source="IB",
                ),
            ],
        )

    def test_strips_name_and_id(self):
        t = self._build_transcript()
        r = redact_for_external(t)
        assert r.student_name is None
        assert r.student_id is None

    def test_preserves_academic_data(self):
        t = self._build_transcript()
        r = redact_for_external(t)
        # The signal the LLM actually uses is fully retained
        assert r.major == "CSSE"
        assert r.class_standing == "JUNIOR"
        assert r.cumulative_gpa == 3.55
        assert len(r.completed) == 1
        assert r.completed[0].course_id == "CSS 142"
        assert r.completed[0].grade == "3.8"
        assert len(r.transfer_credits) == 1
        assert r.transfer_credits[0].course_id == "CHEM 142"

    def test_does_not_mutate_input(self):
        t = self._build_transcript()
        original_name = t.student_name
        redact_for_external(t)
        # Original transcript is untouched
        assert t.student_name == original_name

    def test_handles_already_null_fields(self):
        """A transcript missing the PII fields shouldn't raise."""
        t = Transcript(major="CSSE")  # no name, no id
        r = redact_for_external(t)
        assert r.student_name is None
        assert r.student_id is None

    def test_redacted_fields_constant_in_sync_with_model(self):
        """If we add a new PII field, REDACTED_FIELDS must include it."""
        # The model must at least have student_name and student_id
        t = Transcript()
        for field in ("student_name", "student_id"):
            assert hasattr(t, field), f"Transcript missing field {field!r}"
        # And REDACTED_FIELDS must include the two we care most about
        assert "student_name" in REDACTED_FIELDS
        assert "student_id" in REDACTED_FIELDS


# ── Reasoner wiring ───────────────────────────────────────────────


class TestReasonerAppliesRedaction:
    """When the backend's requires_redaction=True, the reasoner should
    redact the transcript before building the prompt."""

    def test_redacts_when_backend_requires(self, fixture_db):
        from capstone.llm.reasoner import LLMReasoner
        from capstone.ranker import CourseScore

        backend = MagicMock()
        backend.requires_redaction = True
        backend.model = "test"
        backend.generate_json.return_value = {"recommendations": [], "warnings": []}

        reasoner = LLMReasoner(backend, fixture_db)
        with patch("capstone.llm.redact.redact_for_external") as redact:
            redact.side_effect = lambda t: t  # passthrough but record the call
            reasoner.rerank(
                [CourseScore(course_id="CSS 360", title="x", credits=5.0)],
                Transcript(major="CSSE", student_name="Real Name"),
            )
            assert redact.called

    def test_no_redaction_for_local_backend(self, fixture_db):
        from capstone.llm.reasoner import LLMReasoner
        from capstone.ranker import CourseScore

        backend = MagicMock()
        backend.requires_redaction = False
        backend.model = "test"
        backend.generate_json.return_value = {"recommendations": [], "warnings": []}

        reasoner = LLMReasoner(backend, fixture_db)
        with patch("capstone.llm.redact.redact_for_external") as redact:
            reasoner.rerank(
                [CourseScore(course_id="CSS 360", title="x", credits=5.0)],
                Transcript(major="CSSE"),
            )
            assert not redact.called
