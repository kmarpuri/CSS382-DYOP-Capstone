"""Time schedule scraper for UW Bothell.

Scrapes the PUBLIC time schedule at:
  https://www.washington.edu/students/timeschd/pub/B/{QTR}{YEAR}/{dept}.html

No NetID required for the /pub/ variant.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from capstone.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

TIMESCHEDULE_BASE = "https://www.washington.edu/students/timeschd/pub/B"


class TimeScheduleScraper(BaseScraper):
    """Scrape section offerings from the UW Bothell public time schedule."""

    def __init__(
        self,
        quarters: list[str] | None = None,
        departments: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.quarters = quarters or ["AUT2026"]
        self.departments = departments or ["css"]

    def scrape(self, conn: sqlite3.Connection) -> int:
        """Scrape time schedule for all configured quarters and departments."""
        total = 0
        now = datetime.now(timezone.utc).isoformat()

        for qtr in self.quarters:
            for dept in self.departments:
                url = f"{TIMESCHEDULE_BASE}/{qtr}/{dept}.html"
                try:
                    html = self.fetch(url)
                    if not html:
                        continue
                except Exception as e:
                    logger.warning(f"Failed to fetch {url}: {e}")
                    continue

                quarter_code, year = self._parse_quarter_string(qtr)
                sections = self._parse_time_schedule(
                    html, dept, quarter_code, year, now
                )
                count = self._persist_sections(
                    conn, sections, dept, qtr, now
                )
                total += count
                logger.info(
                    f"Scraped {count} sections for {dept} {qtr}"
                )

        return total

    def _parse_quarter_string(self, qtr: str) -> tuple[str, int]:
        """Parse 'AUT2026' into ('AUT', 2026)."""
        match = re.match(r"(SPR|SUM|AUT|WIN)(\d{4})", qtr)
        if not match:
            raise ValueError(f"Invalid quarter string: {qtr}")
        return match.group(1), int(match.group(2))

    def _parse_time_schedule(
        self,
        html: str,
        dept_slug: str,
        quarter: str,
        year: int,
        scraped_at: str,
    ) -> list[dict]:
        """Parse the time schedule HTML and extract section data."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        sections = []

        # The time schedule format is quite irregular HTML.
        # We parse the raw text to find course headers and their sections.
        # Course headers look like: "CSS   342" followed by section lines.

        # Find all course header + section blocks
        # Course headers are in the format: CSS   NNN
        dept_prefix = self._slug_to_prefix(dept_slug)
        prefix_re = re.escape(dept_prefix)

        # Split text into lines for processing
        lines = text.split("\n")

        current_course_id = None
        current_course_title = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this line starts a new course
            course_header = re.match(
                rf"({prefix_re}\s+\d{{3}})\s+(.+?)(?:\(|$)",
                line,
            )
            if course_header:
                cid = re.sub(r"\s+", " ", course_header.group(1).strip())
                current_course_id = cid
                current_course_title = course_header.group(2).strip()
                continue

            if current_course_id is None:
                continue

            # Try to parse a section line
            # Section lines contain SLN numbers (5 digits) and section IDs
            section = self._parse_section_line(
                line, current_course_id, quarter, year, scraped_at
            )
            if section:
                sections.append(section)

        return sections

    def _parse_section_line(
        self,
        line: str,
        course_id: str,
        quarter: str,
        year: int,
        scraped_at: str,
    ) -> dict | None:
        """Try to parse a single section line from the time schedule."""
        # Look for SLN (5-digit number) which is the key identifier
        sln_match = re.search(r"\b(\d{5})\b", line)
        if not sln_match:
            return None

        sln = sln_match.group(1)

        # Section ID (single or double letter, like "A", "B", "AA")
        section_match = re.search(rf"{sln}\s+([A-Z]{{1,2}})\s", line)
        section_id = section_match.group(1) if section_match else None

        # Skip lab/quiz sections for now (they have "LB" or "QZ" designators)
        if section_id and re.search(r"\bLB\b|\bQZ\b", line):
            # Still record them but mark as lab
            pass

        # Credits (single digit or range like "1-5")
        credits_match = re.search(rf"{sln}\s+[A-Z]{{1,2}}\s+(\d[\d\-]*)\s", line)
        credits = credits_match.group(1) if credits_match else None

        # Meeting days/times: MW, TTh, MWF, etc. followed by time
        days_time_match = re.search(
            r"\b(M?T?W?Th?F?(?:Sa)?(?:Su)?)\s+(\d{3,4})-(\d{3,4}(?:P)?)\b",
            line,
        )
        days = days_time_match.group(1) if days_time_match else None
        time_start = days_time_match.group(2) if days_time_match else None
        time_end = days_time_match.group(3) if days_time_match else None

        # "to be arranged" for independent study
        if "to be arranged" in line.lower():
            days = "TBA"

        # Status: Open or Closed
        status = None
        if "Open" in line:
            status = "Open"
        elif "Closed" in line:
            status = "Closed"

        # Enrollment: enrolled/limit (e.g., "33/ 48" or "33/48")
        enrl_match = re.search(r"(\d+)\s*/\s*(\d+)(?:E)?", line)
        enrolled = int(enrl_match.group(1)) if enrl_match else None
        enroll_limit = int(enrl_match.group(2)) if enrl_match else None

        # Fee
        fee_match = re.search(r"\$(\d+)", line)
        fee = f"${fee_match.group(1)}" if fee_match else None

        # Restrictions
        restrictions = None
        if line.startswith("Restr") or "Restr" in line[:10]:
            restrictions = "Restricted"
        if line.startswith("IS ") or " IS " in line[:10]:
            restrictions = "Instructor Signature"

        # Grading
        grading = None
        if "CR/NC" in line:
            grading = "CR/NC"

        # Notes: everything after the enrollment data
        notes = None
        if enrl_match:
            after_enrl = line[enrl_match.end():]
            # Clean up and capture notes
            notes_text = re.sub(r"\$\d+", "", after_enrl).strip()
            # Remove grading info already captured
            notes_text = notes_text.replace("CR/NC", "").strip()
            if notes_text and len(notes_text) > 3:
                notes = notes_text

        return {
            "course_id": course_id,
            "section_id": section_id,
            "sln": sln,
            "quarter": quarter,
            "year": year,
            "credits": credits,
            "days": days,
            "time_start": time_start,
            "time_end": time_end,
            "status": status,
            "enrolled": enrolled,
            "enroll_limit": enroll_limit,
            "fee": fee,
            "restrictions": restrictions,
            "grading": grading,
            "notes": notes,
            "scraped_at": scraped_at,
        }

    def _slug_to_prefix(self, slug: str) -> str:
        """Map URL slug to course prefix."""
        # Reuse the same mapping as catalog scraper
        from capstone.scrapers.catalog import CatalogScraper

        scraper = CatalogScraper.__new__(CatalogScraper)
        return scraper._slug_to_prefix(slug)

    def _persist_sections(
        self,
        conn: sqlite3.Connection,
        sections: list[dict],
        dept_slug: str,
        qtr_str: str,
        scraped_at: str,
    ) -> int:
        """Insert section data into the time_schedule table."""
        # Delete old data for this quarter/department combo
        quarter_code, year = self._parse_quarter_string(qtr_str)
        prefix = self._slug_to_prefix(dept_slug)
        conn.execute(
            """
            DELETE FROM time_schedule
            WHERE course_id LIKE ? AND quarter = ? AND year = ?
            """,
            (f"{prefix}%", quarter_code, year),
        )

        count = 0
        for section in sections:
            conn.execute(
                """
                INSERT INTO time_schedule
                    (course_id, section_id, sln, quarter, year, credits,
                     days, time_start, time_end, status, enrolled,
                     enroll_limit, fee, restrictions, grading, notes, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    section["course_id"],
                    section["section_id"],
                    section["sln"],
                    section["quarter"],
                    section["year"],
                    section["credits"],
                    section["days"],
                    section["time_start"],
                    section["time_end"],
                    section["status"],
                    section["enrolled"],
                    section["enroll_limit"],
                    section["fee"],
                    section["restrictions"],
                    section["grading"],
                    section["notes"],
                    section["scraped_at"],
                ),
            )
            count += 1

        # Update scrape metadata
        conn.execute(
            """
            INSERT INTO scrape_metadata (source, scraped_at, record_count)
            VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                scraped_at = excluded.scraped_at,
                record_count = excluded.record_count
            """,
            (f"timeschedule:{qtr_str}:{dept_slug}", scraped_at, count),
        )
        conn.commit()

        return count
