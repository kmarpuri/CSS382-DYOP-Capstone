"""HS — Health Studies (B.A.).

UW Bothell's only Health Studies undergraduate degree is the B.A.,
housed in the School of Nursing & Health Studies. It's an
interdisciplinary social-science-leaning major (epidemiology, policy,
inequities) without a calculus / o-chem track.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class HealthStudiesProgramScraper(ProgramScraper):
    major_code = "HS"
    major_name = "Health Studies (B.A.)"

    CORE = [
        "BHS 201",  # Intro to Public Health
        "BHS 301",  # Health & Society
        "BHS 310",  # Health Inequities
        "BHS 311",  # Epidemiology
        "BHS 312",  # Biostatistics for Health Sciences
        "BHS 333",  # Environmental Health
        "BHS 365",  # Global Health
        "BHS 414",  # Health Policy
    ]
    CAPSTONE = ["BHS 499"]
    SCIENCE_PREREQS = ["B BIO 180"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "BHS 311",
            ["BHS 312"],
            "Epidemiology methods rest on the biostatistics foundation.",
        ),
        (
            "BHS 414",
            ["BHS 310"],
            "Health Policy debates are most accessible after Health Inequities frames the structural drivers.",
        ),
        (
            "BHS 365",
            ["BHS 301"],
            "Global Health expands the social-determinants framework Health & Society introduces.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "science", self.SCIENCE_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "BHS 300+",
            required_count=20,
            notes="20 credits of upper-division BHS electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} HS requirements + {synergy_count} synergies")
        return count
