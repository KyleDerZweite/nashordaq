import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAdminUsers } from "../../api/hooks";
import { useIdentityPresentation } from "../../contexts/useIdentityPresentation";
import { del, get, post } from "../../api/client";
import { formatLocalDateTime } from "../../utils/format";

interface ResetLink {
  id: number;
  user_id: number;
  expires_at: string;
  consumed_at: string | null;
  revoked_at: string | null;
  status: "active" | "consumed" | "revoked" | "expired";
}
interface CreatedReset extends ResetLink {
  url: string;
}
const queryKey = ["admin", "password-resets"];
const buttonClass =
  "border-2 border-hex-gold px-4 py-2 text-sm font-bold text-hex-gold hover:bg-hex-bg disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-hex-gold";

export default function AdminPasswordResets() {
  const queryClient = useQueryClient();
  const { userName } = useIdentityPresentation();
  const users = useAdminUsers();
  const resets = useQuery({
    queryKey,
    queryFn: () => get<ResetLink[]>("/auth/resets"),
  });
  const [selectedUser, setSelectedUser] = useState("");
  const [latest, setLatest] = useState<CreatedReset>();
  const [copyMessage, setCopyMessage] = useState<string>();
  const create = useMutation({
    mutationFn: (userId: number) =>
      post<CreatedReset>("/auth/resets", { user_id: userId }),
    onSuccess: (reset) => {
      setLatest(reset);
      setCopyMessage(undefined);
      void queryClient.invalidateQueries({ queryKey });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: number) => del(`/auth/resets/${id}`),
    onSuccess: (_, id) => {
      if (latest?.id === id) setLatest(undefined);
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: () => {
      void queryClient.invalidateQueries({ queryKey });
    },
  });
  async function copy() {
    if (!latest) return;
    try {
      await navigator.clipboard.writeText(latest.url);
      setCopyMessage("Reset link copied.");
    } catch {
      setCopyMessage(
        "Select and copy the link above. Clipboard access is unavailable.",
      );
    }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedUser && !create.isPending) create.mutate(Number(selectedUser));
  }
  return (
    <section
      aria-labelledby="password-resets-title"
      className="border-2 border-hex-gold-dim bg-hex-panel p-5 sm:p-6"
    >
      <h2
        id="password-resets-title"
        className="font-serif text-2xl font-bold text-hex-gold"
      >
        Password recovery
      </h2>
      <p className="mt-2 text-sm text-hex-bronze">
        Create a private reset link for an account. It works once for one hour.
        Resetting ends every session of that account.
      </p>
      {users.isPending && (
        <p role="status" className="mt-4 text-sm text-hex-bronze">
          Loading accounts...
        </p>
      )}
      {users.isError && (
        <div className="mt-4">
          <p role="alert" className="text-sm text-red-300">
            Unable to load accounts. {users.error.message}
          </p>
          <button
            type="button"
            onClick={() => void users.refetch()}
            className={`${buttonClass} mt-3`}
          >
            Retry accounts
          </button>
        </div>
      )}
      <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <label
            htmlFor="reset-account"
            className="block text-sm font-bold text-hex-white"
          >
            Account to recover
          </label>
          <select
            id="reset-account"
            required
            value={selectedUser}
            disabled={users.isPending || users.isError || create.isPending}
            onChange={(event) => setSelectedUser(event.target.value)}
            className="mt-2 w-full min-w-0 border-2 border-hex-border bg-hex-bg px-3 py-2 text-hex-white focus:border-hex-gold focus:outline-none disabled:opacity-50"
          >
            <option value="">Choose an account</option>
            {users.data?.map((user) => (
              <option key={user.id} value={user.id}>
                {userName(user.id)}
                {user.role === "admin" ? " (administrator)" : ""}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          disabled={!selectedUser || create.isPending || users.isError}
          className={buttonClass}
        >
          {create.isPending ? "Creating..." : "Create reset link"}
        </button>
      </form>
      {create.isError && (
        <p role="alert" className="mt-4 text-sm text-red-300">
          {create.error.message}
        </p>
      )}
      {latest && (
        <div className="mt-5 border border-hex-gold-dim bg-hex-bg p-4">
          <p role="status" className="text-sm text-hex-white">
            Reset link created for {userName(latest.user_id)}. Share it
            privately with that account's owner.
          </p>
          <label
            htmlFor="password-reset-link"
            className="mt-3 block text-sm font-bold text-hex-white"
          >
            Password reset link
          </label>
          <input
            id="password-reset-link"
            readOnly
            value={latest.url}
            onFocus={(event) => event.target.select()}
            className="mt-2 w-full min-w-0 border-2 border-hex-border bg-hex-bg-alt px-3 py-2 text-sm text-hex-white focus:border-hex-gold focus:outline-none"
          />
          <p className="mt-2 text-xs text-hex-bronze">
            Save this link now. It cannot be retrieved after leaving this page.
          </p>
          <button
            type="button"
            onClick={() => void copy()}
            className={`${buttonClass} mt-3`}
          >
            Copy reset link
          </button>
          {copyMessage && (
            <p role="status" className="mt-3 text-sm text-hex-bronze">
              {copyMessage}
            </p>
          )}
        </div>
      )}
      {resets.isPending && (
        <p role="status" className="mt-5 text-sm text-hex-bronze">
          Loading reset links...
        </p>
      )}
      {resets.isError && (
        <div className="mt-5">
          <p role="alert" className="text-sm text-red-300">
            Unable to load reset links. {resets.error.message}
          </p>
          <button
            type="button"
            onClick={() => void resets.refetch()}
            className={`${buttonClass} mt-3`}
          >
            Retry reset links
          </button>
        </div>
      )}
      {resets.data?.length === 0 && (
        <p className="mt-5 text-sm text-hex-bronze">No reset links yet.</p>
      )}
      <ul className="mt-5 divide-y divide-hex-border">
        {resets.data?.map((reset) => (
          <li
            key={reset.id}
            className="flex flex-wrap items-center justify-between gap-3 py-4"
          >
            <div className="min-w-0 break-words text-sm">
              <p className="text-hex-white">
                Reset #{reset.id} for {userName(reset.user_id)}{" "}
                <span className="capitalize text-hex-gold">{reset.status}</span>
              </p>
              <p className="mt-1 text-hex-bronze">
                Expires {formatLocalDateTime(reset.expires_at)}
              </p>
              {reset.consumed_at && (
                <p className="mt-1 text-hex-bronze">
                  Used {formatLocalDateTime(reset.consumed_at)}
                </p>
              )}
              {reset.revoked_at && (
                <p className="mt-1 text-hex-bronze">
                  Revoked {formatLocalDateTime(reset.revoked_at)}
                </p>
              )}
            </div>
            {reset.status === "active" && (
              <button
                type="button"
                aria-label={`Revoke reset ${reset.id}`}
                onClick={() => revoke.mutate(reset.id)}
                disabled={revoke.isPending}
                className={buttonClass}
              >
                {revoke.isPending && revoke.variables === reset.id
                  ? "Revoking..."
                  : "Revoke"}
              </button>
            )}
          </li>
        ))}
      </ul>
      {revoke.isError && (
        <p role="alert" className="mt-4 text-sm text-red-300">
          {revoke.error.message}
        </p>
      )}
    </section>
  );
}
