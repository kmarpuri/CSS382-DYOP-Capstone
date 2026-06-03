"""Shared base for the IAS-school B.A. programs.

UWB's School of Interdisciplinary Arts and Sciences (IAS) majors all
share the same skeleton:

* a foundational BIS *inquiry* course (e.g., 'social science inquiry'),
* a small set of theme-specific BIS courses (the major's identity),
* an elective bucket at 300+ level inside BIS,
* a BIS 499 capstone.

Subclasses just declare ``CORE``, ``ELECTIVE_AREA``, optionally
``synergies``, and inherit the whole insertion machinery.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class IASProgramScraper(ProgramScraper):
    """Common scaffolding for IAS B.A. programs."""

    # Subclasses override these:
    CORE: list[str] = []
    INQUIRY: list[str] = ["BIS 240"]  # Social-science inquiry default
    ELECTIVE_PREFIX: str = "BIS 300+"
    ELECTIVE_CREDITS: int = 25
    CAPSTONE: list[str] = ["BIS 499"]
    WRITING_PREREQS: list[str] = ["B WRIT 134", "B WRIT 135"]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "inquiry", self.INQUIRY)
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            self.ELECTIVE_PREFIX,
            required_count=self.ELECTIVE_CREDITS,
            notes=f"{self.ELECTIVE_CREDITS} credits of upper-division BIS electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(
            f"Inserted {count} {self.major_code} requirements "
            f"+ {synergy_count} soft synergies"
        )
        return count
