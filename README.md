# Capstone — UW Bothell Course Advisor

A web application that helps UW Bothell undergraduates plan their next quarter's course schedule. It scrapes UW Bothell's catalog, parses a student's transcript PDF, and combines a deterministic rule-based ranker with an LLM reasoning layer to produce a ranked, prereq-satisfying plan. You can also hand it a **free-form preference prompt** (e.g. _"morning classes only, nothing on Fridays"_), and each recommendation shows the **meeting times** of the sections actually on offer for the target quarter.

The app is **dual-mode** — the same codebase powers a deployed public website and a fully-local run on a student's laptop:

| Mode | LLM backend | Catalog database | Selected when |
|------|-------------|------------------|---------------|
| **Hosted** (the deployed site) | Groq — Llama 3.3 70B, free tier | Turso (libSQL cloud) | `GROQ_API_KEY` is set |
| **Local** | Ollama (any pulled model) | on-disk SQLite | no Groq key — automatic fallback |

> **Privacy:** The transcript is never persisted server-side. In **local** mode nothing leaves your machine. In **hosted** mode the transcript's `student_name` and `student_id` are PII-redacted *before* any LLM call (see [`redact.py`](src/capstone/llm/redact.py)); the public catalog / time-schedule / RateMyProfessor scrapes never involve PII.

---

## Quick start

```bash
# 1. install  (any Python ≥ 3.11; just use your python3)
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[ui,llm,dev]"

# 2. scrape catalog + CSSE requirements (one-time, ~1 minute)
capstone scrape refresh

# 3. parse your transcript PDF
capstone parse-transcript UWUnofficialTranscript.pdf -o transcript.json

# 4. get recommendations (rule-based, instant)
capstone recommend transcript.json --load 15 --quarter AUT --no-llm

# 4b. ...or with LLM reasoning + a free-form preference prompt
capstone recommend transcript.json --quarter WIN \
  --prompt "I prefer morning classes, nothing on Fridays"

# 5. or launch the web UI
capstone serve
# → http://127.0.0.1:8765
```

**Hosted mode needs no setup** beyond a free Groq API key (`GROQ_API_KEY`) —
there is no local model to download. The wizard below applies only to the
**local** fallback, where inference runs on your own machine via Ollama.

The first time you run anything that uses the local LLM (`capstone recommend`
without `--no-llm`, or `capstone serve`, *with no Groq key set*), Capstone
walks you through a short setup wizard: it detects your hardware, asks
permission to install [Ollama](https://ollama.com) if needed, asks permission
to pull the recommended model for your tier, and starts the daemon. Re-run the
wizard any time with:

```bash
capstone setup              # interactive
capstone setup --yes        # accept all prompts (CI / scripted use)
```

The UI uploads your transcript, lets you toggle the credit load / target quarter / LLM mode, and renders the ranked plan with reasoning per pick.

---

## Supported platforms

| Platform              | Notes                                                                           |
| --------------------- | ------------------------------------------------------------------------------- |
| macOS (Apple Silicon) | Fully supported. Ollama MLX backend gives ~2x inference speedup.                |
| macOS (Intel)         | Fully supported. CPU inference, ~30-60s/recommendation.                         |
| Linux                 | Fully supported. NVIDIA GPU recommended for tier-3+ models.                     |
| Windows               | Fully supported. CPU-only inference is slow (20-60s/rec) — consider WSL2 + GPU. |

---

## Hardware tiers (local mode only)

These apply **only when running the local Ollama fallback** — the hosted
deployment uses Groq and ignores all of this. Detected on first run;
user-overridable.

| Tier | RAM / VRAM            | Default model         | Notes                                                  |
| ---- | --------------------- | --------------------- | ------------------------------------------------------ |
| 1    | ≤ 8 GB                | `phi4-mini:3.8b`      | Short explanations only; rule-based ranker is primary. |
| 2    | 16 GB                 | `phi4:14b`            | Best reasoning per GB.                                 |
| 3    | 24 GB+                | `qwen3:30b-a3b` (MoE) | **Default** — fast inference despite size.             |
| 4    | 32 GB+ or 24 GB+ VRAM | `gemma3:27b`          | Maximum quality.                                       |

Override with the `CAPSTONE_LLM_MODEL` env var or by editing `config.yaml`.

---

## CLI reference

```text
capstone scrape refresh [--reset]             # (re)build the catalog DB
capstone scrape professors                    # cache RateMyProfessor ratings (UWB)
  --limit N           stop after N professors (debug / quick refresh)
  --force             re-fetch even cache-fresh professors
  --school NAME       override the school to look up (default: UW Bothell)
capstone scrape status                        # show what's been scraped + when
capstone parse-transcript FILE.pdf [-o OUT]   # PDF → Transcript JSON
capstone recommend TRANSCRIPT.json            # ranked next-quarter plan
  --load N            target credit load (default 15, hard ceiling 25)
  --top N             show top-N candidates (default 10)
  --quarter AUT|WIN|SPR|SUM
  --prompt "..."      free-form preferences passed to the LLM (e.g. preferred
                      times, course style); ignored with --no-llm
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
  criticality: 0.35 # how many downstream courses does it unlock?
  availability: 0.25 # inverse of offering frequency
  progress: 0.30 # how directly it advances unmet major reqs
  balance_penalty: 0.10 # discourage stacking high-difficulty courses

credit_limits:
  default: 15
  hard_ceiling: 25
```

---

## Privacy & FERPA awareness

- **The transcript is never persisted server-side and never sent anywhere in raw form.**
  - In **local** mode, no transcript content leaves the machine — inference runs locally via Ollama (or MLX on Apple Silicon).
  - In **hosted** mode, the transcript's `student_name` and `student_id` are stripped by [`redact.py`](src/capstone/llm/redact.py) *before* any call to Groq. Only de-identified course history is sent, and only to generate reasoning text.
- **Web scraping is limited to public pages** on `washington.edu` and `uwb.edu`. No login is performed. **MyPlan is never scraped** — it's behind UW NetID SSO and scraping it would violate UW's ToS.
- **RateMyProfessor** ratings have an **opt-in** scraper (`capstone scrape professors`). Scraping RMP is against their Terms of Service, so it's off by default, rate-limited, cached locally (30-day TTL), and the data is never re-published. Note: UW Bothell's *public* time schedule does not publish instructor names, so cached ratings currently can't be mapped to specific sections and are **not surfaced in the UI** — the recommendation cards show section **meeting times** instead.
- `robots.txt` is honored. Scrapes are rate-limited to 1 req/sec with a clearly-identified User-Agent.
- Transcript PDFs are read but **not copied or persisted** unless the user explicitly saves a profile.
- The local cache lives under `~/.capstone/cache/` (per `platformdirs`).

This application is intended for the student whose transcript is being analyzed. Sharing another student's transcript with this tool without their consent may violate FERPA. The author of this tool is not responsible for misuse.

---

## What's implemented

| Phase | Status                                                                                                                                                  |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | ✅ Catalog scraper, time-schedule scraper, CSSE program scraper, SQLite schema                                                                          |
| 2     | ✅ Transcript PDF parser (two-column-aware, pdfplumber + pypdf + OCR fallback)                                                                          |
| 3     | ✅ Prereq DAG, deterministic ranker, fill-to-N planner, CLI                                                                                             |
| 4     | ✅ Ollama-backed LLM reasoner, FastAPI server, single-page UI                                                                                           |
| 5     | ✅ All 35 UW Bothell undergraduate majors — STEM (CSSE, ACMPT, CE, EE, ME, Cybersec, Math B.S./B.A., Physics, Chem, Bio B.S./B.A.), Business, Health (HSCI/HSBA/Nursing), Education, Environment (EnvStud/Earth/Climate), IAS (Media Arts, MedCom, Studio Visual Art, CLA, IntArts, Philosophy, AES, CommPsy, GWSS, Global Studies, LEPP, Policy Studies, SEHB) |
| 6     | ✅ Hosted LLM mode via Groq (Llama 3.3 70B), PII redaction, deploy configs for Fly / Railway / Heroku-style |
| 7     | ✅ Free-form user-preference prompt routed to the LLM, per-section meeting times shown on each recommendation card, RateMyProfessor scraper + cache (opt-in), and hosted Turso (libSQL) cloud-database backend |

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

The test suite (**516 tests**) covers:

- unit tests for the prereq DAG (cycle detection, OR-clause resolution, min-grade enforcement)
- unit tests for transcript parsing against synthesized sample text + the bundled real PDF
- integration tests asserting that no recommendation violates any hard registration constraint
- LLM-output validator tests (drops hallucinated codes, attaches reasoning, falls back on backend failure)
- user-preference prompt plumbing (API field validation → recommender → LLM)
- RateMyProfessor scraper: name-normalization, cache freshness, lookup, mocked-GraphQL persistence
- Turso / libSQL connection wrapper: `sqlite3.Row` parity (`row["col"]`, `dict(row)`) and backend selection

---

## Deploy to a website

Capstone is dual-mode: the same codebase serves a public website *and* runs locally on a student's laptop. Two environment-driven switches decide the posture — which **LLM backend** answers, and which **database** stores the catalog. Both default to the local option and flip to hosted purely via env vars (no code changes).

| Mode | LLM backend | Catalog DB | Selected when |
|------|-------------|------------|---------------|
| Website | Groq (Llama 3.3 70B, free tier) | Turso (libSQL cloud) | `GROQ_API_KEY` set; `CAPSTONE_TURSO_*` set |
| Local | Ollama (any pulled model) | on-disk SQLite | neither set — falls back automatically |

(The two switches are independent: you can run hosted Groq against a local SQLite file, or vice-versa.)

At startup the server logs which backend it resolved, e.g. `LLM backend: Groq (hosted) · model: llama-3.3-70b-versatile`, so you can confirm the posture at a glance. The same info is exposed at `GET /api/llm-status` and shown in the UI. If it reads `Ollama (local)` when you expected Groq, the process didn't pick up `GROQ_API_KEY` / `CAPSTONE_LLM_BACKEND` — restart the server after setting them (env vars are read once at boot).

When hosted reasoning is on, transcripts have `student_name` and `student_id` redacted before *any* network call (see [`src/capstone/llm/redact.py`](src/capstone/llm/redact.py)). The UI surfaces a yellow banner explaining the data flow.

### Fly.io (free tier — recommended)

```bash
brew install flyctl
fly auth login
fly launch --no-deploy --copy-config            # uses the bundled fly.toml
fly secrets set GROQ_API_KEY=gsk_yourkey
fly deploy
```

The included [`fly.toml`](fly.toml) sets `CAPSTONE_LLM_BACKEND=groq`, mounts a persistent volume for the SQLite catalog, scales to zero when idle, and runs the bootstrap scrape on first boot.

### Hosted database (Turso / libSQL)

By default the deployed app stores its catalog in a SQLite file on the platform's persistent volume. For a submission/demo where you'd rather be backed by a managed **cloud database**, point the app at [Turso](https://turso.tech) (a hosted, SQLite-compatible libSQL service with a free tier). The app then runs as an **embedded replica**: a local file that libSQL keeps in sync with the cloud primary — fast local reads, writes forwarded to the cloud.

```bash
# 1. Create a free Turso database
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup
turso db create capstone-uwb
turso db show capstone-uwb --url           # -> CAPSTONE_TURSO_URL
turso db tokens create capstone-uwb        # -> CAPSTONE_TURSO_AUTH_TOKEN

# 2. Give the deployed app both secrets (Fly example)
fly secrets set \
  CAPSTONE_TURSO_URL=libsql://capstone-uwb-yourname.turso.io \
  CAPSTONE_TURSO_AUTH_TOKEN=eyJhbGci...
fly deploy
```

**How the backend is selected:**

| Storage | Selected when |
|---------|---------------|
| Turso (libSQL cloud) | **both** `CAPSTONE_TURSO_URL` and `CAPSTONE_TURSO_AUTH_TOKEN` are set |
| Local SQLite file | either is missing (local dev + the test suite always use this) |

The switch lives entirely in [`src/capstone/db/connection.py`](src/capstone/db/connection.py); no schema or query changes were needed. A thin wrapper makes libSQL's tuple rows behave exactly like `sqlite3.Row` (`row["col"]`, `dict(row)`), so the rest of the app is backend-agnostic. The deployed image already bundles the driver via the `turso` extra (`pip install -e ".[ui,llm,turso]"`).

> The auth token is a credential — set it only via `fly secrets` / your platform's env vars or a gitignored `.env`. **Never commit it.**

### Railway

Drop the repo into Railway; it picks up [`railway.json`](railway.json) automatically. Set `GROQ_API_KEY` and `CAPSTONE_LLM_BACKEND=groq` in the project's variables, hit deploy.

### Heroku-style platforms

The [`Procfile`](Procfile) declares the same two-step boot: `python -m capstone.deploy.boot && uvicorn capstone.api:app --host 0.0.0.0 --port $PORT`. Works on Render, fly machines, anything that respects a Procfile.

### Bootstrap on cold start

[`src/capstone/deploy/boot.py`](src/capstone/deploy/boot.py) runs before uvicorn. Because a hosted site has **no CLI**, this is how the database gets seeded. Each dataset is guarded by its own emptiness check, so a redeploy is a no-op for what's already there:

* **Catalog + all 35 majors' requirements** — scraped on the first ever deploy.
* **Time schedule** (public UWB section offerings — section IDs, meeting days/times, enrollment) — scraped by default; set `CAPSTONE_SCRAPE_TIMESCHEDULE=0` to skip. This is what populates the per-section meeting times shown on each recommendation card. (The public schedule does not publish instructor names or rooms, so those columns stay empty.)
* **RateMyProfessor ratings** — **opt-in** (RMP's ToS prohibits automated access). Set `CAPSTONE_SCRAPE_PROFESSORS=1` and boot caches them. This is the hosted equivalent of `capstone scrape professors`. Note: because the public schedule has no instructor names, these ratings can't be mapped to sections and are not currently shown in the UI.

On Turso, boot then `sync()`s everything up to the cloud primary before the server starts. Your platform's persistent volume (or your Turso database) keeps it all warm across releases — the expensive scrape happens exactly once.

---

## Docker

A `Dockerfile` and `docker-compose.yml` are included so the app can run in a container — Ollama still runs on the host (where the model weights live).

```bash
# build + start
docker compose up -d

# scrape the catalog and seed every registered major's requirements
docker compose exec capstone capstone scrape refresh --no-timeschedule

# health check
curl http://127.0.0.1:8765/api/health

# UI
open http://127.0.0.1:8765
```

Parse a transcript inside the container:

```bash
docker cp my_transcript.pdf capstone:/tmp/t.pdf
docker compose exec capstone capstone parse-transcript /tmp/t.pdf -o /tmp/t.json
docker compose exec capstone capstone recommend /tmp/t.json --load 15 --quarter AUT
```

Or hit `/api/parse-transcript` over HTTP from the host (the UI does this for you).

**Notes:**

- The container is `~250 MB` and runs as a non-root user.
- The SQLite catalog persists in a named volume (`capstone_data`).
- The image defaults `OLLAMA_HOST=http://host.docker.internal:11434`. On macOS / Windows that's the host's loopback. On Linux, `docker-compose.yml` adds `host.docker.internal:host-gateway` automatically.
- `CAPSTONE_SKIP_FIRSTRUN=1` is set in the image so the first-run wizard never blocks a non-interactive container. Run `docker compose exec -it capstone capstone setup` interactively if you want to invoke it manually.
- Override the LLM model: `docker compose run -e CAPSTONE_LLM_MODEL=qwen2.5:7b capstone ...`.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'capstone'` after `pip install -e .` on macOS.** Python 3.13's `site.py` silently skips `.pth` files that have the `UF_HIDDEN` filesystem flag. macOS sometimes sets that flag on files inside `.venv/`. Fix:

```bash
chflags -R nohidden .venv
```