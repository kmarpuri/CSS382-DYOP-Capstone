"""Tests for the RateMyProfessor scraper.

The GraphQL client is mocked so the suite never hits the network.
We're testing:
  * name-normalization (the trickiest piece — comma-style names, middle
    initials, casing all collapse to the same key)
  * cache-freshness logic
  * the lookup helper that the reasoner/recommender will call
  * the scraper's upsert path inserts rows the lookup can find
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from capstone.db.connection import connect
from capstone.db.schema import init_db
from capstone.scrapers.ratemyprofessor import (
    CACHE_TTL_DAYS,
    RateMyProfessorScraper,
    _cache_is_fresh,
    _normalize_name,
    lookup_ratings,
)


# ── Normalisation ─────────────────────────────────────────────────────


class TestNameNormalization:
    @pytest.mark.parametrize("raw,expected", [
        ("John Smith", "JOHN SMITH"),
        ("Smith, John", "JOHN SMITH"),
        ("SMITH, JOHN", "JOHN SMITH"),
        ("john smith", "JOHN SMITH"),
        ("John Q. Smith", "JOHN SMITH"),
        ("John  Smith", "JOHN SMITH"),
        ("Smith,John", "JOHN SMITH"),
        ("  Smith ,  John  ", "JOHN SMITH"),
        ("O'Brien, Mary", "MARY OBRIEN"),
        ("", ""),
    ])
    def test_normalises_common_formats(self, raw, expected):
        assert _normalize_name(raw) == expected

    def test_normalisation_is_idempotent(self):
        norm = _normalize_name("Smith, John A.")
        assert _normalize_name(norm) == norm


# ── Cache freshness ───────────────────────────────────────────────────


class TestCacheFreshness:
    def test_none_is_never_fresh(self):
        assert _cache_is_fresh(None) is False

    def test_empty_string_is_never_fresh(self):
        assert _cache_is_fresh("") is False

    def test_just_now_is_fresh(self):
        now = datetime.now(timezone.utc).isoformat()
        assert _cache_is_fresh(now) is True

    def test_yesterday_is_fresh(self):
        yesterday = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()
        assert _cache_is_fresh(yesterday) is True

    def test_beyond_ttl_is_stale(self):
        ancient = (
            datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS + 1)
        ).isoformat()
        assert _cache_is_fresh(ancient) is False

    def test_malformed_timestamp_is_stale(self):
        assert _cache_is_fresh("not-a-date") is False


# ── Lookup helper ─────────────────────────────────────────────────────


@pytest.fixture
def ratings_db(tmp_path):
    """Fresh DB with two seeded professor records."""
    conn = connect(tmp_path / "rmp.db")
    init_db(conn)
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        """INSERT INTO professor_ratings (
             name, name_normalized, school_id, school_name, department,
             avg_rating, avg_difficulty, num_ratings,
             would_take_again_pct, rmp_legacy_id, last_scraped
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            ("Munehiro Fukuda", "MUNEHIRO FUKUDA", "1431", "UWB",
             "Computing & Software Systems",
             4.5, 3.2, 42, 88.0, "987654", now),
            ("Hazeline U. Asuncion", "HAZELINE ASUNCION", "1431", "UWB",
             "Computing & Software Systems",
             4.8, 2.5, 15, 95.0, "111222", now),
        ],
    )
    conn.commit()
    return conn


class TestLookupRatings:
    def test_finds_by_exact_name(self, ratings_db):
        out = lookup_ratings(ratings_db, ["Munehiro Fukuda"])
        assert "Munehiro Fukuda" in out
        assert out["Munehiro Fukuda"]["avg_rating"] == 4.5
        assert out["Munehiro Fukuda"]["rmp_url"].endswith("/987654")

    def test_finds_by_comma_style(self, ratings_db):
        out = lookup_ratings(ratings_db, ["Fukuda, Munehiro"])
        assert "Fukuda, Munehiro" in out
        assert out["Fukuda, Munehiro"]["avg_rating"] == 4.5

    def test_finds_with_middle_initial(self, ratings_db):
        out = lookup_ratings(ratings_db, ["Hazeline U. Asuncion"])
        assert "Hazeline U. Asuncion" in out
        assert out["Hazeline U. Asuncion"]["num_ratings"] == 15

    def test_misses_unknown_name(self, ratings_db):
        out = lookup_ratings(ratings_db, ["Nobody Realname"])
        assert out == {}

    def test_handles_empty_input(self, ratings_db):
        assert lookup_ratings(ratings_db, []) == {}

    def test_returns_subset_when_some_unknown(self, ratings_db):
        out = lookup_ratings(ratings_db, ["Munehiro Fukuda", "Nobody Realname"])
        assert "Munehiro Fukuda" in out
        assert "Nobody Realname" not in out


# ── Scraper (mocked GraphQL) ──────────────────────────────────────────


class TestScraperPersistence:
    """End-to-end: mock GraphQL → scrape → assert lookup works."""

    def _build_scraper_with_fake_graphql(self):
        scraper = RateMyProfessorScraper(school_name="Mock School", rate_limit=0)

        # Inject a fake _graphql that returns canned responses.
        school_response = {
            "newSearch": {
                "schools": {
                    "edges": [{"node": {
                        "id": "abc", "legacyId": 1431,
                        "name": "Mock School", "city": "MS", "state": "WA",
                    }}]
                }
            }
        }
        teachers_response = {
            "newSearch": {
                "teachers": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [
                        {"node": {
                            "id": "p1", "legacyId": 1001,
                            "firstName": "Munehiro", "lastName": "Fukuda",
                            "department": "Computing",
                            "avgRating": 4.5, "avgDifficulty": 3.0,
                            "numRatings": 42, "wouldTakeAgainPercent": 90.0,
                        }},
                        {"node": {
                            "id": "p2", "legacyId": 1002,
                            "firstName": "", "lastName": "",   # garbage row
                            "department": None,
                            "avgRating": None, "avgDifficulty": None,
                            "numRatings": 0, "wouldTakeAgainPercent": None,
                        }},
                    ],
                }
            }
        }
        responses = {
            "SearchSchool": school_response,
            "TeacherSearch": teachers_response,
        }

        def fake_graphql(query, variables):
            # Crude: identify the query by its operation name prefix
            for key, resp in responses.items():
                if key in query:
                    return resp
            raise AssertionError(f"unexpected query: {query[:40]}…")

        scraper._graphql = fake_graphql  # type: ignore[assignment]
        return scraper

    def test_full_scrape_then_lookup(self, tmp_path):
        scraper = self._build_scraper_with_fake_graphql()
        conn = connect(tmp_path / "rmp.db")
        init_db(conn)

        n = scraper.scrape(conn)
        # The "garbage row" (no name) is skipped — only 1 inserted
        assert n == 1

        out = lookup_ratings(conn, ["Munehiro Fukuda"])
        assert out["Munehiro Fukuda"]["avg_rating"] == 4.5
        assert out["Munehiro Fukuda"]["num_ratings"] == 42

    def test_idempotent_rescrape_skips_fresh_rows(self, tmp_path):
        scraper = self._build_scraper_with_fake_graphql()
        conn = connect(tmp_path / "rmp.db")
        init_db(conn)
        scraper.scrape(conn)
        # Second pass should skip the fresh row entirely
        n = scraper.scrape(conn)
        assert n == 0

    def test_force_refresh_re_upserts(self, tmp_path):
        scraper = self._build_scraper_with_fake_graphql()
        conn = connect(tmp_path / "rmp.db")
        init_db(conn)
        scraper.scrape(conn)
        n = scraper.scrape(conn, force_refresh=True)
        assert n == 1


# ── Recommender integration ───────────────────────────────────────────


class TestRecommenderUsesRatings:
    """The Recommender's best_instructor field should be populated when
    cached ratings + scheduled sections both exist."""

    def test_best_instructor_attached_to_recommendation(
        self, fixture_db, tmp_path
    ):
        from capstone.config import (
            AppConfig, CreditLimits, DatabaseConfig,
            RankingWeights, ScraperConfig,
        )
        from capstone.recommender import Recommender
        from capstone.transcript.models import CompletedCourse, Transcript

        # Seed a section + rating for CSS 360
        now = datetime.now(timezone.utc).isoformat()
        fixture_db.execute(
            """INSERT INTO time_schedule (
                 course_id, section_id, quarter, year, days, time_start,
                 time_end, instructor, scraped_at
            ) VALUES ('CSS 360', 'A', 'WIN', 2027, 'MW', '0930', '1130',
                      'Smith, John', ?)""",
            (now,),
        )
        fixture_db.execute(
            """INSERT INTO professor_ratings (
                 name, name_normalized, school_id, avg_rating, avg_difficulty,
                 num_ratings, would_take_again_pct, rmp_legacy_id, last_scraped
            ) VALUES ('John Smith', 'JOHN SMITH', '1431', 4.2, 3.0, 30, 85.0,
                      '555', ?)""",
            (now,),
        )
        fixture_db.commit()

        config = AppConfig(
            scraper=ScraperConfig(),
            database=DatabaseConfig(),
            ranking_weights=RankingWeights(),
            credit_limits=CreditLimits(default=15, hard_ceiling=25),
        )
        transcript = Transcript(
            major="CSSE",
            class_standing="JUNIOR",
            completed=[
                CompletedCourse(course_id=c, title=c, credits=5.0,
                                grade="3.0", quarter="AUT", year=2024)
                for c in ("CSS 142", "CSS 143", "STMATH 124", "STMATH 125",
                          "CSS 342", "CSS 343", "CSS 301")
            ],
        )

        rec = Recommender(fixture_db, config)
        result = rec.recommend(transcript, target_quarter="WIN",
                               top_n=10, use_llm=False)

        css_360 = next(
            (r for r in result.recommendations if r.course_id == "CSS 360"),
            None,
        )
        assert css_360 is not None, "CSS 360 should be a candidate"
        assert css_360.best_instructor is not None
        assert css_360.best_instructor["avg_rating"] == 4.2
        assert css_360.best_instructor["num_ratings"] == 30
