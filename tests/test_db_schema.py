"""Tests for the database schema and connection management."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from capstone.db.connection import connect, get_connection
from capstone.db.schema import get_scrape_stats, init_db, reset_db


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db_conn(db_path):
    """Provide an initialized database connection."""
    conn = connect(db_path)
    init_db(conn)
    yield conn
    conn.close()


class TestSchema:
    """Test database schema creation and management."""

    def test_init_creates_tables(self, db_conn):
        """init_db should create all required tables."""
        cur = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cur.fetchall()}
        expected = {
            "courses",
            "prerequisites",
            "major_requirements",
            "time_schedule",
            "scrape_metadata",
            "schema_version",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_schema_version_set(self, db_conn):
        """Schema version should be recorded."""
        cur = db_conn.execute("SELECT version FROM schema_version")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1

    def test_init_is_idempotent(self, db_conn):
        """Calling init_db multiple times should not fail."""
        init_db(db_conn)  # second call
        init_db(db_conn)  # third call
        cur = db_conn.execute("SELECT count(*) FROM schema_version")
        assert cur.fetchone()[0] == 1

    def test_reset_and_reinit(self, db_conn):
        """reset_db should drop all tables and init_db recreates them."""
        # Insert some data
        db_conn.execute(
            "INSERT INTO courses (course_id, title, credits, scraped_at) "
            "VALUES ('TEST 100', 'Test Course', '5', '2026-01-01')"
        )
        db_conn.commit()

        reset_db(db_conn)

        cur = db_conn.execute("SELECT count(*) FROM courses")
        assert cur.fetchone()[0] == 0

    def test_course_insert(self, db_conn):
        """Should be able to insert a course."""
        db_conn.execute(
            """
            INSERT INTO courses (course_id, title, credits, description,
                                 department, scraped_at)
            VALUES ('CSS 342', 'Data Structures I', '5',
                    'Integrating mathematical principles...',
                    'CSS', '2026-05-18T00:00:00')
            """
        )
        db_conn.commit()

        cur = db_conn.execute("SELECT * FROM courses WHERE course_id = 'CSS 342'")
        row = cur.fetchone()
        assert row is not None
        assert row["title"] == "Data Structures I"
        assert row["credits"] == "5"

    def test_prerequisite_insert(self, db_conn):
        """Should be able to insert prerequisites."""
        # Insert courses first
        db_conn.execute(
            "INSERT INTO courses (course_id, title, credits, scraped_at) "
            "VALUES ('CSS 343', 'Data Structures II', '5', '2026-01-01')"
        )
        db_conn.execute(
            "INSERT INTO courses (course_id, title, credits, scraped_at) "
            "VALUES ('CSS 342', 'Data Structures I', '5', '2026-01-01')"
        )

        db_conn.execute(
            """
            INSERT INTO prerequisites (course_id, prereq_id, type, group_id, min_grade)
            VALUES ('CSS 343', 'CSS 342', 'required', 0, '2.0')
            """
        )
        db_conn.commit()

        cur = db_conn.execute(
            "SELECT * FROM prerequisites WHERE course_id = 'CSS 343'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row["prereq_id"] == "CSS 342"
        assert row["min_grade"] == "2.0"

    def test_or_clause_prerequisites(self, db_conn):
        """Should be able to model OR-clause prerequisites with group_id."""
        db_conn.execute(
            "INSERT INTO courses (course_id, title, credits, scraped_at) "
            "VALUES ('CSS 342', 'Data Structures I', '5', '2026-01-01')"
        )

        # CSS 342 requires one of: CSS 133, CSS 143, CSE 143, CSS 162
        for prereq_id in ["CSS 133", "CSS 143", "CSE 143", "CSS 162"]:
            db_conn.execute(
                """
                INSERT INTO prerequisites (course_id, prereq_id, type, group_id, min_grade)
                VALUES ('CSS 342', ?, 'one_of', 1, '2.8')
                """,
                (prereq_id,),
            )
        db_conn.commit()

        cur = db_conn.execute(
            "SELECT * FROM prerequisites WHERE course_id = 'CSS 342' AND group_id = 1"
        )
        rows = cur.fetchall()
        assert len(rows) == 4
        assert all(row["type"] == "one_of" for row in rows)

    def test_major_requirements(self, db_conn):
        """Should be able to insert and query major requirements."""
        db_conn.execute(
            """
            INSERT INTO major_requirements (major, category, course_id, required_count)
            VALUES ('CSSE', 'core', 'CSS 342', 1)
            """
        )
        db_conn.commit()

        cur = db_conn.execute(
            "SELECT * FROM major_requirements WHERE major = 'CSSE' AND category = 'core'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row["course_id"] == "CSS 342"


class TestConnection:
    """Test connection management."""

    def test_context_manager_commits(self, db_path):
        """get_connection should commit on success."""
        with get_connection(db_path) as conn:
            init_db(conn)
            conn.execute(
                "INSERT INTO courses (course_id, title, credits, scraped_at) "
                "VALUES ('TEST 100', 'Test', '5', '2026-01-01')"
            )

        # Verify data persisted
        conn2 = connect(db_path)
        cur = conn2.execute("SELECT count(*) FROM courses")
        assert cur.fetchone()[0] == 1
        conn2.close()

    def test_wal_mode_enabled(self, db_path):
        """WAL mode should be enabled for better concurrency."""
        conn = connect(db_path)
        cur = conn.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        assert mode.lower() == "wal"
        conn.close()


class TestScrapeStats:
    """Test scrape metadata tracking."""

    def test_empty_stats(self, db_conn):
        """get_scrape_stats should return empty dict for fresh DB."""
        stats = get_scrape_stats(db_conn)
        assert stats == {}

    def test_stats_after_insert(self, db_conn):
        """get_scrape_stats should return data after metadata insert."""
        db_conn.execute(
            """
            INSERT INTO scrape_metadata (source, scraped_at, record_count)
            VALUES ('catalog:css', '2026-05-18T00:00:00', 42)
            """
        )
        db_conn.commit()

        stats = get_scrape_stats(db_conn)
        assert "catalog:css" in stats
        assert stats["catalog:css"]["record_count"] == 42
