"""MATH — Mathematics (B.S. and B.A.).

Hardcoded based on:
  - https://www.uwb.edu/stem/undergraduate/majors/bs-math
  - https://www.washington.edu/students/crscatb/stmath.html

Course IDs cross-checked against the scraped catalog. If a future
catalog refresh removes a course, the synergy seeder will skip it
silently rather than poisoning the graph.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class MathProgramScraper(ProgramScraper):
    """Mathematics — heavily STMATH-based with two upper-division anchors:
    Abstract Algebra and Real Analysis."""

    major_code = "MATH"
    major_name = "Mathematics (B.S.)"

    # Calculus sequence — pre-major prerequisites
    CALCULUS = ["STMATH 124", "STMATH 125", "STMATH 126"]

    # Lower-division core
    LINEAR_ALGEBRA = ["STMATH 208"]
    DIFFERENTIAL_EQ = ["STMATH 207"]
    MULTIVARIATE = ["STMATH 224"]

    # Foundations / proof-writing
    FOUNDATIONS = ["STMATH 300", "STMATH 301"]

    # Upper-division core anchors (the two pillars of a math major)
    ABSTRACT_ALGEBRA = ["STMATH 402", "STMATH 403"]
    REAL_ANALYSIS = ["STMATH 424", "STMATH 425"]

    # Stats / probability — pick one
    STATS_OPTIONS = ["STMATH 341", "STMATH 390", "STMATH 392"]

    # Capstone / research
    CAPSTONE = ["STMATH 499"]  # Undergraduate Research in Mathematics

    # Programming literacy is now expected of math majors
    PROGRAMMING = ["CSS 142"]

    # Writing
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "STMATH 402",
            ["STMATH 300"],
            "Foundations introduces the proof techniques that abstract algebra "
            "demands constantly.",
        ),
        (
            "STMATH 424",
            ["STMATH 300"],
            "Real Analysis is a proof-heavy course — Foundations is the natural prep.",
        ),
        (
            "STMATH 425",
            ["STMATH 424"],
            "Real Analysis I builds the topology and limit machinery used in II.",
        ),
        (
            "STMATH 403",
            ["STMATH 402"],
            "Abstract Algebra II picks up directly where I left off — groups → rings → fields.",
        ),
        (
            "STMATH 224",
            ["STMATH 126"],
            "Multivariable calculus builds on Calc III's series and parametric tools.",
        ),
        (
            "STMATH 405",
            ["STMATH 208"],
            "Numerical Analysis assumes comfort with linear systems and matrix algebra.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)

        count = 0
        count += self._insert_each(conn, "calculus", self.CALCULUS)
        count += self._insert_each(conn, "linear_algebra", self.LINEAR_ALGEBRA)
        count += self._insert_each(conn, "differential_eq", self.DIFFERENTIAL_EQ)
        count += self._insert_each(conn, "multivariate", self.MULTIVARIATE)
        count += self._insert_each(conn, "foundations", self.FOUNDATIONS)
        count += self._insert_each(conn, "core", self.ABSTRACT_ALGEBRA)
        count += self._insert_each(conn, "core", self.REAL_ANALYSIS)
        count += self._insert_pick_one_group(
            conn,
            "stats",
            self.STATS_OPTIONS,
            group_id=1,
            notes="Pick one statistics or probability course",
        )
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "programming", self.PROGRAMMING)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "STMATH 400+",
            required_count=15,
            notes="15 credits of upper-division math electives",
        )
        count += 1

        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()

        logger.info(
            f"Inserted {count} MATH requirements + {synergy_count} soft synergies"
        )
        return count
