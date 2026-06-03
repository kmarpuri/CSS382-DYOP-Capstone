"""Course catalog scraper for UW Bothell.

Scrapes course descriptions from https://www.washington.edu/students/crscatb/{dept}.html
and extracts course_id, title, credits, description, and prerequisite relationships.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from capstone.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Base URL for UW Bothell course catalog pages
CATALOG_BASE = "https://www.washington.edu/students/crscatb"


class CatalogScraper(BaseScraper):
    """Scrape course descriptions from the UW Bothell course catalog."""

    def __init__(
        self,
        departments: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.departments = departments or ["css"]

    def scrape(self, conn: sqlite3.Connection) -> int:
        """Scrape all configured departments and persist to the courses table."""
        total = 0
        now = datetime.now(timezone.utc).isoformat()

        for dept in self.departments:
            url = f"{CATALOG_BASE}/{dept}.html"
            try:
                html = self.fetch(url)
                if not html:
                    logger.warning(f"Empty response for {dept}, skipping")
                    continue
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                continue

            courses = self._parse_catalog_page(html, dept, now)
            count = self._persist_courses(conn, courses, dept, now)
            total += count
            logger.info(f"Scraped {count} courses from {dept}")

        return total

    def _parse_catalog_page(
        self, html: str, dept_slug: str, scraped_at: str
    ) -> list[dict]:
        """Parse a catalog page and return a list of course dicts."""
        soup = BeautifulSoup(html, "html.parser")
        courses = []

        # The catalog pages use <a> tags with name anchors for each course,
        # followed by a <b> tag with the course ID and a <br> with the description.
        # However, the more reliable approach is to find all course entries
        # in the page text.

        # Strategy: find all course entries by looking for the pattern
        # "CSS 142 Computer Programming I (5)" in anchor + bold text,
        # then grab the description text that follows.

        # First, try to find all <a> tags with name attributes matching course patterns
        page_text = soup.get_text()

        # The course catalog format from crscatb is:
        # [Course ID] [Title] ([credits]) [gen-ed codes]
        # Description text...
        # Prerequisite: ...
        # Course overlaps with: ...

        # Parse the raw text approach — catalog pages embed all info in
        # contiguous text blocks. We look for course ID patterns.

        # Department code mapping: slug → course prefix
        dept_prefix = self._slug_to_prefix(dept_slug)

        # Find all course blocks using regex on the full page text
        # Pattern: "CSS   342" or "STMATH 124" at the start of a course block
        # In the HTML, courses are individual anchors with detailed text

        # Better approach: parse the HTML structure
        # Each course is typically in a paragraph or div with an anchor
        # The crscatb pages have course info as runs of text between anchors
        # Let's parse by finding course ID patterns in the full HTML text
        # and extracting structured data

        # Use a regex-based approach on the page text
        courses = self._extract_courses_from_text(
            page_text, dept_prefix, dept_slug, scraped_at
        )

        return courses

    def _slug_to_prefix(self, slug: str) -> str:
        """Map a catalog URL slug to the course prefix used in course IDs."""
        mapping = {
            "css": "CSS",
            "cssskl": "CSSSKL",
            "stmath": "STMATH",
            "bwrit": "B WRIT",
            "bbus": "B BUS",
            "bcore": "B CORE",
            "bearth": "BEARTH",
            "bbio": "B BIO",
            "bchem": "B CHEM",
            "bphys": "B PHYS",
            "bis": "BIS",
            "bdata": "B DATA",
            "acmpt": "A CMPT",
            "bimd": "B IMD",
            "beduc": "B EDUC",
            "bacct": "B ACCT",
            "bbecn": "B BECN",
            "bbskl": "B BSKL",
            "bhlth": "B HLTH",
            "bhs": "BHS",
            "bnurs": "B NURS",
            "bce": "B CE",
            "bee": "B EE",
            "bengr": "B ENGR",
            "bmath": "B MATH",
            "bme": "B ME",
            "bst": "BST",
            "barab": "B ARAB",
            "bchin": "B CHIN",
            "blead": "B LEAD",
            "bjapan": "BJAPAN",
            "bkorea": "BKOREA",
            "bspan": "B SPAN",
            "bcusp": "B CUSP",
            "elcbus": "ELCBUS",
            "bpolst": "BPOLST",
            "bispsy": "BISPSY",
            "bissts": "BISSTS",
            "bismcs": "BISMCS",
            "bislep": "BISLEP",
            "bisskl": "BISSKL",
            "bisia": "BISIA",
            "bisgws": "BISGWS",
            "bisgst": "BISGST",
            "biscla": "BISCLA",
            "bculst": "BCULST",
            "bcwrit": "BCWRIT",
            "bisaes": "BISAES",
            "bes": "BES",
            "lede": "LEDE",
        }
        return mapping.get(slug, slug.upper())

    def _extract_courses_from_text(
        self,
        text: str,
        dept_prefix: str,
        dept_slug: str,
        scraped_at: str,
    ) -> list[dict]:
        """Extract course data from the page text using regex patterns."""
        courses = []

        # Escape special regex chars in the prefix
        prefix_re = re.escape(dept_prefix)

        # Match course entries like:
        # "CSS 342 Data Structures, Algorithms, and Discrete Mathematics I (5)"
        # or "CSS 198 Supervised Study (1-5, max. 6)"
        # The prefix might have a space (e.g., "B WRIT"), so we allow for spaces
        # in the number match.
        #
        # NOTE: do NOT use re.DOTALL — course headers are always on a single
        # line, and DOTALL causes the non-greedy .+? to eat across lines into
        # the next course entry.
        pattern = re.compile(
            rf"({prefix_re}\s+\d{{2,3}})[ \t]+"  # Course ID + same-line space
            rf"([A-Z][^\n\(]+?)\s*"  # Title (stays on one line)
            rf"\((\d[\d\-\*,. ]*(?:max\.\s*\d+)?)\)",  # Credits in parens
        )

        matches = list(pattern.finditer(text))

        # Deduplicate: the page text contains "View course details in MyPlan:
        # CSS 342" lines that re-trigger the regex. Keep only the *first*
        # occurrence of each course_id.
        seen: set[str] = set()
        unique_matches = []
        for m in matches:
            cid = re.sub(r"\s+", " ", m.group(1).strip())
            if cid not in seen:
                seen.add(cid)
                unique_matches.append(m)
        matches = unique_matches

        for i, match in enumerate(matches):
            course_id = re.sub(r"\s+", " ", match.group(1).strip())
            title = re.sub(r"\s+", " ", match.group(2).strip())
            credits_str = match.group(3).strip()

            # Extract the description: text between this match end and the
            # next match start (or end of text)
            desc_start = match.end()
            desc_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            description = text[desc_start:desc_end].strip()

            # Clean up the description — remove the "View course details" links
            description = re.sub(
                r"View course details in MyPlan:.*?(?=\n|$)", "", description
            )
            description = re.sub(r"\s+", " ", description).strip()

            # Remove gen-ed designators from title (e.g., "NSc, RSN" at the end)
            gen_ed_pattern = re.compile(
                r"\s*(?:,?\s*(?:NSc|RSN|SSc|DIV|A&H|A&H/NSc|NW|VLPA|I&S|QSR|C|W))+\s*$"
            )
            title = gen_ed_pattern.sub("", title).strip()

            # Extract offering pattern from description if present
            offering_match = re.search(
                r"Offered:\s*((?:jointly with [^;.]+;\s*)?[A-Z][A-Za-z,./]+)\.",
                description,
            )
            offering_pattern = offering_match.group(1) if offering_match else None

            # Parse prerequisites from description
            prereqs = self._parse_prerequisites(description, course_id)

            courses.append(
                {
                    "course_id": course_id,
                    "title": title,
                    "credits": credits_str,
                    "description": description,
                    "offering_pattern": offering_pattern,
                    "department": dept_prefix,
                    "scraped_at": scraped_at,
                    "prerequisites": prereqs,
                }
            )

        return courses

    def _parse_prerequisites(self, description: str, course_id: str) -> list[dict]:
        """Parse prerequisite text from a course description.

        Returns a list of dicts with keys:
            prereq_id, type, group_id, min_grade
        """
        prereqs = []

        # Find the prerequisite section
        prereq_match = re.search(
            r"Prerequisite:\s*(.+?)(?:Offered:|Course (?:overlaps|equivalent)|Credit/|May not|$)",
            description,
            re.IGNORECASE | re.DOTALL,
        )
        if not prereq_match:
            return prereqs

        prereq_text = prereq_match.group(1).strip()
        prereq_text = re.sub(r"\s+", " ", prereq_text)

        # Split by semicolons to get independent prerequisite groups
        # Each semicolon-separated segment is an AND requirement
        segments = [s.strip().rstrip(".") for s in prereq_text.split(";")]

        group_counter = 0

        for segment in segments:
            if not segment:
                continue

            # Detect concurrent
            is_concurrent = (
                "may be taken concurrently" in segment.lower()
                or "which may be taken concurrently" in segment.lower()
            )

            # Detect "minimum grade of X in"
            grade_match = re.search(
                r"minimum grade of ([\d.]+) in", segment, re.IGNORECASE
            )
            default_grade = grade_match.group(1) if grade_match else None

            # Check if this is an OR-clause (contains "or" or "either")
            has_or = " or " in segment.lower() or "either" in segment.lower()

            # Extract all course IDs from this segment
            # Course ID pattern: 1-2 word prefix + 3 digit number
            course_pattern = re.compile(r"\b([A-Z][A-Z &]{0,8})\s+(\d{3})\b")
            found_courses = []
            for m in course_pattern.finditer(segment):
                prefix = m.group(1).strip()
                number = m.group(2)
                cid = f"{prefix} {number}"
                # Skip if it matches the course itself
                if cid != course_id:
                    found_courses.append(cid)

            if not found_courses:
                continue

            if has_or and len(found_courses) > 1:
                # OR-clause: group them together
                group_counter += 1
                for cid in found_courses:
                    prereqs.append(
                        {
                            "prereq_id": cid,
                            "type": "concurrent" if is_concurrent else "one_of",
                            "group_id": group_counter,
                            "min_grade": default_grade,
                        }
                    )
            else:
                # AND requirements (individual)
                for cid in found_courses:
                    prereqs.append(
                        {
                            "prereq_id": cid,
                            "type": "concurrent" if is_concurrent else "required",
                            "group_id": 0,
                            "min_grade": default_grade,
                        }
                    )

        return prereqs

    def _persist_courses(
        self,
        conn: sqlite3.Connection,
        courses: list[dict],
        dept_slug: str,
        scraped_at: str,
    ) -> int:
        """Insert or update courses and their prerequisites in the database."""
        count = 0

        for course in courses:
            # Upsert course
            conn.execute(
                """
                INSERT INTO courses (course_id, title, credits, description,
                                     offering_pattern, department, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(course_id) DO UPDATE SET
                    title = excluded.title,
                    credits = excluded.credits,
                    description = excluded.description,
                    offering_pattern = excluded.offering_pattern,
                    department = excluded.department,
                    scraped_at = excluded.scraped_at
                """,
                (
                    course["course_id"],
                    course["title"],
                    course["credits"],
                    course["description"],
                    course.get("offering_pattern"),
                    course["department"],
                    course["scraped_at"],
                ),
            )

            # Delete old prerequisites for this course, then re-insert
            conn.execute(
                "DELETE FROM prerequisites WHERE course_id = ?",
                (course["course_id"],),
            )
            for prereq in course.get("prerequisites", []):
                conn.execute(
                    """
                    INSERT INTO prerequisites (course_id, prereq_id, type, group_id, min_grade)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        course["course_id"],
                        prereq["prereq_id"],
                        prereq["type"],
                        prereq["group_id"],
                        prereq.get("min_grade"),
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
            (f"catalog:{dept_slug}", scraped_at, count),
        )
        conn.commit()

        return count
