"""RateMyProfessor scraper — optional, opt-in.

⚠️  NOTICE ON RATEMYPROFESSORS.COM TERMS OF SERVICE
   --------------------------------------------------
   RateMyProfessors.com's Terms of Service prohibit automated access.
   This module exists for academic / personal use only; it queries
   their public GraphQL endpoint (the same one their own website
   uses) at a strict 1 req/sec rate limit, caches every response for
   30 days, and is never invoked unless the user runs
   ``capstone scrape professors`` explicitly. We do not store, share,
   or re-publish individual reviews — only aggregate scores (avg
   rating, avg difficulty, would-take-again %) tied to a public name.

   If the legal posture matters for your deployment, **do not** ship
   the scraped data publicly. The data lives in the local SQLite
   cache and the LLM prompt context only.

Implementation notes
--------------------
RMP's public site is powered by a GraphQL endpoint at
``https://www.ratemyprofessors.com/graphql``. The endpoint uses HTTP
Basic Auth with the constant ``test:test`` (this is the credential
their JavaScript bundle ships with — it's not a secret). The two
queries we need:

  1. ``searchSchoolsQuery`` — resolve a school name to an internal
     school ID. We do this once per scrape.
  2. ``TeacherSearchPaginationQuery`` — fetch professors at that
     school, paginated. The response includes ``avgRating``,
     ``avgDifficulty``, ``numRatings``, ``wouldTakeAgainPercent``,
     ``legacyId``, ``department``, ``firstName``, ``lastName``.

Defaults to UW Bothell. School name is configurable via
``CAPSTONE_RMP_SCHOOL`` env var.
"""

from __future__ import annotations

import base64
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

import httpx

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────

GRAPHQL_URL = "https://www.ratemyprofessors.com/graphql"
# RMP's public site uses literal "test:test" as Basic-Auth credentials
# in its JavaScript bundle. This is not a leaked secret.
BASIC_AUTH = base64.b64encode(b"test:test").decode()

DEFAULT_SCHOOL = "University of Washington Bothell Campus"
DEFAULT_USER_AGENT = (
    "Capstone/1.0 (UWB course advisor; educational use; +https://uwb.edu)"
)

# Cache TTL — re-fetch a professor only if their cached record is older.
CACHE_TTL_DAYS = 30
RATE_LIMIT_SECONDS = 1.0


# GraphQL queries (verbatim from RMP's public site bundle).
SCHOOL_QUERY = """
query SearchSchool($query: SchoolSearchQuery!) {
  newSearch {
    schools(query: $query) {
      edges {
        node { id legacyId name city state }
      }
    }
  }
}
"""

TEACHERS_QUERY = """
query TeacherSearch($query: TeacherSearchQuery!, $count: Int!, $cursor: String) {
  newSearch {
    teachers(query: $query, first: $count, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      edges {
        node {
          id legacyId firstName lastName department
          avgRating avgDifficulty numRatings wouldTakeAgainPercent
        }
      }
    }
  }
}
"""


# ── Helpers ────────────────────────────────────────────────────────────


def _normalize_name(name: str) -> str:
    """Normalize a professor name for case/order-insensitive matching.

    Handles "Smith, John" → "JOHN SMITH" and strips middle initials,
    punctuation, and double spaces.
    """
    if not name:
        return ""
    s = name.strip().upper()
    # "Smith, John" → "John Smith"
    if "," in s:
        last, _, first = s.partition(",")
        s = f"{first.strip()} {last.strip()}"
    # Drop middle initials like "J." or " R "
    s = re.sub(r"\b[A-Z]\.\s*", "", s)
    # Collapse whitespace + strip punctuation
    s = re.sub(r"[^A-Z\s\-]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _cache_is_fresh(last_scraped: str | None) -> bool:
    if not last_scraped:
        return False
    try:
        dt = datetime.fromisoformat(last_scraped.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - dt) < timedelta(days=CACHE_TTL_DAYS)


# ── Scraper ────────────────────────────────────────────────────────────


class RateMyProfessorScraper:
    """Fetches aggregate ratings for every professor at a given school."""

    def __init__(
        self,
        school_name: str | None = None,
        *,
        rate_limit: float = RATE_LIMIT_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 15.0,
    ):
        self.school_name = (
            school_name
            or os.environ.get("CAPSTONE_RMP_SCHOOL")
            or DEFAULT_SCHOOL
        )
        self.rate_limit = rate_limit
        self._last_request_at = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Basic {BASIC_AUTH}",
                "Content-Type": "application/json",
                "User-Agent": user_agent,
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    # ── GraphQL plumbing ───────────────────────────────────────────

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_at = time.monotonic()

    def _graphql(self, query: str, variables: dict) -> dict:
        self._respect_rate_limit()
        resp = self._client.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables},
        )
        resp.raise_for_status()
        body = resp.json()
        if "errors" in body and body["errors"]:
            raise RuntimeError(f"RMP GraphQL error: {body['errors']}")
        return body["data"]

    # ── Public API ─────────────────────────────────────────────────

    def _best_school_match(self, edges: list[dict]) -> dict:
        """Pick the school edge that best matches the requested name.

        RMP's relevance ranking can return the wrong campus first (e.g.
        "University of Washington" Seattle ahead of the Bothell campus),
        so we score candidates on token overlap and give a strong bonus
        to a distinguishing campus token (bothell/tacoma/seattle).
        """
        want = self.school_name.strip().lower()
        want_tokens = set(re.findall(r"[a-z]+", want))
        best, best_score = edges[0]["node"], -1
        for e in edges:
            node = e["node"]
            name = (node.get("name") or "").lower()
            if name == want:
                return node
            city = (node.get("city") or "").lower()
            hay = set(re.findall(r"[a-z]+", f"{name} {city}"))
            score = len(want_tokens & hay)
            for campus in ("bothell", "tacoma", "seattle"):
                if campus in want_tokens and campus in hay:
                    score += 5
            if score > best_score:
                best, best_score = node, score
        return best

    def resolve_school_id(self) -> tuple[str, str, str]:
        """Return ``(legacy_id, graphql_id, exact_school_name)``.

        The teachers query needs the opaque GraphQL node id (a base64
        encoding of ``School-<legacyId>``), **not** the numeric legacy
        id — passing the latter triggers an "invalid format" error. We
        keep the legacy id too, for human-readable DB storage.
        """
        data = self._graphql(
            SCHOOL_QUERY,
            {"query": {"text": self.school_name}},
        )
        edges = data["newSearch"]["schools"]["edges"] or []
        if not edges:
            raise RuntimeError(f"No RMP school found for {self.school_name!r}")
        if len(edges) > 1:
            candidates = ", ".join(
                f"{e['node'].get('name')} ({e['node'].get('city') or '?'})"
                for e in edges[:6]
            )
            logger.info(f"RMP school candidates: {candidates}")
        node = self._best_school_match(edges)
        return str(node["legacyId"]), node["id"], node["name"]

    def iter_professors(self, school_id: str) -> Iterator[dict]:
        """Yield every professor record at the given school ID, paginated."""
        cursor: str | None = None
        while True:
            data = self._graphql(
                TEACHERS_QUERY,
                {
                    "query": {"text": "", "schoolID": school_id},
                    "count": 50,
                    "cursor": cursor,
                },
            )
            search = data["newSearch"]["teachers"]
            for edge in search["edges"]:
                yield edge["node"]
            if not search["pageInfo"]["hasNextPage"]:
                return
            cursor = search["pageInfo"]["endCursor"]

    def scrape(
        self,
        conn: sqlite3.Connection,
        *,
        limit: int | None = None,
        force_refresh: bool = False,
    ) -> int:
        """Populate ``professor_ratings`` for the configured school.

        Returns the number of rows inserted/updated.
        """
        school_legacy_id, school_gid, exact_name = self.resolve_school_id()
        logger.info(
            f"Scraping {exact_name} (RMP school ID {school_legacy_id})…"
        )

        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        for node in self.iter_professors(school_gid):
            full_name = f"{node['firstName']} {node['lastName']}".strip()
            norm = _normalize_name(full_name)
            if not norm:
                continue

            # Skip if cached and fresh, unless force_refresh
            if not force_refresh:
                existing = conn.execute(
                    "SELECT last_scraped FROM professor_ratings "
                    "WHERE name_normalized = ? AND school_id = ?",
                    (norm, school_legacy_id),
                ).fetchone()
                if existing and _cache_is_fresh(existing[0]):
                    continue

            conn.execute(
                """
                INSERT INTO professor_ratings (
                    name, name_normalized, school_id, school_name,
                    department, avg_rating, avg_difficulty, num_ratings,
                    would_take_again_pct, rmp_legacy_id, last_scraped
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name_normalized, school_id) DO UPDATE SET
                    name = excluded.name,
                    school_name = excluded.school_name,
                    department = excluded.department,
                    avg_rating = excluded.avg_rating,
                    avg_difficulty = excluded.avg_difficulty,
                    num_ratings = excluded.num_ratings,
                    would_take_again_pct = excluded.would_take_again_pct,
                    rmp_legacy_id = excluded.rmp_legacy_id,
                    last_scraped = excluded.last_scraped
                """,
                (
                    full_name,
                    norm,
                    school_legacy_id,
                    exact_name,
                    node.get("department"),
                    node.get("avgRating"),
                    node.get("avgDifficulty"),
                    node.get("numRatings"),
                    node.get("wouldTakeAgainPercent"),
                    str(node.get("legacyId")) if node.get("legacyId") else None,
                    now,
                ),
            )
            inserted += 1

            if limit and inserted >= limit:
                break

        # Stamp metadata
        conn.execute(
            """
            INSERT INTO scrape_metadata (source, scraped_at, record_count)
            VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                scraped_at = excluded.scraped_at,
                record_count = excluded.record_count
            """,
            ("ratemyprofessor", now, inserted),
        )
        conn.commit()

        logger.info(f"RMP scrape complete — {inserted} professors updated")
        return inserted


# ── Lookup helpers (used by the reasoner) ─────────────────────────────


def lookup_ratings(
    conn: sqlite3.Connection, names: list[str]
) -> dict[str, dict[str, Any]]:
    """Return ``{original_name: {avg_rating, ...}}`` for the supplied names.

    Names may be in any common format ("Smith, John", "John Smith", "JOHN
    SMITH") — normalisation is applied per :func:`_normalize_name`.
    Names that aren't in the cache are simply absent from the result.
    """
    if not names:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw in names:
        norm = _normalize_name(raw)
        if not norm:
            continue
        row = conn.execute(
            """
            SELECT name, avg_rating, avg_difficulty, num_ratings,
                   would_take_again_pct, rmp_legacy_id, department
            FROM professor_ratings
            WHERE name_normalized = ?
            ORDER BY num_ratings DESC NULLS LAST
            LIMIT 1
            """,
            (norm,),
        ).fetchone()
        if row is None:
            continue
        out[raw] = {
            "name": row["name"],
            "avg_rating": row["avg_rating"],
            "avg_difficulty": row["avg_difficulty"],
            "num_ratings": row["num_ratings"],
            "would_take_again_pct": row["would_take_again_pct"],
            "department": row["department"],
            "rmp_url": (
                f"https://www.ratemyprofessors.com/professor/{row['rmp_legacy_id']}"
                if row["rmp_legacy_id"] else None
            ),
        }
    return out
