# Nashordaq

A self-hosted fantasy stock market for a private League of Legends friend group.

Users trade shares in League of Legends players using virtual currency. Share prices fluctuate automatically based on real-time Ranked LP changes fetched from the Riot Games API.

## Features

- **Live Market** -- share prices update automatically from real Riot API data.
- **Portfolio Management** -- buy and sell orders based on player performance.
- **Leaderboards** -- global ranking of users by total portfolio net worth.
- **Self-Hosted** -- single-process deployment, no external database or message broker required.
- **Proxy-Ready Auth** -- designed to sit behind an Identity-Aware Proxy for zero-friction user management.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vite, React, TypeScript, TailwindCSS, TanStack Query |
| Backend | FastAPI (Python) |
| Database | SQLite (via aiosqlite) |
| Background Tasks | APScheduler (in-process) |
| Deployment | Podman-compose |

## Self-Hosting Guide

### Prerequisites

- A Linux server (or any host that runs containers)
- A domain name pointed at your server
- [Pangolin](https://github.com/fosrl/pangolin) (or another Identity-Aware Proxy) for authentication
- A Riot Games API key

### 1. Clone the repository

```bash
git clone https://github.com/youruser/nashordaq.git
cd nashordaq
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in every value. The sections below explain each one.

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

### 6. Set up authentication with Pangolin

Nashordaq does not handle login or passwords. It expects an Identity-Aware Proxy to authenticate users and forward their identity via an HTTP header.

**Using [Pangolin](https://github.com/fosrl/pangolin):**

1. Install and configure Pangolin on your server following the [Pangolin documentation](https://docs.fossorial.io/).
2. Create a new site/resource in Pangolin pointing to your Nashordaq instance.
3. Enable authentication on the resource. Pangolin will handle login (SSO, OIDC, etc.) and inject headers into proxied requests.
4. Ensure the header name in Pangolin matches the `NASHORDAQ_AUTH_HEADER` value in your `.env` (default: `X-Remote-User`).

When a user visits Nashordaq, Pangolin authenticates them first. The backend reads the forwarded header to identify the user. New users are automatically provisioned with the configured starting balance.

### 7. Start the application

No external database or message broker to set up -- Nashordaq uses SQLite (created automatically on first run) and an in-process scheduler.

```bash
podman-compose up -d
```

The SQLite database file is stored at the path configured by `NASHORDAQ_DATABASE_URL` (default: `data/nashordaq.db`). Back up this file to preserve all data.

## Development

### Backend (Python/FastAPI)

```bash
cd backend
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
