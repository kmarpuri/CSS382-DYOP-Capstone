"""SQLite connection management for the Capstone application.

Provides a thin wrapper that ensures the database file exists and
WAL mode is enabled for better concurrent read performance.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


def get_db_path(config_path: str, project_root: Path) -> Path:
    """Resolve the database path from config."""
    if config_path == "project":
        return project_root / "capstone.db"
    return Path(config_path).expanduser()


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection to the SQLite database.

    Creates the parent directories if they don't exist.
    Enables WAL mode and foreign keys.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_connection(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a connection and commits on success."""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
