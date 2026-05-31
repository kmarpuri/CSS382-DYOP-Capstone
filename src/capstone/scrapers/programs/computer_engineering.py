"""CE — Computer Engineering (B.S.).

Hardcoded based on:
  - https://www.uwb.edu/stem/undergraduate/majors/bsce
  - https://www.washington.edu/students/crscatb/bce.html
  - https://www.washington.edu/students/crscatb/bee.html

CE at UWB pulls heavily from both the CSS and B EE catalogs.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class ComputerEngineeringProgramScraper(ProgramScraper):
    """B.S. in Computer Engineering — joint hardware/software major.

    Math + physics + the CSE 142/143/342 sequence on the software side,
    plus B EE 215/233/271 on the hardware side, leading into the joint
    B CE 495/496 capstone sequence.
    """

    major_code = "CE"
    major_name = "Computer Engineering (B.S.)"

    # Programming sequence (shared with CSSE)
    PROGRAMMING_PREREQS = ["CSS 142", "CSS 143"]

    # Software-side core
    CS_CORE = [
        "CSS 342",   # Data Structures, Algorithms, and Discrete Math I
        "CSS 343",   # Data Structures, Algorithms, and Discrete Math II
        "CSS 422",   # Hardware and Computer Organization
        "CSS 430",   # Operating Systems
    ]

    # Hardware-side core
    EE_CORE = [
        "B EE 215",  # Fundamentals of Electrical Engineering
        "B EE 233",  # Circuit Theory
        "B EE 271",  # Digital Circuits and Systems
    ]

    # CE-specific upper-division
    CE_CORE = [
        "B EE 425",  # Microprocessor System Design
        "B EE 427",  # Digital System Design Using HDL
    ]

    # Capstone sequence (two quarters)
    CAPSTONE = ["B CE 495", "B CE 496"]

    # Math + physics prerequisites
    MATH = [
        "STMATH 124", "STMATH 125", "STMATH 126", "STMATH 207", "STMATH 208",
    ]
    PHYSICS = ["B PHYS 121", "B PHYS 122"]   # may not be in catalog; seed_synergies skips missing

    # Writing
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("B EE 425", ["B EE 271"],
         "Microprocessor System Design assumes the digital-logic vocabulary "
         "(flip-flops, FSMs) built up in Digital Circuits."),
        ("B EE 427", ["B EE 271"],
         "HDL design tools formalize what you sketched on paper in Digital "
         "Circuits and Systems."),
        ("CSS 430", ["CSS 422"],
         "Hardware and Computer Organization gives you the assembly + memory "
         "model that makes Operating Systems concrete."),
        ("B CE 495", ["B EE 425", "CSS 422"],
         "The CE capstone bridges the hardware and software stacks — "
         "having microprocessor design AND hardware organization on board "
         "makes the integration story tractable."),
        ("B CE 496", ["B CE 495"],
         "Capstone II is the build-out of the design defended in I."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)

        count = 0
        count += self._insert_each(conn, "programming", self.PROGRAMMING_PREREQS)
        count += self._insert_each(conn, "core", self.CS_CORE)
        count += self._insert_each(conn, "ee_core", self.EE_CORE)
        count += self._insert_each(conn, "ce_core", self.CE_CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH)
        count += self._insert_each(conn, "physics", self.PHYSICS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn, "elective", "B EE 300+ / CSS 300+",
            required_count=15,
            notes="15 credits of upper-division CSS or B EE electives",
        )
        count += 1

        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()

        logger.info(
            f"Inserted {count} CE requirements + {synergy_count} soft synergies"
        )
        return count
