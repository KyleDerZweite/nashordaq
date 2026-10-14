# Contributing to Nashordaq

Nashordaq is a personal project. Contributions are welcome, but there are no guarantees on response time or acceptance.

## Before you start

- Open an issue or discussion first if you're planning a larger change.
- Bug fixes and small improvements can go straight to a pull request.

## Development setup

See the [README](README.md#development) for backend and frontend dev commands.

Use the local setup link and username/password sessions described in [Deployment](docs/DEPLOYMENT.md#local-development). No external identity provider or Riot key is needed for account access or demo development. Live Riot onboarding and updates require your own protected API key.

## Where to change and test

Use [Architecture](docs/ARCHITECTURE.md) for responsibilities and security boundaries, [Deployment](docs/DEPLOYMENT.md) for operator procedures, and [Economy mechanics](docs/ECONOMY_MECHANICS.md) for pricing and game rules.

| Change | Owner and focused tests |
| --- | --- |
| Local accounts, sessions and password resets | `backend/app/auth.py`; `backend/tests/test_local_auth.py` |
| Administrator game interventions and member activity | `backend/app/interventions.py`, `backend/app/routers/admin.py` and `backend/app/routers/activity.py`; `backend/tests/test_admin_participation.py` |
| Streamer aliases and identity presentation | `backend/app/identities.py`, `frontend/src/contexts/useIdentityPresentation.ts`, `frontend/src/utils/identityPresentation.ts`; alias cases in `test_local_auth.py` and `frontend/tests/identityPresentation.test.ts` |
| Riot failures and recovery | `backend/app/riot.py` external adapter, onboarding and scheduler callers; `backend/tests/test_riot_recovery.py` and `backend/tests/test_riot_restart.py` |
| Persistence and operator CLI | `backend/app/database.py`, `backend/app/persistence.py`, `backend/app/operator.py`; `backend/tests/test_operator_backup.py` and `backend/tests/test_supported_updates.py` |

Run a focused backend file with `uv run pytest -v tests/test_local_auth.py` from `backend/`. The shared `conftest.py` fixtures use in-memory SQLite, create tables directly and override request sessions. Use them for route and game logic. Use temporary file SQLite for persistence, concurrency and constraints. The `local_instance` fixture in `test_local_auth.py` calls real `initialize_instance()` startup initialization against a file database. In-process ASGI requests do not run the full server lifespan or prove process restart behavior.

The autouse `stub_initial_player_refresh` fixture in `conftest.py` replaces onboarding's `_initialize_player_market_state` with a no-op. `test_riot_recovery.py` and `test_admin_participation.py` override that fixture to retain real initialization and control upstream HTTP responses. Follow that pattern when testing onboarding failures rather than accidentally skipping the behavior under test. `test_riot_restart.py` launches real server processes against a file database and a controlled HTTP provider. It proves environment replacement and restart behavior, not live Riot access.

Frontend identity tests check the shared name renderer. For rendered flows and browser integration, follow [Self-host acceptance](docs/SELF_HOST_ACCEPTANCE.md) and record the evidence there. Backend HTTP tests and the frontend build do not establish browser behavior.

## Pull requests

- Keep PRs focused on one useful change.
- Make sure linting and tests pass before submitting:
  ```bash
  # Backend
  cd backend && uv run ruff check . && uv run ruff format . && uv run pytest -v

  # Frontend
  cd ../frontend && corepack pnpm@10.34.7 run lint
  corepack pnpm@10.34.7 run format
  corepack pnpm@10.34.7 run test
  corepack pnpm@10.34.7 run build
  ```
- Write a clear description of what the PR does and why.

## Reporting bugs

Use the [bug report template](https://github.com/KyleDerZweite/nashordaq/issues/new?template=bug_report.yml) or open a blank issue.

## Security issues

Please **do not** file security vulnerabilities as public issues. See [SECURITY.md](SECURITY.md) for how to report them.
