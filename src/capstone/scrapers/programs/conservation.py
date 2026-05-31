"""CRSCI — Conservation & Restoration Science (B.S.), IAS-housed."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class ConservationProgramScraper(ProgramScraper):
    major_code = "CRSCI"
    major_name = "Conservation & Restoration Science (B.S.)"

    CORE = [
        "BIS 240",        # Inquiry
        "BBIO 215",       # General Ecology
        "BBIO 360",       # Conservation Biology
        "BBIO 401",       # Restoration Ecology
        "BIS 343",        # Environmental Policy
        "BIS 348",        # Environment & Society
        "BEARTH 270",     # Surface Processes
        "BBIO 480",       # Field Methods
    ]
    CAPSTONE = ["BBIO 499"]
    SCIENCE_PREREQS = ["B BIO 180", "B BIO 200", "B BIO 220", "B CHEM 143"]
    MATH_PREREQS = ["STMATH 124"]
    STATS_OPTIONS = ["B BUS 215", "STMATH 341"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("BBIO 401", ["BBIO 360"],
         "Restoration Ecology applies the conservation-biology framework to interventions."),
        ("BBIO 480", ["BBIO 215"],
         "Field Methods presumes the ecology vocabulary from BBIO 215."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "science", self.SCIENCE_PREREQS)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_pick_one_group(conn, "stats", self.STATS_OPTIONS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(conn, "elective", "BBIO 300+", required_count=15,
                         notes="15 credits of upper-division biology/environment electives")
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} CRSCI requirements + {synergy_count} synergies")
        return count
