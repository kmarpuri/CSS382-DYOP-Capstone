# PISAN-Suggest.md

*Produced by Claude.AI on 2026-05-29*

## Project Overview

Capstone is a fully-local desktop / web app that helps UW Bothell undergraduates plan next quarter's schedule by scraping the public UW course catalog and time schedule, parsing the student's transcript PDF, and producing a ranked, prereq-satisfying course plan via a deterministic ranker layered with an optional local LLM (Ollama / MLX) for reasoning. It is FERPA-aware by design: transcripts never leave the machine, MyPlan is not scraped, and the recommendation pipeline validates every LLM-emitted course code against the SQLite catalog before display.

## Evaluation Against Assignment Specification

Evaluation based only on what is visible in the GitHub repository.

### UW Community Impact (10 pts)
Strong concept directly aimed at UW Bothell undergraduates: course planning is a real, recurring pain point for CSSE majors and an advisor-time multiplier. The README's "Phase 5 — additional UW Bothell majors" roadmap and the `ProgramScraper` ABC in `src/capstone/scrapers/programs/` show the design is intentionally extensible beyond a single major. The privacy / FERPA section in `README.md` (and `ARCHITECTURE.md` section 9) demonstrates real understanding of UW's data sensitivities. Caveat: only CSSE is actually wired up (`programs/csse.py` is the only non-stub), so the realized impact today is narrower than the README suggests.

### AI Integration (15 pts)
AI is **meaningfully embedded**, not a sidecar chat. Evidence:
- `src/capstone/llm/reasoner.py` (`LLMReasoner.rerank`) takes the deterministic top-N and reranks with multi-quarter foresight + attaches per-pick reasoning, using Ollama JSON-mode with a Pydantic-style schema (`LLM_OUTPUT_SCHEMA`).
- `_validate_response` enforces three layers of defense (schema, candidate-list membership, catalog existence) and falls back to deterministic order on failure — this is the right pattern for hallucination-prone local models.
- `_build_synergies_block` constructs a structured "completed_prep / missing_prep / rationale" payload per candidate from `scrapers/programs/synergies.py`, so the LLM is reasoning over typed data, not a free-form chat.
- Hardware-aware model selection (`llm/hardware.py` tiers 1-4, `OllamaBackend._pick_fallback`) shows production-quality thinking.
The integration is structurally central. The one soft spot is that, if `use_llm=False` (or Ollama is absent), the deterministic ranker alone produces the entire plan — so the AI layer is "reasoning + reranking," not the source of recommendations. That is arguably a feature, but graders looking for AI-as-core-logic will want a clearer story.

### Technical Execution (25 pts)
Substantial, well-organized Python codebase (~3,000 LOC across `src/capstone/`, ~1,500 LOC of tests). Notable strengths:
- Clean module map (`api.py`, `cli.py`, `recommender.py`, `ranker.py`, `graph.py`, `llm/`, `scrapers/`, `transcript/`, `ui/`) matching `ARCHITECTURE.md` section 4 exactly.
- Typed config with `pyproject.toml` extras (`[ui]`, `[llm]`, `[pdf]`, `[dev]`) and a Click CLI exposing `scrape`, `parse-transcript`, `recommend`, `serve`, `setup`.
- 80+ tests in `tests/` covering DAG cycle detection, OR-clause prereqs, transcript parsing, LLM validation (hallucination + off-list), API smoke, recommender hard constraints.
- Defensive scraper layer (`scrapers/base.py`) with rate-limiting + robots.txt awareness called out in README.
Weaknesses:
- **No `.github/workflows/`** — there is no CI running `pytest` on push, so the test suite's "80+ tests in ~1 second" claim from `ARCHITECTURE.md` is not enforced.
- **No deployment** (by design — see below), so "deployment stability" is not directly demonstrable.
- Only two student commits in the entire history (`6dce73b Initial commit`, `a62b37e Completed general framework`); the realized work landed in one large drop, which makes it impossible to verify incremental authorship.
- A `capstone_antigravity_prompt.md` and `transcript.json` are committed at the repo root; the latter looks like a fixture but should live under `tests/fixtures/` or be `.gitignore`d to avoid implying a real transcript is in the repo.

### Project Web Presence (15 pts)
**No deployed URL was found** in the README, repo settings, or any config. This is consistent with the project's privacy-first thesis (transcripts must stay local), but it means the DYOP rubric's "live deployment" and "project website explaining the why/how" cannot be evaluated from the repo. `README.md` and `ARCHITECTURE.md` together do an excellent job explaining the *why* and *how* (data-flow diagram, four-phase build, defense-in-depth rationale), and the bundled `src/capstone/ui/index.html` is a clean single-page UI with UW purple/gold branding, transcript upload, credit-load / quarter / LLM toggles, and per-pick reasoning. But there is no public website / landing page reachable without cloning and running the code, which is a real rubric gap.

### Milestones & Planning (20 pts)
Commit history shows **two substantive commits by the student** (`6dce73b`, `a62b37e`), both authored by `Krish Marpuri`. There is no visible iterative cadence (no per-phase commits, no PRs, no issues, no milestones), even though `ARCHITECTURE.md` section 2 describes a clean four-phase build. The phase plan is excellent on paper; the git timeline doesn't reflect it. The DYOP spec calls out commit history as evidence of iterative milestones, so this is the weakest area relative to the code's actual quality. Also: the group-project requirement (2-3 people) is not visible — only one contributor appears in `git log`.

### Peer Review (15 pts)
Not evaluable from the repository alone; depends on teammate survey responses. Note however that only one student contributor (`Krish Marpuri`) is visible in the commit log, so the instructor should verify the team composition out-of-band.

## Suggested Improvements & New Features

### UI / UX
- The single-page `ui/index.html` shows ranked picks and reasoning, but does not visualize the **prereq DAG** (`graph.py`) — a small "why this course" graph view (this pick + its unmet downstream descendants) would make the criticality score concrete to students.
- Add an **explainability panel** that surfaces the four signal weights (`criticality`, `availability`, `progress`, `synergy`) per pick as a stacked bar so students can see *which* component drove the rank, not just the final number.
- The current flow assumes the student knows their declared major. Add a small "I'm undeclared" branch that lets the user pick from `PROGRAM_SCRAPERS` (even when only CSSE is implemented, prompt the user instead of silently defaulting).
- Surface the `warnings[]` field from `RecommendationResult` more prominently in the UI — fallback-to-deterministic, hallucination drops, and credit-fill-short warnings are currently easy to miss.
- The `firstrun.py` wizard is CLI-only. Mirror it inside the web UI (`/api/llm-status` already exposes the needed state) so users who only launch `capstone serve` aren't lost when Ollama isn't installed.

### New Features
- **"What if I take this in a different quarter?"** — let the student pin a candidate to a future quarter and re-run the planner; the ranker already understands `target_quarter`, this is mostly a UI loop.
- **Multi-quarter plan to graduation**: rather than just next quarter, chain the recommender across `target_quarter` values until all unmet `major_requirements` are satisfied. The `PrereqGraph` and `Recommender._fill_to_n` are already the right primitives.
- **Implement at least one more major scraper** beyond CSSE (CSS BA, Math, or IMD are good candidates) to validate the `ProgramScraper` ABC. Right now `programs/stub.py` raises `NotImplementedError`, which under-delivers on the Phase 5 promise in `ARCHITECTURE.md` section 8.
- **Schedule conflict detection**: the `timeschedule` scraper already ingests offering times; flag plans where two picks meet at conflicting MWF/TTh blocks.
- **Saved profiles + diffs**: with explicit opt-in (the README already mentions "save profile"), let a student snapshot a plan and see what changed between scrapes (a new section opened, a prereq waiver, a course retired).

### Code Quality / Technical
- **Add CI**: a `.github/workflows/test.yml` running `pytest -q` on Python 3.11/3.12/3.13 across macOS + Linux. The 80+ tests in `tests/` are the project's strongest quality signal; not running them automatically squanders that signal.
- **Type-check in CI**: the codebase uses `from __future__ import annotations` and Pydantic models throughout; add `mypy --strict` or `pyright` over `src/capstone/` to lock that in.
- **Move `transcript.json` out of the repo root**. Either delete it, move it under `tests/fixtures/`, or add it to `.gitignore`. A file named `transcript.json` at the root of a FERPA-conscious project reads badly even if it's synthetic.
- **`OllamaBackend` retries swallow every exception** in `generate_json`. Narrow the `except Exception` to `(ollama.ResponseError, httpx.HTTPError, KeyError, TypeError)` so genuine bugs (e.g., a None deref in `_build_prompt`) surface instead of silently retrying.
- **`Recommender.recommend` re-imports `default_backend` and `LLMReasoner` inside the function**. Hoist those to module-level imports guarded by a `try/except ImportError` flag — the inline import hides the dependency from static analyzers and makes the `use_llm=False` fast path slower than it needs to be.
- **Pin a `tool.ruff` / `tool.black` config** in `pyproject.toml` and gate it in CI. With ~3,000 LOC and three optional-deps groups, stylistic drift will set in quickly.
- **Add a `--json` flag to `capstone recommend`** so the CLI emits the same `RecommendationResult` schema the API returns. Useful for scripted use and for the future "diff between scrapes" feature.
- **Security note**: `OllamaBackend._host` honors `OLLAMA_HOST`, which can point at a remote Ollama. That conflicts with the README's "no network traffic with transcript content" guarantee. Either reject non-loopback hosts by default, or document the override prominently.
