# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Locally built Docker Compose and Podman Compose packaging, WAL-aware live backup, fresh restore and supported-schema update preflight.
- Isolated temporary demo sessions, permanent streamer aliases and member-visible administrator game interventions.

### Security

- `/api/market/quote` and `/api/market/account` now require authentication; previously they were an unauthenticated proxy to the Riot API using the server's API key.
- Enforced `NASHORDAQ_GAMBA_MAX_ACTIVE_POSITIONS_PER_USER` (default 1); the setting existed but was never checked, allowing unlimited concurrent leveraged positions.
- Replaced proxy-header identity with local username/password accounts, one-time setup, invitations and revocable sessions. Added password changes, reset links and server-side administrator recovery.
- nginx now sends `X-Frame-Options`, `X-Content-Type-Options`, and `Referrer-Policy` headers.
- Dependabot auto-merge now only merges patch/minor updates; major bumps (or PRs whose version change cannot be determined) are left for manual review.
- Capped simulation requests at 20 parameter sets; all simulation endpoints now require a local session.

### Fixed

- All balance mutations in order execution, buy reverts, gamba, playing income, and settlement now round to cents, preventing float drift in stored balances.
- SQLite now enables foreign-key enforcement and a 15s busy timeout (previously FK constraints were silently unenforced).
- `/api/market/quote` and `/api/market/account` return 502 with a clear message when the Riot API fails unexpectedly, instead of an unhandled 500.
- Frontend renders FastAPI validation errors (422) as readable messages instead of `[object Object]`.
- `demo.podman-compose.yaml` sets `NASHORDAQ_DEMO_MODE_ENABLED=true` explicitly instead of relying on the operator's `.env`.

### Docs

- Reconciled English operator, architecture and product documentation with the standalone baseline and recorded acceptance evidence with remaining integration checks.
- Corrected `docs/ARCHITECTURE.md` scheduler cadence (dynamic interval, not a fixed 30 minutes) and `docs/ECONOMY_MECHANICS.md` gamba mark value (mark-to-market, not locked cash).

- Clarified that the future production-facing Nashordaq product path excludes the private-only `gamba` mechanic entirely and is framed as a virtual investing and social market product.

## [0.2.0] - 2026-03-20

### Added

- **Per-match pricing engine** - every ranked match is individually detected, attributed its LP delta, and priced sequentially. A 3-game session now produces three distinct price movements instead of one averaged move.
- **Gamba (leveraged positions)** - place leveraged bets on a randomly selected player. Lock in a cash amount, hold for 24-168 hours, and settle at a 2.0x-4.0x multiplier based on hold duration. Can be toggled on/off via `NASHORDAQ_GAMBA_ENABLED`.
- **Playing income** - linked players earn passive credits when their Riot account completes ranked matches. Wins pay more than losses. First 3 games per day pay full rate, subsequent games at 65%.
- **Bank & rescue loans** - when debt-adjusted net worth drops below 250, claim a one-time 750-credit rescue loan. 2% flat interest charged every 120 hours.
- **Market impact (slippage)** - orders now move the market price. Impact scales with order size relative to configurable liquidity depth.
- **Minimum holding period** - shares must be held for a configurable duration before they can be sold. Prevents instant flip arbitrage.
- **Streamer mode** - toggle name obfuscation across the entire UI for streaming or screenshots.

### Changed

- **Full economy reset** - all balances restored to 1000 + retroactive playing income. All trading history cleared. Prices replayed from match data through the new pricing formulas.
