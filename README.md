# Nashordaq

Local setup and username/password sessions are implemented from [ADR-0001](docs/adr/0001-self-host-baseline.md). Standalone Compose packaging, member invitations and isolated demo sessions are implemented. Recovery remains a subsequent slice of [spec #19](https://github.com/KyleDerZweite/nashordaq/issues/19).

> **Early Development Notice**
> This project is in early development and subject to breaking changes. It is intended for personal use only and is **not compliant with Riot Games Production API key requirements**. Self-hosting requires technical knowledge (environment configuration and containerized deployment). The future production-facing path documented in this repo excludes the private-only `gamba` mechanic entirely.

A self-hosted virtual share market for a private League of Legends friend group.

Users trade shares in League of Legends players using virtual currency. Share prices fluctuate automatically based on real-time Ranked LP changes fetched from the Riot Games API.

## Try It

A live demo is available at **[demo-nashordaq.kylehub.dev](https://demo-nashordaq.kylehub.dev/)**. The previously deployed demo may use older code. This development revision requires demo/demo login when demo mode is explicitly enabled. Each visitor has separate temporary game state in a shared simulated market. Sign out to delete personal state immediately. Inactivity expires access after 30 minutes, and automatic cleanup follows within one minute. Closing a browser does not guarantee immediate deletion.

## What's Next

Nashordaq started as a personal project for my friend group, and it does what I set out to build. The direction now is Nashordaq as a **self-hosted private-league product for friend groups**. There is no hosted version planned.

The next areas of interest are more trackable queues as selectable shares, such as Ranked Flex, TFT Ranked, and TFT Double Up alongside Ranked Solo. See the [Roadmap](docs/ROADMAP.md#future-v2) and open GitHub issues for the current plan.

**If that sounds interesting to you:**
- Drop your thoughts in the [Discussions](https://github.com/KyleDerZweite/nashordaq/discussions) tab
- Leave a star if you self-host it with your group
- Open an [Idea](https://github.com/KyleDerZweite/nashordaq/discussions/categories/ideas) for features you'd like to see

## Features

- **Live Market** -- share prices update automatically from real Riot API data.
- **Portfolio Management** -- buy and sell orders based on player performance.
- **Leaderboards** -- global ranking of users by total portfolio net worth.
- **Self-Hosted** -- single-process deployment, no external database or message broker required.
- **Local authentication**: username/password accounts, operator setup and revocable sessions.

## Self-hosting

Use the [deployment guide](docs/DEPLOYMENT.md) for the release-tag installation procedure, shared Docker Compose and Podman Compose commands, account setup, persistence and HTTPS configuration. Containers build locally from pinned inputs. The frontend publishes a configurable HTTP port, and SQLite stays in the host directory `./data`.

Set `NASHORDAQ_PUBLIC_URL` to your browser-visible LAN HTTP or operator-provided HTTPS origin. No domain, external authentication or tunnel is required for LAN access. Account setup and login work without a Riot key; live Riot onboarding and market updates require one. Gamba is disabled by default and requires explicit private-use opt-in.

Start the standalone version with a fresh data directory. Preserve old proxy installation data separately. Startup rejects the old database without migrating or deleting it. No standalone release has been published from this implementation yet; an implementation-branch checkout is development verification.

## Development

### Backend (Python/FastAPI)

```bash
cd backend
mkdir -p data                     # SQLite directory
uv sync                            # Install dependencies
uv run uvicorn app.main:app --reload  # Start dev server
uv run pytest -v                   # Run tests
uv run ruff check .                # Lint
uv run ruff format .               # Format
```

### Frontend (React/TypeScript)

```bash
cd frontend
corepack pnpm@10.34.7 install --frozen-lockfile  # Install dependencies
pnpm run dev                       # Start dev server
pnpm run build                     # Production build
pnpm run lint                      # Lint (ESLint)
pnpm run format                    # Format (Prettier)
```

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). See [LICENSE](LICENSE).
