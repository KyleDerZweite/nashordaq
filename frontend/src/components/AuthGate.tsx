import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import App from "../App";
import { ApiError, get, post } from "../api/client";

interface AuthStatus {
  setup_required: boolean;
  demo_mode_enabled: boolean;
}

type AuthState =
  | { kind: "checking" }
  | { kind: "signedIn" }
  | { kind: "signedOut"; status: AuthStatus }
  | { kind: "unavailable" };

function AuthPage({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-hex-bg px-6 py-12">
      <div className="w-full max-w-md border-2 border-hex-gold-dim bg-hex-panel p-6 shadow-brutal-lg sm:p-8">
        <h1 className="font-serif text-4xl font-black tracking-tight text-hex-gold">
          NASHORDAQ
        </h1>
        <p className="mb-8 mt-2 text-sm text-hex-bronze">
          Your private fantasy market
        </p>
        {children}
      </div>
    </main>
  );
}

function SignInForm({
  status,
  message,
  onAuthenticated,
}: {
  status: AuthStatus;
  message?: string;
  onAuthenticated: () => void;
}) {
  const [registrationToken] = useState(() =>
    ["/setup", "/invite"].includes(window.location.pathname)
      ? new URLSearchParams(window.location.search).get("token")
      : null,
  );
  const isSetup = window.location.pathname === "/setup";
  const isInvitation = window.location.pathname === "/invite";
  const isRegistration = isSetup || isInvitation;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
  const [isPending, setIsPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isPending) return;
    setError(undefined);
    setIsPending(true);
    try {
      await post<{ status: "ok" }>(
        isSetup
          ? "/auth/setup"
          : isInvitation
            ? "/auth/register"
            : "/auth/login",
        isRegistration
          ? { token: registrationToken, username, password }
          : { username, password },
      );
      if (isRegistration) {
        window.history.replaceState(null, "", "/");
      }
      await get<{ authenticated: true }>("/auth/session");
      onAuthenticated();
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "Unable to connect. Please try again.",
      );
    } finally {
      setIsPending(false);
    }
  }

  if (status.demo_mode_enabled) {
    return (
      <AuthPage>
        <h2 className="font-serif text-2xl font-bold text-hex-white">
          Demo unavailable
        </h2>
        <p className="mt-4 text-sm text-hex-bronze">
          Demo sign-in is not available on this installation yet.
        </p>
      </AuthPage>
    );
  }

  if (isSetup && (!registrationToken || !status.setup_required)) {
    return (
      <AuthPage>
        <h2 className="font-serif text-2xl font-bold text-hex-white">
          Setup unavailable
        </h2>
        <p role="alert" className="mt-4 text-sm text-hex-bronze">
          {status.setup_required
            ? "This setup link is missing its token. Open the complete one-time link from the container log."
            : "Administrator setup has already been completed. Sign in with your account."}
        </p>
        <a href="/" className="mt-6 inline-block text-hex-gold underline">
          Go to sign in
        </a>
      </AuthPage>
    );
  }

  if (isInvitation && !registrationToken) {
    return (
      <AuthPage>
        <h2 className="font-serif text-2xl font-bold text-hex-white">
          Invitation unavailable
        </h2>
        <p role="alert" className="mt-4 text-sm text-hex-bronze">
          This invitation is missing its token. Ask the administrator for a
          complete invitation link.
        </p>
        <a href="/" className="mt-6 inline-block text-hex-gold underline">
          Go to sign in
        </a>
      </AuthPage>
    );
  }

  return (
    <AuthPage>
      <h2 className="font-serif text-2xl font-bold text-hex-white">
        {isSetup
          ? "Create administrator account"
          : isInvitation
            ? "Join the private market"
            : "Sign in"}
      </h2>
      {isSetup ? (
        <p className="mt-3 text-sm text-hex-bronze">
          Create the sole administrator for this private market. You can link
          your Riot account separately.
        </p>
      ) : isInvitation ? (
        <p className="mt-3 text-sm text-hex-bronze">
          Choose your username and password. No email is required. You can link
          your Riot account after joining.
        </p>
      ) : status.setup_required ? (
        <p className="mt-3 text-sm text-hex-bronze">
          This installation needs its first administrator. The operator must
          open the one-time setup link from the backend container log.
        </p>
      ) : null}
      {message && (
        <p role="status" className="mt-4 text-sm text-hex-bronze">
          {message}
        </p>
      )}
      <form
        onSubmit={(event) => void handleSubmit(event)}
        className="mt-6 space-y-5"
      >
        <div>
          <label
            htmlFor="username"
            className="block text-sm font-bold text-hex-white"
          >
            Username
          </label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            required
            maxLength={64}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            disabled={isPending}
            className="mt-2 w-full border-2 border-hex-border bg-hex-bg px-3 py-2 text-hex-white outline-none focus:border-hex-gold disabled:opacity-50"
          />
        </div>
        <div>
          <label
            htmlFor="password"
            className="block text-sm font-bold text-hex-white"
          >
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete={isRegistration ? "new-password" : "current-password"}
            required
            minLength={isRegistration ? 12 : undefined}
            maxLength={1024}
            aria-describedby={isRegistration ? "password-help" : undefined}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={isPending}
            className="mt-2 w-full border-2 border-hex-border bg-hex-bg px-3 py-2 text-hex-white outline-none focus:border-hex-gold disabled:opacity-50"
          />
          {isRegistration && (
            <p id="password-help" className="mt-2 text-xs text-hex-bronze">
              Use at least 12 characters.
            </p>
          )}
        </div>
        {error && (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={isPending}
          className="w-full border-2 border-hex-gold bg-hex-gold px-4 py-3 font-mono text-sm font-bold uppercase tracking-wider text-hex-bg transition-colors hover:bg-hex-gold-dim disabled:cursor-wait disabled:opacity-50"
        >
          {isPending
            ? "Please wait..."
            : isRegistration
              ? "Create account"
              : "Sign in"}
        </button>
      </form>
      {isInvitation && (
        <a
          href="/"
          className="mt-6 inline-block text-sm text-hex-gold underline"
        >
          Already have an account? Sign in
        </a>
      )}
    </AuthPage>
  );
}

export default function AuthGate() {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({ kind: "checking" });
  const [attempt, setAttempt] = useState(0);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string>();
  const [sessionMessage, setSessionMessage] = useState<string>();

  useEffect(() => {
    let active = true;
    async function checkSession() {
      const [status, session] = await Promise.allSettled([
        get<AuthStatus>("/auth/status"),
        get<{ authenticated: true }>("/auth/session"),
      ]);
      if (!active) return;
      if (session.status === "fulfilled") {
        setState({ kind: "signedIn" });
      } else if (
        status.status === "fulfilled" &&
        session.reason instanceof ApiError &&
        session.reason.status === 401
      ) {
        setState({ kind: "signedOut", status: status.value });
      } else {
        setState({ kind: "unavailable" });
      }
    }
    void checkSession();
    return () => {
      active = false;
    };
  }, [attempt]);

  useEffect(() => {
    function onSessionLost() {
      queryClient.clear();
      setLogoutError(undefined);
      setSessionMessage("Your session has ended. Sign in again.");
      setState({ kind: "checking" });
      setAttempt((current) => current + 1);
    }
    window.addEventListener("nashordaq:session-lost", onSessionLost);
    return () =>
      window.removeEventListener("nashordaq:session-lost", onSessionLost);
  }, [queryClient]);

  async function logout() {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    setLogoutError(undefined);
    try {
      await post<{ status: "ok" }>("/auth/logout", {});
      queryClient.clear();
      setSessionMessage(undefined);
      setState({ kind: "checking" });
      setAttempt((current) => current + 1);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        queryClient.clear();
        setSessionMessage("Your session has ended. Sign in again.");
        setState({ kind: "checking" });
        setAttempt((current) => current + 1);
        return;
      }
      setLogoutError(
        cause instanceof ApiError
          ? cause.message
          : "Unable to sign out. Please try again.",
      );
    } finally {
      setIsLoggingOut(false);
    }
  }

  if (state.kind === "signedIn" && window.location.pathname === "/invite") {
    return (
      <AuthPage>
        <h2 className="font-serif text-2xl font-bold text-hex-white">
          Already signed in
        </h2>
        <p className="mt-4 text-sm text-hex-bronze">
          Sign out before using this invitation to create another account.
        </p>
        {logoutError && (
          <p role="alert" className="mt-4 text-sm text-red-300">
            {logoutError}
          </p>
        )}
        <button
          type="button"
          disabled={isLoggingOut}
          onClick={() => void logout()}
          className="mt-6 w-full border-2 border-hex-gold bg-hex-gold px-4 py-3 text-hex-bg disabled:opacity-50"
        >
          {isLoggingOut ? "Signing out..." : "Sign out"}
        </button>
        <a
          href="/"
          className="mt-6 inline-block text-sm text-hex-gold underline"
        >
          Return to the market
        </a>
      </AuthPage>
    );
  }
  if (state.kind === "signedIn") {
    return (
      <App
        onLogout={() => void logout()}
        isLoggingOut={isLoggingOut}
        logoutError={logoutError}
      />
    );
  }
  if (state.kind === "signedOut") {
    return (
      <SignInForm
        status={state.status}
        message={sessionMessage}
        onAuthenticated={() => {
          queryClient.clear();
          setSessionMessage(undefined);
          setState({ kind: "signedIn" });
        }}
      />
    );
  }
  return (
    <AuthPage>
      {state.kind === "checking" ? (
        <p role="status" className="text-sm text-hex-bronze">
          Checking your session...
        </p>
      ) : (
        <>
          <p role="alert" className="text-sm text-red-300">
            Unable to connect to Nashordaq. Please try again.
          </p>
          <button
            type="button"
            onClick={() => {
              setState({ kind: "checking" });
              setAttempt((current) => current + 1);
            }}
            className="mt-6 border-2 border-hex-gold px-4 py-2 font-mono text-sm text-hex-gold"
          >
            Try again
          </button>
        </>
      )}
    </AuthPage>
  );
}
