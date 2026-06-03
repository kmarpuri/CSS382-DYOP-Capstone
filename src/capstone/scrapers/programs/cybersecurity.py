"""CYBERSEC — Cybersecurity Engineering (B.S.)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class CybersecurityEngineeringProgramScraper(ProgramScraper):
    major_code = "CSSEC"
    major_name = "CSSE (B.S. — Information Assurance & Cybersecurity option)"

    CORE = [
        "CSS 342",  # DSA I
        "CSS 343",  # DSA II
        "CSS 360",  # Software Engineering
        "CSS 422",  # Hardware
        "CSS 430",  # OS
        "CSS 410",  # Information Assurance
        "CSS 415",  # Cryptographic Foundations
        "CSS 416",  # Network Security
        "CSS 417",  # Software Security
        "CSS 432",  # Network Design
    ]
    CAPSTONE = ["CSS 497"]
    MATH_PREREQS = ["STMATH 124", "STMATH 125", "STMATH 308", "STMATH 390"]
    PROGRAMMING_PREREQS = ["CSS 142", "CSS 143"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "CSS 416",
            ["CSS 432"],
            "Network Security applies attack/defense models to the protocols you learn in Network Design.",
        ),
        (
            "CSS 415",
            ["STMATH 308"],
            "Crypto's number-theory backbone is much easier after Linear Algebra and modular arithmetic exposure.",
        ),
        (
            "CSS 417",
            ["CSS 360"],
            "Software-security threat modeling assumes SE-level vocabulary about SDLC.",
        ),
        (
            "CSS 410",
            ["CSS 430"],
            "InfoAssurance frames OS-level isolation primitives — having taken OS makes them concrete.",
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
            "CSS 400+",
            required_count=10,
            notes="10 credits of CSS security electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(
            f"Inserted {count} CYBERSEC requirements + {synergy_count} synergies"
        )
        return count
