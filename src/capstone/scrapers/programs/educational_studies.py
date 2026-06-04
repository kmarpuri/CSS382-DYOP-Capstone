"""EDUC — Educational Studies (B.A.)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class EducationalStudiesProgramScraper(ProgramScraper):
    major_code = "EDUC"
    major_name = "Educational Studies (B.A.)"

    CORE = [
        "B EDUC 210",  # Cultural Foundations of Education
        "B EDUC 220",  # Schools & Society
        "B EDUC 300",  # Educational Psychology
        "B EDUC 310",  # Curriculum & Instruction
        "B EDUC 320",  # Assessment in Education
        "B EDUC 350",  # Equity & Education
        "B EDUC 410",  # Inquiry in Education
        "B EDUC 425",  # Educational Policy
    ]
    CAPSTONE = ["B EDUC 495"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "B EDUC 410",
            ["B EDUC 320"],
            "Inquiry methods presume comfort with the assessment vocabulary from 320.",
        ),
        (
            "B EDUC 425",
            ["B EDUC 350"],
            "Equity & Education frames the policy debates in 425 in concrete terms.",
        ),
        (
            "B EDUC 495",
            ["B EDUC 410"],
            "The capstone is an inquiry-led project — 410 is the methodological prerequisite in practice.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "B EDUC 300+",
            required_count=15,
            notes="15 credits of upper-division EDUC electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} EDUC requirements + {synergy_count} synergies")
        return count
