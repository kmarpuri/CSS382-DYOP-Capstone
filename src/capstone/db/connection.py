"""Database connection management for the Capstone application.

Two backends, one interface:

  * **Local / tests (default)** — Python's stdlib ``sqlite3`` against a
    file on disk. WAL mode + ``sqlite3.Row`` as before. Nothing changes
    for development or the test suite.

  * **Hosted (Turso / libSQL)** — when ``CAPSTONE_TURSO_URL`` and
    ``CAPSTONE_TURSO_AUTH_TOKEN`` are set, we open an *embedded replica*:
    a local SQLite file that libSQL keeps in sync with a managed Turso
    database in the cloud. Reads are served locally (fast); writes are
    forwarded to the primary. This is what the deployed website runs on.

The libSQL driver returns plain tuples rather than ``sqlite3.Row``
objects, so the rest of the codebase (which relies on ``row["col"]`` and
``dict(row)``) would break on a naive swap. The thin wrappers below make
a libSQL connection quack exactly like a ``sqlite3`` one — same row
access, same ``dict(row)`` semantics — so no call site has to change.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable, Sequence


def get_db_path(config_path: str, project_root: Path) -> Path:
    """Resolve the database path from config."""
    if config_path == "project":
        return project_root / "capstone.db"
    return Path(config_path).expanduser()


# ── Turso / libSQL configuration ─────────────────────────────────────────


def _turso_config() -> tuple[str, str] | None:
    """Return ``(url, auth_token)`` if Turso env vars are set, else None."""
    url = os.environ.get("CAPSTONE_TURSO_URL", "").strip()
    token = os.environ.get("CAPSTONE_TURSO_AUTH_TOKEN", "").strip()
    if url and token:
        return url, token
    return None


def using_turso() -> bool:
    """True when the hosted libSQL backend is configured."""
    return _turso_config() is not None


# ── sqlite3.Row-compatible wrappers for libSQL ───────────────────────────
#
# libSQL cursors yield plain tuples plus a ``description``. We rebuild a
# Row object that matches sqlite3.Row's dual nature:
#   * iterating a row yields its *values*   (like sqlite3.Row)
#   * ``row["col"]`` / ``row[0]`` both work
#   * ``dict(row)`` yields ``{col: value}`` — Python detects ``.keys()``
#     and builds the mapping from it, exactly as it does for sqlite3.Row.


class _LibsqlRow:
    __slots__ = ("_cols", "_vals")

    def __init__(self, cols: tuple[str, ...], vals: Sequence[Any]):
        self._cols = cols
        self._vals = tuple(vals)

    def keys(self) -> list[str]:
        return list(self._cols)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, (int, slice)):
            return self._vals[key]
        return self._vals[self._cols.index(key)]

    def __iter__(self):
        return iter(self._vals)

    def __len__(self) -> int:
        return len(self._vals)

    def __contains__(self, key: Any) -> bool:
        return key in self._cols

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, _LibsqlRow):
            return self._cols == other._cols and self._vals == other._vals
        return NotImplemented

    def __repr__(self) -> str:
        return f"Row({dict(zip(self._cols, self._vals))!r})"


def _columns(cursor: Any) -> tuple[str, ...]:
    desc = cursor.description
    return tuple(c[0] for c in desc) if desc else ()


class _LibsqlCursor:
    """Wraps a libSQL cursor so fetches return ``_LibsqlRow`` objects."""

    def __init__(self, cursor: Any):
        self._cur = cursor

    @property
    def description(self):
        return self._cur.description

    @property
    def lastrowid(self):
        return getattr(self._cur, "lastrowid", None)

    @property
    def rowcount(self):
        return getattr(self._cur, "rowcount", -1)

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return _LibsqlRow(_columns(self._cur), row)

    def fetchall(self):
        cols = _columns(self._cur)
        return [_LibsqlRow(cols, r) for r in self._cur.fetchall()]

    def fetchmany(self, size: int | None = None):
        cols = _columns(self._cur)
        rows = self._cur.fetchmany(size) if size is not None else self._cur.fetchmany()
        return [_LibsqlRow(cols, r) for r in rows]

    def __iter__(self):
        cols = _columns(self._cur)
        for r in self._cur:
            yield _LibsqlRow(cols, r)

    def execute(self, sql: str, params: Sequence[Any] | None = None):
        if params is None:
            self._cur.execute(sql)
        else:
            self._cur.execute(sql, params)
        return self

    def executemany(self, sql: str, seq: Iterable[Sequence[Any]]):
        self._cur.executemany(sql, seq)
        return self

    def close(self):
        self._cur.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cur, name)


class _LibsqlConnection:
    """Wraps a libSQL connection to mirror the ``sqlite3.Connection`` API
    the rest of the app uses (``execute``, ``executemany``,
    ``executescript``, ``commit``, ``rollback``, ``close``, ``cursor``)."""

    def __init__(self, raw: Any):
        self._raw = raw
        # Present for code that introspects/sets it; libSQL ignores it but
        # our wrapper rows already behave like sqlite3.Row.
        self.row_factory = None

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> _LibsqlCursor:
        cur = self._raw.execute(sql) if params is None else self._raw.execute(sql, params)
        return _LibsqlCursor(cur)

    def executemany(self, sql: str, seq: Iterable[Sequence[Any]]) -> _LibsqlCursor:
        cur = self._raw.executemany(sql, seq)
        return _LibsqlCursor(cur)

    def executescript(self, sql: str) -> Any:
        return self._raw.executescript(sql)

    def cursor(self) -> _LibsqlCursor:
        return _LibsqlCursor(self._raw.cursor())

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()

    def sync(self) -> None:
        """Pull the latest primary state into the embedded replica."""
        sync = getattr(self._raw, "sync", None)
        if callable(sync):
            sync()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._raw, name)


def _connect_turso(db_path: Path, url: str, token: str) -> _LibsqlConnection:
    """Open an embedded-replica connection backed by Turso."""
    import libsql  # imported lazily so local/test runs never need the driver

    db_path.parent.mkdir(parents=True, exist_ok=True)
    raw = libsql.connect(str(db_path), sync_url=url, auth_token=token)
    conn = _LibsqlConnection(raw)
    # Best-effort initial pull so reads see existing cloud data immediately.
    try:
        conn.sync()
    except Exception:
        pass
    try:
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return conn


# ── Public entry points ──────────────────────────────────────────────────


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a database connection.

    Returns a stdlib ``sqlite3`` connection locally, or a libSQL-backed
    connection (duck-compatible with sqlite3) when Turso is configured.
    """
    turso = _turso_config()
    if turso is not None:
        return _connect_turso(db_path, *turso)  # type: ignore[return-value]

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
