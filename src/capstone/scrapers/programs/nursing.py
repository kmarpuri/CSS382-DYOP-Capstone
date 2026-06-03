"""NURS — Nursing (B.S.N.)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class NursingProgramScraper(ProgramScraper):
    """Pre-licensure RN-to-BSN and BSN paths are different; this models the
    traditional BSN core sequence."""

    major_code = "NURS"
    major_name = "Nursing (B.S.) — RN to BSN"

    CORE = [
        "B NURS 301",  # Foundations of Professional Practice
        "B NURS 302",  # Patient-Centered Care I
        "B NURS 303",  # Patient-Centered Care II
        "B NURS 310",  # Pathophysiology
        "B NURS 312",  # Pharmacology
        "B NURS 320",  # Mental Health Nursing
        "B NURS 350",  # Maternal-Child Nursing
        "B NURS 360",  # Community Health
        "B NURS 410",  # Leadership in Nursing
        "B NURS 420",  # Acute & Chronic Care
        "B NURS 450",  # Evidence-Based Practice
    ]
    CAPSTONE = ["B NURS 495"]  # Senior practicum
    SCIENCE_PREREQS = [
        "B BIO 220",  # Anatomy & Physiology
        "B BIO 230",  # Microbiology
        "B CHEM 143",  # General Chem
        "B NURS 200",  # Intro to Nursing
    ]
    STATS_OPTIONS = ["B BUS 215", "STMATH 341", "STMATH 390"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "B NURS 312",
            ["B NURS 310"],
            "Pharmacology mechanisms make far more sense after pathophysiology.",
        ),
        (
            "B NURS 420",
            ["B NURS 302", "B NURS 303"],
            "Acute/chronic care is the synthesis of the patient-centered care sequence.",
        ),
        (
            "B NURS 495",
            ["B NURS 410", "B NURS 420"],
            "The senior practicum exercises leadership and acute-care competencies together.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "science", self.SCIENCE_PREREQS)
        count += self._insert_pick_one_group(
            conn, "stats", self.STATS_OPTIONS, notes="Complete one statistics course"
        )
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} NURS requirements + {synergy_count} synergies")
        return count
