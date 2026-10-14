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
