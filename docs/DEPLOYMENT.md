# Deployment guide

One installation runs one private market. Docker Compose and Podman Compose use the same `podman-compose.yaml` and build application images locally. No external authentication service, tunnel, database server or Riot key is required for account setup, login and password recovery. The [Architecture](ARCHITECTURE.md#authentication-and-session-trust-boundary) owns the authentication and security contract.

## Fresh installation

Install either Docker Engine with the Compose plugin, or Podman with `podman-compose`, through your Linux distribution. The verified Podman versions are 5.8.4 and podman-compose 1.5.0. A `docker` command that emulates Podman does not establish Docker Engine compatibility.

Choose a published standalone release tag from [Releases](https://github.com/KyleDerZweite/nashordaq/releases). This implementation has not published a standalone release yet. Until one exists, a checkout of the implementation branch is development verification rather than a released installation. Replace `RELEASE_TAG` below with the actual selected tag; do not use a moving branch for a release installation.

```bash
git clone --branch RELEASE_TAG --depth 1 https://github.com/KyleDerZweite/nashordaq.git
cd nashordaq
cp .env.example .env
chmod 600 .env
mkdir -p data
chmod 700 data
```

Edit `.env` before starting. For LAN access, set `NASHORDAQ_PUBLIC_URL=http://your-server:8080` to the exact origin you will open in your browser. Leave `NASHORDAQ_RIOT_API_KEY` empty when live Riot data is unavailable. Keep `.env`, database files, backup files and setup links private. Git ignores instance configuration and `data/`; image build contexts exclude environment files and local caches.

Start with your selected runtime:

```bash
# Docker Engine and Docker Compose
docker compose -f podman-compose.yaml up --build -d
docker compose -f podman-compose.yaml ps
docker compose -f podman-compose.yaml logs backend

# Podman and podman-compose
podman-compose -f podman-compose.yaml up --build -d
podman-compose -f podman-compose.yaml ps
podman-compose -f podman-compose.yaml logs backend
```

The frontend alone publishes the configured host HTTP port. Nginx re-resolves the backend service through the container runtime's DNS so restart does not retain an old container address. Nginx serves the application and forwards `/api/` and `/health` to the internal backend. Both services have startup health checks; the frontend starts after the backend becomes healthy. Verify the entry point with `curl -f http://your-server:8080/health`, which returns `{"status":"ok"}`. Open the same origin in a browser.

On a fresh normal installation, open the one-time setup link from the backend log and choose a username and a password with at least 12 characters. The link creates the sole administrator and signs you in. Setup stays closed after restart. An unused setup link rotates on restart. Reload preserves a valid session; logout revokes it immediately. Normal sessions last seven days. A missing Riot key does not block local account access; live Riot linking and market updates require a valid key.

Verify setup, reload, logout and login in the browser. Without a session, game queries return 401 even when a request carries forged proxy identity headers. `/health` and `/api/auth/status` remain public and contain no game data.

## Riot configuration and recovery

Local setup, login and administrator access work with an empty or rejected Riot key. The authenticated market and player-setup views show whether the key is missing, rejected, rate limited or affected by an upstream outage. Status never returns the key. A configured key starts as unverified until Riot accepts a request.

New player links require a successful account and ranked Solo Queue lookup. A failed lookup leaves the local account usable and creates no linked tracked player. Retry the same player after recovery. Real refreshes roll back their entire transaction when Riot authentication, rate limits or network availability fail. Existing prices and history remain unchanged. Demo uses its own simulated market and requires no key.

For a missing or rejected key, replace `NASHORDAQ_RIOT_API_KEY` in the protected environment file and restart the backend process with that environment. Container environments are fixed at creation: recreate the stack after editing the file, rather than using a Compose `restart` that retains its old environment. Use `podman-compose -f podman-compose.yaml up -d --force-recreate` or `docker compose -f podman-compose.yaml up -d --force-recreate`. Keep the existing data bind mount and database. Do not repeat setup or create another administrator.

Sign in again if needed, retry player setup, and check authenticated system status and the next due market refresh. A rate limit needs a later retry; a Riot outage needs upstream recovery. No reinstall is required. Controlled-response tests verify failure handling and retry behavior. Live linking and refresh recovery require an operator-owned valid Riot key and a separately recorded check; they have not been verified for the no-key local installation.

## Invite members

Sign in as the administrator and select Admin View. In Member invitations, select Create invitation. Copy the generated link and share it privately with the intended member. The link is shown only after creation; later visits show lifecycle metadata without the secret. Create another invitation if you lose an unused link, and revoke the lost invitation. The frontend omits query strings and referrers from access logs. Configure any external reverse proxy to do the same for access-link routes.

Each invitation expires after seven days and admits one member. The invited member opens the complete `/invite?token=...` link and chooses a username and a password of at least 12 characters. Registration signs them in and removes the token from the browser URL. Email and Riot details are unnecessary for account creation. Riot onboarding remains a separate step after login.

Member invitations lists active, consumed, revoked and expired links. Select Revoke beside an active invitation to withdraw access. An invalid, expired, revoked or consumed link cannot create an account. Ask the administrator for a new link when registration reports that the invitation is unavailable. A validation error or taken username leaves the invitation usable for another attempt.

## Change and recover passwords

Open Change password in your account view. Enter your current password and a new password with at least 12 characters. A successful change ends every session of your account, including the current browser. Sign in again with your new password. Other users retain their sessions.

As administrator, open Password recovery in Admin View. Choose the account and select Create reset link. Copy the generated link and share it privately with that account's owner. The link is delivered only at creation. It expires after one hour and works once. Select Revoke beside an active link to withdraw it.

Open the complete `/reset?token=...` link and choose your new password. Successful reset removes the token from the URL, ends every previous session and requires a new login. Invalid, expired, revoked and used links change nothing. A successful password change or reset also revokes other unused reset links for that account. Ask the administrator for another link when needed. Password and reset operations are unavailable for demo accounts and demo installations.

If the sole administrator cannot sign in, recover that same account on the server. From the backend directory, run:

```bash
uv run python -m app.operator recover-admin --database /absolute/path/to/nashordaq.db
```

For the installed Compose stack, run the command in the backend container with your selected runtime:

```bash
docker compose -f podman-compose.yaml exec backend python -m app.operator recover-admin --database /app/data/nashordaq.db
podman-compose -f podman-compose.yaml exec backend python -m app.operator recover-admin --database /app/data/nashordaq.db
```

The command reads and confirms the new password with hidden terminal input. Select the existing standalone SQLite file, not a new or legacy proxy database. Recovery preserves the administrator's identity, game state and sole administrator role. It ends all old administrator sessions and revokes unused administrator reset links. It does not create an account or reopen setup. No Riot key is required.

For automation, pass `--password-stdin` and supply exactly one password line through a protected pipe or file. Never supply a password as a command argument. For example, an existing permission-restricted secret file can be redirected to stdin:

```bash
uv run python -m app.operator recover-admin --database /absolute/path/to/nashordaq.db \
  --password-stdin < /protected/path/new-admin-password
```

Check the command's exit status. Zero means recovery committed; a nonzero status reports a failed operation without committing a password change. Sign in with the new password and verify administrator access. Passwords and reset secrets do not enter the game activity log. Protect reset-link query strings and referrers in any external reverse-proxy logs.

## Configuration and persistence

| Variable | Example default | Purpose |
|---|---|---|
| `NASHORDAQ_PUBLIC_URL` | `http://localhost:8080` | Exact browser-visible origin for access links and Secure cookies |
| `NASHORDAQ_HTTP_BIND` | `0.0.0.0` | Host interface for the sole HTTP entry point |
| `NASHORDAQ_HTTP_PORT` | `8080` | Host HTTP port |
| `NASHORDAQ_CORS_ORIGINS` | empty | Optional comma-separated additional browser origins; same-origin traffic needs none |
| `NASHORDAQ_RIOT_API_KEY` | empty | Optional for local accounts, required for live Riot data |
| `NASHORDAQ_DEMO_MODE_ENABLED` | `false` | Explicit demo deployment selection |
| `NASHORDAQ_GAMBA_ENABLED` | `false` | Explicit private-use Gamba opt-in |
| `NASHORDAQ_STARTING_BALANCE` | `1000.0` | Initial virtual balance |
| `NASHORDAQ_RIOT_API_BASE_URL` | `https://europe.api.riotgames.com` | Riot account and match region |
| `NASHORDAQ_RIOT_API_REGION_URL` | `https://euw1.api.riotgames.com` | Riot league and summoner region |

Compose fixes `NASHORDAQ_DATABASE_URL` to `sqlite+aiosqlite:////app/data/nashordaq.db`. The four slashes identify the absolute container path `/app/data/nashordaq.db`. The host directory `./data` binds to `/app/data` with shared SELinux relabeling. This is a directory bind, not a named volume. Keep the same checkout directory and bind when replacing containers. Ensure the operator can write the directory; rootless Podman uses the operator's user namespace.

Container restart or recreation preserves accounts, consumed setup, sessions and game state. Use your selected runtime's `restart`, or `up -d --force-recreate`, with the same manifest and working directory. `down` removes containers and the project network while retaining `./data`. Do not delete this directory. Copying an active SQLite main file alone is not a consistent backup because committed data may remain in its WAL. Use the operator backup procedure when that slice is available.

Both Containerfiles pin their base-image tags and immutable manifest digests. The backend copies uv 0.10.12 and installs the committed `uv.lock` with `--frozen`. The frontend uses pnpm 10.34.7, also declared in `packageManager`, and installs the committed `pnpm-lock.yaml` with `--frozen-lockfile`. Release updates deliberately review these inputs together.

## LAN HTTP and public HTTPS

For LAN HTTP, use an HTTP public URL with the actual hostname and port. Browsers then use an HttpOnly, SameSite=Strict session cookie without Secure. Change the example `localhost` URL for other machines; their `localhost` refers to themselves.

For public HTTPS, the operator's existing reverse proxy must terminate TLS and forward traffic to the frontend HTTP entry point. Set `NASHORDAQ_PUBLIC_URL=https://market.example.com` and usually set `NASHORDAQ_HTTP_BIND=127.0.0.1` for a proxy on the same host. A proxy on another host requires a reachable bind and appropriate host firewall rules. Preserve the original Host header, including any nonstandard external port. Proxy `/api/` to this same frontend entry point, not to a separately published backend. Public certificate and domain provisioning belongs to the operator.

The explicit HTTPS public URL sets Secure cookies even though the containers receive HTTP. Forwarded scheme and identity headers do not change authentication. Access the configured HTTPS origin for setup and login; Secure cookies will not authenticate over plain HTTP. Same-origin browser traffic needs no extra CORS entry. Configure additional origins only when deliberately serving a separate frontend. State-changing API requests require `X-Nashordaq-CSRF: 1` and a trusted browser origin. An HTTP-only check does not verify public TLS integration.

## Demo and optional Gamba

Use a separate checkout and empty `data/` directory for demo operation, with its own port and public URL. Set `NASHORDAQ_DEMO_MODE_ENABLED=true` in `.env`. The shared manifest already mounts the seed directory at `/demo` read-only, so explicit demo mode loads its simulated market without a Riot key. Sign in with `demo/demo`. Each browser session receives separate personal game state in the shared simulated market. Reload preserves a valid session. Logout deletes personal state immediately. Sessions expire after 30 minutes of inactivity, and cleanup runs every minute. Closing the browser does not delete state immediately. Background polling does not renew inactivity.

If running normal and demo installations on the same host, use distinct project names with `-p nashordaq-demo` for all demo Compose commands. Keep their directories and published ports separate. Use different browser-visible hostnames or separate browser profiles, because session cookies are scoped to the hostname and do not isolate ports.

The existing `demo.podman-compose.yaml` is an optional override that enables the same flag. It must be combined with the shared manifest:

```bash
podman-compose -f podman-compose.yaml -f demo.podman-compose.yaml up --build -d
# Equivalent Docker command:
docker compose -f podman-compose.yaml -f demo.podman-compose.yaml up --build -d
```

Gamba is disabled by default in both the application and environment example. Its API returns 404 and its UI is hidden. To opt in for a private installation, set `NASHORDAQ_GAMBA_ENABLED=true` and recreate the stack with `podman-compose -f podman-compose.yaml up -d --force-recreate`, or `docker compose -f podman-compose.yaml up -d --force-recreate`. A plain restart retains the container's old environment. It is outside the production-facing product path.

## Transition from proxy installations

The previous proxy version is incompatible with standalone account storage. Before switching, stop the old installation and preserve its data directory, including any WAL and SHM files. Choose a fresh, separate directory for this installation. Startup rejects a legacy or unsupported database before modifying its schema or persistent WAL mode. It does not migrate, overwrite or delete old data. Keep the old release and its data for recovery; this transition does not authorize deletion.

## Local development

From `backend/`, create `data/`, run `uv sync --locked --dev`, then run `NASHORDAQ_PUBLIC_URL=http://localhost:5173 uv run uvicorn app.main:app --reload`. The development SQLite path is backend-relative unless explicitly overridden. From `frontend/`, run `corepack pnpm@10.34.7 install --frozen-lockfile`, then `corepack pnpm@10.34.7 run dev`. Vite proxies `/api` to the backend and preserves Host. Open the setup link printed by the backend. No header-injection extension is required.

Tracked players enter through Riot onboarding rather than editing deployment seed files. A new player cannot be traded until its first successful market update. The scheduler wakes every 30 seconds and fetches Riot only when the dynamic interval is due. The [Architecture](ARCHITECTURE.md) owns that calculation and [Economy mechanics](ECONOMY_MECHANICS.md) owns pricing formulas.
