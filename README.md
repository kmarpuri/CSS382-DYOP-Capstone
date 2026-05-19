# Capstone — UW Bothell Course Advisor

A **fully local** desktop application that helps UW Bothell undergraduates plan their next quarter's course schedule. The app scrapes UW Bothell's catalog, parses a student's transcript PDF, and combines a deterministic rule-based ranker with an optional local LLM (via Ollama) to produce a ranked, prereq-satisfying course plan for the next quarter.

> **Privacy:** No transcript data ever leaves your machine. All inference is strictly local via Ollama or MLX. The only network traffic is the public catalog/time-schedule scrape (no PII involved).

---

## Quick start

```bash
# 1. install
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[ui,llm,dev]"

# 2. scrape catalog + CSSE requirements (one-time, ~1 minute)
capstone scrape refresh

# 3. parse your transcript PDF
capstone parse-transcript UWUnofficialTranscript.pdf -o transcript.json

# 4. get recommendations (rule-based, instant)
capstone recommend transcript.json --load 15 --quarter AUT --no-llm

# 5. or launch the web UI
capstone serve
# → http://127.0.0.1:8765
```

The first time you run anything that uses the LLM (`capstone recommend`
without `--no-llm`, or `capstone serve`), Capstone walks you through a
short setup wizard: it detects your hardware, asks permission to
install [Ollama](https://ollama.com) if needed, asks permission to pull
the recommended model for your tier, and starts the daemon. Re-run the
wizard any time with:

```bash
capstone setup              # interactive
capstone setup --yes        # accept all prompts (CI / scripted use)
```

The UI uploads your transcript, lets you toggle the credit load / target quarter / LLM mode, and renders the ranked plan with reasoning per pick.

---

## Supported platforms

| Platform | Notes |
|----------|-------|
| macOS (Apple Silicon) | Fully supported. Ollama MLX backend gives ~2x inference speedup. |
| macOS (Intel) | Fully supported. CPU inference, ~30-60s/recommendation. |
| Linux | Fully supported. NVIDIA GPU recommended for tier-3+ models. |
| Windows | Fully supported. CPU-only inference is slow (20-60s/rec) — consider WSL2 + GPU. |

---

## Hardware tiers (LLM model selection)

Detected on first run; user-overridable.

| Tier | RAM / VRAM | Default model | Notes |
|------|------------|---------------|-------|
| 1 | ≤ 8 GB | `phi4-mini:3.8b` | Short explanations only; rule-based ranker is primary. |
| 2 | 16 GB | `phi4:14b` | Best reasoning per GB. |
| 3 | 24 GB+ | `qwen3:30b-a3b` (MoE) | **Default** — fast inference despite size. |
| 4 | 32 GB+ or 24 GB+ VRAM | `gemma3:27b` | Maximum quality. |

Override with the `CAPSTONE_LLM_MODEL` env var or by editing `config.yaml`.

---

## CLI reference

```text
capstone scrape refresh [--reset]             # (re)build the local catalog DB
capstone scrape status                        # show what's been scraped + when
capstone parse-transcript FILE.pdf [-o OUT]   # PDF → Transcript JSON
capstone recommend TRANSCRIPT.json            # ranked next-quarter plan
  --load N            target credit load (default 15, hard ceiling 25)
  --top N             show top-N candidates (default 10)
  --quarter AUT|WIN|SPR|SUM
  --no-llm            skip LLM reasoning (instant, deterministic only)
capstone serve [--port 8765]                  # FastAPI + bundled UI
```

---

## Configuration

`config.yaml` (project root) tunes everything without code changes:

```yaml
scraper:
  rate_limit_seconds: 1.0
  user_agent: "Capstone/1.0 (UWB Course Advisor; you@uw.edu)"
  bothell_departments: [css, stmath, bwrit, bbus, ...]
  time_schedule_quarters: ["AUT2026", "WIN2027"]

ranking_weights:
  criticality: 0.35       # how many downstream courses does it unlock?
  availability: 0.25      # inverse of offering frequency
  progress: 0.30          # how directly it advances unmet major reqs
  balance_penalty: 0.10   # discourage stacking high-difficulty courses

credit_limits:
  default: 15
  hard_ceiling: 25
```

---

## Privacy & FERPA awareness

* **No transcript data ever leaves the machine.** No remote API calls with transcript content under any circumstance. All LLM inference is strictly local via Ollama (or MLX on Apple Silicon).
* **Web scraping is limited to public pages** on `washington.edu` and `uwb.edu`. No login is performed. **MyPlan is never scraped** — it's behind UW NetID SSO and scraping it would violate UW's ToS.
* `robots.txt` is honored. Scrapes are rate-limited to 1 req/sec with a clearly-identified User-Agent.
* Transcript PDFs are read but **not copied or persisted** unless the user explicitly saves a profile.
* The local cache lives under `~/.capstone/cache/` (per `platformdirs`).

This application is intended for the student whose transcript is being analyzed. Sharing another student's transcript with this tool without their consent may violate FERPA. The author of this tool is not responsible for misuse.

---

## What's implemented

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Catalog scraper, time-schedule scraper, CSSE program scraper, SQLite schema |
| 2 | ✅ Transcript PDF parser (two-column-aware, pdfplumber + pypdf + OCR fallback) |
| 3 | ✅ Prereq DAG, deterministic ranker, fill-to-N planner, CLI |
| 4 | ✅ Ollama-backed LLM reasoner, FastAPI server, single-page UI |
| 5 | 🚧 Additional UW Bothell majors — architecture is in place, scrapers TBD |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design rationale and data-flow diagrams.

---

## Development

```bash
# install dev deps
pip install -e ".[ui,llm,dev]"

# run tests
pytest -q

# run with auto-reload
capstone serve --reload
```

The test suite covers:
* unit tests for the prereq DAG (cycle detection, OR-clause resolution, min-grade enforcement)
* unit tests for transcript parsing against synthesized sample text + the bundled real PDF
* integration tests asserting that no recommendation violates any hard registration constraint
* LLM-output validator tests (drops hallucinated codes, attaches reasoning, falls back on backend failure)

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'capstone'` after `pip install -e .` on macOS.** Python 3.13's `site.py` silently skips `.pth` files that have the `UF_HIDDEN` filesystem flag. macOS sometimes sets that flag on files inside `.venv/`. Fix:

```bash
chflags -R nohidden .venv
```

## License

MIT
