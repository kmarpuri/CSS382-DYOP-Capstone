"""BUSADM — Business Administration (B.A.).

Hardcoded based on:
  - https://www.uwb.edu/business/undergraduate/program/business-administration
  - https://www.washington.edu/students/crscatb/bbus.html
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class BusinessAdminProgramScraper(ProgramScraper):
    """B.A. in Business Administration.

    UW Bothell's School of Business uses ``BUSADM`` as the major code on
    transcripts; we use that as the canonical identifier here.
    """

    major_code = "BUSADM"
    major_name = "Business Administration (B.A.)"

    # Pre-major (must complete before applying to the major)
    PRE_MAJOR = [
        "B BUS 201",  # Introduction to Business
        "B BUS 210",  # Principles of Financial Accounting
        "B BUS 211",  # Principles of Managerial Accounting
        "B BUS 215",  # Introduction to Business Statistics
        "B BUS 220",  # Introduction to Microeconomics
        "B BUS 221",  # Introduction to Macroeconomics
        "B BUS 230",  # Introduction to Business Law
    ]

    # Upper-division core (all required)
    CORE = [
        "B BUS 300",  # Organizational Behavior, Ethics, and Inclusivity
        "B BUS 305",  # Managerial Communication
        "B BUS 310",  # Managerial Economics
        "B BUS 320",  # Marketing Management
        "B BUS 330",  # Information Management and Analysis
        "B BUS 340",  # Operations Management
        "B BUS 350",  # Business Finance
    ]

    CAPSTONE = ["B BUS 489"]  # Digital Business Lab

    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "B BUS 350",
            ["B BUS 210", "B BUS 211"],
            "Finance presumes you can read income statements and trace cash "
            "flows — financial + managerial accounting are the prep.",
        ),
        (
            "B BUS 310",
            ["B BUS 220", "B BUS 221"],
            "Managerial Economics applies micro and macro frameworks to firm "
            "decisions.",
        ),
        (
            "B BUS 340",
            ["B BUS 215"],
            "Operations Management leans on statistical thinking for quality "
            "control and forecasting.",
        ),
        (
            "B BUS 489",
            ["B BUS 320", "B BUS 350"],
            "The Digital Business Lab integrates marketing and finance, so "
            "completing both first makes capstone projects far more tractable.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)

        count = 0
        count += self._insert_each(conn, "pre_major", self.PRE_MAJOR)
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "B BUS 400+",
            required_count=15,
            notes="15 credits of upper-division business electives "
            "(typically area-of-emphasis courses)",
        )
        count += 1

        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()

        logger.info(
            f"Inserted {count} BUSADM requirements + {synergy_count} soft synergies"
        )
        return count
