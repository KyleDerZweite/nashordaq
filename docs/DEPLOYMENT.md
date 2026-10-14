# Deployment Guide

Local setup, invitations and revocable sessions are implemented. Container packaging still uses the original tunnel wiring until the deployment slice of [spec #19](https://github.com/KyleDerZweite/nashordaq/issues/19). The full standalone installation procedure is not yet delivered. No external authentication service is required by the application.

## Local account setup

Set `NASHORDAQ_PUBLIC_URL` to the browser-visible frontend origin, such as `http://localhost:5173` for development or `https://market.example.com` behind your TLS reverse proxy. HTTPS enables Secure session cookies even when the backend receives HTTP. Proxy identity headers and forwarded scheme headers cannot grant access or weaken that policy.

Start with a separate empty SQLite directory. Startup rejects the previous proxy database before changing its schema or WAL mode. Stop the previous installation and preserve its data, including WAL/SHM files, before selecting a fresh directory. Nothing is deleted or migrated automatically.

Open the setup link printed in the backend log. Choose a username and a password with at least 12 characters. Only that link creates the sole administrator. Successful setup signs you in and closes setup permanently. An unused link rotates on restart. Normal login sessions last seven days, reload preserves a valid session, and logout revokes the current session immediately.

Setup, login and administrator access do not require a Riot key. Live Riot onboarding and updates still require one. Recovery flows, administrator participation and explicit isolated demo sessions are separate implementation slices. Demo access currently fails closed.

The [Architecture](ARCHITECTURE.md#authentication-and-session-trust-boundary) owns the security contract. Every state-changing API request requires `X-Nashordaq-CSRF: 1`. Browser origins are checked; native API clients may omit Origin when sending this header. All game-data endpoints require the local session cookie.

## Riot configuration and recovery

Local setup, login and administrator access work with an empty or rejected Riot key. The authenticated market and player-setup views show whether the key is missing, rejected, rate limited or affected by an upstream outage. Status never returns the key. A configured key starts as unverified until Riot accepts a request.

New player links require a successful account and ranked Solo Queue lookup. A failed lookup leaves the local account usable and creates no linked tracked player. Retry the same player after recovery. Real refreshes roll back their entire transaction when Riot authentication, rate limits or network availability fail. Existing prices and history remain unchanged. Demo uses its own simulated market and requires no key.

For a missing or rejected key, replace `NASHORDAQ_RIOT_API_KEY` in the protected environment file and restart the backend process with that environment. Container environments are fixed at creation: recreate the stack after editing the file, rather than using a Compose `restart` that retains its old environment. Use `podman-compose up -d --force-recreate` or the corresponding `docker compose` command. Keep the existing data bind mount and database. Do not repeat setup or create another administrator.

Sign in again if needed, retry player setup, and check authenticated system status and the next due market refresh. A rate limit needs a later retry; a Riot outage needs upstream recovery. No reinstall is required. Controlled-response tests verify failure handling and retry behavior. Live linking and refresh recovery require an operator-owned valid Riot key and a separately recorded check; they have not been verified for the no-key local installation.

## Invite members

Sign in as the administrator and select Admin View. In Member invitations, select Create invitation. Copy the generated link and share it privately with the intended member. The link is shown only after creation; later visits show lifecycle metadata without the secret. Create another invitation if you lose an unused link, and revoke the lost invitation. The frontend omits query strings and referrers from access logs. Configure any external reverse proxy to do the same for access-link routes.

Each invitation expires after seven days and admits one member. The invited member opens the complete `/invite?token=...` link and chooses a username and a password of at least 12 characters. Registration signs them in and removes the token from the browser URL. Email and Riot details are unnecessary for account creation. Riot onboarding remains a separate step after login.

Member invitations lists active, consumed, revoked and expired links. Select Revoke beside an active invitation to withdraw access. An invalid, expired, revoked or consumed link cannot create an account. Ask the administrator for a new link when registration reports that the invitation is unavailable. A validation error or taken username leaves the invitation usable for another attempt.

## Configuration

Copy `.env.example` to `.env`. Relevant settings for this slice:

| Variable | Default | Description |
|---|---|---|
| `NASHORDAQ_PUBLIC_URL` | `http://localhost:8080` | Frontend origin for setup/invitation links and HTTPS cookie policy |
| `NASHORDAQ_CORS_ORIGINS` | `http://localhost:5173` | Explicit allowed frontend origins |
| `NASHORDAQ_DATABASE_URL` | `sqlite+aiosqlite:///data/nashordaq.db` | SQLite path relative to the backend directory |
| `NASHORDAQ_RIOT_API_KEY` | empty | Optional for authentication, required for live Riot data |
| `NASHORDAQ_STARTING_BALANCE` | `1000.0` | Initial virtual balance |
| `NASHORDAQ_RIOT_API_BASE_URL` | `https://europe.api.riotgames.com` | Riot account/match region |
| `NASHORDAQ_RIOT_API_REGION_URL` | `https://euw1.api.riotgames.com` | Riot league/summoner region |

Proxy-header and configured-admin-list settings have been removed. Exactly one administrator comes from setup.

### Market Update Cadence

Market updates are dynamic:

- The scheduler wakes every 30 seconds and runs a full Riot fetch only when the required interval is due.
- The interval derives from the trackable player count and the Riot rate-limit budget. See `ARCHITECTURE.md` for the calculation.

The scheduler wakes every 30 seconds internally and runs immediately on startup, but only performs a full Riot fetch/order execution cycle when the dynamic interval is due.

## 2. Tracked Players

Tracked players are created through user self-onboarding. On first authenticated visit, each user must enter their own Riot `game_name` and `tag_line`. After submission, their linked Riot account is added to the tracked player set.

Players cannot be bought until they have received their first successful market update. This avoids trading against the placeholder pre-update price.

This replaces static player seeding and does not require editing JSON files during deployment.

If you are preparing a public-facing, compliance-oriented, or future production-style deployment, set:

```env
NASHORDAQ_GAMBA_ENABLED=false
```

## 3. Build and Run

```bash
podman-compose up --build -d
```

The frontend is served on port 80. The backend runs internally on port 8000 with Nginx reverse-proxying `/api/` requests.

## 4. HTTP entry point

The supplied Compose file still contains its legacy Newt transport. Its replacement with a configurable LAN HTTP entry point belongs to the deployment slice. A reverse proxy may terminate public HTTPS but never establishes application identity. Configure `NASHORDAQ_PUBLIC_URL` for the visible HTTPS origin and preserve the Host header, including any external port.

## 5. Verify

Open the frontend without a session. It displays login or setup guidance and fetches only authentication metadata. Open the setup link from the operator log, create the administrator, reload, sign out and sign in again. After sign-out, direct game API requests return 401, including requests carrying forged identity headers.

`GET /health` remains public. `/api/auth/status` contains only setup and deployment-mode information. `/api/system/status` and all game queries require login.

## 6. Local development

Start the backend with a fresh SQLite directory:

```bash
cd backend
mkdir -p data
NASHORDAQ_PUBLIC_URL=http://localhost:5173 uv run uvicorn app.main:app --reload
```

Start the frontend in another terminal:

```bash
cd frontend
pnpm run dev
```

Open the setup URL printed by the backend, then use normal browser login. Vite proxies `/api` to `http://localhost:8000` while preserving Host. No browser header-injection extension is needed.

For API clients, log in and retain the session cookie:

```bash
curl -c /tmp/nashordaq-cookies -H 'X-Nashordaq-CSRF: 1' \
  -H 'Content-Type: application/json' \
  -d '{"username":"your-user","password":"your-password"}' \
  http://localhost:8000/api/auth/login
curl -b /tmp/nashordaq-cookies http://localhost:8000/api/user/me
```

Use disposable credentials when running examples and keep cookie files private.
