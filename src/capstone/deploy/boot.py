"""One-shot startup task for hosted deployments.

Runs *before* uvicorn on Railway / Fly / Render to make sure the
SQLite catalog is populated. If the DB already exists and has rows,
this is a no-op (so subsequent restarts are fast).

Usage (from Procfile / fly.toml / railway.json):

    python -m capstone.deploy.boot && uvicorn capstone.api:app ...

Environment:
    CAPSTONE_DB              path to the SQLite file (Docker volume / Fly mount)
    CAPSTONE_SKIP_SCRAPE     if "1", skip the bootstrap scrape entirely
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from capstone.config import PROJECT_ROOT, load_config
from capstone.db.connection import connect, using_turso
from capstone.db.schema import get_scrape_stats, init_db

# Make sure GROQ_API_KEY etc. are loaded from .env if present.
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


logging.basicConfig(
    level=os.environ.get("CAPSTONE_LOG_LEVEL", "INFO"),
    format="[boot] %(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _count(conn, table: str) -> int:
    """Row count for a table, or 0 if it can't be read."""
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return 0


def main() -> int:
    if os.environ.get("CAPSTONE_SKIP_SCRAPE") == "1":
        logger.info("CAPSTONE_SKIP_SCRAPE=1 — skipping bootstrap scrape.")
        return 0

    config = load_config()
    db_path = config.database.resolve_path(PROJECT_ROOT)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Database path: {db_path}")

    logger.info(
        "Storage backend: %s",
        "Turso (libSQL cloud)" if using_turso() else "local SQLite",
    )

    conn = connect(db_path)
    init_db(conn)
    stats = get_scrape_stats(conn)
    course_count = stats.get("courses", 0)
    req_count = stats.get("major_requirements", 0)
    logger.info(f"Existing catalog: {course_count} courses, {req_count} requirements")

    # Each dataset seeds independently (guarded by its own emptiness check)
    # so a redeploy is a no-op for what's already there, but newly-enabled
    # scrapes (e.g. flipping on professor ratings) still get picked up.

    # 1. Catalog + 2. major requirements for every registered major
    if course_count > 0 and req_count > 0:
        logger.info("Catalog + requirements already populated — skipping.")
    else:
        logger.info("Cold start — scraping catalog + all major requirements…")
        from capstone.scrapers.catalog import CatalogScraper
        from capstone.scrapers.programs import PROGRAM_SCRAPERS

        try:
            with CatalogScraper(
                departments=config.scraper.bothell_departments,
                rate_limit=config.scraper.rate_limit_seconds,
                user_agent=config.scraper.user_agent,
            ) as scraper:
                n = scraper.scrape(conn)
            logger.info(f"  ✓ Scraped {n} catalog rows")
        except Exception as e:
            logger.warning(f"Catalog scrape failed ({e}); continuing with empty catalog.")

        for code, cls in PROGRAM_SCRAPERS.items():
            try:
                count = cls().scrape_requirements(conn)
                logger.info(f"  ✓ {code:10}: {count} requirement rows")
            except Exception as e:
                logger.warning(f"  ✗ {code}: {e}")

    # 3. Time schedule — public UWB section offerings. This is what carries
    #    the per-section instructor names the rating badges attach to. On by
    #    default; set CAPSTONE_SCRAPE_TIMESCHEDULE=0 to skip.
    if (
        os.environ.get("CAPSTONE_SCRAPE_TIMESCHEDULE", "1") != "0"
        and _count(conn, "time_schedule") == 0
    ):
        logger.info("Scraping time schedule (section offerings + instructors)…")
        try:
            from capstone.scrapers.timeschedule import TimeScheduleScraper

            ts = TimeScheduleScraper(
                quarters=config.scraper.time_schedule_quarters,
                departments=config.scraper.bothell_departments,
                rate_limit=config.scraper.rate_limit_seconds,
                user_agent=config.scraper.user_agent,
            )
            n = ts.scrape(conn)
            logger.info(f"  ✓ Scraped {n} time-schedule sections")
        except Exception as e:
            logger.warning(
                f"Time-schedule scrape failed ({e}); instructor badges may be empty."
            )

    # 4. RateMyProfessor ratings — OPT-IN. RMP's ToS prohibits automated
    #    access, so this only runs when CAPSTONE_SCRAPE_PROFESSORS=1 is set
    #    explicitly. It's the hosted equivalent of `capstone scrape professors`.
    if (
        os.environ.get("CAPSTONE_SCRAPE_PROFESSORS") == "1"
        and _count(conn, "professor_ratings") == 0
    ):
        logger.info("CAPSTONE_SCRAPE_PROFESSORS=1 — caching RateMyProfessor ratings…")
        try:
            from capstone.scrapers.ratemyprofessor import RateMyProfessorScraper

            rmp = RateMyProfessorScraper(rate_limit=config.scraper.rate_limit_seconds)
            try:
                n = rmp.scrape(conn)
                logger.info(f"  ✓ Cached {n} professor ratings")
            finally:
                rmp.close()
        except Exception as e:
            logger.warning(
                f"Professor-ratings scrape failed ({e}); instructor badges hidden."
            )

    # On Turso the embedded replica forwards writes to the primary; a
    # final sync makes sure everything is durable in the cloud before the
    # process exits and the next reader (uvicorn) starts.
    sync = getattr(conn, "sync", None)
    if callable(sync):
        try:
            sync()
            logger.info("Synced bootstrap data to Turso primary.")
        except Exception as e:
            logger.warning(f"Turso sync after bootstrap failed: {e}")

    conn.close()
    logger.info("Bootstrap complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
