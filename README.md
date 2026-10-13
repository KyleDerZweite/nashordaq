# Nashordaq

Local setup and username/password sessions are implemented from [ADR-0001](docs/adr/0001-self-host-baseline.md). The complete standalone deployment, invitations, recovery and explicit demo sessions remain subsequent slices of [spec #19](https://github.com/KyleDerZweite/nashordaq/issues/19).

> **Early Development Notice**
> This project is in early development and subject to breaking changes. It is intended for personal use only and is **not compliant with Riot Games Production API key requirements**. Self-hosting requires technical knowledge (environment configuration and containerized deployment). The future production-facing path documented in this repo excludes the private-only `gamba` mechanic entirely.

A self-hosted virtual share market for a private League of Legends friend group.

Users trade shares in League of Legends players using virtual currency. Share prices fluctuate automatically based on real-time Ranked LP changes fetched from the Riot Games API.

## Try It

A live demo is available at **[demo-nashordaq.kylehub.dev](https://demo-nashordaq.kylehub.dev/)**. The previously deployed demo may use older code. This development revision denies demo access until explicit isolated demo sessions are implemented.

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

## Self-Hosting Guide

### Prerequisites

- A Linux server (or any host that runs containers)
- A domain name pointed at your server
- A Riot Games API key for live market data, optional for account setup and login

### 1. Clone the repository

```bash
git clone https://github.com/KyleDerZweite/nashordaq.git
cd nashordaq
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Open `.env` and configure the visible frontend origin. Leave the Riot key empty while setting up account access if needed.

### 3. Get a Riot Games API key

1. Go to the [Riot Developer Portal](https://developer.riotgames.com/).
2. Sign in with your Riot account.
3. Generate a **Development API Key** (regenerates every 24 hours) or apply for a **Personal/Production API Key** for persistent access.
4. Paste the key into `.env`:
   ```
   NASHORDAQ_RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```

### 4. Set your Riot API region

Nashordaq needs two API base URLs. Set them in `.env` based on the server your players play on.

| Player Server | `RIOT_API_BASE_URL` (continent) | `RIOT_API_REGION_URL` (platform) |
|---|---|---|
| EU West | `https://europe.api.riotgames.com` | `https://euw1.api.riotgames.com` |
| EU Nordic & East | `https://europe.api.riotgames.com` | `https://eun1.api.riotgames.com` |
| North America | `https://americas.api.riotgames.com` | `https://na1.api.riotgames.com` |
| Korea | `https://asia.api.riotgames.com` | `https://kr.api.riotgames.com` |

Full list: [Riot routing values](https://developer.riotgames.com/docs/lol#routing-values)

### 5. Configure your domain

Set `NASHORDAQ_DOMAIN` to the public domain you will serve the app on, and `NASHORDAQ_CORS_ORIGINS` to the full origin URL of your frontend:

```
NASHORDAQ_DOMAIN=nashordaq.yourdomain.com
NASHORDAQ_CORS_ORIGINS=https://nashordaq.yourdomain.com
```

### 6. Create the administrator

Set `NASHORDAQ_PUBLIC_URL` to the externally visible frontend origin. Use HTTP for LAN access and HTTPS when your reverse proxy terminates TLS. This setting controls the setup link and Secure cookie policy. Proxy identity headers have no effect.

Start with an empty SQLite data directory. The application rejects databases from the old proxy version before changing them. Preserve old data separately; there is no migration or automatic deletion.

On fresh startup, open the one-time setup link in the backend log and choose an administrator username and password. Passwords require at least 12 characters. The link creates the sole administrator and signs you in. Later visits use local login. Logout immediately ends the current session; normal sessions expire after seven days. Account access needs no Riot key.

See [Deployment](docs/DEPLOYMENT.md) for current development startup and [Architecture](docs/ARCHITECTURE.md#authentication-and-session-trust-boundary) for request protections. The supplied tunnel-based Compose packaging has not yet been replaced by the standalone deployment slice.

For any public-facing, compliance-oriented, or future production-style deployment, also set:

```env
NASHORDAQ_GAMBA_ENABLED=false
```

Newly tracked players cannot be bought until they receive their first successful market update, so users do not trade against the placeholder startup price.

Riot API timeout behavior is also configurable:

```env
NASHORDAQ_HTTP_TIMEOUT_SECONDS=10
NASHORDAQ_HTTP_CONNECT_TIMEOUT_SECONDS=5
```

Riot onboarding remains separate from local account access. Administrator participation and invitation registration arrive in their dedicated implementation slices.

### 7. Start the application

No external database or message broker to set up -- Nashordaq uses SQLite (created automatically on first run) and an in-process scheduler.

```bash
podman-compose up -d
```

The SQLite database file is stored at the path configured by `NASHORDAQ_DATABASE_URL` (default: `data/nashordaq.db`). Consistent live backup tooling is a separate implementation slice; copying an active SQLite file alone is insufficient.

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
pnpm install                       # Install dependencies
pnpm run dev                       # Start dev server
pnpm run build                     # Production build
pnpm run lint                      # Lint (ESLint)
pnpm run format                    # Format (Prettier)
```

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). See [LICENSE](LICENSE).
