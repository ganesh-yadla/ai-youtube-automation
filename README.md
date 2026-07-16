# AI Creator OS

An AI-powered platform that discovers trending topics, analyzes successful content, and (eventually) generates and publishes YouTube Shorts. Near-term goal: a personal tool to run against your own channel(s) and earn YouTube ad revenue — not a multi-tenant SaaS product yet (see [Roadmap](#roadmap)). Built incrementally, one validated feature at a time.

## Status

**Phase 0 — Trend Intelligence backend: done and verified against real infrastructure.** Give it a keyword, get back trending YouTube videos plus AI-generated insights on why they're working. Verified end-to-end against a live Postgres, Redis, and the YouTube API. The `/insights` endpoint (Claude) is implemented but not yet verified against the real Anthropic API — deliberately deferred to avoid spend until needed. No frontend yet; the API is used via `/docs` or any HTTP client.

## Architecture

Clean Architecture, layered by responsibility — the API never talks to the database or an external API directly:

```
API (FastAPI routers)
  -> Services (business logic: caching, scoring, orchestration)
    -> Repository (persistence, behind an interface)
      -> Infrastructure (SQLAlchemy/Postgres, Redis, YouTube, Claude)
```

| Layer | Location |
|---|---|
| API routes, request/response schemas, DI wiring | `backend/app/api/` |
| Business logic | `backend/app/services/` |
| Persistence (interface + SQLAlchemy implementation) | `backend/app/repositories/` |
| External integrations (YouTube, Claude, Redis, DB) | `backend/app/infrastructure/` |
| Internal domain models (Pydantic) | `backend/app/domain/` |
| Domain exceptions | `backend/app/exceptions/` |

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic, Redis
- **AI:** Anthropic Claude API (`claude-opus-4-8`, structured output)
- **External data:** YouTube Data API v3
- **Frontend (planned):** Next.js, React, TypeScript, Tailwind CSS
- **Infra:** Docker, Docker Compose

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/trends/search` | POST | Search a keyword against YouTube; returns trending videos (cached in Redis, persisted to Postgres) |
| `/api/v1/trends/{search_id}/insights` | POST | Run AI analysis (Claude) over a search's videos; returns insights |
| `/api/v1/trends/{search_id}` | GET | Fetch a prior search with its videos and analysis |
| `/health` | GET | Liveness check |

Full interactive docs at `/docs` once the server is running.

## Getting Started

### Prerequisites

- Docker Desktop (for Postgres + Redis + the API container)
- A [YouTube Data API v3 key](https://console.cloud.google.com/apis/library/youtube.googleapis.com)
- An [Anthropic API key](https://console.anthropic.com/)

### Setup

```bash
cp backend/.env.example backend/.env
# edit backend/.env and set YOUTUBE_API_KEY and ANTHROPIC_API_KEY

docker compose up --build
```

This starts Postgres, Redis, and the API on `http://localhost:8000`.

### Apply database migrations

```bash
cd backend
alembic upgrade head
```

### Running locally without Docker

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate   # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Requires a local Postgres and Redis reachable at the URLs in `backend/.env`.

### Running tests

```bash
cd backend
pytest              # 20 tests against fakes/stubs — no live Postgres/Redis/YouTube/Claude needed
pytest -m db        # 5 tests against a real Postgres — requires `docker compose up -d postgres` + `alembic upgrade head` first
```

`ruff check app tests alembic` for linting. The `-m db` tests exist specifically because two real bugs (a datetime timezone mismatch, a missing SQLAlchemy relationship load) passed the fake-based suite completely and only surfaced against a live database — see `backend/tests/db/test_trend_repository_db.py` for what each one regression-tests.

## Known Gaps

- **`/insights` (Claude) not yet verified against the real Anthropic API.** `/search` and `GET /{id}` are verified end-to-end against live Postgres, Redis, and YouTube. `ANTHROPIC_API_KEY` is still a placeholder — deferred deliberately since each real call has a small but nonzero cost.
- **No frontend.** The API is usable via `/docs` or any HTTP client; a UI is a separate, not-yet-approved feature.
- **Growth score is an estimate**, not verified velocity — `views ÷ days since publish`, not a time-series measurement.
- **No Auth/multi-tenancy**, deliberately — see Roadmap below.

## Roadmap

Revised phase order (personal-use-first, not the original module list order):

1. ~~Trend Intelligence~~ — done
2. Script Agent — turn trend insights into an actual video script
3. Thumbnail Agent + Voice Generation
4. Video Generation — the major cost inflection point (video-gen APIs are far more expensive than LLM/text calls)
5. Publishing Automation — upload to YouTube; this is the revenue-unlock step (YouTube Partner Program ad revenue)

Deferred until/unless the product opens up to other creators: Auth, Payments/multi-tenancy. Flexible, not on the critical path: Competitor Analysis, Research Agent, SEO Optimization, Analytics Dashboard.
