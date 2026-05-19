"""Tests for the soft-prereq / pedagogical-synergy feature.

The synergy feature uses ``type='recommended'`` edges in the
prerequisites table to capture "X makes Y easier" pairings that aren't
formal prerequisites. The ranker rewards candidates whose soft prereqs
are already completed.
"""

from __future__ import annotations

from capstone.config import (
    AppConfig,
    CreditLimits,
    DatabaseConfig,
    RankingWeights,
    ScraperConfig,
)
from capstone.graph import PrereqGraph
from capstone.ranker import Ranker
from capstone.recommender import Recommender
from capstone.transcript.models import CompletedCourse, Transcript


def _transcript(completed: list[tuple[str, str]]) -> Transcript:
    return Transcript(
        major="CSSE",
        class_standing="JUNIOR",
        completed=[
            CompletedCourse(
                course_id=cid, title=cid, credits=5.0,
                grade=grade, quarter="AUT", year=2024,
            )
            for cid, grade in completed
        ],
    )


def _default_config(synergy_weight: float = 0.20) -> AppConfig:
    return AppConfig(
        scraper=ScraperConfig(),
        database=DatabaseConfig(),
        ranking_weights=RankingWeights(
            criticality=0.30, availability=0.20, progress=0.30,
            synergy=synergy_weight, balance_penalty=0.10,
        ),
        credit_limits=CreditLimits(default=15, hard_ceiling=25),
    )


class TestSynergyEdgesPresent:
    def test_recommended_edges_in_graph(self, fixture_db):
        """The conftest fixture seeds CSS 430 ← CSS 422 as a soft edge."""
        g = PrereqGraph.from_db(fixture_db)
        edges = g.direct_prereqs("CSS 430")
        soft = [e for e in edges if e.type == "recommended"]
        assert any(e.prereq_id == "CSS 422" for e in soft)

    def test_recommended_not_required_for_satisfaction(self, fixture_db):
        """CSS 430's formal prereq is CSS 343 only. Soft prereq CSS 422
        is not required to satisfy the course."""
        g = PrereqGraph.from_db(fixture_db)
        ok, reasons = g.prereqs_satisfied("CSS 430", {"CSS 343": "3.0"})
        assert ok
        assert reasons == []


class TestSynergyScore:
    def test_zero_when_no_prep_done(self, fixture_db):
        """Student has CSS 343 only — none of the soft prereqs for 430."""
        config = _default_config()
        transcript = _transcript([("CSS 142", "3.8"), ("CSS 143", "3.0"),
                                  ("STMATH 124", "4.0"), ("STMATH 125", "3.9"),
                                  ("CSS 342", "3.2"), ("CSS 343", "3.5"),
                                  ("CSS 301", "3.0")])

        ranker = Ranker(fixture_db, config)
        scores = {s.course_id: s for s in ranker.score_all(transcript)}
        css_430 = scores["CSS 430"]
        assert css_430.synergy_score == 0.0
        assert css_430.eligibility_ok

    def test_full_credit_when_prep_done(self, fixture_db):
        """Student took CSS 422 — CSS 430's soft prereq is satisfied,
        so synergy_score is 1.0."""
        config = _default_config()
        transcript = _transcript([("CSS 142", "3.8"), ("CSS 143", "3.0"),
                                  ("STMATH 124", "4.0"), ("STMATH 125", "3.9"),
                                  ("CSS 342", "3.2"), ("CSS 343", "3.5"),
                                  ("CSS 301", "3.0"), ("CSS 422", "3.4")])

        ranker = Ranker(fixture_db, config)
        scores = {s.course_id: s for s in ranker.score_all(transcript)}
        css_430 = scores["CSS 430"]
        assert css_430.synergy_score == 1.0

    def test_synergy_reorders_top_picks(self, fixture_db):
        """Among two roughly-equivalent candidates, the one whose soft prep
        is already done should rank higher when synergy weight is non-zero."""
        # Heavy synergy weight to make the effect dominant
        config = _default_config(synergy_weight=0.50)
        # Student has CSS 422 → synergy on CSS 430 is 1.0
        transcript = _transcript([("CSS 142", "3.8"), ("CSS 143", "3.0"),
                                  ("STMATH 124", "4.0"), ("STMATH 125", "3.9"),
                                  ("CSS 342", "3.2"), ("CSS 343", "3.5"),
                                  ("CSS 301", "3.0"), ("CSS 422", "3.4")])

        rec = Recommender(fixture_db, config)
        result = rec.recommend(transcript, target_quarter="WIN", top_n=10,
                               use_llm=False)
        ids = [r.course_id for r in result.recommendations]
        # CSS 430 should be in the top 2 thanks to the synergy bonus
        assert "CSS 430" in ids[:2], f"CSS 430 not in top 2, got {ids}"


class TestMajorAgnosticDispatch:
    """Adding a new major shouldn't require touching the synergy code —
    just subclass ProgramScraper and register it."""

    def test_unknown_major_returns_empty(self):
        from capstone.scrapers.programs.synergies import synergy_map
        assert synergy_map("UNKNOWN_MAJOR") == {}

    def test_csse_synergies_via_dispatcher(self):
        from capstone.scrapers.programs.synergies import synergy_map
        m = synergy_map("CSSE")
        assert "CSS 430" in m
        # Each entry is a list of (upstream, rationale)
        upstreams = [u for u, _ in m["CSS 430"]]
        assert "CSS 422" in upstreams

    def test_subclass_owns_synergy_data(self, fixture_db):
        """A hypothetical new major scraper can register synergies just
        by declaring the class attribute — no other module changes."""
        from capstone.scrapers.base import ProgramScraper

        class HypotheticalMajorScraper(ProgramScraper):
            major_code = "HYPO"
            major_name = "Hypothetical Studies"
            synergies = [
                ("CSS 430", ["CSS 422"], "same reasoning, different major"),
            ]

            def scrape_requirements(self, conn):
                return 0

        scraper = HypotheticalMajorScraper()
        # synergy_map returns the dict shape
        m = scraper.synergy_map()
        assert m == {"CSS 430": [("CSS 422", "same reasoning, different major")]}
        # seed_synergies uses the base-class implementation
        inserted = scraper.seed_synergies(fixture_db)
        # CSS 430 ← CSS 422 was already in the fixture; no duplicate inserted
        assert inserted == 0


class TestRecommendationOutput:
    def test_completed_and_missing_prep_surfaced(self, fixture_db):
        """The Recommendation object should expose which soft prereqs are
        done vs. missing so the UI can render them."""
        config = _default_config()
        transcript = _transcript([("CSS 142", "3.8"), ("CSS 143", "3.0"),
                                  ("STMATH 124", "4.0"), ("STMATH 125", "3.9"),
                                  ("CSS 342", "3.2"), ("CSS 343", "3.5"),
                                  ("CSS 301", "3.0")])

        rec = Recommender(fixture_db, config)
        result = rec.recommend(transcript, target_quarter="WIN", top_n=10,
                               use_llm=False)
        by_id = {r.course_id: r for r in result.recommendations}
        css_430 = by_id["CSS 430"]
        # Student doesn't have CSS 422 yet
        assert "CSS 422" in css_430.missing_soft_prereqs
        assert css_430.completed_soft_prereqs == []
