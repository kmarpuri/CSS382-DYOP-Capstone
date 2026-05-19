"""Base scraper with rate limiting, User-Agent, and robots.txt respect.

All concrete scrapers inherit from BaseScraper and get automatic
rate-limiting (default 1 req/sec) and a well-identified User-Agent.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Rate-limited HTTP scraper with robots.txt compliance."""

    def __init__(
        self,
        rate_limit: float = 1.0,
        user_agent: str = "Capstone/1.0 (UWB Course Advisor)",
    ):
        self.rate_limit = rate_limit
        self.user_agent = user_agent
        self._last_request_time: float = 0.0
        self._robot_parsers: dict[str, RobotFileParser] = {}
        self._client = httpx.Client(
            headers={"User-Agent": self.user_agent},
            timeout=30.0,
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _respect_rate_limit(self) -> None:
        """Sleep if needed to respect the rate limit."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

    def _check_robots(self, url: str) -> bool:
        """Check robots.txt for the given URL. Returns True if allowed."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        if base not in self._robot_parsers:
            rp = RobotFileParser()
            robots_url = f"{base}/robots.txt"
            try:
                rp.set_url(robots_url)
                rp.read()
            except Exception:
                # If we can't read robots.txt, assume allowed
                logger.debug(f"Could not read robots.txt at {robots_url}, proceeding")
                rp = None
            self._robot_parsers[base] = rp

        rp = self._robot_parsers[base]
        if rp is None:
            return True
        return rp.can_fetch(self.user_agent, url)

    def fetch(self, url: str) -> str:
        """Fetch a URL with rate limiting and robots.txt checks.

        Returns the response body as text.
        Raises httpx.HTTPStatusError for 4xx/5xx responses.
        """
        if not self._check_robots(url):
            logger.warning(f"robots.txt disallows {url}, skipping")
            return ""

        self._respect_rate_limit()
        logger.info(f"Fetching {url}")

        response = self._client.get(url)
        self._last_request_time = time.time()
        response.raise_for_status()
        return response.text

    @abstractmethod
    def scrape(self, conn: sqlite3.Connection) -> int:
        """Run the scraper and persist results to the database.

        Returns the number of records written.
        """
        ...


class ProgramScraper(ABC):
    """Abstract base class for major/program requirement scrapers.

    Each UW Bothell major gets its own subclass. The architecture is
    generic so new majors can be added in Phase 5 without refactoring.

    Subclasses declare two things:

    1. ``scrape_requirements`` — populates the ``major_requirements``
       table with the major's core/elective/capstone courses.
    2. ``synergies`` — a list of pedagogical "X makes Y easier"
       pairings that aren't formal prerequisites. These get seeded as
       ``type='recommended'`` rows in the ``prerequisites`` table so the
       ranker can compute a synergy_score and the LLM can articulate
       multi-quarter sequencing.

    Both pieces are major-specific and live entirely in the subclass —
    no other module needs to know which major it's working with.
    """

    major_code: str = ""    # e.g., "CSSE"
    major_name: str = ""    # e.g., "Computer Science & Software Engineering"

    # Per-major pedagogical synergies. Each tuple is
    #   (downstream_course_id, [upstream_course_ids], short_rationale)
    # Default empty. Subclasses override.
    synergies: list[tuple[str, list[str], str]] = []

    @abstractmethod
    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        """Populate the major_requirements table for this major.

        Implementations should call ``self.seed_synergies(conn)`` at the
        end so soft pedagogical edges get persisted alongside the formal
        requirements.

        Returns the number of requirement rows inserted.
        """
        ...

    # ── Requirement-row helpers (shared across all majors) ─────────────

    def _clear_existing_requirements(self, conn: sqlite3.Connection) -> None:
        """Drop this major's existing requirement rows so re-runs are idempotent."""
        conn.execute(
            "DELETE FROM major_requirements WHERE major = ?",
            (self.major_code,),
        )

    def _insert_req(
        self,
        conn: sqlite3.Connection,
        category: str,
        course_id: str,
        *,
        required_count: int = 1,
        group_id: int = 0,
        notes: str | None = None,
    ) -> None:
        """Insert a single requirement row."""
        conn.execute(
            """
            INSERT INTO major_requirements
                (major, category, course_id, required_count, group_id, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (self.major_code, category, course_id,
             required_count, group_id, notes),
        )

    def _insert_each(
        self,
        conn: sqlite3.Connection,
        category: str,
        course_ids: list[str],
        *,
        notes: str | None = None,
    ) -> int:
        """Insert each course as its own required row. Returns count."""
        for cid in course_ids:
            self._insert_req(conn, category, cid, notes=notes)
        return len(course_ids)

    def _insert_pick_one_group(
        self,
        conn: sqlite3.Connection,
        category: str,
        course_ids: list[str],
        *,
        group_id: int = 1,
        notes: str | None = "pick one",
    ) -> int:
        """Insert an OR-group: student must complete any one of these."""
        for cid in course_ids:
            self._insert_req(
                conn, category, cid,
                required_count=1, group_id=group_id, notes=notes,
            )
        return len(course_ids)

    def _record_scrape_metadata(
        self,
        conn: sqlite3.Connection,
        *,
        timestamp: str,
        record_count: int,
    ) -> None:
        """Stamp the scrape_metadata table so the cache-staleness UI works."""
        conn.execute(
            """
            INSERT INTO scrape_metadata (source, scraped_at, record_count)
            VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                scraped_at = excluded.scraped_at,
                record_count = excluded.record_count
            """,
            (f"requirements:{self.major_code}", timestamp, record_count),
        )

    # ── Synergy persistence (shared across all majors) ─────────────────

    def seed_synergies(self, conn: sqlite3.Connection) -> int:
        """Insert this major's soft synergy edges into ``prerequisites``.

        Skips pairs that are already formal prereqs, and pairs whose
        downstream course isn't in the catalog (placeholder pollution).
        Returns the count of edges inserted.
        """
        inserted = 0
        for downstream, upstreams, _rationale in self.synergies:
            if conn.execute(
                "SELECT 1 FROM courses WHERE course_id = ?", (downstream,)
            ).fetchone() is None:
                continue

            for upstream in upstreams:
                existing = conn.execute(
                    "SELECT 1 FROM prerequisites "
                    "WHERE course_id = ? AND prereq_id = ?",
                    (downstream, upstream),
                ).fetchone()
                if existing is not None:
                    continue
                conn.execute(
                    "INSERT INTO prerequisites "
                    "(course_id, prereq_id, type, group_id) "
                    "VALUES (?, ?, 'recommended', 0)",
                    (downstream, upstream),
                )
                inserted += 1

        conn.commit()
        return inserted

    def synergy_map(self) -> dict[str, list[tuple[str, str]]]:
        """Return ``{downstream: [(upstream, rationale), ...]}``.

        Used by the LLM reasoner to feed the synergies block into its
        prompt context.
        """
        out: dict[str, list[tuple[str, str]]] = {}
        for downstream, upstreams, rationale in self.synergies:
            out[downstream] = [(u, rationale) for u in upstreams]
        return out
