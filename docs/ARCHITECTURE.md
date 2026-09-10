# Architecture

## Overview

Nashordaq is a single-process Python application backed by SQLite. The FastAPI server, background scheduler, and database all run within one process -- no external services required beyond the Riot Games API.

The current architecture is single-tenant: one deployment runs one private market for one group. Demo mode is optional. The long-term product strategy is documented separately in [PRODUCTIZATION_PLAN.md](PRODUCTIZATION_PLAN.md).

```
                   +-----------+
                   |   Nginx/  |
                   |  Pangolin |   (Identity-Aware Proxy)
                   +-----+-----+
                         |  Remote-Email header
                         |  Remote-User fallback
                         v
+----------------------------------------------------------+
|  FastAPI Application                                     |
|                                                          |
|  Routers          Auth          Scheduler (APScheduler)  |
|  /api/user/*      Remote-Email  dynamic-interval job     |
|  /api/market/*    primary key   - Fetch LP from Riot     |
|  /api/orders/*    auto-provision- Update prices          |
|  /api/portfolio   new users     - Execute pending orders |
|  /api/leaderboard                                        |
|                                                          |
|  Pricing Engine   Riot Client   Self-onboarding          |
|  LP_abs, IPO,     httpx async   Creates tracked players  |
|  dynamic price    3 API calls   at first user login      |
|                   per player                             |
+---------------------------+------------------------------+
                            |
                            v
                  +-------------------+
                  |  SQLite (WAL)     |
                  |  nashordaq.db     |
                  +-------------------+
```

## Frontend

- **Vite + TypeScript:** Build toolchain.
- **TailwindCSS:** Utility-first styling.
- **TanStack Query:** Server state management and caching.

## Backend

- **FastAPI:** Async Python web framework. Hosts all REST endpoints and the scheduler in a single process.
- **SQLAlchemy 2.0:** ORM layer using the `Mapped`/`mapped_column` declarative style. No SQLModel.
- **SQLite (aiosqlite):** Embedded database with WAL mode enabled for concurrent read/write access.
- **APScheduler v3:** In-process `AsyncIOScheduler` that wakes every 30 seconds and runs a full market update when the dynamic interval (derived from tracked-player count and the Riot rate-limit budget) is due. See [DEPLOYMENT.md](DEPLOYMENT.md) "Market Update Cadence".
- **httpx:** Async HTTP client for Riot Games API calls.

## Data Model

Current SQLAlchemy tables:

| Table | Purpose |
|---|---|
| `users` | User accounts, identity fields, balances, debt state, demo flag, linked player. |
| `tracked_players` | Riot accounts whose prices are tracked in the market. |
| `holdings` | Aggregate user-player share positions. |
| `holding_lots` | FIFO lots used for hold-period enforcement and buy reverts. |
| `orders` | Manual and system-generated orders with execution details. |
| `transactions` | Immutable executed trade ledger. |
| `price_history` | Share-price history across market refreshes and trades. |
| `player_matches` | Per-match LP attribution and pricing audit trail. |
| `playing_income_entries` | Match-based virtual income ledger for linked players. |
| `bank_ledger_entries` | Rescue-loan borrowing, interest, and repayment ledger. |
| `user_wealth_snapshots` | Time-series snapshots for balance insights and admin views. |
| `gamba_positions` | Private-only optional leveraged side-position records. Not part of the planned production-compliant product path. |
| `poro_spawns` | Server-side poro reward spawns and claims. |
| `user_poro_states` | Per-user poro scheduling state. |

## API Surface

All endpoints are prefixed with `/api` except the health check.

Core endpoints:

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Health check |
| GET | `/api/system/status` | No | Scheduler, market, demo, and feature-flag status |
| GET | `/api/user/me` | Yes | Current user profile (auto-provisions on first call) |
| POST | `/api/user/onboarding` | Yes | Link user Riot account and create tracked player |
| PUT | `/api/user/profile` | Yes | Update linked Riot account |
| GET | `/api/market/players` | No | List all tracked players with current prices |
| GET | `/api/market/players/{id}` | No | Player detail with price history |
| GET | `/api/market/quote` | Yes | Ad hoc Riot rank lookup |
| GET | `/api/market/account` | Yes | Riot account verification by Riot ID |
| POST | `/api/orders` | Yes | Place a buy or sell order |
| GET | `/api/orders` | Yes | List user's orders |
| GET | `/api/orders/recent` | Yes | List recent executed orders |
| GET | `/api/orders/{id}` | Yes | Order detail with execution breakdown |
| DELETE | `/api/orders/{id}` | Yes | Cancel or revert an eligible order |
| GET | `/api/portfolio` | Yes | Current holdings, balance, debt, and total net worth |
| GET | `/api/leaderboard` | No | Ranked user leaderboard |

Additional optional/admin endpoints exist for bank, poro, simulation, demo helpers, admin dashboards, and the private-only `gamba` feature.

## Authentication

Authentication is handled by Pangolin, which acts as an Identity-Aware Proxy. When SSO authentication is configured, Pangolin forwards identity headers to downstream services (`Remote-User`, `Remote-Email`, `Remote-Name`, `Remote-Role`). The backend identifies users primarily from `Remote-Email` (configurable via `NASHORDAQ_REMOTE_EMAIL_HEADER`), with `Remote-User` retained as a legacy fallback (`NASHORDAQ_AUTH_HEADER`). New users are auto-provisioned with the starting balance and then complete a one-time self-onboarding step to link their Riot account. In demo mode, the backend can also create temporary cookie-backed demo users when no auth headers are present.

## Security Boundary and Hardening

- **Primary trust boundary:** The backend is intended to be reachable only through Pangolin/Newt + IAP.
- **Identity source:** The application identifies users primarily from `NASHORDAQ_REMOTE_EMAIL_HEADER` (`Remote-Email` by default), with `NASHORDAQ_AUTH_HEADER` (`Remote-User`) as a legacy fallback.
- **Trusted proxy enforcement (defense-in-depth):**
  - `NASHORDAQ_ENFORCE_TRUSTED_PROXY=true` rejects auth requests from non-trusted source IPs.
  - `NASHORDAQ_TRUSTED_PROXY_CIDRS` defines allowed proxy/tunnel CIDR ranges.
- **Production-compliant feature framing:** The future production-facing product path excludes the private-only `gamba` mechanic entirely and positions Nashordaq as a virtual investing and social market product, not a gambling application.
- **Outbound resiliency:** Riot API requests use configurable timeouts:
  - `NASHORDAQ_HTTP_TIMEOUT_SECONDS`
  - `NASHORDAQ_HTTP_CONNECT_TIMEOUT_SECONDS`
- **CORS posture:** Origins are explicitly configured via `NASHORDAQ_CORS_ORIGINS`, with only required methods/headers enabled.

## Scheduler Pipeline

The market update job runs as a single atomic operation:

1. **Fetch LP:** For each tracked player, call the Riot Games API (account lookup, summoner lookup, league entries). Rate-limit-aware stagger between requests (configurable via `NASHORDAQ_RIOT_REQUEST_STAGGER_SECONDS`, default 200ms). Update interval is dynamically computed from the number of trackable players and the API rate-limit budget (`NASHORDAQ_RIOT_RATE_LIMIT_REQUESTS` / `NASHORDAQ_RIOT_RATE_LIMIT_WINDOW_SECONDS`).
2. **Update prices:** Compute new `LP_abs`, apply the pricing formula (IPO pricing on first fetch, dynamic pricing thereafter), record a `PriceHistory` entry.
3. **Execute orders:** Process all PENDING orders in FIFO order. Validate balances/holdings at execution time. Create `Transaction` records for executed orders.
4. **Commit:** All changes are committed in a single database transaction.

## Infrastructure

- **Podman-compose:** Manages containers for the frontend and backend.
- **No external services:** No Redis, no PostgreSQL, no separate worker process. SQLite and APScheduler keep the deployment minimal.

## File Structure

```
backend/
  app/
    main.py                     # FastAPI app, lifespan, middleware, router mounts
    config.py                   # Pydantic settings (env vars with NASHORDAQ_ prefix)
    database.py                 # Async SQLAlchemy engine, session factory, init_db
    models.py                   # ORM models for market, debt, poro, income, and audit state
    schemas.py                  # Pydantic request/response models
    auth.py                     # Remote-Email auth dependency, Remote-User fallback, auto-provisioning
    pricing.py                  # Pure pricing functions (LP_abs, IPO, dynamic price, streak, market impact)
    riot.py                     # Riot Games API client (httpx)
    banking.py                  # Rescue-loan and wealth snapshot helpers
    poro.py                     # Poro scheduling and claim helpers
    scheduler.py                # APScheduler jobs (market, poro, demo)
    routers/
      user.py                   # User profile, onboarding, balance insights
      market.py                 # Market list/detail endpoints
      orders.py                 # Order placement, history, revert
      portfolio.py              # Portfolio summary
      leaderboard.py            # Leaderboard endpoints
      bank.py                   # Rescue-loan endpoints
      poro.py                   # Poro state and claim endpoints
      gamba.py                  # Private-only side-position endpoints
      admin.py                  # Admin dashboards and maintenance actions
      simulation.py             # Pricing simulation endpoints
  tests/
    conftest.py                 # Fixtures (in-memory SQLite, auth client, seeded data)
    test_api.py                 # Health and system status tests
    test_riot.py                # Riot API client tests
    test_pricing.py             # Pricing engine unit tests
    test_auth.py                # Auth auto-provisioning tests
    test_orders.py              # Order placement/cancellation/revert tests
    test_market.py              # Market data endpoint tests
    test_portfolio.py           # Portfolio calculation tests
    test_leaderboard.py         # Leaderboard ranking tests
    test_bank.py                # Rescue-loan tests
    test_gamba.py               # Private-only side-position tests
    test_poro.py                # Poro reward tests
    test_scheduler.py           # Market update and ledger processing tests
```
