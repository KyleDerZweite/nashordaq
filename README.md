# Nashordaq

Nashordaq is a self-hosted virtual share market for a private League of Legends friend group. Users trade whole shares in tracked players with virtual currency. Ranked Solo Queue performance drives prices through the Riot API and the existing [economy rules](docs/ECONOMY_MECHANICS.md).

One installation runs one private market with one administrator. Local username/password accounts, invitation access, revocable sessions and password recovery require no external identity provider. The administrator can participate after ordinary Riot onboarding. Members can inspect game interventions, and Streamer Mode uses permanent League aliases across views.

The standalone baseline is implemented but unreleased. [Self-host acceptance](docs/SELF_HOST_ACCEPTANCE.md) records development verification and the remaining release, live Riot, public HTTPS and owner checks. This implementation does not claim Riot production-key approval. Future hosted service and OAuth/OIDC ideas are outside the accepted baseline.

## Try the demo

The [public demo](https://demo-nashordaq.kylehub.dev/) may run older code. This revision uses explicit demo deployment and `demo/demo` login. Each visitor receives separate temporary balance, holdings and orders in a shared simulated market, without administrator permissions or a Riot key.

Reload preserves a valid demo session. Sign out to delete personal state immediately. Thirty minutes of inactivity ends access; automatic cleanup runs every minute. Closing a browser does not guarantee immediate deletion.

## Self-hosting

Follow the [deployment guide](docs/DEPLOYMENT.md) to install, create the administrator, invite members, recover passwords, back up, restore and update. Docker Compose and Podman Compose use the same manifest and build locally from pinned inputs. Only the frontend HTTP entry point is published. SQLite persists in the host directory `./data`.

Set `NASHORDAQ_PUBLIC_URL` to the exact LAN HTTP or operator-provided HTTPS origin before setup. No domain or tunnel is required for LAN access. Login and administration work without a Riot key; live onboarding and updates require one. Gamba is disabled by default and requires an explicit private-use choice.

Start with a separate empty data directory when leaving the previous proxy installation. Startup rejects its database without migrating or deleting it. Preserve the old installation and data. No standalone release tag has been published from this implementation; an implementation-branch checkout establishes development verification only.

## Development

Use the [local development procedure](docs/DEPLOYMENT.md#local-development) to configure the browser origin and create an account. Backend commands run from `backend/`:

```bash
mkdir -p data
uv sync --locked --dev
NASHORDAQ_PUBLIC_URL=http://localhost:5173 uv run uvicorn app.main:app --reload
uv run pytest -v
uv run ruff check .
uv run ruff format .
```

Frontend commands run from `frontend/` with the version declared in `packageManager`:

```bash
corepack pnpm@10.34.7 install --frozen-lockfile
corepack pnpm@10.34.7 run dev
corepack pnpm@10.34.7 run lint
corepack pnpm@10.34.7 run format
corepack pnpm@10.34.7 run build
```

Use [GitHub issues](https://github.com/KyleDerZweite/nashordaq/issues) for work and [Discussions](https://github.com/KyleDerZweite/nashordaq/discussions) for ideas. The [roadmap](docs/ROADMAP.md) separates the implemented baseline from possible later work.

## License

Nashordaq uses the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
