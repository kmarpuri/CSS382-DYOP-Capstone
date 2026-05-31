"""End-to-end recommendation pipeline.

Wires together the deterministic ranker, the optional LLM reasoning
layer, the LLM-output validator, and the fill-to-N quarterly plan
builder.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Iterable

from pydantic import BaseModel, Field

from capstone.config import AppConfig
from capstone.graph import PrereqGraph
from capstone.ranker import (
    CourseScore,
    Ranker,
    _course_level,
    _parse_credits,
    build_completed_grades,
    build_in_progress_set,
)
from capstone.transcript.models import Transcript

logger = logging.getLogger(__name__)


# ── Public output shapes ─────────────────────────────────────────────────

class Recommendation(BaseModel):
    """One ranked recommendation, suitable for JSON output to the UI/LLM."""

    course_id: str
    rank: int
    title: str | None = None
    credit_hours: float = 0.0
    criticality_score: float = 0.0
    availability_score: float = 0.0
    progress_score: float = 0.0
    synergy_score: float = 0.0
    score: float = 0.0
    fits_load: bool = False
    fits_major: bool = True
    offered_next_quarter: bool = True
    reasoning: str | None = None
    completed_soft_prereqs: list[str] = Field(default_factory=list)
    missing_soft_prereqs: list[str] = Field(default_factory=list)
    # Best available instructor rating across this course's scheduled
    # sections, sourced from the optional RateMyProfessor cache. Null
    # when no rating is on file. The "best" tiebreaker is num_ratings
    # so single-review outliers don't surface as "5 stars".
    best_instructor: dict | None = None


class RecommendationResult(BaseModel):
    """Final structured output of the recommendation pipeline."""

    recommendations: list[Recommendation] = Field(default_factory=list)
    total_credits: float = 0.0
    target_load: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    used_llm: bool = False
    target_quarter: str | None = None


# ── Recommender ──────────────────────────────────────────────────────────

class Recommender:
    """Compose the ranker, validator, and fill-to-N planner."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        config: AppConfig,
        graph: PrereqGraph | None = None,
    ):
        self.conn = conn
        self.config = config
        self.graph = graph or PrereqGraph.from_db(conn)
        self.ranker = Ranker(conn, config, self.graph)

    # ── Main entry point ────────────────────────────────────────────────

    def recommend(
        self,
        transcript: Transcript,
        target_quarter: str | None = None,
        credit_load: int | None = None,
        top_n: int = 10,
        use_llm: bool = True,
        user_prompt: str = "",
    ) -> RecommendationResult:
        if credit_load is None:
            credit_load = self.config.credit_limits.default

        all_scores = self.ranker.score_all(transcript, target_quarter)

        # Hard filter — registration constraints
        eligible = [
            s for s in all_scores
            if s.eligibility_ok and s.offered_next_quarter and s.fits_major
        ]
        # Fallback: if filtering by `fits_major` left too few candidates,
        # re-include eligible non-major courses
        if len(eligible) < top_n:
            for s in all_scores:
                if (s.eligibility_ok and s.offered_next_quarter
                        and s not in eligible):
                    eligible.append(s)

        ranked = self.ranker.rank(eligible)

        warnings: list[str] = []

        # Optional LLM reranking
        llm_used = False
        if use_llm:
            try:
                from capstone.llm.backend import default_backend
                from capstone.llm.reasoner import LLMReasoner

                backend = default_backend()
                reasoner = LLMReasoner(backend, self.conn)
                ranked, llm_warnings = reasoner.rerank(
                    ranked[: max(top_n * 2, 20)],
                    transcript=transcript,
                    target_quarter=target_quarter,
                    user_prompt=user_prompt,
                )
                warnings.extend(llm_warnings)
                llm_used = True
            except Exception as e:
                logger.warning(f"LLM layer unavailable, falling back to rule-based: {e}")
                warnings.append(f"LLM reasoning skipped: {e}")

        # Fill-to-N plan
        chosen, fill_warnings = self._fill_to_n(ranked, credit_load)
        warnings.extend(fill_warnings)
        chosen_ids = {s.course_id for s in chosen}

        # Build output recommendations
        w = self.config.ranking_weights
        completed = {c.course_id for c in transcript.completed if not c.is_withdrawn}

        # Look up cached instructor ratings for every recommended course
        # in one pass so we don't N+1 the DB.
        course_to_best_instructor = self._lookup_best_instructors(
            [s.course_id for s in ranked[:top_n]], target_quarter,
        )

        recs: list[Recommendation] = []
        for i, s in enumerate(ranked[:top_n], 1):
            soft_edges = [
                e for e in self.graph.direct_prereqs(s.course_id)
                if e.type == "recommended"
            ]
            done_soft = [e.prereq_id for e in soft_edges if e.prereq_id in completed]
            missing_soft = [e.prereq_id for e in soft_edges if e.prereq_id not in completed]

            recs.append(
                Recommendation(
                    course_id=s.course_id,
                    rank=i,
                    title=s.title,
                    credit_hours=s.credits,
                    criticality_score=round(s.criticality_score, 3),
                    availability_score=round(s.availability_score, 3),
                    progress_score=round(s.progress_score, 3),
                    synergy_score=round(s.synergy_score, 3),
                    score=round(
                        w.criticality * s.criticality_score
                        + w.availability * s.availability_score
                        + w.progress * s.progress_score
                        + w.synergy * s.synergy_score,
                        3,
                    ),
                    fits_load=s.course_id in chosen_ids,
                    fits_major=s.fits_major,
                    offered_next_quarter=s.offered_next_quarter,
                    reasoning=getattr(s, "reasoning", None),
                    completed_soft_prereqs=done_soft,
                    missing_soft_prereqs=missing_soft,
                    best_instructor=course_to_best_instructor.get(s.course_id),
                )
            )

        return RecommendationResult(
            recommendations=recs,
            total_credits=sum(s.credits for s in chosen),
            target_load=float(credit_load),
            warnings=warnings,
            used_llm=llm_used,
            target_quarter=target_quarter,
        )

    # ── Instructor ratings ─────────────────────────────────────────────

    def _lookup_best_instructors(
        self,
        course_ids: list[str],
        target_quarter: str | None,
    ) -> dict[str, dict]:
        """Return ``{course_id: best_rating_dict}`` from cached RMP data.

        "Best" = highest ``num_ratings`` among the course's sections in
        the target quarter, then by ``avg_rating``. Courses without
        scheduled sections (or whose instructors aren't in the cache)
        are simply absent from the result.
        """
        if not course_ids:
            return {}
        try:
            from capstone.scrapers.ratemyprofessor import lookup_ratings
        except Exception:
            return {}

        # Pull instructor names for each course in this quarter
        qmark = ",".join(["?"] * len(course_ids))
        params: list = list(course_ids)
        sql = (
            f"SELECT course_id, instructor FROM time_schedule "
            f"WHERE course_id IN ({qmark}) AND instructor IS NOT NULL "
            f"AND TRIM(instructor) != ''"
        )
        if target_quarter:
            sql += " AND quarter = ?"
            params.append(target_quarter)
        try:
            rows = self.conn.execute(sql, params).fetchall()
        except Exception:
            return {}

        by_course: dict[str, list[str]] = {}
        for r in rows:
            by_course.setdefault(r["course_id"], []).append(r["instructor"])

        # Look up every distinct instructor once
        all_names = sorted({n for names in by_course.values() for n in names})
        ratings = lookup_ratings(self.conn, all_names)

        result: dict[str, dict] = {}
        for cid, names in by_course.items():
            best = None
            for n in names:
                r = ratings.get(n)
                if r is None or r.get("avg_rating") is None:
                    continue
                if (
                    best is None
                    or (r.get("num_ratings") or 0) > (best.get("num_ratings") or 0)
                    or (
                        (r.get("num_ratings") or 0) == (best.get("num_ratings") or 0)
                        and (r.get("avg_rating") or 0) > (best.get("avg_rating") or 0)
                    )
                ):
                    best = r
            if best is not None:
                result[cid] = best
        return result

    # ── Fill-to-N ──────────────────────────────────────────────────────

    def _fill_to_n(
        self,
        ranked: list[CourseScore],
        target: int,
    ) -> tuple[list[CourseScore], list[str]]:
        """Greedy: walk ranked list, add courses until total ∈ [target-2, target+2].

        Respects the hard credit ceiling and avoids stacking too many
        high-difficulty (300+) courses in one quarter.
        """
        ceiling = self.config.credit_limits.hard_ceiling
        chosen: list[CourseScore] = []
        total = 0.0
        high_diff_count = 0
        warnings: list[str] = []

        for s in ranked:
            if total >= target - 2 and total + s.credits > target + 2:
                continue
            if total + s.credits > ceiling:
                continue
            # Balance: at most 2 courses at the 400+ level in one quarter
            if _course_level(s.course_id) >= 400 and high_diff_count >= 2:
                continue
            chosen.append(s)
            total += s.credits
            if _course_level(s.course_id) >= 400:
                high_diff_count += 1
            if target - 2 <= total <= target + 2:
                break

        if total < target - 2:
            warnings.append(
                f"Could only assemble {total:g} credits of eligible courses "
                f"(target {target}±2). The catalog may not have enough "
                f"offerings for this quarter that satisfy your prereqs."
            )

        return chosen, warnings
