# Architecture

## Frontend (Client)

- **Vite + TypeScript:** Build tool and language constraint.
- **UI Framework:** TailwindCSS for styling.
- **State Management:** TanStack Query for handling server state, caching, and background UI updates.

## Backend (API)

- **FastAPI:** Handles all REST endpoints (authentication, executing trades, fetching portfolios).
- **ORM:** SQLAlchemy or SQLModel to interact with the database.

## Data & Workers

- **PostgreSQL:** Primary relational database storing users, tracked players, portfolios, and the transaction ledger.
- **Redis:** Message broker for the background worker queue.
- **`arq` (Python):** Asynchronous worker process. Runs scheduled tasks to query the Riot Games API, calculate new share prices, and write updates to PostgreSQL.

## Infrastructure

- **Podman-compose:** Manages the isolated containers for the Frontend, Backend, Database, Redis, and Worker.
