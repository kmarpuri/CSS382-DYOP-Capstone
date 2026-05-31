"""SQLite schema definition and migration for the Capstone application.

Tables
------
- courses          — course catalog entries
- prerequisites    — prerequisite relationships (DAG edges)
- major_requirements — per-major required/elective courses
- time_schedule    — concrete section offerings per quarter
- scrape_metadata  — timestamps for cache-staleness checks
"""

from __future__ import annotations

import sqlite3

# ── Schema DDL ──────────────────────────────────────────────────────────────

SCHEMA_VERSION = 1

CREATE_TABLES = """
-- Course catalog
CREATE TABLE IF NOT EXISTS courses (
    course_id       TEXT PRIMARY KEY,   -- e.g., "CSS 343"
    title           TEXT NOT NULL,
    credits         TEXT,               -- TEXT to handle "1-5" ranges
    description     TEXT,
    offering_pattern TEXT,              -- e.g., "AWSp", "A,Sp"
    last_offered    TEXT,               -- ISO date or quarter string
    department      TEXT,               -- e.g., "CSS", "STMATH"
    campus          TEXT DEFAULT 'Bothell',
    scraped_at      TEXT NOT NULL       -- ISO timestamp
);

-- Prerequisite relationships (edges in the DAG)
CREATE TABLE IF NOT EXISTS prerequisites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   TEXT NOT NULL,          -- the course that HAS the prereq
    prereq_id   TEXT NOT NULL,          -- the prerequisite course
    type        TEXT NOT NULL DEFAULT 'required',
                                        -- "required", "concurrent", "recommended", "one_of"
    group_id    INTEGER DEFAULT 0,      -- groups OR-clauses together
    min_grade   TEXT,                   -- e.g., "2.0", "2.8"
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);
CREATE INDEX IF NOT EXISTS idx_prereq_course ON prerequisites(course_id);
CREATE INDEX IF NOT EXISTS idx_prereq_prereq ON prerequisites(prereq_id);

-- Major / program requirements
CREATE TABLE IF NOT EXISTS major_requirements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    major           TEXT NOT NULL,       -- e.g., "CSSE"
    category        TEXT NOT NULL,       -- "core", "elective", "math", "stats",
                                         -- "writing", "gen_ed", "capstone"
    course_id       TEXT NOT NULL,       -- specific course or "CSS 200+"
    required_count  INTEGER DEFAULT 1,   -- how many from this group are needed
    group_id        INTEGER DEFAULT 0,   -- for "pick one of" groups
    notes           TEXT                 -- freeform notes
);
CREATE INDEX IF NOT EXISTS idx_major_req ON major_requirements(major, category);

-- Time schedule (concrete section offerings)
CREATE TABLE IF NOT EXISTS time_schedule (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   TEXT NOT NULL,
    section_id  TEXT,                    -- e.g., "A", "B", "AA"
    sln         TEXT,                    -- Schedule Line Number
    quarter     TEXT NOT NULL,           -- "SPR", "SUM", "AUT", "WIN"
    year        INTEGER NOT NULL,
    credits     TEXT,
    days        TEXT,                    -- e.g., "MW", "TTh"
    time_start  TEXT,                    -- e.g., "1100"
    time_end    TEXT,                    -- e.g., "100"
    status      TEXT,                    -- "Open", "Closed"
    enrolled    INTEGER,
    enroll_limit INTEGER,
    instructor  TEXT,
    building    TEXT,
    room        TEXT,
    notes       TEXT,
    restrictions TEXT,                   -- e.g., "Restr", "IS"
    fee         TEXT,
    grading     TEXT,                    -- e.g., "CR/NC"
    scraped_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ts_course ON time_schedule(course_id);
CREATE INDEX IF NOT EXISTS idx_ts_quarter ON time_schedule(quarter, year);

-- Professor ratings (cache of public RateMyProfessor data, opt-in)
CREATE TABLE IF NOT EXISTS professor_ratings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,        -- e.g., "John Smith"
    name_normalized TEXT NOT NULL,        -- "JOHN SMITH" for case/order-insensitive match
    school_id       TEXT,                 -- RMP school ID
    school_name     TEXT,                 -- "University of Washington Bothell Campus"
    department      TEXT,
    avg_rating      REAL,                 -- 0.0–5.0
    avg_difficulty  REAL,                 -- 0.0–5.0
    num_ratings     INTEGER,
    would_take_again_pct REAL,            -- 0.0–100.0, NULL if unknown
    rmp_legacy_id   TEXT,                 -- legacy numeric ID, used for the public profile URL
    last_scraped    TEXT NOT NULL,
    UNIQUE(name_normalized, school_id)
);
CREATE INDEX IF NOT EXISTS idx_prof_name ON professor_ratings(name_normalized);

-- Scrape metadata for cache management
CREATE TABLE IF NOT EXISTS scrape_metadata (
    source      TEXT PRIMARY KEY,        -- e.g., "catalog:css", "timeschedule:AUT2026:css"
    scraped_at  TEXT NOT NULL,           -- ISO timestamp
    record_count INTEGER DEFAULT 0
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist and set the schema version."""
    conn.executescript(CREATE_TABLES)

    # Check / set schema version
    cur = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
    row = cur.fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()


def reset_db(conn: sqlite3.Connection) -> None:
    """Drop all tables and recreate them.  Used for --refresh."""
    tables = [
        "time_schedule",
        "prerequisites",
        "major_requirements",
        "professor_ratings",
        "courses",
        "scrape_metadata",
        "schema_version",
    ]
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    init_db(conn)


def get_scrape_stats(conn: sqlite3.Connection) -> dict[str, dict]:
    """Return a summary of what's been scraped and when."""
    cur = conn.execute("SELECT source, scraped_at, record_count FROM scrape_metadata")
    return {
        row["source"]: {
            "scraped_at": row["scraped_at"],
            "record_count": row["record_count"],
        }
        for row in cur.fetchall()
    }
