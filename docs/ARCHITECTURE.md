# Architecture

## Overview

Nashordaq is a single-process Python application backed by SQLite. The FastAPI server, background scheduler, and database all run within one process. Local account access requires no external service or Riot key.

The current architecture is single-tenant: one deployment runs one private market for one group. Demo mode is optional. The long-term product strategy is documented separately in [PRODUCTIZATION_PLAN.md](PRODUCTIZATION_PLAN.md).

```text
Browser -> HTTP entry point -> FastAPI routers
                                  |
                    Local authentication and sessions
                                  |
                    SQLite accounts and game state

Scheduler -> Riot client -> existing pricing engine -> SQLite
```

## Frontend

- **Vite + TypeScript:** Build toolchain.
- **TailwindCSS:** Utility-first styling.
- **TanStack Query:** Server state management and caching.

## Backend

- **FastAPI:** Async Python web framework. Hosts all REST endpoints and the scheduler in a single process.
- **SQLAlchemy 2.0:** ORM layer using the `Mapped`/`mapped_column` declarative style. No SQLModel.
- **SQLite (aiosqlite):** Embedded database with WAL mode enabled for concurrent read/write access.
- **APScheduler v3:** In-process `AsyncIOScheduler` that wakes every 30 seconds and runs a full market update when the dynamic interval (derived from tracked-player count and the Riot rate-limit budget) is due. See [the scheduler pipeline](#scheduler-pipeline).
- **httpx:** Async HTTP client for Riot Games API calls.

## Data model

Current SQLAlchemy tables:

| Table | Purpose |
|---|---|
| `users` | Local usernames, password verifiers, sole administrator flag and personal game state. |
| `auth_sessions` | Hashed revocable session tokens and seven-day expiry. |
| `access_tokens` | Hashed one-time setup, invitation and password-reset tokens with lifecycle state. |
| `game_interventions` | Atomic administrator game changes with actor, affected member and concrete values. |
| `instance_metadata` | Supported standalone database schema version. |
| `identity_aliases` | Unique permanent League aliases for users and unlinked tracked-player presentation. |
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

## API routes

All endpoints are prefixed with `/api` except the health check.

Core endpoints:

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Health check |
| GET | `/api/auth/status` | No | Setup-required and deployment-mode metadata only |
| POST | `/api/auth/setup` | Setup token | Create the sole administrator and a session |
| POST | `/api/auth/login` | Credentials | Issue a local session |
| POST | `/api/auth/register` | Invitation token | Create a member account and session |
| POST | `/api/auth/invites` | Admin | Create and deliver a seven-day invitation link |
| GET | `/api/auth/invites` | Admin | Inspect invitation lifecycle metadata |
| DELETE | `/api/auth/invites/{id}` | Admin | Revoke an unused active invitation |
| POST | `/api/auth/password` | Yes | Verify current password, change own password and revoke all own sessions |
| POST | `/api/auth/resets` | Admin | Create and deliver a one-hour password-reset link |
| GET | `/api/auth/resets` | Admin | Inspect reset lifecycle and target account metadata |
| DELETE | `/api/auth/resets/{id}` | Admin | Revoke an unused active reset link |
| POST | `/api/auth/reset` | Reset token | Set the target password and revoke all target sessions atomically |
| GET | `/api/auth/session` | Yes | Verify the current session |
| POST | `/api/auth/logout` | Yes | Revoke the current session |
| GET | `/api/system/status` | Yes | Scheduler, market, demo, and feature-flag status |
| GET | `/api/user/me` | Yes | Current local user profile |
| POST | `/api/user/onboarding` | Yes | Link user Riot account and create tracked player |
| PUT | `/api/user/profile` | Yes | Update linked Riot account |
| GET | `/api/market/players` | Yes | List all tracked players with current prices |
| GET | `/api/market/players/{id}` | Yes | Player detail with price history |
| GET | `/api/market/quote` | Yes | Ad hoc Riot rank lookup |
| GET | `/api/market/account` | Yes | Riot account verification by Riot ID |
| POST | `/api/orders` | Yes | Place a buy or sell order |
| GET | `/api/orders` | Yes | List user's orders |
| GET | `/api/orders/recent` | Yes | List recent executed orders |
| GET | `/api/orders/{id}` | Yes | Order detail with execution breakdown |
| DELETE | `/api/orders/{id}` | Yes | Cancel or revert an eligible order |
| GET | `/api/portfolio` | Yes | Current holdings, balance, debt, and total net worth |
| GET | `/api/activity` | Yes | Administrator game interventions, newest first |
| GET | `/api/leaderboard` | Yes | Ranked user leaderboard |

Additional optional/admin endpoints exist for bank, poro, simulation, admin dashboards, and the private-only `gamba` feature.

## Standalone self-host baseline

The accepted direction is recorded in [ADR-0001](adr/0001-self-host-baseline.md). It uses standalone local accounts and sessions in the existing single-process, SQLite architecture. OAuth/OIDC and hosted multi-room operation are outside this baseline.

The application owns identity, authentication, invite access and administrator permissions. A deployment's reverse proxy owns public TLS termination and does not establish application identity. Game data requires an authenticated session. Demo operation is explicit and isolates each visitor's temporary game state.

Setup, invitations, password recovery, local login, logout, isolated demo sessions, standalone Compose packaging, administrator participation, member-visible game interventions and the private game-data gate are implemented. These follow [spec #19](https://github.com/KyleDerZweite/nashordaq/issues/19). Implementation is unreleased; [self-host acceptance](SELF_HOST_ACCEPTANCE.md) records technical evidence and remaining checks.

## Authentication and session trust boundary

`app/auth.py` owns credential verification, setup and invitation lifecycles, sessions and administrator authorization. Routers consume `CurrentUser`, `CurrentOnboardedUser` and `CurrentAdminUser`. The application startup calls persistence initialization before authentication setup. Authentication depends on persistence and does not call Riot or game services.

Fresh startup logs a setup link using `NASHORDAQ_PUBLIC_URL`. Only its 256-bit random token permits administrator creation. SQLite conditionally consumes the token and creates the administrator and initial session in one transaction. A unique partial index permits only one administrator. Restart rotates an unused setup link; completed setup stays closed.

Only the administrator creates, lists and revokes invitations. Creation delivers the usable link once; later listing contains only its ID, expiry, consumption, revocation and lifecycle status. Invitation tokens use 256 bits of randomness and only SHA-256 hashes enter SQLite. Registration conditionally consumes an unexpired, unused, unrevoked invitation and creates the member and session in one transaction. Invalid credentials and duplicate usernames preserve the invitation. Members have no administrator permissions and can register without Riot or email.

Password changes require the authenticated user's current credential. Reset creation, listing and revocation require the sole administrator. Reset links use hashed 256-bit tokens, expire after one hour and work once. Consumption, credential replacement, deletion of every target session and revocation of other unused target reset links share one SQLite transaction. Invalid, expired, revoked or replayed tokens change neither credentials nor sessions. Password changes and operator recovery use the same auth-owned replacement operation. Session issuance conditionally rechecks the verified credential under the SQLite write lock, so a concurrent password replacement cannot leave a new session based on the old password. Unrelated accounts retain access. These operations create no game-intervention entry and are unavailable in demo mode.

Persistence in `app/database.py` owns the initial complete standalone schema version 1, including `identity_aliases`, and read-only compatibility/integrity checks shared by startup and operator commands. Existing databases must retain the required column definitions, uniqueness, foreign keys, check constraints and sole-administrator index before startup changes persistent WAL mode or initializes setup. Missing tables in a marked database are rejected rather than created. Invalid administrator/demo flags and a missing administrator in existing normal account or completed-setup state fail before setup can reopen. Additional stored tables and columns are preserved. The first baseline supports complete version 1 restart/update only, with no released predecessor or generic migration framework. [Deployment](DEPLOYMENT.md#supported-standalone-updates-and-failed-update-recovery) owns supported transitions, candidate `check-update` preflight and exact-old-code/matching-backup recovery.

`app/operator.py` owns the server-side command boundary. It requires an explicit existing SQLite file, checks the supported schema through persistence before mutation and recovers the existing sole non-demo administrator. It accepts hidden terminal input or explicit protected stdin, with no password argument, public recovery endpoint, new administrator or startup/setup call. See [Deployment](DEPLOYMENT.md#change-and-recover-passwords) for the command procedure.

Passwords use salted scrypt verifiers with N=131072, r=8 and p=1. Two simultaneous derivations bound memory use. Normal session tokens have 256 bits of randomness and only their SHA-256 hashes enter SQLite. Sessions expire seven days after creation. Logout deletes the current session; each request validates its persisted session. The poro stream also validates its session before each protected event. Validation responses omit submitted values so they cannot echo credentials or access tokens.

The browser session cookie is `HttpOnly`, `SameSite=Strict`, scoped to `/`, and lasts seven days. `Secure` follows the explicit `NASHORDAQ_PUBLIC_URL` scheme. Configure its HTTPS origin when an operator reverse proxy terminates TLS, even though the backend receives HTTP. Forwarded identity and scheme headers cannot grant access or weaken cookie policy. LAN HTTP uses an HTTP public URL and an ordinary HTTP cookie.

Every state-changing `/api` request requires `X-Nashordaq-CSRF: 1`, including setup, login and logout. Browser `Origin` must match the request origin, configured public URL or an explicit CORS origin. `Origin: null` and cross-site Fetch Metadata are rejected. Native/API tools may omit Origin if they supply the custom header. CORS allows explicit origins and this header, so an unrelated browser origin cannot send an authorized mutation. Public endpoints contain only health and login/setup metadata. Market, leaderboard, history, simulation, system status and administrator data require a valid session.

API responses use `Cache-Control: no-store`. Responses and the frontend use `Referrer-Policy: no-referrer` to avoid disclosing setup or invitation URLs. Frontend access logs omit query strings and referrers. The frontend mounts game components after session validation and clears cached game queries when login ends. No proxy header creates a user, and no anonymous request creates demo state. Explicit demo mode accepts only demo/demo and creates a distinct temporary user. Sessions from the other mode cannot resume. Demo order lists and details authorize personal state against that user. Leaderboard aggregates contain only users in the requester's account mode. Leaderboard portfolio details enforce the same demo ownership boundary, and normal users cannot inspect temporary demo portfolios or order details, and their recent-order feed excludes preserved demo rows. Authentication owns deletion of personal state; scheduler invokes the same cleanup operation each minute. Shared tracked players, prices and history remain outside personal cleanup.

Demo sessions retain the same seven-day browser cookie, but the persisted deadline expires after thirty minutes without explicit activity. Only protected `POST /api/auth/activity` extends it, and it cannot revive an expired session. Normal requests, polling and SSE never extend it. The visible authenticated browser sends that signal on trusted pointer, keyboard, scroll or touch events, immediately on the first event. Further events within one second are coalesced into one trailing signal, so the last gesture in a burst is retained. The timer sends only when trusted human input is pending; it never sends a periodic renewal. Logout revokes access and deletes all temporary personal rows immediately. Browser closure does not guarantee immediate deletion.

Persistence checks the database marker before schema creation, alteration or switching SQLite to WAL. A database from the proxy version fails startup with instructions to preserve it and select a separate empty data directory. There is no automatic migration or deletion. Supported standalone databases preserve users, sessions and completed setup across restart.

## Operator persistence boundary

`app.operator` owns explicit-path maintenance commands. `app.persistence` creates live SQLite online backups and restores into absent database paths. A read transaction pins a consistent WAL snapshot while members continue writing. Snapshot checks require the matching release's complete schema, SQLite integrity and consistent foreign keys. The entire database is included, so later supported persisted state uses the same backup path. Private temporary files and exclusive publication prevent overwriting existing databases or sidecars. Restore does not run setup, credential recovery, Riot or the scheduler. See [Deployment](DEPLOYMENT.md#live-backup-and-fresh-restore) for storage and recovery commands.

## Riot availability boundary

`app/riot.py` owns configuration checks and safe upstream failure reports. Authenticated system status exposes its availability and operator instructions without credentials. Authentication and administration never call Riot to establish access. New links require successful ranked data; failed onboarding rolls back the player and link together. A real scheduler refresh rolls back its complete transaction on authentication, rate-limit or upstream availability failures, preserving existing prices and history. The simulated demo market remains independent.

## Scheduler pipeline

The market update job runs as a single atomic operation:

1. **Fetch LP:** For each tracked player, call the Riot Games API (account lookup, summoner lookup, league entries). Rate-limit-aware stagger between requests (configurable via `NASHORDAQ_RIOT_REQUEST_STAGGER_SECONDS`, default 200ms). Update interval is dynamically computed from the number of trackable players and the API rate-limit budget (`NASHORDAQ_RIOT_RATE_LIMIT_REQUESTS` / `NASHORDAQ_RIOT_RATE_LIMIT_WINDOW_SECONDS`).
2. **Update prices:** Compute new `LP_abs`, apply the pricing formula (IPO pricing on first fetch, dynamic pricing thereafter), record a `PriceHistory` entry.
3. **Execute orders:** Process all PENDING orders in FIFO order. Validate balances/holdings at execution time. Create `Transaction` records for executed orders.
4. **Commit:** All changes are committed in a single database transaction.

## Infrastructure

- **Docker Compose and Podman Compose:** Build and manage the frontend and backend through the shared `podman-compose.yaml`.
- **No external services:** No Redis, no PostgreSQL, no separate worker process. SQLite and APScheduler keep the deployment minimal.

## File structure

```
backend/
  app/
    main.py                     # FastAPI app, lifespan, middleware, router mounts
    config.py                   # Pydantic settings (env vars with NASHORDAQ_ prefix)
    database.py                 # Async SQLAlchemy engine, session factory, init_db
    models.py                   # ORM models for market, debt, poro, income, and audit state
    schemas.py                  # Pydantic request/response models
    auth.py                     # Local credentials, access tokens, sessions and demo cleanup
    identities.py               # Permanent League alias allocation
    interventions.py            # Atomic game intervention and activity record
    operator.py                 # Admin recovery, backup, restore and update preflight
    persistence.py              # Consistent online snapshots and fresh restore
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
    test_auth.py                # Authenticated account and onboarding tests
    test_local_auth.py          # Setup, sessions, CSRF and persistence boundary tests
    test_orders.py              # Order placement/cancellation/revert tests
    test_market.py              # Market data endpoint tests
    test_portfolio.py           # Portfolio calculation tests
    test_leaderboard.py         # Leaderboard ranking tests
    test_bank.py                # Rescue-loan tests
    test_gamba.py               # Private-only side-position tests
    test_poro.py                # Poro reward tests
    test_scheduler.py           # Market update and ledger processing tests
```

## Administrator participation and intervention boundary

Administrator permissions add access to account management and game administration. They do not restrict ordinary participant functions. `CurrentOnboardedUser` applies the same Riot-link requirement to members and the administrator. The frontend offers a dismissible linking flow and separate participant and administrator views, so account management remains available without Riot.

`app/interventions.py` owns rescue-access restoration. A conditional SQLite update changes the affected account's remaining uses from zero to one and inserts a typed `game_interventions` record in the same transaction. The administrator router builds its response before committing; failure rolls back both writes. Already available access returns 409 without an event. The economy and loan eligibility checks remain in the bank module.

`GET /api/activity` requires a session and exposes the actor and affected member through stable user IDs, usernames and optional linked Riot identity, UTC timestamp, intervention kind and previous/new values. It does not expose credentials, access tokens or email. The frontend renders this list for every member. Read-only administration and access management produce no intervention records. Demo visitors receive an empty activity list, preserving normal-market privacy if the operator changes deployment mode. The shared identity presentation interface renders its actor and affected member consistently with the other participant views.

## Identity presentation and alias persistence

`app/identities.py` owns permanent League alias allocation through a shared SQLAlchemy creation invariant. New administrator, member, demo-user and tracked-player records receive unique aliases in the same transaction as their creation. Allocation takes SQLite's writer lock before selecting an unused name. A pinned champion pool is followed by item and ability names; exhausting the complete pool rejects creation without consuming an invitation or saving a partial account. Existing aliases remain unchanged after Riot linking, renaming and restart. The initial complete version 1 schema includes the alias table. Startup assigns missing aliases within an otherwise compatible complete schema and retains existing assignments. It rejects partial development schemas; it does not add missing tables to a marked database.

Authenticated `GET /api/identities` provides the presentation directory. Linked tracked players resolve to their user's alias; unlinked tracked players retain their own alias. Normal requests exclude demo users. Demo requests expose only the requesting temporary user and mask linked identities belonging to excluded users. Shared market aliases remain available.

`useIdentityPresentation` is the shared frontend interface for participant and tracked-player names across market, portfolio, orders, leaderboard, administrator controls, activity, simulation and Gamba. Normal labels show username plus linked RiotName, with username-only fallback. Streamer Mode uses persisted aliases and suppresses Riot tags, identifying links and profile-editor values. A missing directory never falls back to a real name. The account editor offers an explicit action to leave Streamer Mode before editing. Streamer Mode is presentation privacy, not an additional API authorization rule.
