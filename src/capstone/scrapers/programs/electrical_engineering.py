"""EE — Electrical Engineering (B.S.)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class ElectricalEngineeringProgramScraper(ProgramScraper):
    major_code = "EE"
    major_name = "Electrical Engineering (B.S.)"

    CORE = [
        "B EE 215",  # Fundamentals of Electrical Engineering
        "B EE 233",  # Circuits I
        "B EE 235",  # Continuous Time Linear Systems
        "B EE 271",  # Digital Circuits and Systems
        "B EE 331",  # Devices and Circuits II
        "B EE 341",  # Discrete Time Linear Systems
        "B EE 351",  # Electronics I
        "B EE 361",  # Applied Electromagnetics
        "B EE 371",  # Design of Digital Circuits and Systems
        "B EE 425",  # Engineering Probability
    ]
    CAPSTONE = ["B EE 497", "B EE 498"]  # Two-quarter senior design
    MATH_PREREQS = [
        "STMATH 124",
        "STMATH 125",
        "STMATH 126",
        "STMATH 207",
        "STMATH 208",
    ]
    SCIENCE_PREREQS = ["B PHYS 121", "B PHYS 122", "B PHYS 123"]
    PROGRAMMING_PREREQS = ["CSS 142", "CSS 143"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "B EE 331",
            ["B EE 233"],
            "Devices II builds directly on Circuits I — same KCL/KVL methods, deeper device physics.",
        ),
        (
            "B EE 341",
            ["B EE 235"],
            "Discrete-time analysis mirrors the continuous-time framework you just learned.",
        ),
        (
            "B EE 371",
            ["B EE 271"],
            "Design extends the digital fundamentals from 271 into HDL-driven systems.",
        ),
        (
            "B EE 497",
            ["B EE 351", "B EE 371"],
            "Senior design typically requires both analog and digital toolchains.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_each(conn, "science", self.SCIENCE_PREREQS)
        count += self._insert_each(conn, "programming", self.PROGRAMMING_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "B EE 400+",
            required_count=15,
            notes="15 credits of EE technical electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} EE requirements + {synergy_count} synergies")
        return count
