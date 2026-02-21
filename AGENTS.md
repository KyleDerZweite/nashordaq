# AI Agent Instructions

This document defines the strict tooling and workflow rules for contributing to the Nashordaq project. Adhere strictly to these constraints.

## Tech Stack and Tooling

### Backend (Python/FastAPI)
* Package Manager: `uv`
* Linter and Formatter: `ruff`
* Do not use `pip`, `poetry`, or `conda`. Use `uv` for all dependency management and environment execution.

### Frontend (Vite/TypeScript)
* Package Manager: `pnpm`
* Linter: ESLint
* Formatter: Prettier
* Do not use `npm` or `yarn`. Use `pnpm` for all dependency management.

### Authentication Strategy
* The application relies on an Identity-Aware Proxy (IAP) for authentication. 
* Do not implement JWT generation, password hashing, or login forms.
* The backend must identify users strictly by reading the `X-Remote-User` HTTP header injected by the reverse proxy.

## Workflow Rules

### 1. Dependency Management
* Backend: Add packages using `uv add <package>`.
* Frontend: Add packages using `pnpm add <package>`.

### 2. Validation and Linting
After making any major changes, refactoring code, or completing a feature, you must run the appropriate linting and formatting tools to verify the codebase before concluding the task.

**Backend Checks:**
* Run `uv run ruff check .` to catch linting errors. Fix any issues found.
* Run `uv run ruff format .` to ensure consistent code styling.

**Frontend Checks:**
* Run `pnpm run lint` to check for TypeScript and syntax errors.
* Run `pnpm run format` to format the code.

### 3. Execution
* Ensure all code runs without errors before presenting it as a final solution. If a linter throws an error, fix it autonomously without asking for permission.

### 4. Style
* Write clean, modular, and typed code (TypeScript for frontend, Python type hints for backend).
* Keep documentation and comments minimalistic. No emojis.
* Adhere to core software engineering principles:
  * KISS (Keep It Simple, Stupid): Avoid unnecessary complexity.
  * YAGNI (You Aren't Gonna Need It): Do not implement features before they are strictly required.
  * DRY (Don't Repeat Yourself): Consolidate logic to prevent code duplication.
  * SOLID: Ensure scalable and maintainable object-oriented design.