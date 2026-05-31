"""ME — Mechanical Engineering (B.S.)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class MechanicalEngineeringProgramScraper(ProgramScraper):
    major_code = "ME"
    major_name = "Mechanical Engineering (B.S.)"

    CORE = [
        "B ME 220",   # Statics
        "B ME 230",   # Dynamics
        "B ME 250",   # Mechanics of Materials
        "B ME 313",   # Thermodynamics
        "B ME 314",   # Heat Transfer
        "B ME 315",   # Fluid Mechanics
        "B ME 330",   # System Dynamics
        "B ME 354",   # Mechanical Design
        "B ME 410",   # Manufacturing Processes
        "B ME 420",   # Control Systems
        "B ME 451",   # Mechanical Design II
    ]
    CAPSTONE = ["B ME 495", "B ME 496"]   # Two-quarter senior design
    MATH_PREREQS = ["STMATH 124", "STMATH 125", "STMATH 126", "STMATH 207", "STMATH 208"]
    SCIENCE_PREREQS = ["B PHYS 121", "B PHYS 122", "B PHYS 123", "B CHEM 143"]
    PROGRAMMING_PREREQS = ["CSS 142"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("B ME 230", ["B ME 220"],
         "Dynamics extends Statics from equilibrium to motion."),
        ("B ME 250", ["B ME 220"],
         "Mechanics of Materials builds on statics free-body diagrams to compute internal stresses."),
        ("B ME 314", ["B ME 313"],
         "Heat Transfer presumes thermo fluency in energy balances and properties."),
        ("B ME 451", ["B ME 354"],
         "Mechanical Design II iterates on Design I's component-selection methodology."),
        ("B ME 495", ["B ME 451", "B ME 420"],
         "Senior capstone usually needs both design synthesis and control."),
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
        self._insert_req(conn, "elective", "B ME 400+", required_count=12,
                         notes="12 credits of ME technical electives")
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} ME requirements + {synergy_count} synergies")
        return count
