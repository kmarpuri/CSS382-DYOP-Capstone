# Capstone: UW Bothell Course Recommendation Application

## Project Overview

Build a desktop application called **Capstone** that helps University of Washington Bothell undergraduates plan their next quarter's course schedule. The application:

1. Scrapes UW Bothell's course catalog, time schedule, and program requirements
2. Parses a student's transcript PDF
3. Uses a local LLM (via Ollama) layered on top of a deterministic rule-based engine to recommend courses for the next quarter, ranked by criticality, availability, and balance
4. Lets the student dial in their desired course load and regenerates the schedule

**Before generating any code, ask me clarifying questions about anything ambiguous in this spec. Then propose a project structure and confirm the first phase you'll deliver before writing implementation code.**

---

## Tech Stack

- **Language:** Python 3.11+
- **Backend:** FastAPI, served on localhost
- **Frontend:** Either PyQt6 (desktop) or a local React + Vite UI served by FastAPI — recommend which gives cleaner separation and why
- **Database:** SQLite for the course catalog, prerequisite graph, and cached metadata
- **Graph library:** `networkx` for the prerequisite DAG, persisted to SQLite (adjacency table) plus a pickled `.gpickle` for fast load
- **PDF parsing:** `pdfplumber` primary, `pypdf` fallback, `pytesseract` OCR as last resort for scanned transcripts
- **Web scraping:** `httpx` + `selectolax` (or `BeautifulSoup`); use `playwright` only if a target page strictly requires JS rendering
- **LLM integration:** `ollama` Python client. Wrap inference behind a thin `LLMBackend` interface so the backend can be swapped (Ollama default; MLX optional on Apple Silicon)

---

## Architecture & Phases

Deliver in **four independently runnable phases**, not one monolithic build. Each phase must work on its own before the next is started.

**Phase 1 — Scraper + Course DB (CSSE-first, generic architecture)**
- Scrape the full UW Bothell course catalog and time schedule — these are major-agnostic and apply to every student
- For program/major requirements, build a **generic scraper architecture** (e.g., a `ProgramScraper` base class or strategy pattern) that can be extended to any UW Bothell undergraduate major, but **only wire up CSSE in this phase**
- Other majors should be stubbed with a clear "not yet implemented" error so the structure is visible but unimplemented
- Persist everything to SQLite
- CLI: `capstone scrape --refresh` (scrapes catalog + CSSE requirements)

**Phase 2 — Transcript Parser**
- Accept a UW transcript PDF; extract completed courses, in-progress courses, grades, transfer/AP credits, GPA, class standing
- CLI: `capstone parse-transcript <file.pdf>` emits structured JSON

**Phase 3 — Prerequisite Graph + Rule-Based Ranking**
- Build the prereq DAG from the scraped data
- Implement deterministic ranking based on criticality, availability, progress toward major, and balance
- CLI: `capstone recommend <transcript.json> --load=15` returns ranked courses with no LLM involvement

**Phase 4 — LLM Reasoning Layer + UI**
- Layer the Ollama-backed reasoning engine on top of Phase 3
- Build the GUI on top of the FastAPI backend
- Final user-facing product for CSSE students

**Phase 5 — Expand to additional UW Bothell majors (future scope)**
- Implement the remaining `ProgramScraper` subclasses for other UW Bothell undergraduate majors (e.g., Math, Business, IMD, Biology)
- No core logic changes should be needed if Phase 1's abstraction was clean — this phase is primarily new scraper implementations and test coverage per major
- This phase is **out of scope for the initial build** but the architecture from Phase 1 must support it without refactoring

---

## Data Sources

Scrape from these specific URLs. **Do not invent endpoints.** If a page returns 404 or the structure has changed, stop and report it rather than fabricating data.

- **Course catalog (campus-wide):** `https://www.washington.edu/students/crscat/`
- **UW Bothell course listings:** under `https://www.uwb.edu/registrar/courses` (verify the current URL at build time)
- **Time Schedule (Bothell):** `https://www.washington.edu/students/timeschd/B/`
- **Program / major requirements:** the relevant department pages under `https://www.uwb.edu/`. **Scope:** the scraper architecture must be generic (extensible to any UW Bothell undergraduate major), but only the **CSSE program page** needs a working scraper implementation in the initial build. All other majors are deferred to Phase 5.
- **General education requirements:** UW Bothell gen-ed page on uwb.edu

**Do NOT attempt to scrape MyPlan (`myplan.uw.edu`).** It requires UW NetID authentication via SSO; scraping it would violate ToS and the auth flow is not something this app should automate. If course-offering data needs to come from MyPlan, design the app to accept a manual export from the user.

Respect `robots.txt`. Rate-limit requests to at most 1/sec with a custom User-Agent identifying the app and a contact email.

---

## Data Structures

### Course catalog (SQLite schema sketch)

```sql
courses(
  course_id TEXT PRIMARY KEY,    -- e.g., "CSS 343"
  title TEXT,
  credits INTEGER,
  description TEXT,
  offering_pattern TEXT,          -- e.g., "AWSp", "A,Sp"
  last_offered TEXT,              -- ISO date
  scraped_at TEXT
)

prerequisites(
  course_id TEXT,
  prereq_id TEXT,
  type TEXT,                      -- "required", "concurrent", "recommended", "one_of"
  group_id INTEGER                -- groups OR-clauses like "MATH 124 OR MATH 134"
)

major_requirements(
  major TEXT,
  category TEXT,                  -- "core", "elective", "capstone"
  course_id TEXT,
  required_count INTEGER
)
```

### Prerequisite DAG

Built from the `prerequisites` table at app startup using `networkx.DiGraph`. Required for:

- Topological ranking ("how many downstream courses does this unlock?")
- Cycle detection (catches scraping errors)
- Shortest-path queries from the student's current state to graduation requirements

Persist a pickled `.gpickle` keyed on the catalog's `scraped_at` timestamp; rebuild whenever the catalog is re-scraped.

---

## Transcript Parsing

UW transcripts (typically unofficial PDFs from MyUW) are reasonably structured. The parser must extract:

- Course code, title, grade, credits, quarter taken
- In-progress courses (`IP` or blank grade)
- Withdrawn courses (`W`) — exclude from "completed" but flag for retry candidacy
- Repeats — keep the highest grade per UW's repeat policy; flag the rest
- Transfer credits — often without UW course numbers; map to UW equivalents where possible and surface unmapped credits to the user for manual mapping
- AP/IB credits — usually at the top of the transcript
- Cumulative GPA, major GPA, class standing

Output a `Transcript` Pydantic model, not a raw dict. Provide a `--debug` flag that dumps intermediate parsing state for failed extractions.

---

## User Inputs (collected at first run, editable later)

- Declared major(s) and minor(s) — e.g., "CSSE"
- Target graduation quarter — e.g., "Sp 2027"
- AP / transfer credits not on the transcript
- Time-of-day preferences (e.g., "no classes before 10 AM")
- Instructor preferences ("must take Professor X" / "avoid Professor Y") — optional soft filter
- Maximum credit load (default 15, hard ceiling 18 unless overridden)
- Optimization mode: prioritize early graduation vs. balanced workload

---

## Hard Registration Constraints

The recommendation engine MUST respect:

- **Prerequisites met** — never recommend a course the student can't register for
- **Class standing** (e.g., "junior standing required")
- **Major restrictions** (some courses are major-only or require add codes)
- **Credit cap** per quarter (default 18, configurable)
- **Time conflicts** when concrete sections are pulled from the Time Schedule
- **Offering availability** — don't recommend a course not offered next quarter

When a constraint blocks a course, log the reason and surface it in the output. Do not silently filter.

---

## Recommendation Engine

### Layer 1 — Rule-based ranker (deterministic, runs first)

For each course the student is *eligible* to take, compute:

- `criticality_score`: out-degree in the prereq DAG, weighted by whether downstream courses are required for the student's declared major
- `availability_score`: inverse of offering frequency (rarely-offered courses rank higher because deferring them costs more)
- `progress_score`: how directly the course advances unmet major requirements
- `balance_penalty`: applied when too many high-difficulty courses are stacked in one quarter (use course level + credit hours as a proxy; historical average grade if available)

Combine into a weighted ranking. Weights live in a `config.yaml` so they can be tuned without code changes.

### Layer 2 — LLM reasoning layer (Ollama)

The LLM does **NOT** pick courses from scratch. It receives the top-N candidates from the rule-based ranker and:

- Validates picks against the student's graduation timeline
- Reranks with awareness of multi-quarter sequencing (e.g., "take this prereq now so you can take its sequel in Sp")
- Produces final ranked output with natural-language reasoning

### Fill-to-N Algorithm

User toggles desired credit load `N`. Walk the ranked list and add courses until the credit total falls in `[N-2, N+2]`, respecting all hard constraints. If no valid combination exists, return the closest valid load and explain why in the warnings field.

---

## LLM Backend & Hardware-Aware Selection

Use Ollama as the default backend (cross-platform: Windows, macOS, Linux). On Apple Silicon, optionally support MLX for ~2x faster inference.

At first run, detect available system RAM and dedicated VRAM, then recommend a model tier:

| Tier | RAM / VRAM | Recommended Model | Notes |
|------|------------|-------------------|-------|
| 1 | ≤ 8 GB | Gemma 4 E4B or Phi-4-mini 3.8B | LLM used only for short explanations; rule-based ranker is primary |
| 2 | 16 GB | Phi-4 14B (best reasoning per GB) or Qwen 3.5 9B (better instruction following) | |
| 3 | 24 GB+ | **Qwen 3.5 35B-A3B (MoE) — default** or Gemma 4 26B A4B | MoE = fast inference despite size |
| 4 | 32 GB+ or 24 GB+ VRAM | Gemma 4 31B Dense | Maximum quality |

- Allow the user to override the recommendation.
- Show a progress bar during the first-time `ollama pull` — these are 5–20 GB downloads.
- Warn CPU-only Windows users that inference may take 20–60 seconds per recommendation.

---

## LLM Output Contract

The LLM MUST return structured JSON matching this schema:

```json
{
  "recommendations": [
    {
      "course_id": "CSS 343",
      "rank": 1,
      "criticality_score": 0.92,
      "availability_score": 0.40,
      "progress_score": 0.85,
      "reasoning": "Unlocks CSS 422, CSS 430, CSS 487 — all required for the CSSE major. Offered every quarter so deferral is safe, but completing it next quarter keeps you on track for Sp 2027 graduation.",
      "credit_hours": 5,
      "fits_load": true
    }
  ],
  "total_credits": 15,
  "warnings": []
}
```

**Critical:** every `course_id` the LLM returns MUST be validated against the SQLite catalog before being shown to the user. Local reasoning models hallucinate course codes constantly. If the LLM emits a non-existent code (e.g., "CSS 999"), drop it from the output and log the hallucination. Defense in depth is non-negotiable.

Use Ollama's structured-output / JSON mode where supported; otherwise wrap with a Pydantic validator and retry on parse failure (max 2 retries before falling back to the rule-based output).

---

## Privacy & Local-Only Guarantee

- **No transcript data ever leaves the machine.** No remote API calls with transcript content under any circumstance. All LLM inference is strictly local via Ollama/MLX.
- Web scraping of the public UW catalog is fine (no PII involved).
- Cache location: `~/.capstone/cache/` (use `platformdirs` for cross-platform correctness).
- Catalog re-scrape policy: cache is stale after 30 days; prompt the user to refresh on next launch, or refresh on-demand via `capstone scrape --refresh`.
- Transcript PDFs are read but not copied or persisted unless the user explicitly opts in to "save profile."
- README must include a FERPA-awareness section and the local-only guarantee.

---

## Evaluation Plan

Build a test harness using my own (sanitized) transcript as ground truth:

- Did the app recommend any course I've already completed? (Must be zero.)
- Did the app recommend any course whose prereqs I haven't met? (Must be zero.)
- Did the app recommend non-existent courses? (Must be zero.)
- Did the app recommend reasonable next-quarter CSSE courses given my current standing? (Manual sanity check.)

Provide a `pytest` suite covering at minimum:

- Unit tests for the prereq DAG (cycle detection, downstream traversal, OR-clause resolution)
- Unit tests for transcript parsing against at least two synthesized sample PDFs
- Integration test that runs the full pipeline against a fixture transcript and asserts the recommendations satisfy every hard constraint

---

## Deliverables

- Source code in a clean Python project layout (`src/capstone/`, `tests/`, `pyproject.toml`)
- `README.md` with setup instructions, supported platforms, hardware requirements, privacy statement
- `ARCHITECTURE.md` explaining the four-phase design, data flow, and the LLM-validation strategy
- The four phases delivered as separate runnable artifacts so I can verify each before moving on

---

## Before You Start

1. Ask me clarifying questions about anything ambiguous (e.g., PyQt6 vs. web frontend, whether I want a CLI in addition to the GUI, how strictly to enforce major restrictions when historical data is missing).
2. Confirm which phase you'll deliver first and what the acceptance criteria are.
3. List any UW URLs you can't access or that have changed since this spec was written.
