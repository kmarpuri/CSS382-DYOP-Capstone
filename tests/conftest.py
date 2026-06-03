"""Shared pytest fixtures for the Capstone test suite."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from capstone.db.connection import connect
from capstone.db.schema import init_db


# ── Minimal CSSE-flavored catalog fixture ───────────────────────────────

SCRAPED_AT = datetime(2026, 5, 18, tzinfo=timezone.utc).isoformat()


def _add_course(conn, cid, title, credits="5", offering="A,W,Sp", dept=None):
    conn.execute(
        """INSERT INTO courses (course_id, title, credits, description,
           offering_pattern, department, scraped_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (cid, title, credits, "", offering, dept or cid.split()[0], SCRAPED_AT),
    )


def _add_prereq(conn, course, prereq, type_="required", group_id=0):
    conn.execute(
        """INSERT INTO prerequisites (course_id, prereq_id, type, group_id)
           VALUES (?, ?, ?, ?)""",
        (course, prereq, type_, group_id),
    )


@pytest.fixture
def fixture_db(tmp_path):
    """A small CSSE-style catalog + prereq DAG for unit tests.

    Mirrors the real UWB structure:
    - 100-level: CSS 142, CSS 143, STMATH 124, STMATH 125
    - 200-level: CSS 301
    - 300-level: CSS 342 (needs 143 + 125), CSS 343 (needs 342 + 301-concurrent),
                 CSS 360 (needs 143), CSS 370 (needs 301 + 360 + 342)
    - 400-level: CSS 422 (needs 342), CSS 430 (needs 343), CSS 497 (needs 360)
    - Major requirements for CSSE
    """
    path = tmp_path / "fixture.db"
    conn = connect(path)
    init_db(conn)

    courses = [
        ("CSS 142", "Computer Programming I"),
        ("CSS 143", "Computer Programming II"),
        ("CSE 142", "Computer Programming I"),    # alt
        ("CSE 143", "Computer Programming II"),   # alt
        ("CSS 301", "Technical Writing"),
        ("CSS 342", "Data Structures I", "5", "A,W,Sp"),
        ("CSS 343", "Data Structures II", "5", "A,W,Sp"),
        ("CSS 350", "Management Principles"),
        ("CSS 360", "Software Engineering"),
        ("CSS 370", "Analysis & Design"),
        ("CSS 422", "Hardware & Computer Organization"),
        ("CSS 430", "Operating Systems"),
        ("CSS 497", "CS & SE Capstone", "5", "A,W,Sp"),
        ("STMATH 124", "Calculus I"),
        ("STMATH 125", "Calculus II"),
        ("MATH 125", "Calculus II"),               # alt
        ("B BUS 215", "Intro to Business Stats"),
        ("B WRIT 134", "Composition"),
        ("B WRIT 135", "Research Writing"),
    ]
    for c in courses:
        _add_course(conn, *c)

    # Prereqs
    _add_prereq(conn, "CSS 143", "CSS 142", "one_of", group_id=1)
    _add_prereq(conn, "CSS 143", "CSE 142", "one_of", group_id=1)
    _add_prereq(conn, "CSS 342", "CSS 143", "one_of", group_id=1)
    _add_prereq(conn, "CSS 342", "CSE 143", "one_of", group_id=1)
    _add_prereq(conn, "CSS 342", "STMATH 125", "one_of", group_id=2)
    _add_prereq(conn, "CSS 342", "MATH 125", "one_of", group_id=2)
    _add_prereq(conn, "CSS 343", "CSS 342")
    _add_prereq(conn, "CSS 343", "CSS 301", type_="concurrent")
    _add_prereq(conn, "CSS 360", "CSS 143", "one_of", group_id=1)
    _add_prereq(conn, "CSS 360", "CSE 143", "one_of", group_id=1)
    _add_prereq(conn, "CSS 370", "CSS 301")
    _add_prereq(conn, "CSS 370", "CSS 360")
    _add_prereq(conn, "CSS 370", "CSS 342")
    _add_prereq(conn, "CSS 422", "CSS 342")
    _add_prereq(conn, "CSS 430", "CSS 343")
    _add_prereq(conn, "CSS 497", "CSS 360")
    _add_prereq(conn, "STMATH 125", "STMATH 124")

    # Soft (pedagogical) prereqs — e.g., Hardware preps OS
    _add_prereq(conn, "CSS 430", "CSS 422", "recommended")
    _add_prereq(conn, "CSS 360", "CSS 350", "recommended")

    # CSSE major requirements
    csse_core = ["CSS 342", "CSS 343", "CSS 360", "CSS 370", "CSS 350",
                 "CSS 301", "CSS 422", "CSS 430"]
    for cid in csse_core:
        conn.execute(
            "INSERT INTO major_requirements (major, category, course_id) VALUES (?,?,?)",
            ("CSSE", "core", cid),
        )
    conn.execute(
        "INSERT INTO major_requirements (major, category, course_id) VALUES (?,?,?)",
        ("CSSE", "capstone", "CSS 497"),
    )
    conn.execute(
        "INSERT INTO major_requirements (major, category, course_id, group_id, notes) "
        "VALUES (?,?,?,?,?)",
        ("CSSE", "stats", "B BUS 215", 1, "pick one"),
    )

    conn.commit()
    yield conn
    conn.close()
