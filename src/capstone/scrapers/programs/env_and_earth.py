"""Environmental Studies + Earth System Science (both IAS-housed B.A.s)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class EnvironmentalStudiesProgramScraper(ProgramScraper):
    major_code = "ENVSTUD"
    major_name = "Environmental Studies (B.A.)"

    CORE = [
        "BIS 240",   # Social Science Inquiry
        "BIS 243",   # Intro to Environmental Studies
        "BIS 343",   # Environmental Policy
        "BIS 348",   # Environment & Society
        "BIS 355",   # Sustainable Development
        "BIS 442",   # Political Ecology
    ]
    CAPSTONE = ["BIS 499"]
    SCIENCE_PREREQS = ["B BIO 180", "BBIO 215"]  # ecology
    STATS_OPTIONS = ["B BUS 215", "STMATH 341"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("BIS 355", ["BIS 348"],
         "Sustainable Development extends the Environment & Society framing onto policy contexts."),
        ("BIS 442", ["BIS 343"],
         "Political Ecology presumes the policy vocabulary from BIS 343."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "science", self.SCIENCE_PREREQS)
        count += self._insert_pick_one_group(conn, "stats", self.STATS_OPTIONS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(conn, "elective", "BIS 300+", required_count=20,
                         notes="20 credits of BIS electives related to environment")
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} ENVSTUD requirements + {synergy_count} synergies")
        return count


class EarthSystemScienceProgramScraper(ProgramScraper):
    major_code = "EARTH"
    major_name = "Earth System Science (B.S.)"

    CORE = [
        "BEARTH 200",   # Intro to Earth System Science
        "BEARTH 270",   # Surface Processes
        "BEARTH 305",   # Atmosphere
        "BEARTH 310",   # Hydrosphere
        "BEARTH 315",   # Biosphere
        "BEARTH 420",   # Climate Dynamics
    ]
    CAPSTONE = ["BEARTH 495"]
    SCIENCE_PREREQS = ["B CHEM 143", "B PHYS 121", "B BIO 180"]
    MATH_PREREQS = ["STMATH 124", "STMATH 125"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("BEARTH 420", ["BEARTH 305", "BEARTH 310"],
         "Climate Dynamics integrates atmospheric and hydrologic systems — better with both as foundations."),
        ("BEARTH 315", ["B BIO 180"],
         "The Biosphere course builds on intro biology's ecology vocabulary."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "science", self.SCIENCE_PREREQS)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(conn, "elective", "BEARTH 300+", required_count=15,
                         notes="15 credits of upper-division earth-science electives")
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} EARTH requirements + {synergy_count} synergies")
        return count
