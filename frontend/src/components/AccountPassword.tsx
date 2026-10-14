import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, post } from "../api/client";

const inputClass =
  "mt-2 w-full border-2 border-hex-border bg-hex-bg px-3 py-2 text-hex-white focus:border-hex-gold focus:outline-none disabled:opacity-50";

export default function AccountPassword() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string>();
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError(undefined);
    try {
      await post("/auth/password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      window.dispatchEvent(
        new CustomEvent("nashordaq:session-lost", {
          detail:
            "Your password changed. All your sessions have ended. Sign in again.",
        }),
      );
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

  return (
    <details className="mb-6 border-2 border-hex-border bg-hex-panel p-4">
      <summary className="cursor-pointer text-sm font-bold text-hex-gold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">
        Change password
      </summary>
      <p id="account-password-help" className="mt-3 text-sm text-hex-bronze">
        Use at least 12 characters. Changing your password ends all your
        sessions, including this one.
      </p>
      <form
        onSubmit={(event) => void submit(event)}
        className="mt-4 max-w-md space-y-4"
      >
        <div>
          <label
            htmlFor="current-password"
            className="block text-sm text-hex-white"
          >
            Current password
          </label>
          <input
            id="current-password"
            type="password"
            autoComplete="current-password"
            required
            maxLength={1024}
            disabled={pending}
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label
            htmlFor="new-account-password"
            className="block text-sm text-hex-white"
          >
            New password
          </label>
          <input
            id="new-account-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={1024}
            aria-describedby="account-password-help"
            disabled={pending}
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            className={inputClass}
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        )}
        <button
          disabled={pending}
          type="submit"
          className="border-2 border-hex-gold px-4 py-2 text-sm font-bold text-hex-gold hover:bg-hex-bg disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          {pending ? "Changing..." : "Save new password"}
        </button>
      </form>
    </details>
  );
}
