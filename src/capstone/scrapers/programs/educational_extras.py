"""DYS & ELEMED — School of Educational Studies B.A.s.

* :class:`DevelopmentalYouthStudiesProgramScraper` — Developmental & Youth Studies
* :class:`ElementaryEducationProgramScraper`      — Elementary Education Option (teacher certification track)
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from capstone.scrapers.base import ProgramScraper

logger = logging.getLogger(__name__)


class DevelopmentalYouthStudiesProgramScraper(ProgramScraper):
    major_code = "DYS"
    major_name = "Developmental & Youth Studies (B.A.)"

    CORE = [
        "B EDUC 210",   # Cultural Foundations of Education
        "B EDUC 220",   # Schools & Society
        "B EDUC 240",   # Child Development
        "B EDUC 300",   # Educational Psychology
        "B EDUC 330",   # Adolescent Development
        "B EDUC 360",   # Youth in Community
        "B EDUC 410",   # Inquiry in Education
        "B EDUC 440",   # Family-Community-School Partnerships
    ]
    CAPSTONE = ["B EDUC 495"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("B EDUC 330", ["B EDUC 240"],
         "Adolescent development builds on the child-development framework."),
        ("B EDUC 440", ["B EDUC 360"],
         "Family-Community-School Partnerships extends the youth-in-community vocabulary."),
        ("B EDUC 495", ["B EDUC 410"],
         "The capstone is an inquiry-led project — 410 is the methodological prerequisite in practice."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        self._insert_req(conn, "elective", "B EDUC 300+", required_count=15,
                         notes="15 credits of upper-division Educational Studies electives")
        count += 1
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} DYS requirements + {synergy_count} synergies")
        return count


class ElementaryEducationProgramScraper(ProgramScraper):
    """Elementary Education Option — leads to a Washington State teaching
    certificate. Embedded in the Educational Studies B.A. with a
    certification-track methods sequence."""

    major_code = "ELEMED"
    major_name = "Elementary Education Option (B.A.)"

    CORE = [
        "B EDUC 210",   # Cultural Foundations of Education
        "B EDUC 220",   # Schools & Society
        "B EDUC 300",   # Educational Psychology
        "B EDUC 320",   # Assessment in Education
        "B EDUC 410",   # Inquiry in Education
    ]
    METHODS = [
        "B EDUC 450",   # Literacy Methods
        "B EDUC 451",   # Math Methods
        "B EDUC 452",   # Science Methods
        "B EDUC 453",   # Social Studies Methods
    ]
    PRACTICUM = [
        "B EDUC 470",   # Field Experience I
        "B EDUC 471",   # Field Experience II
        "B EDUC 472",   # Student Teaching
    ]
    CAPSTONE = ["B EDUC 495"]
    SCIENCE_PREREQS = ["B BIO 180"]
    MATH_PREREQS = ["STMATH 170", "STMATH 171"]
    WRITING_PREREQS = ["B WRIT 134", "B WRIT 135"]

    synergies = [
        ("B EDUC 451", ["STMATH 171"],
         "Elementary Math Methods leans on the elementary-teacher math sequence."),
        ("B EDUC 472", ["B EDUC 470", "B EDUC 471"],
         "Student Teaching is the culmination of the field-experience sequence."),
    ]

    def scrape_requirements(self, conn: sqlite3.Connection) -> int:
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "methods", self.METHODS)
        count += self._insert_each(conn, "practicum", self.PRACTICUM)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        count += self._insert_each(conn, "math", self.MATH_PREREQS)
        count += self._insert_each(conn, "science", self.SCIENCE_PREREQS)
        count += self._insert_each(conn, "writing", self.WRITING_PREREQS)
        synergy_count = self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        conn.commit()
        logger.info(f"Inserted {count} ELEMED requirements + {synergy_count} synergies")
        return count
