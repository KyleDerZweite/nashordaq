import { useState } from "react";
import AdminPasswordResets from "./AdminPasswordResets";
import SecretLinkDelivery from "./SecretLinkDelivery";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { del, get, post } from "../../api/client";
import { formatLocalDateTime } from "../../utils/format";

interface Invitation {
  id: number;
  expires_at: string;
  consumed_at: string | null;
  revoked_at: string | null;
  status: "active" | "consumed" | "revoked" | "expired";
}

interface CreatedInvitation extends Invitation {
  url: string;
}

const queryKey = ["admin", "invitations"];
const buttonClass =
  "border-2 border-hex-gold px-4 py-2 text-sm font-bold text-hex-gold hover:bg-hex-bg disabled:cursor-wait disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-hex-gold";

function MemberInvitations() {
  const queryClient = useQueryClient();
  const [latestInvitation, setLatestInvitation] = useState<CreatedInvitation>();
  const invitations = useQuery({
    queryKey,
    queryFn: () => get<Invitation[]>("/auth/invites"),
  });
  const create = useMutation({
    mutationFn: () => post<CreatedInvitation>("/auth/invites", {}),
    onSuccess: (invitation) => {
      setLatestInvitation(invitation);
      void queryClient.invalidateQueries({ queryKey });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: number) => del<{ status: "ok" }>(`/auth/invites/${id}`),
    onSuccess: (_, id) => {
      if (latestInvitation?.id === id) setLatestInvitation(undefined);
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: () => {
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  return (
    <section
      aria-labelledby="invitations-title"
      className="border-2 border-hex-gold-dim bg-hex-panel p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2
            id="invitations-title"
            className="font-serif text-2xl font-bold text-hex-gold"
          >
            Member invitations
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-hex-bronze">
            Invite a member to choose their own username and password. Each
            invitation works once and expires after seven days.
          </p>
        </div>
        <button
          type="button"
          onClick={() => create.mutate()}
          disabled={create.isPending}
          className={buttonClass}
        >
          {create.isPending ? "Creating..." : "Create invitation"}
        </button>
      </div>
      {create.isError && (
        <p role="alert" className="mt-4 text-sm text-red-300">
          {create.error.message}
        </p>
      )}
      {latestInvitation && (
        <SecretLinkDelivery
          key={latestInvitation.id}
          id="invitation-link"
          label="Invitation link"
          url={latestInvitation.url}
          copyLabel="Copy invitation link"
          copySuccess="Invitation link copied."
          buttonClass={buttonClass}
        >
          Invitation #{latestInvitation.id} created. Share this link privately
          with the invited member.
        </SecretLinkDelivery>
      )}
      {invitations.isPending && (
        <p role="status" className="mt-5 text-sm text-hex-bronze">
          Loading invitations...
        </p>
      )}
      {invitations.isError && (
        <div className="mt-5">
          <p role="alert" className="text-sm text-red-300">
            Unable to load invitations. {invitations.error.message}
          </p>
          <button
            type="button"
            onClick={() => void invitations.refetch()}
            className={`${buttonClass} mt-3`}
          >
            Retry
          </button>
        </div>
      )}
      {invitations.data?.length === 0 && (
        <p className="mt-5 text-sm text-hex-bronze">No invitations yet.</p>
      )}
      {invitations.data && invitations.data.length > 0 && (
        <ul className="mt-5 divide-y divide-hex-border">
          {invitations.data.map((invitation) => (
            <li
              key={invitation.id}
              className="flex flex-wrap items-center justify-between gap-3 py-4"
            >
              <div className="text-sm">
                <p className="text-hex-white">
                  Invitation #{invitation.id}{" "}
                  <span className="capitalize text-hex-gold">
                    {invitation.status}
                  </span>
                </p>
                <p className="mt-1 text-hex-bronze">
                  Expires {formatLocalDateTime(invitation.expires_at)}
                </p>
                {invitation.consumed_at && (
                  <p className="mt-1 text-hex-bronze">
                    Used {formatLocalDateTime(invitation.consumed_at)}
                  </p>
                )}
                {invitation.revoked_at && (
                  <p className="mt-1 text-hex-bronze">
                    Revoked {formatLocalDateTime(invitation.revoked_at)}
                  </p>
                )}
              </div>
              {invitation.status === "active" && (
                <button
                  type="button"
                  aria-label={`Revoke invitation ${invitation.id}`}
                  onClick={() => revoke.mutate(invitation.id)}
                  disabled={revoke.isPending}
                  className={buttonClass}
                >
                  {revoke.isPending && revoke.variables === invitation.id
                    ? "Revoking..."
                    : "Revoke"}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {revoke.isError && (
        <p role="alert" className="mt-4 text-sm text-red-300">
          {revoke.error.message}
        </p>
      )}
    </section>
  );
}

export default function AdminAccessManagement() {
  return (
    <>
      <MemberInvitations />
      <AdminPasswordResets />
    </>
  );
}
