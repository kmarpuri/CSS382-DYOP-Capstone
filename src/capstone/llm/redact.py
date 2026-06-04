"""PII redaction for hosted-LLM payloads.

When the LLM runs locally (Ollama), the whole transcript can be passed
freely. When it runs on a hosted API (Groq, Gemini, ...) we strip
identifying fields first so the third-party provider only sees the
academic data they actually need to reason over.

This is defense-in-depth, not a replacement for the user's consent —
the UI also surfaces an explicit privacy banner when the hosted
backend is active.
"""

from __future__ import annotations

import logging

from capstone.transcript.models import Transcript

logger = logging.getLogger(__name__)


# Fields the LLM never needs and should never see.
REDACTED_FIELDS = (
    "student_name",
    "student_id",
    "advisor",
    "advisor_email",
    "address",
)


def redact_for_external(transcript: Transcript) -> Transcript:
    """Return a deep copy of ``transcript`` with PII fields stripped.

    The LLM only needs the academic profile (courses, grades, GPA,
    major, class standing, transfer credits). Personal identifiers are
    zeroed out so they never enter the prompt or the provider's logs.

    Course-level data is preserved verbatim because it's the actual
    signal for the recommendation.
    """
    redacted = transcript.model_copy(deep=True)

    stripped = []
    for field in REDACTED_FIELDS:
        if hasattr(redacted, field) and getattr(redacted, field) is not None:
            setattr(redacted, field, None)
            stripped.append(field)

    # Transfer credits sometimes carry the originating institution's
    # name (e.g., "Bellevue College"). That's not strictly PII but it's
    # gratuitous detail — drop it.
    for tc in redacted.transfer_credits or []:
        if hasattr(tc, "source_institution"):
            setattr(tc, "source_institution", None)

    if stripped:
        logger.debug(f"Redacted fields for hosted LLM: {stripped}")
    return redacted
