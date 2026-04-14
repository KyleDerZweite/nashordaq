# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## First Rule

Read and follow [AGENTS.md](AGENTS.md) as the primary source of instructions.

## Project Overview

Nashordaq is a self-hosted virtual share market for a private League of Legends friend group. Users trade shares in LoL players using virtual currency; share prices fluctuate based on real-time Ranked LP changes fetched from the Riot Games API.

## Tech Stack

- **Frontend:** Vite + TypeScript + TailwindCSS + TanStack Query
- **Backend:** FastAPI (Python) with SQLAlchemy 2.0
- **Database:** SQLite (via aiosqlite)
- **Background Tasks:** APScheduler (in-process)
- **Deployment:** Podman-compose

## Canonical Docs

- Architecture and security boundary: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Pricing model and formulas: [docs/ECONOMY_MECHANICS.md](docs/ECONOMY_MECHANICS.md)
- Product behavior and scope: [docs/PRD.md](docs/PRD.md)

Do not duplicate complex architecture or formula details outside those canonical docs.

## Project Layout

```
nashordaq/
  backend/               # FastAPI + uv
    app/
      main.py            # App entrypoint, lifespan, router mounts
      config.py          # Pydantic settings (NASHORDAQ_ env prefix)
      database.py        # Async SQLAlchemy engine + session factory
      models.py          # ORM models and table definitions
      schemas.py         # Pydantic request/response schemas
      auth.py            # Remote-Email auth dependency with Remote-User fallback
      pricing.py         # Pure pricing functions
      riot.py            # Riot Games API client
      scheduler.py       # APScheduler market update job
      routers/           # FastAPI route modules
    tests/               # pytest (async, in-memory SQLite)
  frontend/              # Vite + React + pnpm
  docs/                  # Architecture, PRD, economy mechanics
```

## Quick Commands

### Backend (run from `backend/`)
```bash
uv add <package>           # Add a dependency
uv run ruff check .        # Lint
uv run ruff format .       # Format
uv run pytest -v           # Test
uv run uvicorn app.main:app --reload  # Dev server
```

### Frontend (run from `frontend/`)
```bash
pnpm add <package>         # Add a dependency
pnpm run lint              # Lint (ESLint)
pnpm run format            # Format (Prettier)
pnpm run dev               # Dev server
pnpm run build             # Production build
```
