import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { cp, lstat, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(frontend, "..");
const args = process.argv.slice(2).filter((arg) => arg !== "--");
if (
  args.length !== 2 ||
  args[0] !== "--runtime" ||
  !["docker", "podman"].includes(args[1])
) {
  console.error("Usage: pnpm run test:browser --runtime docker|podman");
  process.exit(1);
}
const runtime = args[1];
const command = runtime === "docker" ? "docker" : "podman-compose";
const composePrefix = runtime === "docker" ? ["compose"] : [];
const environment = Object.fromEntries(
  Object.entries(process.env).filter(
    ([key]) =>
      !key.startsWith("NASHORDAQ_") &&
      !key.startsWith("COMPOSE_") &&
      !["DEBUG", "PWDEBUG", "PW_TEST_HTML_REPORT_OPEN"].includes(key),
  ),
);
const abort = new AbortController();
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => abort.abort());
}

// Each command has its own process group so cancellation also stops its children.
function run(executable, arguments_, options = {}) {
  const {
    timeout = 30_000,
    signal = abort.signal,
    cwd = frontend,
    env = environment,
    capture = false,
  } = options;
  return new Promise((resolveRun, reject) => {
    if (signal.aborted) return reject(new Error("Run interrupted."));
    const child = spawn(executable, arguments_, {
      cwd,
      env,
      detached: true,
      stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
    });
    let output = "";
    let stopped = false;
    let finished = false;
    let killTimer;
    function kill(signalName) {
      if (!child.pid) return;
      try {
        process.kill(-child.pid, signalName);
      } catch (error) {
        if (error.code !== "ESRCH") throw error;
      }
    }
    function stop() {
      if (stopped || finished) return;
      stopped = true;
      kill("SIGTERM");
      killTimer = setTimeout(() => kill("SIGKILL"), 5_000);
    }
    if (capture) {
      child.stdout.on("data", (data) => (output += data));
      child.stderr.on("data", (data) => (output += data));
    }
    const timer = setTimeout(stop, timeout);
    signal.addEventListener("abort", stop, { once: true });
    function finish(error, code) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      clearTimeout(killTimer);
      signal.removeEventListener("abort", stop);
      if (error || code !== 0 || stopped) {
        reject(
          new Error(
            `${executable} ${arguments_[0] ?? ""} ${stopped ? "interrupted or timed out" : `failed (${error?.code ?? code})`}.`,
          ),
        );
      } else resolveRun(output.trim());
    }
    child.once("error", (error) => finish(error));
    child.once("close", (code) => finish(undefined, code));
  });
}

async function freePort() {
  const server = createServer();
  await new Promise((resolveListen, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolveListen);
  });
  const port = server.address().port;
  await new Promise((resolveClose, reject) =>
    server.close((error) => (error ? reject(error) : resolveClose())),
  );
  return port;
}

async function copyInputs(directory) {
  const files = [
    "podman-compose.yaml",
    "backend/Containerfile",
    "backend/.dockerignore",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "demo/demo_seed.json",
  ];
  const tracked = await run(
    "git",
    ["ls-files", "-z", "--", "frontend", "backend/app"],
    {
      cwd: repository,
      capture: true,
    },
  );
  const allowed = [
    ...files,
    ...tracked.split("\0").filter(Boolean),
    "frontend/browser-tests/run.mjs",
    "frontend/browser-tests/playwright.config.ts",
    "frontend/browser-tests/demo.spec.ts",
  ];
  for (const input of [...files, "backend/app", "frontend"]) {
    await cp(join(repository, input), join(directory, input), {
      recursive: true,
      verbatimSymlinks: true,
      filter: async (source) => {
        const path = relative(repository, source);
        if (
          !allowed.some((file) => file === path || file.startsWith(`${path}/`))
        )
          return false;
        const parts = path.split("/");
        if (
          parts.some(
            (name) =>
              name.startsWith(".env") ||
              name.endsWith(".pyc") ||
              name.endsWith(".log") ||
              name.endsWith(".local") ||
              [
                "__pycache__",
                ".git",
                "node_modules",
                ".venv",
                "data",
                "dist",
                "dist-ssr",
                "logs",
                ".cache",
                ".pytest_cache",
                ".ruff_cache",
                "browser-results",
                "artifacts",
              ].includes(name),
          )
        )
          return false;
        const stat = await lstat(source);
        if (stat.isSymbolicLink()) throw new Error(`Symlink input: ${input}`);
        return true;
      },
    });
  }
}

async function ready(origin) {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    abort.signal.throwIfAborted();
    try {
      const options = { signal: AbortSignal.timeout(2_000) };
      const health = await fetch(`${origin}/health`, options);
      const status = await fetch(`${origin}/api/auth/status`, options);
      if (health.ok && status.ok) {
        const metadata = await status.json();
        if (metadata.demo_mode_enabled === true && !metadata.setup_required)
          return;
        throw new Error("The isolated instance did not select demo mode.");
      }
    } catch (error) {
      if (error.message.includes("did not select demo mode")) throw error;
    }
    await delay(500, undefined, { signal: abort.signal });
  }
  throw new Error("The isolated demo did not become ready within 120 seconds.");
}

let directory;
let composeArgs;
let results;
let stage = "source preflight";
let success = false;
let cleanup = "not needed";
const project = `nashordaq-browser-${randomUUID().slice(0, 12)}`;
try {
  for (const name of ["backend", "frontend", "demo"]) {
    const directory = await lstat(join(repository, name));
    if (directory.isSymbolicLink() || !directory.isDirectory()) {
      throw new Error(`Source directory must be a real directory: ${name}`);
    }
  }
  stage = "provider preflight";
  const version = await run(runtime, ["--version"], { capture: true });
  if (runtime === "docker" && /podman/i.test(version)) {
    throw new Error(
      "docker is a Podman shim. Select --runtime podman instead.",
    );
  }
  console.log(`Provider: ${version}`);
  if (runtime === "docker") {
    const engine = await run(
      "docker",
      ["version", "--format", "{{.Server.Platform.Name}} {{.Server.Version}}"],
      { capture: true },
    );
    if (/podman/i.test(engine))
      throw new Error("Docker Engine is unavailable.");
    console.log(`Engine: ${engine}`);
  } else {
    console.log(
      `Engine: ${await run("podman", ["info", "--format", "{{.Version.Version}}"], { capture: true })}`,
    );
  }
  console.log(
    await run(command, [...composePrefix, "--version"], { capture: true }),
  );
  stage = "Chromium preflight";
  const browser = await chromium.launch({ timeout: 15_000 });
  await browser.close();
  directory = await mkdtemp(join(tmpdir(), "nashordaq-browser-"));
  results = join(frontend, "browser-results", project);
  await mkdir(results, { recursive: true, mode: 0o700 });
  stage = "copy inputs";
  await copyInputs(directory);
  await mkdir(join(directory, "data"), { mode: 0o700 });
  const port = await freePort();
  const origin = `http://127.0.0.1:${port}`;
  await writeFile(
    join(directory, ".env"),
    [
      "NASHORDAQ_DEMO_MODE_ENABLED=true",
      "NASHORDAQ_RIOT_API_KEY=",
      "NASHORDAQ_GAMBA_ENABLED=false",
      "NASHORDAQ_HTTP_BIND=127.0.0.1",
      `NASHORDAQ_HTTP_PORT=${port}`,
      `NASHORDAQ_PUBLIC_URL=${origin}`,
      "",
    ].join("\n"),
    { mode: 0o600 },
  );
  composeArgs = [
    ...composePrefix,
    "-p",
    project,
    "-f",
    join(directory, "podman-compose.yaml"),
  ];
  console.log(
    `Project: ${project}\nTemporary directory: ${directory}\nOrigin: ${origin}\nResults: ${results}`,
  );
  stage = "Compose build and startup";
  await run(command, [...composeArgs, "up", "--build", "-d"], {
    cwd: directory,
    timeout: 600_000,
  });
  stage = "HTTP readiness";
  await ready(origin);
  stage = "browser journey";
  const require = createRequire(import.meta.url);
  await run(
    process.execPath,
    [
      require.resolve("@playwright/test/cli"),
      "test",
      "--config",
      "browser-tests/playwright.config.ts",
    ],
    {
      timeout: 120_000,
      env: {
        ...environment,
        NASHORDAQ_BROWSER_URL: origin,
        NASHORDAQ_BROWSER_RESULTS: join(results, "screenshots"),
      },
    },
  );
  success = true;
} catch (error) {
  console.error(`Failed at ${stage}: ${error.message}`);
  process.exitCode = 1;
} finally {
  if (composeArgs) {
    try {
      await run(command, [...composeArgs, "down", "--remove-orphans"], {
        cwd: directory,
        timeout: 60_000,
        signal: new AbortController().signal,
      });
      cleanup = "passed";
    } catch {
      cleanup = "failed";
      process.exitCode = 1;
      console.error(
        `Cleanup failed. Preserve ${directory}. Retry: ${command} ${composeArgs.join(" ")} down --remove-orphans`,
      );
    }
  }
  if (directory && cleanup !== "failed") {
    await rm(directory, { recursive: true, force: true });
  }
  if (results) {
    await writeFile(
      join(results, "result.json"),
      JSON.stringify(
        {
          project,
          runtime,
          stage,
          success,
          cleanup,
          exitCode: process.exitCode ?? 0,
        },
        null,
        2,
      ) + "\n",
      { mode: 0o600 },
    );
  }
  console.log(
    `Browser journey: ${success ? "passed" : "failed"}; cleanup: ${cleanup}`,
  );
}
