# Architecture

## Overview

Nashordaq is a single-process Python application backed by SQLite. The FastAPI server, background scheduler, and database all run within one process -- no external services required beyond the Riot Games API.

```
                   +-----------+
                   |   Nginx/  |
                   |  Pangolin |   (Identity-Aware Proxy)
                   +-----+-----+
                         |  Remote-User header
                         v
+--------------------------------------------------------+
|  FastAPI Application                                   |
|                                                        |
|  Routers          Auth          Scheduler (APScheduler) |
|  /api/user/*      X-Remote-     30-min interval job     |
|  /api/market/*    User header   - Fetch LP from Riot    |
|  /api/orders/*    auto-provision- Update prices          |
|  /api/portfolio   new users     - Execute pending orders |
|  /api/leaderboard                                       |
|                                                        |
|  Pricing Engine   Riot Client   Self-onboarding         |
|  LP_abs, IPO,     httpx async   Creates tracked players |
|  dynamic price    3 API calls   at first user login     |
|                   per player                            |
+---------------------------+----------------------------+
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
- **APScheduler v3:** In-process `AsyncIOScheduler` that runs the market update job on a configurable interval (default 30 minutes).
- **httpx:** Async HTTP client for Riot Games API calls.

## Data Model

Six tables managed by SQLAlchemy ORM:

| Table | Purpose |
|---|---|
| `users` | User accounts (auto-provisioned). Stores username and cash balance. |
| `tracked_players` | League of Legends accounts whose share prices are tracked. Added during user onboarding. |
| `holdings` | User-player share positions. One row per pair, quantity updated in place. |
| `orders` | Buy/sell orders. Created as PENDING, resolved to EXECUTED or CANCELLED by the scheduler. |
| `transactions` | Immutable ledger. One record per executed order. |
| `price_history` | Time series of player share prices, one row per player per update cycle. |

## API Endpoints

All endpoints are prefixed with `/api` except the health check.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Health check |
| GET | `/api/user/me` | Yes | Current user profile (auto-provisions on first call) |
| POST | `/api/user/onboarding` | Yes | Link user Riot account and create tracked player |
| GET | `/api/market/players` | No | List all tracked players with current prices |
| GET | `/api/market/players/{id}` | No | Player detail with price history |
| POST | `/api/orders` | Yes | Place a buy or sell order |
| GET | `/api/orders` | Yes | List user's orders (filterable by status) |
| DELETE | `/api/orders/{id}` | Yes | Cancel a pending order |
| GET | `/api/portfolio` | Yes | User's holdings, balance, and total net worth |
| GET | `/api/leaderboard` | No | All users ranked by total portfolio value |

## Authentication

Authentication is handled by Pangolin, which acts as an Identity-Aware Proxy. When SSO authentication is configured, Pangolin forwards identity headers to downstream services (`Remote-User`, `Remote-Email`, `Remote-Name`, `Remote-Role`). The backend reads the `Remote-User` header (configurable via `NASHORDAQ_AUTH_HEADER`) and auto-provisions new users with a starting balance of 10,000. Each user then completes a one-time self-onboarding step to link their Riot account. No passwords, JWTs, or login forms exist in the application.

## Security Boundary and Hardening

- **Primary trust boundary:** The backend is intended to be reachable only through Pangolin/Newt + IAP.
- **Identity source:** The application identifies users only from the configured auth header (`NASHORDAQ_AUTH_HEADER`, default `Remote-User`).
- **Trusted proxy enforcement (defense-in-depth):**
  - `NASHORDAQ_ENFORCE_TRUSTED_PROXY=true` rejects auth requests from non-trusted source IPs.
  - `NASHORDAQ_TRUSTED_PROXY_CIDRS` defines allowed proxy/tunnel CIDR ranges.
- **Outbound resiliency:** Riot API requests use configurable timeouts:
  - `NASHORDAQ_HTTP_TIMEOUT_SECONDS`
  - `NASHORDAQ_HTTP_CONNECT_TIMEOUT_SECONDS`
- **CORS posture:** Origins are explicitly configured via `NASHORDAQ_CORS_ORIGINS`, with only required methods/headers enabled.

## Scheduler Pipeline

The market update job runs as a single atomic operation:

1. **Fetch LP:** For each tracked player, call the Riot Games API (account lookup, summoner lookup, league entries). Rate limit delays of 100ms between players.
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
    models.py                   # 6 ORM tables (User, TrackedPlayer, Holding, Order, Transaction, PriceHistory)
    schemas.py                  # Pydantic request/response models
    auth.py                     # Remote-User auth dependency, auto-provisioning
    pricing.py                  # Pure pricing functions (LP_abs, IPO, dynamic price, streak, gamma)
    riot.py                     # Riot Games API client (httpx)
    scheduler.py                # APScheduler job (LP fetch, price update, order execution)
    routers/
      user.py                   # GET /api/user/me
      market.py                 # GET /api/market/players, GET /api/market/players/{id}
      orders.py                 # POST, GET, DELETE /api/orders
      portfolio.py              # GET /api/portfolio
      leaderboard.py            # GET /api/leaderboard
  tests/
    conftest.py                 # Fixtures (in-memory SQLite, auth client, seeded data)
    test_api.py                 # Health check tests
    test_riot.py                # Riot API client tests
    test_pricing.py             # Pricing engine unit tests
    test_auth.py                # Auth auto-provisioning tests
    test_orders.py              # Order placement/cancellation tests
    test_market.py              # Market data endpoint tests
    test_portfolio.py           # Portfolio calculation tests
    test_leaderboard.py         # Leaderboard ranking tests
```
