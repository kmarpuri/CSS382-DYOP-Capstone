"""ECON — Economics (B.S.), housed in the School of Business."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class EconomicsProgramScraper(ProgramScraper):
    major_code = "ECON"
    major_name = "Economics (B.S.)"

    CORE = [
        "B ECON 200",   # Microeconomics
        "B ECON 201",   # Macroeconomics
        "B ECON 300",   # Intermediate Micro
        "B ECON 301",   # Intermediate Macro
        "B ECON 351",   # Econometrics I
        "B ECON 352",   # Econometrics II
        "B ECON 421",   # Money & Banking
        "B ECON 450",   # International Economics
    ]
    CAPSTONE = ["B ECON 495"]
    MATH_PREREQS = ["STMATH 124", "STMATH 125", "STMATH 208"]
    STATS_OPTIONS = ["B BUS 215", "STMATH 341", "STMATH 390"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("B ECON 300", ["B ECON 200"],
         "Intermediate Micro formalizes the consumer/firm models from intro Micro."),
        ("B ECON 301", ["B ECON 201"],
         "Intermediate Macro adds dynamic structure to intro Macro's IS-LM intuition."),
        ("B ECON 352", ["B ECON 351"],
         "Econometrics II extends I's OLS framework to time-series and panel data."),
        ("B ECON 495", ["B ECON 352"],
         "The capstone is essentially an econometric research paper."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_pick_one_group(conn, "stats", self.STATS_OPTIONS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(conn, "elective", "B ECON 400+", required_count=15,
                         notes="15 credits of upper-division economics electives")
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} ECON requirements + {synergy_count} synergies")
        return count
