# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nashordaq is a self-hosted fantasy stock market for a private League of Legends friend group. Users trade shares in LoL players using virtual currency; share prices fluctuate based on real-time Ranked LP changes fetched from the Riot Games API.

## Tech Stack

- **Frontend:** Vite + TypeScript + TailwindCSS + TanStack Query
- **Backend:** FastAPI (Python) with SQLAlchemy/SQLModel
- **Database:** SQLite (via aiosqlite)
- **Background Tasks:** APScheduler (in-process)
- **Deployment:** Podman-compose

## Tooling Constraints

- **Backend package manager:** `uv` only. Never use `pip`, `poetry`, or `conda`.
- **Frontend package manager:** `pnpm` only. Never use `npm` or `yarn`.

## Project Layout

```
nashordaq/
  backend/       # FastAPI + uv
  frontend/      # Vite + React + pnpm
```

## Commands

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

## Architecture

- **Frontend** serves a dashboard (market overview, trading, portfolio, leaderboard) and uses TanStack Query for server state and caching.
- **Backend (FastAPI)** exposes REST endpoints for trades, portfolios, and market data.
- **Scheduler (APScheduler)** runs in-process on a schedule (30-60 min), fetches LP data from the Riot API, recalculates share prices, and executes pending orders (forward pricing model).
- **SQLite** stores users, tracked players, portfolios, and the transaction ledger.

## Authentication

Authentication is delegated to an external Identity-Aware Proxy (e.g., Zitadel/Pangolin). The backend identifies users by reading the `X-Remote-User` HTTP header. Do not implement JWT, password hashing, or login forms. New users are auto-provisioned with a starting balance on first request.

## Economy / Pricing Model

Share prices are derived from Absolute LP (`LP_abs = T*400 + D*100 + LP_current`). Price updates use: `P_new = P_old + (Delta_LP * Alpha * (1 + Beta*S)) * Gamma`, where Alpha=0.15 (base volatility), Beta=0.1 (momentum), S=streak counter, and Gamma includes per-account obfuscation + random noise. Floor price is 1.00.

Orders use **forward pricing**: orders are saved as PENDING, then executed at the *next* price update to prevent front-running.

## Style

- Write typed code (TypeScript for frontend, Python type hints for backend).
- Keep comments and documentation minimalistic. No emojis.
- After completing features or refactoring, always run lint and format checks before concluding.

## AGENTS.md

**Read [`AGENTS.md`](AGENTS.md) before starting any work.**