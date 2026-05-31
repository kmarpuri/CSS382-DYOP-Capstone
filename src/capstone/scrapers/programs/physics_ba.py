"""PHYSBA — Physics (B.A.)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class PhysicsBAProgramScraper(ProgramScraper):
    """Physics B.A. — same intro sequence as the B.S., shallower upper
    division (drops one QM quarter and the math-methods course),
    broader humanities/electives latitude."""

    major_code = "PHYSBA"
    major_name = "Physics (B.A.)"

    CORE = [
        "B PHYS 121", "B PHYS 122", "B PHYS 123",   # Intro sequence
        "B PHYS 224", "B PHYS 225",                 # Thermal + Modern
        "B PHYS 321",                               # Classical Mechanics
        "B PHYS 322",                               # Electromagnetism
        "B PHYS 324",                               # Quantum Mechanics I
    ]
    CAPSTONE = ["B PHYS 495"]
    MATH_PREREQS = ["STMATH 124", "STMATH 125", "STMATH 126", "STMATH 207"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("B PHYS 321", ["STMATH 207"],
         "Classical mechanics leans heavily on ODE methods."),
        ("B PHYS 322", ["B PHYS 122"],
         "Upper-division E&M extends intro E&M's field framework."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(conn, "elective", "B PHYS 300+", required_count=10,
                         notes="10 credits of upper-division physics electives")
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} PHYSBA requirements + {synergy_count} synergies")
        return count
