# Capstone — Architecture

## 1. Goals

Build a desktop course-recommendation app for UW Bothell undergraduates that:

1. Runs **fully offline** after a one-time scrape (privacy-first).
2. Reasons deterministically over a prereq DAG **first**, then layers an LLM on top for natural-language explanation and multi-quarter foresight.
3. **Validates every LLM output** against the SQLite catalog — local reasoning models hallucinate course codes constantly, so defense in depth is non-negotiable.
4. Is **extensible to other UW Bothell majors** without refactoring (Phase 5).

## 2. Four-phase build

| Phase | Deliverable | Independent runnable? |
|-------|-------------|-----------------------|
| 1 | Catalog + time-schedule + CSSE program scrapers → SQLite | `capstone scrape refresh` |
| 2 | Transcript PDF parser → `Transcript` Pydantic model | `capstone parse-transcript FILE.pdf` |
| 3 | Prereq DAG + deterministic ranker + fill-to-N planner | `capstone recommend TRANSCRIPT.json --no-llm` |
| 4 | Ollama-backed reasoner + FastAPI + bundled UI | `capstone serve` |
| 5 | Additional major scrapers — Math, Biology, Business, IMD, CE, Applied Computing | parametrized test suite over the full registry |

Each phase is independently runnable so the previous phases stay verifiable as you build on top of them.

## 3. Data flow

```
        ┌──────────────────────────────────────────────────────────┐
        │                       USER MACHINE                       │
        │                                                          │
   PDF ─┤→ TranscriptParser ──→ Transcript (Pydantic)              │
        │                              │                           │
        │                              ▼                           │
        │             ┌──────────────────────────────┐             │
        │             │  Recommender                 │             │
        │             │  1. Ranker (deterministic)   │             │
        │             │  2. LLMReasoner (optional)   │             │
        │             │  3. fill-to-N planner        │             │
        │             └────────────┬─────────────────┘             │
        │                          ▼                               │
   UI ──┤  RecommendationResult ──→ JSON over HTTP (FastAPI)       │
        │                          ▲                               │
        │                          │                               │
        │   SQLite catalog ────────┘                               │
        │       ▲                                                  │
        │       │  one-time scrape                                 │
        │       │                                                  │
        │   CatalogScraper, TimeScheduleScraper, CSSEProgramScraper│
        └───────┬──────────────────────────────────────────────────┘
                │ HTTP (read-only, rate-limited, robots.txt-aware)
                ▼
    https://www.washington.edu/students/crscatb/*.html
    https://www.washington.edu/students/timeschd/pub/B/*/*.html
    https://www.uwb.edu/stem/.../bscsse/curriculum
```

## 4. Module map

```
src/capstone/
├── cli.py              # click commands: scrape / parse-transcript / recommend / serve
├── config.py           # YAML → typed dataclasses
├── api.py              # FastAPI app
├── db/
│   ├── schema.py       # SQLite DDL + migration
│   └── connection.py   # WAL-mode wrapper
├── scrapers/
│   ├── base.py         # BaseScraper (rate-limit + robots.txt) + ProgramScraper ABC
│   ├── catalog.py      # public catalog → courses + prerequisites tables
│   ├── timeschedule.py # public time schedule → time_schedule table
│   └── programs/
│       ├── csse.py     # CSSE major requirements (hardcoded, verified May 2026)
│       └── stub.py     # NotImplementedError for unimplemented majors
├── transcript/
│   ├── models.py       # Transcript, CompletedCourse, InProgressCourse, ...
│   └── parser.py       # pdfplumber → text → regex → Transcript
├── graph.py            # PrereqGraph: networkx.DiGraph + satisfaction logic
├── ranker.py           # CourseScore + Ranker (criticality, availability, progress)
├── recommender.py      # End-to-end pipeline + fill-to-N planner
├── llm/
│   ├── backend.py      # LLMBackend (ABC) + OllamaBackend
│   ├── hardware.py     # Detect RAM/VRAM → pick model tier
│   └── reasoner.py     # LLMReasoner: rerank + reasoning + validation
└── ui/
    └── index.html      # Single-page UI served by FastAPI
```

## 5. The recommendation pipeline

```
Transcript ─┐
            │
            ▼
   ┌──────────────────────┐
   │ build_completed_grades │  collapses repeats, includes AP/IB/transfer as 'S'
   └────────┬─────────────┘
            │
            ▼
   ┌──────────────────────┐
   │ Ranker.score_all     │
   │   for each course:   │
   │     - prereqs_satisfied (with OR-clauses)
   │     - offered_next_quarter (uses time_schedule data if present)
   │     - criticality   = (effective_unlocked / max) × major_relevance_bonus
   │     - availability  = (4 - offering_freq + 1) / 4
   │     - progress      = 1.0 if course satisfies an unmet req
   │                       0.3 + 0.15·|unlocked & unmet| otherwise
   └────────┬─────────────┘
            │
            ▼
   ┌──────────────────────┐
   │ filter:              │
   │  - eligibility_ok    │
   │  - offered_next_qtr  │
   │  - fits_major (with fallback if too few candidates)
   │  - level < 500       │
   └────────┬─────────────┘
            │
            ▼
   ┌──────────────────────┐
   │ Ranker.rank          │  weighted combination from config.yaml
   └────────┬─────────────┘
            │
            ▼
   ┌────────────────────────────┐
   │ LLMReasoner.rerank (opt'l) │  JSON-mode Ollama; max 2 retries
   │  - validates every code    │
   │  - drops hallucinations    │
   │  - attaches reasoning text │
   └────────┬───────────────────┘
            │
            ▼
   ┌──────────────────────┐
   │ Recommender._fill_to_n │  greedy walk: add until ∈ [N-2, N+2]
   │                        │  + balance penalty (≤ 2 400-level courses)
   │                        │  + hard ceiling (18 cr default)
   └────────┬─────────────┘
            │
            ▼
   RecommendationResult  → JSON  → UI / CLI / API consumer
```

## 6. Prereq graph

Edges point **from prereq → course** so:
* `out_degree(c)` = how many courses `c` directly unlocks.
* `nx.descendants(c)` = the full downstream impact set.

OR-clauses (e.g., "CSS 142 OR CSE 142") share a non-zero `group_id`. The satisfaction check needs only **one** option in the group to be met.

**Effective downstream** is the subtle bit. A naive `len(downstream(c))` over-credits 100-level courses that "unlock" everything — even for a junior who's already passed them. We instead compute, for each candidate `c`:

> "If the student took `c` (and only `c`), which currently-ineligible downstream courses would *newly* become eligible?"

That's the only definition of "criticality" that matches what a human advisor means.

## 7. LLM defense in depth

The spec calls this out explicitly: *"every `course_id` the LLM returns MUST be validated against the SQLite catalog before being shown to the user. Local reasoning models hallucinate course codes constantly."*

`LLMReasoner._validate_response` enforces three layers of defense:

1. **Schema validation** — Ollama JSON mode + a Pydantic-validatable schema. Two retries before falling back to deterministic order.
2. **Candidate-list membership** — the LLM may only reorder courses we already handed it. If it emits a code we didn't pass in, we drop it with a `warning`.
3. **Catalog validation** — even if a code wasn't in the candidate list, we still check if it *exists* in `courses`. The warning message disambiguates "hallucination" (doesn't exist) vs. "off-list" (exists but shouldn't have been picked).

If validation drops everything, we fall back to the deterministic order with a clear warning rather than refusing to recommend.

## 8. Extending to a new major

Adding a major is two small changes — no other module touches:

```python
# src/capstone/scrapers/programs/cybersec.py
from capstone.scrapers.base import ProgramScraper

class CybersecurityProgramScraper(ProgramScraper):
    major_code = "CSEC"
    major_name = "Cybersecurity Engineering"

    CORE = ["CSS 310", "CSS 422", "CSS 430", "CSS 480"]
    CAPSTONE = ["CSS 499"]

    synergies = [
        ("CSS 480", ["CSS 422"],
         "Network security assumes the OS/memory background from Hardware."),
    ]

    def scrape_requirements(self, conn):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self._clear_existing_requirements(conn)
        count = 0
        count += self._insert_each(conn, "core", self.CORE)
        count += self._insert_each(conn, "capstone", self.CAPSTONE)
        self.seed_synergies(conn)
        self._record_scrape_metadata(conn, timestamp=now, record_count=count)
        return count
```

Then register it in `programs/__init__.py`:

```python
PROGRAM_SCRAPERS = {
    "CSSE": CSSEProgramScraper,
    ...
    "CSEC": CybersecurityProgramScraper,    # ← new
}
```

That's it. The CLI, FastAPI `/api/majors` endpoint, web UI dropdown,
LLM synergy prompt, parametrized test suite, and synergy seeder all
pick it up automatically. The parametrized tests in
`tests/test_phase5_majors.py` exercise the new scraper without any
new test code.

## 9. Privacy guarantees in code

| Concern | Mechanism |
|---------|-----------|
| Transcript leaks to network | LLM backend is constrained to the `LLMBackend` interface (Ollama / MLX). No HTTP client in `LLMReasoner`. |
| MyPlan scraping | Not implemented and not exposed. The spec explicitly forbids it. |
| Caching of PII | The transcript is parsed in-memory and discarded; PDFs are not persisted unless the user clicks "save profile." |
| Public scrape rate | `BaseScraper` enforces 1 req/sec via `_respect_rate_limit`; `robots.txt` is consulted before every fetch. |
| User-Agent | Identifies the app + a contact email (`config.yaml`). |

## 10. Testing strategy

| Layer | What's tested |
|-------|---------------|
| `tests/test_db_schema.py` | tables, indexes, migrations |
| `tests/test_catalog_scraper.py` | HTML parsing, prereq extraction |
| `tests/test_program_scrapers.py` | CSSE requirement seeding, stub error |
| `tests/test_transcript_parser.py` | header/courses/WIP/AP-IB/summary, real PDF fixture |
| `tests/test_prereq_graph.py` | OR-clauses, min-grade, concurrent prereqs, cycle detection, pickle |
| `tests/test_recommender.py` | hard constraints (no completed, no unmet prereq, no fake codes), fill-to-N, ceiling |
| `tests/test_llm_validation.py` | hallucinations dropped, off-list dropped, reasoning attached, fallback on backend error |
| `tests/test_api.py` | health, hardware, UI served, end-to-end parse→recommend over HTTP |

Run with `pytest -q`. 80+ tests, runs in ~1 second.
