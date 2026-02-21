# Nashordaq

A self-hosted, fantasy stock market for a private League of Legends friend group. 

Nashordaq allows users to use virtual currency to buy and sell shares in specific League of Legends players. The value of these shares fluctuates automatically based on the players' real-time Ranked LP (League Points) changes.

## Features
* Live Market: Account valuations update automatically based on real Riot API data.
* Portfolio Management: Users can execute buy and sell orders based on player performance.
* Leaderboards: Global ranking of users by total portfolio net worth.
* Self-Hosted First: Containerized with Podman for easy deployment.
* Proxy-Ready Auth: Designed to sit behind an Identity-Aware Proxy (like Zitadel/Pangolin) for zero-friction user management.

## Authentication
Nashordaq delegates authentication to your reverse proxy. The API expects an `X-Remote-User` header containing the authenticated user's identifier. If you are self-hosting without a proxy, you will need to implement your own authentication middleware or basic auth.

## Tech Stack

- Frontend: Vite + TypeScript + TailwindCSS + TanStack Query
- Backend: FastAPI (Python)
- Database: PostgreSQL
- Background Tasks: Redis + `arq`
- Deployment: Podman-compose

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). See [LICENSE](LICENSE).
