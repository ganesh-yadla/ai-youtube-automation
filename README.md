# AI Creator OS

An AI-powered platform that discovers trending topics, analyzes successful content, and (eventually) generates YouTube Shorts and other social content. Long-term SaaS product, built incrementally one validated feature at a time.

## Status

**Phase 1 — Trend Intelligence MVP.** This is the first feature, built deliberately before authentication or payments: give it a keyword, get back trending YouTube videos plus AI-generated insights on why they're working. Backend is implemented; a frontend has not been built yet (see [Roadmap](#roadmap)).

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
pytest
```

20 unit and integration tests, run against fakes/stubs (no live Postgres, Redis, YouTube, or Claude required). `ruff check app tests alembic` for linting.

## Known Gaps

- **No real-infrastructure verification yet.** All tests pass against fakes/stubs; the app has not been run end-to-end against a live Postgres, Redis, YouTube API, or Claude API. Needs Docker installed and real API keys in `backend/.env`.
- **No frontend.** The API is usable via `/docs` or any HTTP client; a UI is a separate, not-yet-approved feature.
- **Growth score is an estimate**, not verified velocity — `views ÷ days since publish`, not a time-series measurement.

## Roadmap

Planned modules beyond Phase 1 (not yet built): Competitor Analysis, Research Agent, Script Agent, Thumbnail Agent, Voice Generation, Video Generation, SEO Optimization, Publishing Automation, Analytics Dashboard.
