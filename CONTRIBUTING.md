# Contributing to Nashordaq

Nashordaq is a personal project. Contributions are welcome, but there are no guarantees on response time or acceptance.

## Before you start

- Open an issue or discussion first if you're planning a larger change.
- Bug fixes and small improvements can go straight to a pull request.

## Development setup

See the [README](README.md#development) for backend and frontend dev commands.

You will need:
- A [Riot Games API key](https://developer.riotgames.com/) (development keys rotate every 24 hours)
- An Identity-Aware Proxy (e.g. [Pangolin](https://github.com/fosrl/pangolin)) or a way to inject `Remote-Email`, `Remote-Name`, and optional `Remote-User` fallback headers for local testing

## Pull requests

- Keep PRs focused -- one change per PR.
- Make sure linting and tests pass before submitting:
  ```bash
  # Backend
  cd backend && uv run ruff check . && uv run pytest -v

  # Frontend
  cd frontend && pnpm run lint && pnpm run build
  ```
- Write a clear description of what the PR does and why.

## Reporting bugs

Use the [bug report template](https://github.com/KyleDerZweite/nashordaq/issues/new?template=bug_report.yml) or open a blank issue.

## Security issues

Please **do not** file security vulnerabilities as public issues. See [SECURITY.md](SECURITY.md) for how to report them.
