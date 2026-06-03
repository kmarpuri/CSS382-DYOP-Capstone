"""Data Visualization — IAS-housed, two variants (B.A. and B.S.)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class DataVisualizationBAProgramScraper(ProgramScraper):
    """B.A. variant — narrative + design forward, lighter on statistics."""

    major_code = "DVBA"
    major_name = "Data Visualization (B.A.)"

    CORE = [
        "BIS 240",  # Inquiry
        "BIS 215",  # Understanding Statistics
        "BIS 312",  # Data Visualization Fundamentals
        "BIS 315",  # Information Aesthetics
        "BIS 365",  # Storytelling with Data
        "BIS 412",  # Visual Analytics
        "BIS 442",  # Interactive Data Visualization
    ]
    CAPSTONE = ["BIS 499"]
    PROGRAMMING_PREREQS = ["CSS 142"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "BIS 365",
            ["BIS 312"],
            "Storytelling with Data presumes comfort with the visualization grammar from BIS 312.",
        ),
        (
            "BIS 442",
            ["BIS 412"],
            "Interactive Visualization extends the Visual Analytics toolkit into live, web-native artifacts.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "programming", self.PROGRAMMING_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "BIS 300+",
            required_count=15,
            notes="15 credits of upper-division BIS electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} DVBA requirements + {synergy_count} synergies")
        return count


class DataVisualizationBSProgramScraper(ProgramScraper):
    """B.S. variant — quantitative + programming forward, more statistics
    and a real data-engineering elective track."""

    major_code = "DVBS"
    major_name = "Data Visualization (B.S.)"

    CORE = [
        "BIS 240",  # Inquiry
        "BIS 312",  # Data Visualization Fundamentals
        "BIS 412",  # Visual Analytics
        "BIS 442",  # Interactive Data Visualization
        "STMATH 390",  # Statistics for Data Science
        "CSS 142",  # Programming I
        "CSS 143",  # Programming II
        "CSS 340",  # Data Analytics
    ]
    CAPSTONE = ["BIS 499"]
    MATH_PREREQS = ["STMATH 124", "STMATH 208"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "CSS 340",
            ["CSS 143", "STMATH 390"],
            "Data Analytics expects both programming fluency and statistical literacy.",
        ),
        (
            "BIS 442",
            ["BIS 412", "CSS 143"],
            "Interactive Vis blends visual analytics ideas with programming.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "CSS 300+",
            required_count=10,
            notes="10 credits of data/programming electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} DVBS requirements + {synergy_count} synergies")
        return count
