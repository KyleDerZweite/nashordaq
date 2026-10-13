import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, post } from "../api/client";

export default function ResetPasswordForm({
  demoMode,
  onReset,
}: {
  demoMode: boolean;
  onReset: () => void;
}) {
  const [token] = useState(() =>
    new URLSearchParams(window.location.search).get("token"),
  );
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState<string>();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError(undefined);
    try {
      await post("/auth/reset", { token, new_password: password });
      setPassword("");
      window.history.replaceState(null, "", "/reset");
      setComplete(true);
      onReset();
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "Unable to connect. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }

  if (demoMode || !token || complete) {
    return (
      <>
        <h2 className="font-serif text-2xl font-bold text-hex-white">
          {complete ? "Password reset" : "Reset unavailable"}
        </h2>
        <p
          role={complete ? "status" : "alert"}
          className="mt-4 text-sm text-hex-bronze"
        >
          {complete
            ? "Your password has changed and all your previous sessions have ended. Sign in with your new password."
            : demoMode
              ? "Password recovery is unavailable in demo mode."
              : "This link is missing its token. Ask the administrator for a complete reset link."}
        </p>
        <a href="/" className="mt-6 inline-block text-hex-gold underline">
          Go to sign in
        </a>
      </>
    );
  }
  return (
    <>
      <h2 className="font-serif text-2xl font-bold text-hex-white">
        Reset your password
      </h2>
      <p id="reset-password-help" className="mt-3 text-sm text-hex-bronze">
        Choose a password with at least 12 characters. This link works once and
        expires after one hour. All your existing sessions will end.
      </p>
      <form onSubmit={(event) => void submit(event)} className="mt-6 space-y-5">
        <div>
          <label
            htmlFor="reset-password"
            className="block text-sm font-bold text-hex-white"
          >
            New password
          </label>
          <input
            id="reset-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={1024}
            aria-describedby="reset-password-help"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={pending}
            className="mt-2 w-full border-2 border-hex-border bg-hex-bg px-3 py-2 text-hex-white focus:border-hex-gold focus:outline-none disabled:opacity-50"
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={pending}
          className="w-full border-2 border-hex-gold bg-hex-gold px-4 py-3 font-bold text-hex-bg hover:bg-hex-gold-dim disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          {pending ? "Resetting..." : "Set new password"}
        </button>
      </form>
      <a href="/" className="mt-6 inline-block text-sm text-hex-gold underline">
        Go to sign in
      </a>
    </>
  );
}
