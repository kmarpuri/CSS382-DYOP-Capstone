"""CLI commands for the Capstone application.

Usage:
    capstone scrape refresh            # Scrape catalog + time schedule + CSSE requirements
    capstone scrape status             # Show last scrape timestamps and counts
    capstone parse-transcript FILE     # Parse a UW transcript PDF to JSON
    capstone recommend TRANSCRIPT.json # Rule-based course recommendations
    capstone serve                     # Run the FastAPI web UI
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from capstone.config import PROJECT_ROOT, load_config
from capstone.db.connection import get_connection
from capstone.db.schema import get_scrape_stats, init_db, reset_db

console = Console()


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging with rich output."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """Capstone — UW Bothell Course Recommendation Application."""
    _setup_logging(verbose)


@cli.group()
def scrape() -> None:
    """Scrape UW Bothell course data."""
    pass


@scrape.command("refresh")
@click.option(
    "--departments",
    "-d",
    multiple=True,
    help="Only scrape these departments (default: all from config)",
)
@click.option(
    "--no-timeschedule",
    is_flag=True,
    help="Skip time schedule scraping",
)
@click.option(
    "--no-requirements",
    is_flag=True,
    help="Skip CSSE requirements population",
)
@click.option(
    "--reset",
    is_flag=True,
    help="Drop and recreate all tables before scraping",
)
def scrape_refresh(
    departments: tuple[str, ...],
    no_timeschedule: bool,
    no_requirements: bool,
    reset: bool,
) -> None:
    """Scrape the UW Bothell course catalog, time schedule, and CSSE requirements."""
    config = load_config()
    db_path = config.database.resolve_path(PROJECT_ROOT)

    console.print(f"\n[bold blue]Capstone Scraper[/bold blue]")
    console.print(f"Database: {db_path}")

    with get_connection(db_path) as conn:
        if reset:
            console.print("[yellow]Resetting database...[/yellow]")
            reset_db(conn)
        else:
            init_db(conn)

        # ── 1. Course Catalog ──────────────────────────────────────
        console.print("\n[bold]📚 Scraping Course Catalog...[/bold]")

        from capstone.scrapers.catalog import CatalogScraper

        dept_list = list(departments) if departments else config.scraper.bothell_departments

        with CatalogScraper(
            departments=dept_list,
            rate_limit=config.scraper.rate_limit_seconds,
            user_agent=config.scraper.user_agent,
        ) as catalog_scraper:
            try:
                catalog_count = catalog_scraper.scrape(conn)
                console.print(
                    f"[green]✓ Scraped {catalog_count} courses "
                    f"across {len(dept_list)} departments[/green]"
                )
            except Exception as e:
                console.print(f"[red]✗ Catalog scrape failed: {e}[/red]")
                logging.exception("Catalog scrape error")
                catalog_count = 0

        # ── 2. Time Schedule ──────────────────────────────────────
        if not no_timeschedule:
            console.print("\n[bold]📅 Scraping Time Schedule...[/bold]")

            from capstone.scrapers.timeschedule import TimeScheduleScraper

            with TimeScheduleScraper(
                quarters=config.scraper.time_schedule_quarters,
                departments=dept_list,
                rate_limit=config.scraper.rate_limit_seconds,
                user_agent=config.scraper.user_agent,
            ) as ts_scraper:
                try:
                    ts_count = ts_scraper.scrape(conn)
                    console.print(
                        f"[green]✓ Scraped {ts_count} sections "
                        f"for {', '.join(config.scraper.time_schedule_quarters)}[/green]"
                    )
                except Exception as e:
                    console.print(f"[red]✗ Time schedule scrape failed: {e}[/red]")
                    logging.exception("Time schedule scrape error")
                    ts_count = 0
        else:
            ts_count = 0
            console.print("[dim]Skipping time schedule (--no-timeschedule)[/dim]")

        # ── 3. CSSE Requirements ──────────────────────────────────
        if not no_requirements:
            console.print("\n[bold]🎓 Populating CSSE Requirements...[/bold]")

            from capstone.scrapers.programs import get_program_scraper

            try:
                csse_scraper = get_program_scraper("CSSE")
                req_count = csse_scraper.scrape_requirements(conn)
                console.print(
                    f"[green]✓ Inserted {req_count} CSSE requirements[/green]"
                )
            except Exception as e:
                console.print(f"[red]✗ CSSE requirements failed: {e}[/red]")
                logging.exception("CSSE requirements error")
                req_count = 0
        else:
            req_count = 0
            console.print("[dim]Skipping requirements (--no-requirements)[/dim]")

        # ── Summary ───────────────────────────────────────────────
        console.print("\n[bold green]═══ Scrape Complete ═══[/bold green]")

        # Show DB stats
        cur = conn.execute("SELECT count(*) FROM courses")
        total_courses = cur.fetchone()[0]
        cur = conn.execute("SELECT count(*) FROM prerequisites")
        total_prereqs = cur.fetchone()[0]
        cur = conn.execute("SELECT count(*) FROM time_schedule")
        total_sections = cur.fetchone()[0]
        cur = conn.execute("SELECT count(*) FROM major_requirements")
        total_reqs = cur.fetchone()[0]

        table = Table(title="Database Summary")
        table.add_column("Table", style="cyan")
        table.add_column("Records", justify="right", style="green")
        table.add_row("Courses", str(total_courses))
        table.add_row("Prerequisites", str(total_prereqs))
        table.add_row("Time Schedule Sections", str(total_sections))
        table.add_row("Major Requirements", str(total_reqs))
        console.print(table)


@scrape.command("status")
def scrape_status() -> None:
    """Show the current state of scraped data."""
    config = load_config()
    db_path = config.database.resolve_path(PROJECT_ROOT)

    if not db_path.exists():
        console.print("[yellow]No database found. Run 'capstone scrape refresh' first.[/yellow]")
        return

    with get_connection(db_path) as conn:
        init_db(conn)
        stats = get_scrape_stats(conn)

        if not stats:
            console.print("[yellow]No scrape data found. Run 'capstone scrape refresh' first.[/yellow]")
            return

        table = Table(title="Scrape Status")
        table.add_column("Source", style="cyan")
        table.add_column("Last Scraped", style="green")
        table.add_column("Records", justify="right")

        for source, info in sorted(stats.items()):
            table.add_row(
                source,
                info["scraped_at"][:19],
                str(info["record_count"]),
            )

        console.print(table)

        # Overall counts
        cur = conn.execute("SELECT count(*) FROM courses")
        console.print(f"\nTotal courses in database: [bold]{cur.fetchone()[0]}[/bold]")
        cur = conn.execute("SELECT count(*) FROM prerequisites")
        console.print(f"Total prerequisite links: [bold]{cur.fetchone()[0]}[/bold]")
        cur = conn.execute("SELECT count(*) FROM time_schedule")
        console.print(f"Total scheduled sections: [bold]{cur.fetchone()[0]}[/bold]")


@cli.command("parse-transcript")
@click.argument("pdf_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path),
              help="Write JSON to this path (default: stdout)")
@click.option("--debug", is_flag=True, help="Dump intermediate parser state on failures")
def parse_transcript_cmd(pdf_path: Path, output: Path | None, debug: bool) -> None:
    """Parse a UW transcript PDF and emit structured JSON."""
    from capstone.transcript import parse_transcript

    try:
        transcript = parse_transcript(pdf_path, debug=debug)
    except Exception as e:
        console.print(f"[red]Failed to parse transcript:[/red] {e}")
        if debug:
            logging.exception("Transcript parse error")
        sys.exit(1)

    payload = transcript.model_dump(mode="json")
    text = json.dumps(payload, indent=2, default=str)

    if output:
        output.write_text(text)
        console.print(f"[green]✓ Wrote transcript JSON to {output}[/green]")
    else:
        click.echo(text)

    summary = (
        f"Parsed {len(transcript.completed)} completed courses, "
        f"{len(transcript.in_progress)} in-progress, "
        f"{len(transcript.transfer_credits)} transfer credits."
    )
    click.echo(summary, err=True)


@cli.command("recommend")
@click.argument("transcript_json", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--load", "credit_load", type=int, default=None,
              help="Target credit load (default: from config)")
@click.option("--top", "top_n", type=int, default=10, help="Show top-N ranked courses")
@click.option("--quarter", default=None, help="Target quarter (e.g., AUT2026)")
@click.option("--no-llm", is_flag=True, help="Skip LLM reasoning, return rule-based output only")
@click.option("--major", default=None, help="Override the major declared on the transcript")
def recommend_cmd(
    transcript_json: Path,
    credit_load: int | None,
    top_n: int,
    quarter: str | None,
    no_llm: bool,
    major: str | None,
) -> None:
    """Generate ranked course recommendations from a parsed transcript."""
    from capstone.transcript.models import Transcript
    from capstone.recommender import Recommender

    config = load_config()
    db_path = config.database.resolve_path(PROJECT_ROOT)

    if not db_path.exists():
        console.print("[red]No course DB. Run 'capstone scrape refresh' first.[/red]")
        sys.exit(1)

    transcript = Transcript.model_validate_json(transcript_json.read_text())
    if major:
        transcript.major = major

    if credit_load is None:
        credit_load = config.credit_limits.default

    # First-run check: if the user wants LLM reasoning, make sure Ollama
    # + a model exist before we kick off the pipeline. Skipped on --no-llm.
    if not no_llm:
        _maybe_run_first_run(console)

    with get_connection(db_path) as conn:
        recommender = Recommender(conn, config)
        result = recommender.recommend(
            transcript=transcript,
            target_quarter=quarter,
            credit_load=credit_load,
            top_n=top_n,
            use_llm=not no_llm,
        )

    # Render
    table = Table(title=f"Top {top_n} Recommendations for {transcript.major or 'student'}")
    table.add_column("Rank", justify="right")
    table.add_column("Course", style="cyan")
    table.add_column("Title")
    table.add_column("Cr", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Fits", justify="center")
    table.add_column("Reasoning", overflow="fold")

    for r in result.recommendations[:top_n]:
        table.add_row(
            str(r.rank),
            r.course_id,
            r.title or "",
            str(r.credit_hours),
            f"{r.score:.2f}",
            "✓" if r.fits_load else "",
            (r.reasoning or "")[:80],
        )
    console.print(table)

    console.print(
        f"\n[bold]Plan total: {result.total_credits} credits "
        f"(target {credit_load} ±2)[/bold]"
    )
    if result.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in result.warnings:
            console.print(f"  • {w}")


@cli.command("setup")
@click.option("--yes", "non_interactive", is_flag=True,
              help="Don't prompt for confirmation; accept all install steps.")
@click.option("--model", default=None,
              help="Override the recommended model to pull.")
def setup_cmd(non_interactive: bool, model: str | None) -> None:
    """One-time setup: install Ollama (with consent) and pull the LLM model."""
    from capstone.firstrun import run_first_run_setup

    ok = run_first_run_setup(
        ask=not non_interactive,
        auto_pull=True,
        console=console,
        model=model,
    )
    sys.exit(0 if ok else 1)


@cli.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True, type=int)
@click.option("--reload", is_flag=True, help="Enable auto-reload (dev only)")
def serve_cmd(host: str, port: int, reload: bool) -> None:
    """Run the FastAPI web server (Phase 4 UI)."""
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]uvicorn is not installed.[/red] "
            "Install with: pip install 'capstone[ui]'"
        )
        sys.exit(1)

    _maybe_run_first_run(console)

    console.print(f"[green]Serving Capstone UI at http://{host}:{port}/[/green]")
    uvicorn.run("capstone.api:app", host=host, port=port, reload=reload)


def _maybe_run_first_run(console_) -> None:
    """If this is the user's first LLM-using run, walk through setup."""
    try:
        from capstone.firstrun import is_first_run, run_first_run_setup
    except Exception as e:
        logging.debug(f"firstrun module unavailable: {e}")
        return

    if not is_first_run():
        return

    console_.print(
        "[bold magenta]First-time LLM setup needed.[/bold magenta] "
        "Capstone runs language models locally via Ollama."
    )
    try:
        run_first_run_setup(ask=True, auto_pull=True, console=console_)
    except KeyboardInterrupt:
        console_.print("\n[yellow]Setup aborted — continuing without LLM.[/yellow]")


if __name__ == "__main__":
    cli()
