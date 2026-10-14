# Deployment guide

One installation runs one private market. Docker Compose and Podman Compose use the same `podman-compose.yaml` and build application images locally. No external authentication service, tunnel, database server or Riot key is required for account setup, login and password recovery. The [Architecture](ARCHITECTURE.md#authentication-and-session-trust-boundary) owns the authentication and security contract.

## Fresh installation

Install either Docker Engine with the Compose plugin, or Podman with `podman-compose`, through your Linux distribution. Development verification used Docker Engine 29.9.0 with Compose 5.6.0 and Podman 5.8.4 with podman-compose 1.5.0. See [self-host acceptance](SELF_HOST_ACCEPTANCE.md) for exact revisions, scenarios and limits. A `docker` command that emulates Podman does not establish Docker Engine compatibility.

Choose a published standalone release tag from [Releases](https://github.com/KyleDerZweite/nashordaq/releases). This implementation has not published a standalone release yet. Until one exists, a checkout of the implementation branch is development verification rather than a released installation. Replace `RELEASE_TAG` below with the actual selected tag; do not use a moving branch for a release installation.

```bash
git clone --branch RELEASE_TAG --depth 1 https://github.com/KyleDerZweite/nashordaq.git
cd nashordaq
cp .env.example .env
chmod 600 .env
mkdir -p data
chmod 700 data
```

Edit `.env` before starting. For LAN access, set `NASHORDAQ_PUBLIC_URL=http://your-server:8080` to the exact origin you will open in your browser. Keep the normal and demo modes in separate installations. Leave `NASHORDAQ_RIOT_API_KEY` empty when live Riot data is unavailable. Keep `.env`, database files, backup files and setup links private. Git ignores instance configuration and `data/`; image build contexts exclude environment files and local caches.

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

For a missing or rejected key, replace `NASHORDAQ_RIOT_API_KEY` in the protected environment file. Recreate the full Compose stack to load the changed environment. A Compose `restart` retains its old environment. Use `podman-compose -f podman-compose.yaml up -d --force-recreate` or `docker compose -f podman-compose.yaml up -d --force-recreate`. Keep the existing data bind mount and database. Do not repeat setup or create another administrator.

Sign in again if needed, retry player setup, and check authenticated system status and the next due market refresh. A rate limit needs a later retry; a Riot outage needs upstream recovery. No reinstall is required. Controlled-response tests verify failure handling and retry behavior. Live linking and refresh recovery require an operator-owned valid Riot key and a separately recorded check; they have not been verified for the no-key local installation.

## Invite members

Sign in as the administrator and select Admin View. In Member invitations, select Create invitation. Copy the generated link and share it privately with the intended member. The link is shown only after creation; later visits show lifecycle metadata without the secret. Create another invitation if you lose an unused link, and revoke the lost invitation. The frontend omits query strings and referrers from access logs. Configure any external reverse proxy to do the same for access-link routes.

Each invitation expires after seven days and admits one member. The invited member opens the complete `/invite?token=...` link and chooses a username and a password of at least 12 characters. Registration signs them in and removes the token from the browser URL. Email and Riot details are unnecessary for account creation. Riot onboarding remains a separate step after login.

Member invitations lists active, consumed, revoked and expired links. Select Revoke beside an active invitation to withdraw access. An invalid, expired, revoked or consumed link cannot create an account. Ask the administrator for a new link when registration reports that the invitation is unavailable. A validation error or taken username leaves the invitation usable for another attempt.

## Change and recover passwords

Open the Change password panel below the account header. Enter your current password and a new password with at least 12 characters. A successful change ends every session of your account, including the current browser. Sign in again with your new password. Other users retain their sessions.

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

Container restart or recreation preserves accounts, consumed setup, sessions and game state. Use your selected runtime's `restart`, or `up -d --force-recreate`, with the same manifest and working directory. `down` removes containers and the project network while retaining `./data`. Do not delete this directory. Copying an active SQLite main file alone is not a consistent backup because committed data may remain in its WAL. Use the [live backup and fresh restore procedure](#live-backup-and-fresh-restore).

Both Containerfiles pin their base-image tags and immutable manifest digests. The backend copies uv 0.10.12 and installs the committed `uv.lock` with `--frozen`. The frontend uses pnpm 10.34.7, also declared in `packageManager`, and installs the committed `pnpm-lock.yaml` with `--frozen-lockfile`. Release updates deliberately review these inputs together.

## Live backup and fresh restore

Use the operator CLI's SQLite online backup. Keep the application running during backup. A copy of only `nashordaq.db` can omit committed writes in `nashordaq.db-wal`.

Backups contain the complete supported database, including password verifiers, sessions, invitation/reset state and game history. Treat them as credential data. Store backups outside the checkout and application data directory in operator-only storage with directory mode 700 and file mode 600. Keep an encrypted off-host copy and test restore regularly. The command creates its database file with mode 600. Protect the encryption keys separately. Preserve the matching release tag and protected `.env` configuration separately; database backups do not include configuration or the Riot key.

Run from the installation directory. Choose a new filename for every backup and export. Run only the commands for your selected runtime. The following examples store the snapshot in the mounted data directory before exporting it to protected storage:

```bash
# Docker Compose
docker compose -f podman-compose.yaml exec -T backend python -m app.operator backup \
  --database /app/data/nashordaq.db --output /app/data/backup-2026-10-14.db

# Podman Compose
podman-compose -f podman-compose.yaml exec -T backend python -m app.operator backup \
  --database /app/data/nashordaq.db --output /app/data/backup-2026-10-14.db

mkdir -p "$HOME/nashordaq-backups"
chmod 700 "$HOME/nashordaq-backups"
# Export only the completed snapshot. Noclobber refuses an existing export.
(umask 077; set -C; docker compose -f podman-compose.yaml exec -T backend \
  cat /app/data/backup-2026-10-14.db > "$HOME/nashordaq-backups/backup-2026-10-14.db")

# Equivalent Podman export:
(umask 077; set -C; podman-compose -f podman-compose.yaml exec -T backend \
  cat /app/data/backup-2026-10-14.db > "$HOME/nashordaq-backups/backup-2026-10-14.db")
```

Success prints `Backup created` and returns exit code 0. Check that export also returns exit code 0 before treating the off-directory copy as usable. A failed export may leave a partial export file; preserve the completed snapshot and retry to a new export filename. Errors return a nonzero code with instructions. Existing destination files, dangling symlinks and WAL/SHM/journal remnants are refused. A partial or failed snapshot is not published. A lock or copy lasting longer than 60 seconds needs a retry after the lock or load has cleared. Never remove the live database or its WAL/SHM files to make a backup succeed.

Restore into a separate, fresh installation before starting it. Use the matching supported release and restore its protected configuration with the intended public URL and mode. Do not restore over an initialized installation. If you are recovering a failed update, preserve its database and select a separate empty checkout/data directory instead of deleting it.

1. Clone the matching release, configure `.env`, create private `data/` and build the backend image. Keep the destination stack stopped.
2. Copy the selected backup to `data/restore-source.db`, set its file mode to 600, and retain the original backup in protected storage.
3. Run one of these commands from the fresh installation directory. The CLI requires the destination database and its SQLite sidecars to be absent.

```bash
# Docker Compose
docker compose -f podman-compose.yaml build backend
docker compose -f podman-compose.yaml run --rm --no-deps backend \
  python -m app.operator restore \
  --backup /app/data/restore-source.db --database /app/data/nashordaq.db

# Podman Compose
podman-compose -f podman-compose.yaml build backend
podman-compose -f podman-compose.yaml run --rm --no-deps backend \
  python -m app.operator restore \
  --backup /app/data/restore-source.db --database /app/data/nashordaq.db
```

4. Confirm `Restore completed` and exit code 0. Preserve `restore-source.db` until the restored installation passes the checks below. The command validates supported schema, SQLite integrity and foreign-key consistency before publishing the destination and never alters or deletes the backup.
5. Start the fresh stack with your runtime's `up -d`. Check `/health` and sign in with the existing administrator and member credentials. Confirm their balances, portfolios, orders and history. Completed setup stays closed and no new administrator setup link appears. Existing unexpired sessions and links retain their saved lifecycle state. Writes made after the snapshot are outside that backup.
6. After successful verification, keep the original protected backup. Remove only the staging copies you created if your retention policy no longer needs them. Restrict who can operate the host, containers and backup directory.

For a source checkout with backend tools installed, run from `backend/` using `uv run python -m app.operator backup --database /absolute/live.db --output /absolute/new-backup.db` or `uv run python -m app.operator restore --backup /absolute/backup.db --database /absolute/fresh.db`. All source and destination paths must be absolute. Restore does not run setup, change passwords, migrate a legacy proxy database or call Riot. Demo snapshots preserve demo state with its original expiry deadlines; they do not extend visitor lifetime. Start a restored database in its original account mode.

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

## Supported standalone updates and failed-update recovery

This is the first, unreleased standalone baseline. Its initial schema version is `1`, stored in the single `instance_metadata` row with ID `1`. Version 1 means the complete current model, including local authentication, game tables and `identity_aliases`. Earlier development checkpoints with partial tables are unsupported. There is no published standalone predecessor and no automatic migration from proxy databases.

| Source database | Supported action in this baseline |
|---|---|
| Fresh empty database | Initialize version 1 and perform one-time setup. |
| Complete standalone version 1 | Restart or update with compatible version 1 code, preserving persisted state. |
| Partial, malformed or unsupported standalone version | Refuse before schema, persistent WAL, setup or account mutation. Use matching code and a healthy backup. |
| Previous proxy database | Preserve the old installation and configure a separate fresh database. |

Startup and the shared operator commands inspect required table/column definitions, uniqueness and reference protections, the sole-administrator constraint, SQLite integrity and foreign-key consistency. They also reject invalid administrator/demo flags or existing normal members/completed setup without the sole administrator. They preserve additional stored tables and columns. They never repair an incomplete database by silently creating missing tables. Normal supported startup preserves credentials, administrator identity, completed setup, unexpired sessions, access-link lifecycle, aliases and game records. Expiry, scheduled market operations and demo cleanup retain their normal behavior.

Before updating, retain the exact old release tag or commit, its locally built images and protected configuration. Make a consistent backup with that old code using [the backup procedure](#live-backup-and-fresh-restore). Name or record the snapshot together with the old revision and deployment mode. Keep it outside the live data directory. A snapshot taken after an unsuccessful schema change is not the matching pre-update backup.

1. Read the candidate release's advertised supported source versions. This baseline supports complete schema version 1 only; it does not establish compatibility with a released predecessor.
2. Create and export the matching consistent backup while the old installation is running. Confirm both commands succeed. Stop its stack with the runtime's `down`; retain the data directory and configuration.
3. Select the candidate tag or commit in the checkout, preserving `.env` and `data/`. Build the candidate backend, then preflight the stopped database with the candidate code:

```bash
# Docker Compose
docker compose -f podman-compose.yaml build backend
docker compose -f podman-compose.yaml run --rm --no-deps backend \
  python -m app.operator check-update --database /app/data/nashordaq.db

# Podman Compose
podman-compose -f podman-compose.yaml build backend
podman-compose -f podman-compose.yaml run --rm --no-deps backend \
  python -m app.operator check-update --database /app/data/nashordaq.db
```

For a source checkout, run from `backend/` with `uv run python -m app.operator check-update --database /absolute/path/nashordaq.db`. The command uses an existing file, returns exit code 0 with `Compatible standalone schema version 1`, and changes no persisted data. Failure returns a nonzero code and recovery instructions. Read-only SQLite access can create WAL/SHM sidecars; preserve them along with the source.

4. If preflight succeeds, build both candidate images and start the stack with `up --build -d`. Normal startup performs the supported version 1 restart; there is no separate migration command. Check `/health`, backend logs and existing administrator/member logins. Confirm the same administrator ID, completed setup, balances, holdings, orders, history, aliases and access-link lifecycle. Check retained unexpired sessions. A healthy process alone does not prove account/game preservation.
5. If preflight or startup fails, stop the candidate stack. Preserve its database, sidecars and logs. Do not change its version marker, delete tables, retry setup or run old code against possibly changed data.
6. Recover in a separate fresh checkout/data directory using the exact old release and its pre-update matching snapshot. Restore its protected configuration with the intended origin and deployment mode. Use [fresh restore](#live-backup-and-fresh-restore) with that old code, then start the old stack. Verify existing credentials, administrator identity, setup closure and coherent game state before returning users to it. Keep both the failed installation and original snapshot intact. Writes after the snapshot are outside the recovered state.

The previous-standalone-release update acceptance check is **unexecuted** for the first release because no such release exists. Current-schema restart and synthetic unsupported-version recovery establish only those scenarios. Before the following release, its release owner must advertise an explicit supported transition and verify update from the actual released predecessor on a populated Compose instance, plus recovery using that predecessor and its matching backup. Any future schema change must define its compatibility/version transition before implementation; this baseline adds no speculative migration framework.

## Transition from proxy installations

The previous proxy version is incompatible with standalone account storage. Before switching, stop the old installation and preserve its data directory, including any WAL and SHM files. Choose a fresh, separate directory for this installation. Startup rejects a legacy or unsupported database before modifying its schema or persistent WAL mode. It does not migrate, overwrite or delete old data. Keep the old release and its data for recovery; this transition does not authorize deletion.

## Local development

From `backend/`, create `data/`, run `uv sync --locked --dev`, then run `NASHORDAQ_PUBLIC_URL=http://localhost:5173 uv run uvicorn app.main:app --reload`. The development SQLite path is backend-relative unless explicitly overridden. From `frontend/`, run `corepack pnpm@10.34.7 install --frozen-lockfile`, then `corepack pnpm@10.34.7 run dev`. Vite proxies `/api` to the backend and preserves Host. Open the setup link printed by the backend. No header-injection extension is required.

Tracked players enter through Riot onboarding rather than editing deployment seed files. A new player cannot be traded until its first successful market update. The scheduler wakes every 30 seconds and fetches Riot only when the dynamic interval is due. The [Architecture](ARCHITECTURE.md) owns that calculation and [Economy mechanics](ECONOMY_MECHANICS.md) owns pricing formulas.
