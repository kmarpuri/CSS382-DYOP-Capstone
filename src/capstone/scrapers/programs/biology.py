"""BIO — Biology (B.S.).

Hardcoded based on:
  - https://www.uwb.edu/stem/undergraduate/majors/bs-biology
  - https://www.washington.edu/students/crscatb/bbio.html
  - https://www.washington.edu/students/crscatb/bchem.html
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class BiologyProgramScraper(ProgramScraper):
    """B.S. in Biology — heavy chemistry and quantitative-skills prep,
    followed by a tight sub-discipline core (genetics → cell → physiology)."""

    major_code = "BIO"
    major_name = "Biology (B.S.)"

    # Introductory biology sequence (pre-major)
    INTRO_BIO = ["B BIO 180", "B BIO 200", "B BIO 220"]

    # General chemistry — required for the major
    GENERAL_CHEM = ["B CHEM 143", "B CHEM 144"]

    # Organic chemistry (full year)
    ORGANIC_CHEM = ["B CHEM 237", "B CHEM 238", "B CHEM 239"]

    # Math + stats prerequisites
    MATH = ["STMATH 124", "STMATH 125"]
    STATS_OPTIONS = ["STMATH 341", "STMATH 390", "B BUS 215"]

    # Upper-division biology core
    CORE = [
        "B BIO 360",  # Introduction to Genetics
        "B BIO 370",  # Microbiology
        "B BIO 364",  # Biochemistry I
    ]

    # Anatomy & physiology (pick the sequence appropriate to track)
    A_AND_P = ["B BIO 351", "B BIO 352"]

    # Capstone — independent research project
    # The Biology B.S. doesn't have a single capstone number; we use 499
    # research as the placeholder. Students can also satisfy via 495.
    CAPSTONE = ["B BIO 499"]

    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "B BIO 360",
            ["B BIO 200"],
            "Intro Biology II covers Mendelian inheritance and molecular "
            "basics that genetics formalizes.",
        ),
        (
            "B BIO 364",
            ["B CHEM 238"],
            "Biochemistry I assumes the mechanisms and reactivity patterns "
            "introduced in Organic Chemistry II.",
        ),
        (
            "B BIO 370",
            ["B BIO 200"],
            "Microbiology builds on the cell-structure material from Intro Bio II.",
        ),
        (
            "B CHEM 237",
            ["B CHEM 144"],
            "Organic Chemistry I assumes comfort with General Chem lab "
            "techniques (titration, recrystallization).",
        ),
        (
            "B BIO 352",
            ["B BIO 351"],
            "A&P II picks up where I left off — system by system.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)

        count = 0
        count += self._insert_each(conn, "intro", self.INTRO_BIO)
        count += self._insert_each(conn, "general_chem", self.GENERAL_CHEM)
        count += self._insert_each(conn, "organic_chem", self.ORGANIC_CHEM)
        count += self._insert_each(conn, "math", self.MATH)
        count += self._insert_pick_one_group(
            conn,
            "stats",
            self.STATS_OPTIONS,
            group_id=1,
            notes="Pick one statistics course",
        )
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "anatomy_physiology", self.A_AND_P)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "B BIO 300+",
            required_count=15,
            notes="15 credits of upper-division biology electives",
        )
        count += 1

        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()

        logger.info(
            f"Inserted {count} BIO requirements + {synergy_count} soft synergies"
        )
        return count
