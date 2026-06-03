"""PHYS — Physics (B.S.)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class PhysicsProgramScraper(ProgramScraper):
    major_code = "PHYS"
    major_name = "Physics (B.S.)"

    CORE = [
        "B PHYS 121",  # Mechanics
        "B PHYS 122",  # E&M
        "B PHYS 123",  # Waves
        "B PHYS 224",  # Thermal
        "B PHYS 225",  # Modern Physics
        "B PHYS 321",  # Classical Mechanics
        "B PHYS 322",  # Electromagnetism
        "B PHYS 324",  # Quantum Mechanics I
        "B PHYS 325",  # Quantum Mechanics II
        "B PHYS 334",  # Mathematical Methods in Physics
    ]
    CAPSTONE = ["B PHYS 495"]
    MATH_PREREQS = [
        "STMATH 124",
        "STMATH 125",
        "STMATH 126",
        "STMATH 207",
        "STMATH 208",
    ]
    PROGRAMMING_PREREQS = ["CSS 142"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "B PHYS 325",
            ["B PHYS 324"],
            "QM II builds on the operator formalism from QM I.",
        ),
        (
            "B PHYS 322",
            ["B PHYS 122", "STMATH 208"],
            "E&M at the upper-division level needs both intro E&M and vector calc.",
        ),
        (
            "B PHYS 321",
            ["STMATH 207"],
            "Classical mechanics is a course in ODE-solving as much as physics.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_each(conn, "programming", self.PROGRAMMING_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "B PHYS 400+",
            required_count=15,
            notes="15 credits of upper-division physics electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} PHYS requirements + {synergy_count} synergies")
        return count
