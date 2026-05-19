"""Tests for the CSSE program requirements scraper."""

import pytest

from capstone.db.connection import connect
from capstone.db.schema import init_db
from capstone.scrapers.programs.csse import CSSEProgramScraper
from capstone.scrapers.programs.stub import StubProgramScraper
from capstone.scrapers.programs import get_program_scraper


@pytest.fixture
def db_conn(tmp_path):
    """Provide an initialized test database."""
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    init_db(conn)
    yield conn
    conn.close()


class TestCSSERequirements:
    """Test CSSE program requirements population."""

    def test_scrape_requirements(self, db_conn):
        """Should insert all CSSE requirements."""
        scraper = CSSEProgramScraper()
        count = scraper.scrape_requirements(db_conn)
        assert count > 0

        # Check core courses
        cur = db_conn.execute(
            "SELECT course_id FROM major_requirements "
            "WHERE major = 'CSSE' AND category = 'core'"
        )
        core_courses = {row[0] for row in cur.fetchall()}
        assert "CSS 342" in core_courses
        assert "CSS 343" in core_courses
        assert "CSS 430" in core_courses
        assert "CSS 422" in core_courses
        assert "CSS 360" in core_courses
        assert "CSS 370" in core_courses
        assert "CSS 350" in core_courses
        assert "CSS 301" in core_courses

    def test_capstone_requirement(self, db_conn):
        """Should include the capstone course."""
        scraper = CSSEProgramScraper()
        scraper.scrape_requirements(db_conn)

        cur = db_conn.execute(
            "SELECT course_id FROM major_requirements "
            "WHERE major = 'CSSE' AND category = 'capstone'"
        )
        capstone = {row[0] for row in cur.fetchall()}
        assert "CSS 497" in capstone

    def test_stats_requirement(self, db_conn):
        """Should include statistics options as a group."""
        scraper = CSSEProgramScraper()
        scraper.scrape_requirements(db_conn)

        cur = db_conn.execute(
            "SELECT course_id, group_id FROM major_requirements "
            "WHERE major = 'CSSE' AND category = 'stats'"
        )
        stats = cur.fetchall()
        assert len(stats) >= 2
        # All should share the same group_id
        group_ids = {row[1] for row in stats}
        assert len(group_ids) == 1  # single group

    def test_math_prerequisites(self, db_conn):
        """Should include all math prerequisites."""
        scraper = CSSEProgramScraper()
        scraper.scrape_requirements(db_conn)

        cur = db_conn.execute(
            "SELECT course_id FROM major_requirements "
            "WHERE major = 'CSSE' AND category = 'math'"
        )
        math = {row[0] for row in cur.fetchall()}
        assert "STMATH 124" in math
        assert "STMATH 125" in math
        assert "STMATH 208" in math

    def test_elective_requirement(self, db_conn):
        """Should include the CSS elective requirement marker."""
        scraper = CSSEProgramScraper()
        scraper.scrape_requirements(db_conn)

        cur = db_conn.execute(
            "SELECT course_id, required_count, notes FROM major_requirements "
            "WHERE major = 'CSSE' AND category = 'elective'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "CSS 200+"
        assert row[1] == 25
        assert "25 credits" in row[2]

    def test_idempotent(self, db_conn):
        """Running scrape_requirements twice should not duplicate rows."""
        scraper = CSSEProgramScraper()
        scraper.scrape_requirements(db_conn)
        count1 = db_conn.execute(
            "SELECT count(*) FROM major_requirements WHERE major = 'CSSE'"
        ).fetchone()[0]

        scraper.scrape_requirements(db_conn)
        count2 = db_conn.execute(
            "SELECT count(*) FROM major_requirements WHERE major = 'CSSE'"
        ).fetchone()[0]

        assert count1 == count2


class TestStubScraper:
    """Test that unimplemented majors fail cleanly."""

    def test_stub_raises(self, db_conn):
        """StubProgramScraper should raise NotImplementedError."""
        scraper = StubProgramScraper("MATH")
        with pytest.raises(NotImplementedError, match="MATH"):
            scraper.scrape_requirements(db_conn)

    def test_factory_returns_csse(self):
        """get_program_scraper should return CSSEProgramScraper for CSSE."""
        scraper = get_program_scraper("CSSE")
        assert isinstance(scraper, CSSEProgramScraper)

    def test_factory_returns_stub(self):
        """get_program_scraper should return StubProgramScraper for unknown majors."""
        scraper = get_program_scraper("BIOLOGY")
        assert isinstance(scraper, StubProgramScraper)
