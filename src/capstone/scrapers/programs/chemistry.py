"""Chemistry — three flavors at UW Bothell:

* :class:`ChemistryBSProgramScraper`        — Chemistry (B.S.)
* :class:`ChemistryBSBiochemProgramScraper` — Chemistry (B.S., Biochemistry option)
* :class:`ChemistryBAProgramScraper`        — Chemistry (B.A.)

All three share the same general-chemistry + organic-chemistry core.
The B.A. drops physical chemistry depth; the biochemistry option
swaps the second PChem quarter for a biochem-heavy elective track.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


# ── shared building blocks ────────────────────────────────────────────

GENERAL_CHEM = ["B CHEM 143", "B CHEM 144", "B CHEM 145"]
ORGANIC_CHEM = ["B CHEM 237", "B CHEM 238", "B CHEM 239"]
ORGANIC_LAB = ["B CHEM 241", "B CHEM 242"]
INORGANIC = "B CHEM 317"
PHYSICAL_CHEM = ["B CHEM 455", "B CHEM 456"]
PHYSICAL_CHEM_LAB = "B CHEM 461"
BIOCHEM = "B CHEM 460"
INTRO_BIO = ["B BIO 180", "B BIO 200", "B BIO 220"]


# ── B.S. ───────────────────────────────────────────────────────────────


class ChemistryBSProgramScraper(ProgramScraper):
    major_code = "CHEM"
    major_name = "Chemistry (B.S.)"

    CAPSTONE = ["B CHEM 499"]
    MATH_PREREQS = ["STMATH 124", "STMATH 125", "STMATH 126"]
    SCIENCE_PREREQS = ["B PHYS 121", "B PHYS 122"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "B CHEM 238",
            ["B CHEM 237"],
            "OChem II picks up where I leaves off — mechanisms expand to more functional groups.",
        ),
        (
            "B CHEM 456",
            ["B CHEM 455"],
            "PChem II's quantum applications need PChem I's thermodynamics framework.",
        ),
        (
            "B CHEM 460",
            ["B CHEM 239"],
            "Biochem mechanisms presume comfort with OChem III's carbonyl chemistry.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "general_chem", GENERAL_CHEM)
        count += self._insert_each(conn, "organic", ORGANIC_CHEM)
        count += self._insert_each(conn, "organic_lab", ORGANIC_LAB)
        count += self._insert_each(
            conn, "physical_chem", [*PHYSICAL_CHEM, PHYSICAL_CHEM_LAB]
        )
        self._insert_req(conn, "inorganic", INORGANIC)
        count += 1
        self._insert_req(conn, "biochem", BIOCHEM)
        count += 1
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_each(conn, "science", self.SCIENCE_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "B CHEM 400+",
            required_count=10,
            notes="10 credits of upper-division chemistry electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} CHEM requirements + {synergy_count} synergies")
        return count


# ── B.S. Biochemistry option ───────────────────────────────────────────


class ChemistryBSBiochemProgramScraper(ProgramScraper):
    major_code = "CHEMBIO"
    major_name = "Chemistry (B.S. — Biochemistry option)"

    CAPSTONE = ["B CHEM 499"]
    BIOCHEM_DEPTH = [
        "B CHEM 460",  # Biochemistry I
        "B CHEM 461",  # Biochemistry II
        "B CHEM 462",  # Biochemistry III / experimental
    ]
    MATH_PREREQS = ["STMATH 124", "STMATH 125", "STMATH 126"]
    SCIENCE_PREREQS = ["B PHYS 121", "B PHYS 122"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        (
            "B CHEM 461",
            ["B CHEM 460"],
            "Biochem II extends Biochem I's metabolism + enzymology core.",
        ),
        (
            "B CHEM 460",
            ["B CHEM 239"],
            "Biochem mechanisms presume comfort with OChem III's carbonyl chemistry.",
        ),
        (
            "B CHEM 462",
            ["B CHEM 461"],
            "Biochem III usually targets molecular biology applications building on I+II.",
        ),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "general_chem", GENERAL_CHEM)
        count += self._insert_each(conn, "organic", ORGANIC_CHEM)
        count += self._insert_each(conn, "organic_lab", ORGANIC_LAB)
        self._insert_req(conn, "physical_chem", PHYSICAL_CHEM[0])
        count += 1  # Only PChem I in this option
        self._insert_req(conn, "inorganic", INORGANIC)
        count += 1
        count += self._insert_each(conn, "biochemistry", self.BIOCHEM_DEPTH)
        count += self._insert_each(conn, "biology_for_biochem", INTRO_BIO)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_each(conn, "science", self.SCIENCE_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "B CHEM 400+",
            required_count=5,
            notes="5 credits of upper-division chemistry electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(
            f"Inserted {count} CHEMBIO requirements + {synergy_count} synergies"
        )
        return count


# ── B.A. ───────────────────────────────────────────────────────────────


class ChemistryBAProgramScraper(ProgramScraper):
    """Chemistry B.A. — lighter quantitative load, breadth-oriented."""

    major_code = "CHEMBA"
    major_name = "Chemistry (B.A.)"

    CAPSTONE = ["B CHEM 499"]
    MATH_PREREQS = ["STMATH 124", "STMATH 125"]
    SCIENCE_PREREQS = ["B PHYS 121"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("B CHEM 238", ["B CHEM 237"], "OChem II picks up directly from OChem I."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "general_chem", GENERAL_CHEM)
        count += self._insert_each(conn, "organic", ORGANIC_CHEM)
        count += self._insert_each(conn, "organic_lab", ORGANIC_LAB)
        self._insert_req(conn, "inorganic", INORGANIC)
        count += 1
        self._insert_req(conn, "physical_chem", PHYSICAL_CHEM[0])
        count += 1
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_each(conn, "science", self.SCIENCE_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(
            conn,
            "elective",
            "B CHEM 300+",
            required_count=15,
            notes="15 credits of chemistry electives",
        )
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} CHEMBA requirements + {synergy_count} synergies")
        return count
