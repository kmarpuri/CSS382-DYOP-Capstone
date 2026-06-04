"""End-to-end tests for the rule-based recommendation pipeline.

These verify the hard registration constraints from the spec:
- never recommend a course already completed
- never recommend a course whose prereqs aren't met
- never recommend a non-existent course
"""

from __future__ import annotations

import pytest

from capstone.config import (
    AppConfig,
    CreditLimits,
    DatabaseConfig,
    RankingWeights,
    ScraperConfig,
)
from capstone.recommender import Recommender
from capstone.transcript.models import CompletedCourse, InProgressCourse, Transcript


def _build_transcript(
    completed: list[tuple[str, str]], in_progress: list[str] | None = None
) -> Transcript:
    """Convenience: build a Transcript from (course_id, grade) tuples."""
    return Transcript(
        major="CSSE",
        class_standing="JUNIOR",
        cumulative_gpa=3.5,
        total_credits_earned=float(len(completed) * 5),
        completed=[
            CompletedCourse(
                course_id=cid,
                title=cid,
                credits=5.0,
                grade=grade,
                quarter="AUT",
                year=2024,
            )
            for cid, grade in completed
        ],
        in_progress=[
            InProgressCourse(
                course_id=cid, title=cid, credits=5.0, quarter="SPR", year=2026
            )
            for cid in (in_progress or [])
        ],
    )


def _add_section(conn, cid, days, ts, te, *, quarter="WIN", year=2026, section="A"):
    """Insert a single scheduled section into the fixture's time_schedule."""
    from datetime import datetime, timezone

    conn.execute(
        "INSERT INTO time_schedule "
        "(course_id, section_id, quarter, year, days, time_start, time_end, "
        " status, scraped_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            cid,
            section,
            quarter,
            year,
            days,
            ts,
            te,
            "Open",
            datetime(2026, 5, 18, tzinfo=timezone.utc).isoformat(),
        ),
    )


@pytest.fixture
def default_config() -> AppConfig:
    return AppConfig(
        scraper=ScraperConfig(),
        database=DatabaseConfig(),
        ranking_weights=RankingWeights(),
        credit_limits=CreditLimits(default=15, hard_ceiling=25),
    )


class TestHardConstraints:
    """Every recommendation MUST satisfy these. Spec line 251-255."""

    def test_never_recommends_completed_courses(self, fixture_db, default_config):
        completed = [("CSS 142", "3.8"), ("CSS 143", "3.0"), ("STMATH 124", "4.0")]
        transcript = _build_transcript(completed)

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(transcript, target_quarter="WIN", use_llm=False)

        completed_ids = {c for c, _ in completed}
        recommended_ids = {r.course_id for r in result.recommendations}
        assert not (
            completed_ids & recommended_ids
        ), f"Recommended already-completed: {completed_ids & recommended_ids}"

    def test_never_recommends_unmet_prereqs(self, fixture_db, default_config):
        # Student has only CSS 142 — cannot take 300+ courses
        transcript = _build_transcript([("CSS 142", "3.0")])

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(transcript, target_quarter="WIN", use_llm=False)

        # CSS 422 requires CSS 342 — should NOT be in any recommendation
        recommended_ids = {r.course_id for r in result.recommendations}
        assert "CSS 422" not in recommended_ids
        assert "CSS 430" not in recommended_ids
        assert "CSS 343" not in recommended_ids

    def test_only_recommends_existing_courses(self, fixture_db, default_config):
        transcript = _build_transcript(
            [
                ("CSS 142", "3.8"),
                ("CSS 143", "3.0"),
                ("STMATH 124", "4.0"),
                ("STMATH 125", "3.9"),
                ("CSS 342", "3.2"),
                ("CSS 301", "3.0"),
            ]
        )

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(transcript, target_quarter="WIN", use_llm=False)

        # Every course_id returned must exist in the catalog
        for r in result.recommendations:
            row = fixture_db.execute(
                "SELECT 1 FROM courses WHERE course_id = ?", (r.course_id,)
            ).fetchone()
            assert row is not None, f"recommended non-existent course {r.course_id}"

    def test_in_progress_treated_as_completed(self, fixture_db, default_config):
        # Same student, but CSS 342 is in-progress instead of completed
        transcript = _build_transcript(
            [
                ("CSS 142", "3.8"),
                ("CSS 143", "3.0"),
                ("STMATH 124", "4.0"),
                ("STMATH 125", "3.9"),
                ("CSS 301", "3.0"),
            ],
            in_progress=["CSS 342"],
        )

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(transcript, target_quarter="WIN", use_llm=False)

        # CSS 342 must not be recommended (in progress)
        ids = {r.course_id for r in result.recommendations}
        assert "CSS 342" not in ids


class TestRanking:
    def test_csse_junior_gets_core_courses_first(self, fixture_db, default_config):
        """The standard junior — past CSS 143/STMATH 125/CSS 342 — should
        see CSS 360 and CSS 343 as top picks (they unlock CSS 370, CSS 430,
        CSS 497)."""
        transcript = _build_transcript(
            [
                ("CSS 142", "3.8"),
                ("CSS 143", "3.0"),
                ("STMATH 124", "4.0"),
                ("STMATH 125", "3.9"),
                ("CSS 342", "3.2"),
                ("CSS 301", "3.0"),
            ]
        )

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(transcript, target_quarter="WIN", top_n=5, use_llm=False)

        top_ids = [r.course_id for r in result.recommendations[:3]]
        # CSS 343 and CSS 360 are gateway courses for everything else
        assert "CSS 343" in top_ids or "CSS 360" in top_ids

    def test_fill_to_n_respects_target_load(self, fixture_db, default_config):
        transcript = _build_transcript(
            [
                ("CSS 142", "3.8"),
                ("CSS 143", "3.0"),
                ("STMATH 124", "4.0"),
                ("STMATH 125", "3.9"),
                ("CSS 342", "3.2"),
                ("CSS 301", "3.0"),
            ]
        )

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(transcript, credit_load=15, use_llm=False)

        # Plan total should land within [target-2, target+2]
        assert 13 <= result.total_credits <= 17

    def test_credit_ceiling_respected(self, fixture_db, default_config):
        default_config.credit_limits.hard_ceiling = 10

        transcript = _build_transcript(
            [
                ("CSS 142", "3.8"),
                ("CSS 143", "3.0"),
                ("STMATH 124", "4.0"),
                ("STMATH 125", "3.9"),
                ("CSS 342", "3.2"),
                ("CSS 301", "3.0"),
            ]
        )

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(transcript, credit_load=15, use_llm=False)
        assert result.total_credits <= 10


class TestTimePreference:
    """Issue 1: a stated time window must actually filter the schedule."""

    def _junior(self):
        return _build_transcript(
            [
                ("CSS 142", "3.8"),
                ("CSS 143", "3.0"),
                ("STMATH 124", "4.0"),
                ("STMATH 125", "3.9"),
                ("CSS 342", "3.2"),
                ("CSS 301", "3.0"),
            ]
        )

    def test_afternoon_only_course_dropped_for_morning_pref(
        self, fixture_db, default_config
    ):
        # B WRIT 135 is not a major requirement → droppable when it conflicts.
        _add_section(fixture_db, "CSS 360", "MWF", "930", "1020")  # morning
        _add_section(fixture_db, "CSS 343", "MWF", "1030", "1120")  # morning
        _add_section(fixture_db, "B WRIT 135", "TTh", "145", "245")  # afternoon only
        fixture_db.commit()

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(
            self._junior(),
            target_quarter="WIN",
            user_prompt="I only want morning classes",
            use_llm=False,
        )
        ids = {r.course_id for r in result.recommendations}
        assert "B WRIT 135" not in ids
        assert "CSS 360" in ids or "CSS 343" in ids
        assert any("Filtered out" in w for w in result.warnings)

    def test_required_course_kept_with_warning(self, fixture_db, default_config):
        # CSS 360 is a CSSE core requirement; even if it only meets in the
        # afternoon it must survive a morning preference — but be flagged.
        _add_section(fixture_db, "CSS 360", "TTh", "145", "245")  # afternoon, required
        fixture_db.commit()

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(
            self._junior(),
            target_quarter="WIN",
            user_prompt="mornings only please",
            use_llm=False,
        )
        ids = {r.course_id for r in result.recommendations}
        assert "CSS 360" in ids
        assert any("CSS 360" in w and "required" in w for w in result.warnings)

    def test_no_pref_keeps_afternoon_courses(self, fixture_db, default_config):
        _add_section(fixture_db, "CSS 360", "TTh", "145", "245")
        fixture_db.commit()

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(self._junior(), target_quarter="WIN", use_llm=False)
        ids = {r.course_id for r in result.recommendations}
        assert "CSS 360" in ids  # no preference → not filtered


class TestPrereqOrdering:
    """Issue 2: a prereq that's also recommended must precede its dependent."""

    def test_concurrent_prereq_ranked_before_dependent(
        self, fixture_db, default_config
    ):
        # CSS 343 needs CSS 342 (done) + CSS 301 (concurrent, NOT done). Both
        # CSS 301 and CSS 343 should be recommended; 301 must come first.
        transcript = _build_transcript(
            [
                ("CSS 142", "3.8"),
                ("CSS 143", "3.0"),
                ("STMATH 124", "4.0"),
                ("STMATH 125", "3.9"),
                ("CSS 342", "3.2"),  # note: CSS 301 intentionally NOT completed
            ]
        )

        rec = Recommender(fixture_db, default_config)
        result = rec.recommend(transcript, target_quarter="WIN", use_llm=False)
        ids = [r.course_id for r in result.recommendations]

        assert "CSS 343" in ids
        assert "CSS 301" in ids
        assert ids.index("CSS 301") < ids.index(
            "CSS 343"
        ), f"prereq CSS 301 should precede CSS 343; got {ids}"
