# Nashordaq frontend

The React/TypeScript application uses Vite, Tailwind CSS and TanStack Query. It uses the backend's local session interface and shared identity presentation for normal and Streamer Mode views.

Follow the [root development guide](../README.md#development) and [local account setup](../docs/DEPLOYMENT.md#local-development). Vite proxies `/api` to the backend. Account access requires login, including explicit `demo/demo` sessions in demo mode.

Use the pnpm version declared in `package.json`. From this directory, run:

```bash
corepack pnpm@10.34.7 install --frozen-lockfile
corepack pnpm@10.34.7 run dev
corepack pnpm@10.34.7 run lint
corepack pnpm@10.34.7 run format
corepack pnpm@10.34.7 run build
corepack pnpm@10.34.7 run test
```

`pnpm run test` runs the three existing identity presentation tests with Node's built-in test runner. CI runs them on Node 22 alongside lint, format checks and the build.

[Architecture](../docs/ARCHITECTURE.md) owns component and security boundaries. [Self-host acceptance](../docs/SELF_HOST_ACCEPTANCE.md) records rendered browser checks and remaining verification.

## Local demo browser regression

The opt-in browser check builds a fresh demo through the shared Compose manifest and drives Chromium through login, one stock purchase, reload and logout. Two isolated browser contexts verify that one visitor's portfolio and logout do not affect the other. It runs outside CI. Detailed backend authorization, expiry and physical cleanup remain covered by `backend/tests/test_demo.py`.

Use a Git checkout on Linux with Node 22 or 24, this project's pnpm dependencies, and either native Docker Engine with Docker Compose or Podman with `podman-compose`. Install the package-matched browser into your user cache, then select the runtime explicitly:

```bash
corepack pnpm@10.34.7 install --frozen-lockfile
corepack pnpm@10.34.7 exec playwright install chromium
corepack pnpm@10.34.7 run test:browser -- --runtime podman
# Or, with native Docker Engine:
corepack pnpm@10.34.7 run test:browser -- --runtime docker
```

The runner checks the browser before building containers. It does not install host libraries or global packages. If Chromium reports missing host libraries, resolve those through your existing system setup before retrying. A `docker` command that emulates Podman is rejected as Docker evidence. On unsupported Linux distributions, Playwright may use a fallback browser build; a successful launch proves only the tested host.

Each invocation copies tracked frontend files and backend build inputs from the working tree into a private temporary directory. This includes frontend docs and tooling because Tailwind scans them during builds. Stage new application files with `git add` before testing; unknown untracked files are excluded. Environment files, Git metadata, dependencies, build outputs and local artifacts are excluded. The runner generates demo-only configuration with an empty Riot key and Gamba disabled. A random project name, fresh database and available loopback port keep it separate from existing installations. The runner never reads your instance `.env` or uses your desktop browser profile. Port selection has a short release-to-bind race; a collision fails the run without stopping the other listener.

The runner tears down its own Compose project after success, failure, SIGINT or SIGTERM, then removes its temporary source and data. If teardown fails, it preserves the directory and prints the exact cleanup command. SIGKILL and host failure can leave resources behind. Build images and engine caches remain available for reuse; the runner never prunes them.

Each run keeps a status report in ignored `browser-results/<project>/`. Browser assertion failures also keep screenshots for both visitors. Traces, videos, saved cookies, database copies and raw request logs are disabled. These files are local verification evidence, not owner acceptance or deployment evidence. A cold run downloads images and builds both services; later runs can reuse the engine cache.

The ordinary format script covers application sources. When editing this test tooling, also run `corepack pnpm@10.34.7 exec prettier --write browser-tests eslint.config.js`.
