"""ACMPT — Applied Computing (B.S.).

Hardcoded based on:
  - https://www.uwb.edu/stem/undergraduate/majors/bsac
  - The catalog's CSS 496 "Applied Computing Capstone" entry confirms
    this track lives mostly inside the CSS department rather than its
    own course code.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class AppliedComputingProgramScraper(ProgramScraper):
    """Applied Computing — practical computing track at UWB.

    Sister program to CSSE; shares the CSS 142/143/342 spine but
    branches toward applied web/database/multimedia work instead of
    the theoretical CSSE 343/430/422 sequence.
    """

    major_code = "ACMPT"
    major_name = "Applied Computing (B.A.)"

    PROGRAMMING_PREREQS = ["CSS 142", "CSS 143"]
    DATA_STRUCTURES = ["CSS 342"]

    # Applied-track upper-division courses
    APPLIED_CORE = [
        "CSS 301",   # Technical Writing for Computing Professionals
        "CSS 310",   # Information Assurance and Cybersecurity
        "CSS 340",   # Applied Algorithmics
        "CSS 350",   # Management Principles for Computing Professionals
        "CSS 360",   # Software Engineering
    ]

    # Capstone is specific to Applied Computing
    CAPSTONE = ["CSS 496"]   # Applied Computing Capstone

    MATH = ["STMATH 124", "STMATH 125"]
    STATS_OPTIONS = ["B BUS 215", "STMATH 341", "STMATH 390"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("CSS 360", ["CSS 350"],
         "Management Principles introduces the SDLC and team workflows that "
         "Software Engineering then formalizes."),
        ("CSS 310", ["CSS 342"],
         "Cybersecurity assumes comfort with data structures and the "
         "memory-corruption story they enable."),
        ("CSS 496", ["CSS 360"],
         "The Applied Computing capstone is where Software Engineering "
         "process knowledge gets exercised end-to-end."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)

        count = 0
        count += self._insert_each(conn, "programming", self.PROGRAMMING_PREREQS)
        count += self._insert_each(conn, "core", self.DATA_STRUCTURES)
        count += self._insert_each(conn, "core", self.APPLIED_CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH)
        count += self._insert_pick_one_group(
            conn, "stats", self.STATS_OPTIONS,
            group_id=1, notes="Pick one statistics course",
        )
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn, "elective", "CSS 200+",
            required_count=20,
            notes="20 credits of CSS electives at 200-level or above",
        )
        count += 1

        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()

        logger.info(
            f"Inserted {count} ACMPT requirements + {synergy_count} soft synergies"
        )
        return count
