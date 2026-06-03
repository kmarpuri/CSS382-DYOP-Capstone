"""Tests for the catalog scraper's parsing logic.

Uses fixture HTML instead of live requests to test parsing in isolation.
"""

import pytest

from capstone.db.connection import connect
from capstone.db.schema import init_db
from capstone.scrapers.catalog import CatalogScraper


# Sample HTML snippet modeled after real crscatb/css.html content
SAMPLE_CSS_HTML = """
<html><body>
<a name="css342"></a>
CSS 342 Data Structures, Algorithms, and Discrete Mathematics I (5)
Integrating mathematical principles with detailed instruction in computer
programming. Explores mathematical reasoning and discrete structures through
object-oriented programming. Includes algorithm analysis, basic abstract data
types, and data structures. May not be repeated. Course overlaps with: T INFO 473.
Prerequisite: a minimum grade of 2.8 in either CSS 133, CSS 143, CSE 143, or
CSS 162; and minimum grade of 2.5 in either STMATH 125 or MATH 125.
<a href="https://myplan.washington.edu/course/#/courses/CSS342">
View course details in MyPlan: CSS 342</a>

<a name="css343"></a>
CSS 343 Data Structures, Algorithms, and Discrete Mathematics II (5)
Develops competencies associated with problem-solving, algorithms, and
computational models. Explores algorithm development and analysis; abstract data
types including trees, priority queues, heaps, graphs, and hash tables.
Prerequisite: CSS 301, which may be taken concurrently; and a minimum grade of
2.0 in CSS 342.
<a href="https://myplan.washington.edu/course/#/courses/CSS343">
View course details in MyPlan: CSS 343</a>

<a name="css430"></a>
CSS 430 Operating Systems (5)
Principles of operating systems, including process management, memory management,
auxiliary storage management, and resource allocation. May not be repeated.
Course overlaps with: CSE 451 and TCES 420.
Prerequisite: a minimum grade of 2.0 in CSS 343.
Offered: AWSp.
<a href="https://myplan.washington.edu/course/#/courses/CSS430">
View course details in MyPlan: CSS 430</a>

<a name="css382"></a>
CSS 382 Introduction to Artificial Intelligence (5) RSN
Principal ideas and developments in artificial intelligence, such as problem
solving, knowledge representation, search, reasoning under uncertainty, learning,
and natural language processing.
Prerequisite: either a minimum grade of 2.0 in CSS 340, or a minimum grade of
2.0 in CSS 342.
<a href="https://myplan.washington.edu/course/#/courses/CSS382">
View course details in MyPlan: CSS 382</a>
</body></html>
"""


@pytest.fixture
def scraper():
    """Provide a CatalogScraper instance."""
    return CatalogScraper(departments=["css"])


@pytest.fixture
def db_conn(tmp_path):
    """Provide an initialized in-memory-like test database."""
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    init_db(conn)
    yield conn
    conn.close()


class TestCatalogParsing:
    """Test course extraction from HTML."""

    def test_extracts_courses(self, scraper):
        """Should extract all course entries from sample HTML."""
        from bs4 import BeautifulSoup

        text = BeautifulSoup(SAMPLE_CSS_HTML, "html.parser").get_text()
        courses = scraper._extract_courses_from_text(
            text, "CSS", "css", "2026-05-18T00:00:00"
        )

        course_ids = {c["course_id"] for c in courses}
        assert "CSS 342" in course_ids
        assert "CSS 343" in course_ids
        assert "CSS 430" in course_ids
        assert "CSS 382" in course_ids

    def test_course_title_extraction(self, scraper):
        """Should extract clean course titles."""
        from bs4 import BeautifulSoup

        text = BeautifulSoup(SAMPLE_CSS_HTML, "html.parser").get_text()
        courses = scraper._extract_courses_from_text(
            text, "CSS", "css", "2026-05-18T00:00:00"
        )

        titles = {c["course_id"]: c["title"] for c in courses}
        assert "Data Structures, Algorithms, and Discrete Mathematics I" in titles.get(
            "CSS 342", ""
        )
        assert "Operating Systems" in titles.get("CSS 430", "")

    def test_credits_extraction(self, scraper):
        """Should extract credit values."""
        from bs4 import BeautifulSoup

        text = BeautifulSoup(SAMPLE_CSS_HTML, "html.parser").get_text()
        courses = scraper._extract_courses_from_text(
            text, "CSS", "css", "2026-05-18T00:00:00"
        )

        credits = {c["course_id"]: c["credits"] for c in courses}
        assert credits.get("CSS 342") == "5"

    def test_offering_pattern(self, scraper):
        """Should extract offering pattern when present."""
        from bs4 import BeautifulSoup

        text = BeautifulSoup(SAMPLE_CSS_HTML, "html.parser").get_text()
        courses = scraper._extract_courses_from_text(
            text, "CSS", "css", "2026-05-18T00:00:00"
        )

        patterns = {c["course_id"]: c.get("offering_pattern") for c in courses}
        assert patterns.get("CSS 430") == "AWSp"


class TestPrerequisiteParsing:
    """Test prerequisite extraction and structuring."""

    def test_or_clause_detection(self, scraper):
        """Should detect OR-clauses and group them."""
        desc = (
            "Prerequisite: a minimum grade of 2.8 in either CSS 133, "
            "CSS 143, CSE 143, or CSS 162; and minimum grade of 2.5 in "
            "either STMATH 125 or MATH 125."
        )
        prereqs = scraper._parse_prerequisites(desc, "CSS 342")

        # Should have two OR-groups
        groups = {}
        for p in prereqs:
            gid = p["group_id"]
            if gid not in groups:
                groups[gid] = []
            groups[gid].append(p["prereq_id"])

        # Group with CSS 133, CSS 143, CSE 143, CSS 162
        or_groups = {gid: courses for gid, courses in groups.items() if gid > 0}
        assert len(or_groups) >= 2, f"Expected at least 2 OR-groups, got {or_groups}"

    def test_concurrent_detection(self, scraper):
        """Should detect concurrent prerequisites."""
        desc = (
            "Prerequisite: CSS 301, which may be taken concurrently; "
            "and a minimum grade of 2.0 in CSS 342."
        )
        prereqs = scraper._parse_prerequisites(desc, "CSS 343")

        concurrent = [p for p in prereqs if p["type"] == "concurrent"]
        assert len(concurrent) >= 1
        assert any(p["prereq_id"] == "CSS 301" for p in concurrent)

    def test_min_grade_extraction(self, scraper):
        """Should extract minimum grade requirements."""
        desc = "Prerequisite: a minimum grade of 2.0 in CSS 343."
        prereqs = scraper._parse_prerequisites(desc, "CSS 430")

        assert len(prereqs) >= 1
        css343 = [p for p in prereqs if p["prereq_id"] == "CSS 343"]
        assert len(css343) == 1
        assert css343[0]["min_grade"] == "2.0"

    def test_no_self_reference(self, scraper):
        """Should not include the course itself as its own prerequisite."""
        desc = "Prerequisite: a minimum grade of 2.0 in CSS 342."
        prereqs = scraper._parse_prerequisites(desc, "CSS 342")
        assert all(p["prereq_id"] != "CSS 342" for p in prereqs)


class TestCatalogPersistence:
    """Test that parsed courses are correctly persisted to the database."""

    def test_persist_courses(self, scraper, db_conn):
        """Should insert courses into the database."""
        from bs4 import BeautifulSoup

        text = BeautifulSoup(SAMPLE_CSS_HTML, "html.parser").get_text()
        courses = scraper._extract_courses_from_text(
            text, "CSS", "css", "2026-05-18T00:00:00"
        )

        count = scraper._persist_courses(db_conn, courses, "css", "2026-05-18T00:00:00")

        assert count >= 4

        cur = db_conn.execute("SELECT count(*) FROM courses")
        assert cur.fetchone()[0] >= 4

        cur = db_conn.execute("SELECT * FROM courses WHERE course_id = 'CSS 343'")
        row = cur.fetchone()
        assert row is not None
        assert "Data Structures" in row["title"]

    def test_prerequisites_persisted(self, scraper, db_conn):
        """Should persist prerequisite relationships."""
        from bs4 import BeautifulSoup

        text = BeautifulSoup(SAMPLE_CSS_HTML, "html.parser").get_text()
        courses = scraper._extract_courses_from_text(
            text, "CSS", "css", "2026-05-18T00:00:00"
        )
        scraper._persist_courses(db_conn, courses, "css", "2026-05-18T00:00:00")

        cur = db_conn.execute("SELECT * FROM prerequisites WHERE course_id = 'CSS 430'")
        rows = cur.fetchall()
        prereq_ids = {row["prereq_id"] for row in rows}
        assert "CSS 343" in prereq_ids
