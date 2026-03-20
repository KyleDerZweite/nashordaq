# Nashordaq

> **Early Development Notice**
> This project is in early development and subject to breaking changes. It is intended for personal use only and is **not compliant with Riot Games Production API key requirements**. Self-hosting requires technical knowledge (Identity-Aware Proxy setup, environment configuration, containerized deployment). Use at your own risk.

A self-hosted fantasy stock market for a private League of Legends friend group.

Users trade shares in League of Legends players using virtual currency. Share prices fluctuate automatically based on real-time Ranked LP changes fetched from the Riot Games API.

## Try It

A live demo is available at **[demo-nashordaq.kylehub.dev](https://demo-nashordaq.kylehub.dev/)**. No account or API key needed -- just open the link and start trading with simulated data.

## What's Next? You Decide

Nashordaq started as a personal project for my friend group, and it does what I set out to build. But I'm curious whether others would find it useful too.

I'm considering turning this into a **hosted service with public rooms** -- one instance where any League friend group can create their own market without self-hosting anything. See the [Roadmap](docs/ROADMAP.md#future-v2) for more on this idea.

**If that sounds interesting to you:**
- Drop your thoughts in the [Discussions](https://github.com/KyleDerZweite/nashordaq/discussions) tab
- Leave a star if you'd want a hosted version
- Open an [Idea](https://github.com/KyleDerZweite/nashordaq/discussions/categories/ideas) for features you'd like to see

I'll keep developing this if there's a community that wants it.

## Features

- **Live Market** -- share prices update automatically from real Riot API data.
- **Portfolio Management** -- buy and sell orders based on player performance.
- **Leaderboards** -- global ranking of users by total portfolio net worth.
- **Self-Hosted** -- single-process deployment, no external database or message broker required.
- **Proxy-Ready Auth** -- designed to sit behind an Identity-Aware Proxy for zero-friction user management.

## Self-Hosting Guide

### Prerequisites

- A Linux server (or any host that runs containers)
- A domain name pointed at your server
- [Pangolin](https://github.com/fosrl/pangolin) (or another Identity-Aware Proxy) for authentication
- A Riot Games API key

### 1. Clone the repository

```bash
git clone https://github.com/KyleDerZweite/nashordaq.git
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
4. Ensure SSO authentication is enabled on the resource. Pangolin will automatically forward `Remote-User`, `Remote-Email`, and `Remote-Name` headers. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for a step-by-step Pangolin setup guide.

For defense-in-depth, enable trusted-proxy enforcement so direct backend requests are rejected unless they originate from your reverse proxy network:

```env
# Header injected by Pangolin (default: Remote-User)
NASHORDAQ_AUTH_HEADER=Remote-User

# Optional admin account list for the operator dashboard. Comma-separate
# multiple usernames if you want more than one admin.
NASHORDAQ_ADMIN_REMOTE_USERS=admin@yourdomain.com

# Optional hardening (recommended in production)
NASHORDAQ_ENFORCE_TRUSTED_PROXY=true
NASHORDAQ_TRUSTED_PROXY_CIDRS=10.89.0.0/16,127.0.0.1/32,::1/128
```

Set `NASHORDAQ_TRUSTED_PROXY_CIDRS` to the CIDR(s) used by your proxy/tunnel containers on the Podman network.

Newly tracked players cannot be bought until they receive their first successful market update, so users do not trade against the placeholder startup price.

Riot API timeout behavior is also configurable:

```env
NASHORDAQ_HTTP_TIMEOUT_SECONDS=10
NASHORDAQ_HTTP_CONNECT_TIMEOUT_SECONDS=5
```

When a user visits Nashordaq, Pangolin authenticates them first. The backend reads the forwarded header to identify the user. New users are automatically provisioned with the configured starting balance and then complete a one-time in-app self-onboarding step to link their Riot `game_name`, `tag_line`, and `display_name`.

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
