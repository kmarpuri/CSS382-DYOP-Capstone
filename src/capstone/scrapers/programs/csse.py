"""CSSE — Computer Science & Software Engineering (B.S.).

Hardcoded based on verified data from:
  - https://www.uwb.edu/stem/undergraduate/majors/bscsse/curriculum
  - https://www.washington.edu/students/crscatb/css.html
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class CSSEProgramScraper(ProgramScraper):
    """Populate CSSE major requirements + synergies."""

    major_code = "CSSE"
    major_name = "Computer Science & Software Engineering"

    CORE = [
        "CSS 301",   # Technical Writing for Computing Professionals
        "CSS 342",   # Data Structures, Algorithms, and Discrete Mathematics I
        "CSS 343",   # Data Structures, Algorithms, and Discrete Mathematics II
        "CSS 350",   # Management Principles for Computing Professionals
        "CSS 360",   # Software Engineering
        "CSS 370",   # Analysis and Design
        "CSS 422",   # Hardware and Computer Organization
        "CSS 430",   # Operating Systems
    ]
    CAPSTONE = ["CSS 497"]
    STATS_OPTIONS = [
        "B BUS 215", "STMATH 341", "STMATH 390",
    ]
    MATH_PREREQS = [
        "STMATH 124", "STMATH 125", "STMATH 126", "STMATH 207", "STMATH 208",
    ]
    PROGRAMMING_PREREQS = ["CSS 142", "CSS 143"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("CSS 430", ["CSS 422"],
         "Hardware and Computer Organization gives you assembly, caches, "
         "and memory hierarchy — OS becomes far less abstract."),
        ("CSS 422", ["CSS 343"],
         "DS & Algorithms II solidifies pointer semantics and memory "
         "layout, which carry directly into hardware/assembly."),
        ("CSS 360", ["CSS 350"],
         "Management Principles introduces SDLC and team workflows that "
         "Software Engineering then formalizes."),
        ("CSS 497", ["CSS 370"],
         "Analysis & Design feeds directly into the architecture choices "
         "you'll defend in the capstone."),
        ("CSS 370", ["CSS 350"],
         "Management Principles introduces stakeholder/process concepts "
         "that A&D builds on."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)

        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_pick_one_group(
            conn, "stats", self.STATS_OPTIONS,
            group_id=1, notes="Complete one statistics course",
        )
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_each(conn, "programming", self.PROGRAMMING_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn, "elective", "CSS 200+",
            required_count=25,
            notes="25 credits of CSS courses at 200-level or above",
        )
        count += 1

        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()

        logger.info(
            f"Inserted {count} CSSE requirements + {synergy_count} soft synergies"
        )
        return count
