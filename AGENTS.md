# AI Agent Instructions

This is the primary instruction file for contributors and coding agents. Follow it strictly.

## 1) Hard Constraints

### Backend (Python/FastAPI)
- Package manager: `uv` only.
- Lint/format: `ruff` only.
- Never use `pip`, `poetry`, or `conda`.

### Frontend (Vite/TypeScript)
- Package manager: `pnpm` only.
- Lint: ESLint.
- Format: Prettier.
- Never use `npm` or `yarn`.

### Authentication / Security Model
- Authentication is external (IAP + reverse proxy).
- Never implement JWT issuance, password hashing, sessions, or login forms.
- Backend identity source is `Remote-Email` (stable key), with `Remote-Name` for display name and `Remote-User` as fallback (matching Pangolin's forwarded headers).
- Keep security assumptions aligned with `docs/ARCHITECTURE.md` (trust boundary and hardening settings).

## 2) Canonical References

- Architecture and security boundary: `docs/ARCHITECTURE.md`
- Pricing model and formulas: `docs/ECONOMY_MECHANICS.md`
- Product scope and behavior: `docs/PRD.md`

Do not duplicate complex formula or architecture details in multiple places; reference canonical docs instead.

## 3) Required Workflow

### Dependency changes
- Backend: `uv add <package>`
- Frontend: `pnpm add <package>`

### Validation before finishing
- Backend (run from `backend/`):
  - `uv run ruff check .`
  - `uv run ruff format .`
  - `uv run pytest -v` (when backend behavior changed)
- Frontend (run from frontend folder):
  - `pnpm run lint`
  - `pnpm run format`
  - `pnpm run build` (when frontend behavior changed)

If checks fail, fix issues autonomously before concluding.

## 4) Coding Principles

- Keep code typed, modular, and minimal.
- Prefer small, targeted edits over large rewrites.
- Follow: KISS, YAGNI, DRY, SOLID.
- Keep comments and docs concise. No emojis.
- Do not add features beyond the requested scope.