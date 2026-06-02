"""LLM reasoning layer (Phase 4).

The LLM does **not** select courses from scratch. It receives the
top-N candidates from the deterministic ranker and:

* validates picks against the student's graduation timeline,
* reranks with awareness of multi-quarter sequencing, and
* attaches a short natural-language ``reasoning`` field to each pick.

Every ``course_id`` the LLM returns is validated against the SQLite
catalog before being shown to the user. Local reasoning models
hallucinate course codes constantly, so defense in depth is required.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from capstone.llm.backend import LLMBackend
from capstone.ranker import CourseScore
from capstone.scheduling import format_time_window
from capstone.transcript.models import Transcript

logger = logging.getLogger(__name__)


# ── LLM JSON schema (Ollama structured-output) ───────────────────────────

LLM_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "course_id": {"type": "string"},
                    "rank": {"type": "integer"},
                    "reasoning": {"type": "string"},
                },
                "required": ["course_id", "rank", "reasoning"],
            },
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["recommendations"],
}


SYSTEM_PROMPT = """You are an academic advisor for UW Bothell undergraduates.

You will be given:
- A student's academic profile (completed courses, in-progress courses, GPA,
  class standing, declared major, graduation target).
- A pre-filtered list of next-quarter candidate courses, each with a
  deterministic score breakdown (criticality, availability, progress,
  synergy) AND a `sections` list of scheduled meeting times for the target
  quarter (days, time window, instructor, room, open/closed status). Some
  sections additionally include an `instructor_rating` dict from
  RateMyProfessors — `avg_rating` (1–5, higher = better), `avg_difficulty`
  (1–5, higher = harder), `num_ratings`, `would_take_again_pct`. Treat
  ratings with few reviews (< 5) as low-signal.
- A `synergies` block: a map of "this course is materially easier if you've
  taken these other courses first" — these are pedagogical prep
  relationships, NOT formal prerequisites. The prereq DAG already
  enforces formal prereqs.
- Optionally, a `user_constraints` field — a free-form sentence the
  student wrote describing personal preferences (e.g., "prefer mornings",
  "no Fridays", "I learn better in project-heavy classes"). Day/time
  preferences in this field have ALREADY been enforced deterministically:
  the candidate list has been pre-filtered so every non-critical course
  shown has at least one section matching the requested window. Section
  `time` values are human-readable (e.g. "11:15 AM – 12:20 PM"). The only
  exception is a major-required course that conflicts — it is intentionally
  still present so you can call out the conflict rather than hide it.
  Honor any non-time preferences (project-heavy, etc.) as a strong signal.

YOUR JOB:
1. RERANK the candidates with multi-quarter foresight. Favor courses that
   unlock future quarters' required courses, especially those rarely offered.
2. Use the `synergies` block to reason about sequencing. If a candidate has
   unmet soft prep, consider whether to recommend the prep course first or
   alongside. If the prep is already done, call that out as a positive.
3. Honor `user_constraints` where it's compatible with the academic plan.
   If a section's days/time conflict with the student's stated preferences,
   call that out in `reasoning` so they can pick a different section.
4. For each course in your final ranking, write a short (1-2 sentence)
   `reasoning` field explaining why it belongs at that rank for THIS student
   — referencing the user's constraints where relevant.
5. Flag concerns in `warnings`.

HARD RULES:
- DO NOT invent new course codes. Only use course IDs from the supplied
  candidate list. Any code you emit must appear verbatim in that list.
- DO NOT recommend a course already completed or in progress.
- DO NOT drop a major-critical course solely because of a user time
  preference — call out the conflict and let the user decide.
- Output STRICTLY a JSON object with `recommendations` (list of
  {course_id, rank, reasoning}) and `warnings` (list of strings).
"""


# ── Reasoner ────────────────────────────────────────────────────────────

class LLMReasoner:
    """Rerank deterministic candidates with an LLM and attach reasoning."""

    def __init__(self, backend: LLMBackend, conn: sqlite3.Connection):
        self.backend = backend
        self.conn = conn

    def rerank(
        self,
        candidates: list[CourseScore],
        transcript: Transcript,
        target_quarter: str | None = None,
        user_prompt: str = "",
    ) -> tuple[list[CourseScore], list[str]]:
        """Return the LLM-reranked candidates and any extra warnings.

        ``user_prompt`` is a free-form string the student typed into the
        UI (e.g., "prefer mornings", "no Fridays", "I love
        project-heavy classes"). It's surfaced to the LLM as a
        ``user_constraints`` block and is allowed to influence the
        ranking, but cannot override the hard registration constraints
        — the candidate list itself was already filtered by the
        deterministic ranker.

        Falls back to the deterministic order if the LLM output cannot be
        validated.
        """
        if not candidates:
            return candidates, []

        # If the backend is hosted (e.g., Groq), strip PII from the
        # transcript before it ever reaches the prompt builder.
        if getattr(self.backend, "requires_redaction", False):
            from capstone.llm.redact import redact_for_external
            transcript = redact_for_external(transcript)

        prompt = self._build_prompt(
            candidates, transcript, target_quarter, user_prompt,
        )
        try:
            response = self.backend.generate_json(
                system=SYSTEM_PROMPT,
                prompt=prompt,
                schema=LLM_OUTPUT_SCHEMA,
            )
        except Exception as e:
            logger.warning(f"LLM call failed; using deterministic order: {e}")
            return candidates, [f"LLM error: {e}"]

        reranked, validation_warnings = self._validate_response(response, candidates)

        if not reranked:
            return candidates, validation_warnings + [
                "LLM output failed validation; using deterministic order."
            ]
        return reranked, validation_warnings

    # ── prompt building ───────────────────────────────────────────────

    def _build_prompt(
        self,
        candidates: list[CourseScore],
        transcript: Transcript,
        target_quarter: str | None,
        user_prompt: str = "",
    ) -> str:
        completed_summary = [
            {
                "course_id": c.course_id,
                "title": c.title,
                "grade": c.grade,
                "quarter": f"{c.quarter}{c.year}",
            }
            for c in transcript.completed[-15:]  # cap context
        ]
        in_progress = [
            {"course_id": c.course_id, "title": c.title}
            for c in transcript.in_progress
        ]
        # Pre-fetch meeting-time data so the LLM can reason about
        # time-of-day / day-of-week preferences expressed in user_prompt.
        sections_by_course = self._fetch_sections(
            [s.course_id for s in candidates], target_quarter,
        )

        candidate_table = [
            {
                "course_id": s.course_id,
                "title": s.title,
                "credits": s.credits,
                "criticality": round(s.criticality_score, 2),
                "availability": round(s.availability_score, 2),
                "progress": round(s.progress_score, 2),
                "synergy": round(s.synergy_score, 2),
                "offering_pattern": s.offering_pattern,
                "sections": sections_by_course.get(s.course_id, []),
            }
            for s in candidates
        ]

        # Pedagogical synergies the student should consider
        synergies = self._build_synergies_block(candidates, transcript)

        payload = {
            "student": {
                "major": transcript.major,
                "class_standing": transcript.class_standing,
                "gpa": transcript.cumulative_gpa,
                "total_credits": transcript.total_credits_earned,
            },
            "completed_recent": completed_summary,
            "in_progress": in_progress,
            "target_quarter": target_quarter,
            "candidates": candidate_table,
            "synergies": synergies,
        }
        if user_prompt and user_prompt.strip():
            payload["user_constraints"] = user_prompt.strip()
        return (
            "Rerank the candidates below for this student.\n\n"
            "Student profile + candidate list:\n"
            + json.dumps(payload, indent=2)
            + "\n\nReturn JSON only."
        )

    def _fetch_sections(
        self,
        course_ids: list[str],
        target_quarter: str | None,
    ) -> dict[str, list[dict]]:
        """Return ``{course_id: [{days, time, instructor, ...}, ...]}``.

        Reads the ``time_schedule`` table. Empty dict if the table is
        absent (older catalogs) or no sections are scheduled.
        """
        if not course_ids:
            return {}
        try:
            # Filter to the target quarter when known so we don't surface
            # stale sections from past quarters.
            qmark = ",".join(["?"] * len(course_ids))
            if target_quarter:
                rows = self.conn.execute(
                    f"""SELECT course_id, section_id, days, time_start,
                              time_end, instructor, building, room, status
                       FROM time_schedule
                       WHERE course_id IN ({qmark}) AND quarter = ?
                       ORDER BY course_id, section_id""",
                    [*course_ids, target_quarter],
                ).fetchall()
            else:
                rows = self.conn.execute(
                    f"""SELECT course_id, section_id, days, time_start,
                              time_end, instructor, building, room, status
                       FROM time_schedule
                       WHERE course_id IN ({qmark})
                       ORDER BY course_id, section_id""",
                    course_ids,
                ).fetchall()
        except Exception as e:
            logger.debug(f"time_schedule lookup failed: {e}")
            return {}

        # Look up cached professor ratings, if any
        try:
            from capstone.scrapers.ratemyprofessor import lookup_ratings
            instructor_names = [r["instructor"] for r in rows if r["instructor"]]
            ratings = lookup_ratings(self.conn, instructor_names)
        except Exception as e:
            logger.debug(f"professor-ratings lookup failed: {e}")
            ratings = {}

        out: dict[str, list[dict]] = {}
        for r in rows:
            cid = r["course_id"]
            rating = ratings.get(r["instructor"]) if r["instructor"] else None
            section_info = {
                "section": r["section_id"],
                "days": r["days"],
                "time": format_time_window(r["time_start"], r["time_end"]),
                "instructor": r["instructor"],
                "room": f"{r['building']} {r['room']}".strip() if r["building"] else None,
                "status": r["status"],
            }
            if rating:
                section_info["instructor_rating"] = {
                    "avg_rating": rating["avg_rating"],
                    "avg_difficulty": rating["avg_difficulty"],
                    "num_ratings": rating["num_ratings"],
                    "would_take_again_pct": rating["would_take_again_pct"],
                }
            out.setdefault(cid, []).append(section_info)
        return out

    def _build_synergies_block(
        self,
        candidates: list[CourseScore],
        transcript: Transcript,
    ) -> dict:
        """For each candidate, list the soft prereqs the student has done /
        not done, plus a one-line rationale."""
        from capstone.scrapers.programs.synergies import synergy_map

        rationale_map = synergy_map(transcript.major or "CSSE")
        completed_ids = {c.course_id for c in transcript.completed if not c.is_withdrawn}

        out: dict[str, dict] = {}
        for s in candidates:
            entry = rationale_map.get(s.course_id)
            if not entry:
                continue
            done = [u for u, _ in entry if u in completed_ids]
            missing = [u for u, _ in entry if u not in completed_ids]
            out[s.course_id] = {
                "completed_prep": done,
                "missing_prep": missing,
                "rationale": entry[0][1] if entry else "",
            }
        return out

    # ── output validation ─────────────────────────────────────────────

    def _validate_response(
        self,
        response: dict[str, Any],
        candidates: list[CourseScore],
    ) -> tuple[list[CourseScore], list[str]]:
        warnings: list[str] = []
        candidate_by_id = {c.course_id: c for c in candidates}

        raw_recs = response.get("recommendations") or []
        if not isinstance(raw_recs, list):
            return [], ["LLM 'recommendations' was not a list"]

        seen: set[str] = set()
        ordered: list[CourseScore] = []

        for entry in raw_recs:
            if not isinstance(entry, dict):
                continue
            cid = (entry.get("course_id") or "").strip()
            reasoning = (entry.get("reasoning") or "").strip()

            if cid not in candidate_by_id:
                # Validate against the full catalog so we can give a
                # clear hallucination warning, not a silent drop.
                exists = self.conn.execute(
                    "SELECT 1 FROM courses WHERE course_id = ?", (cid,),
                ).fetchone()
                if exists:
                    warnings.append(
                        f"LLM picked {cid} which exists but wasn't in the "
                        f"candidate list — ignoring."
                    )
                else:
                    warnings.append(f"LLM hallucinated course code {cid!r} — dropped.")
                continue

            if cid in seen:
                continue
            seen.add(cid)

            cscore = candidate_by_id[cid]
            cscore.reasoning = reasoning   # attach LLM rationale
            ordered.append(cscore)

        # Append any candidates the LLM omitted (preserve their order)
        for c in candidates:
            if c.course_id not in seen:
                ordered.append(c)

        extra = response.get("warnings") or []
        if isinstance(extra, list):
            warnings.extend(str(x) for x in extra)

        return ordered, warnings
