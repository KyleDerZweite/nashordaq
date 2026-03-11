import { useState } from "react";

import { ApiError, getMarketAccount } from "../api";
import type { MarketAccountResponse, UserOnboardingCreate } from "../types";

interface Props {
  title: string;
  description: string;
  submitLabel: string;
  initialValues?: UserOnboardingCreate;
  isPending: boolean;
  errorMessage?: string;
  onSubmit: (body: UserOnboardingCreate) => void;
  onClose?: () => void;
}

export default function PlayerProfileModal({
  title,
  description,
  submitLabel,
  initialValues,
  isPending,
  errorMessage,
  onSubmit,
  onClose,
}: Props) {
  const [gameName, setGameName] = useState(initialValues?.game_name ?? "");
  const [tagLine, setTagLine] = useState(initialValues?.tag_line ?? "");
  const [displayName, setDisplayName] = useState(
    initialValues?.display_name ?? "",
  );
  const [isCheckingProfile, setIsCheckingProfile] = useState(false);
  const [lookupErrorMessage, setLookupErrorMessage] = useState<string>();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload = {
      game_name: gameName.trim(),
      tag_line: tagLine.trim().replace(/^#/, ""),
      display_name: displayName.trim(),
    };

    setLookupErrorMessage(undefined);
    setIsCheckingProfile(true);

    try {
      await getMarketAccount<MarketAccountResponse>(
        payload.game_name,
        payload.tag_line,
      );
      onSubmit(payload);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setLookupErrorMessage(
          "Summoner not found. Check the game name and tag line spelling before saving.",
        );
      } else if (error instanceof ApiError && error.status === 429) {
        setLookupErrorMessage(
          "Riot lookup is temporarily rate limited. Please wait a moment and try again.",
        );
      } else if (error instanceof Error) {
        setLookupErrorMessage(
          "We could not verify this Riot account right now. Please try again in a moment.",
        );
      } else {
        setLookupErrorMessage(
          "We could not verify this Riot account right now. Please try again in a moment.",
        );
      }
    } finally {
      setIsCheckingProfile(false);
    }
  }

  const canSubmit =
    gameName.trim().length > 0 &&
    tagLine.trim().length > 0 &&
    displayName.trim().length > 0;
  const isBusy = isPending || isCheckingProfile;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/90 px-4"
      onClick={onClose}
    >
      <section
        className="w-full max-w-md border-4 border-hex-gold bg-hex-panel shadow-brutal-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b-4 border-hex-gold px-5 py-3">
          <div>
            <h2 className="font-serif text-xl font-bold text-hex-gold">
              {title}
            </h2>
            <p className="mt-1 font-mono text-xs text-hex-bronze">
              {description}
            </p>
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="border-2 border-hex-border px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-bronze transition-colors hover:border-hex-white hover:text-hex-white"
            >
              Close
            </button>
          )}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-4">
          <div>
            <label className="mb-1 block font-mono text-xs uppercase tracking-wider text-hex-bronze">
              Game Name
            </label>
            <input
              type="text"
              value={gameName}
              onChange={(e) => {
                setGameName(e.target.value);
                setLookupErrorMessage(undefined);
              }}
              autoFocus
              className="w-full border-2 border-hex-border bg-hex-bg px-3 py-2 font-mono text-sm text-hex-white outline-none focus:border-hex-gold"
            />
          </div>

          <div>
            <label className="mb-1 block font-mono text-xs uppercase tracking-wider text-hex-bronze">
              Tag Line (without #)
            </label>
            <input
              type="text"
              value={tagLine}
              onChange={(e) => {
                setTagLine(e.target.value.replace(/^#/, ""));
                setLookupErrorMessage(undefined);
              }}
              placeholder="EUW"
              className="w-full border-2 border-hex-border bg-hex-bg px-3 py-2 font-mono text-sm text-hex-white outline-none focus:border-hex-gold"
            />
          </div>

          <div>
            <label className="mb-1 block font-mono text-xs uppercase tracking-wider text-hex-bronze">
              Display Name
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => {
                setDisplayName(e.target.value);
                setLookupErrorMessage(undefined);
              }}
              className="w-full border-2 border-hex-border bg-hex-bg px-3 py-2 font-mono text-sm text-hex-white outline-none focus:border-hex-gold"
            />
          </div>

          {lookupErrorMessage && (
            <p className="font-mono text-xs text-hex-zaun">
              {lookupErrorMessage}
            </p>
          )}

          {errorMessage && (
            <p className="font-mono text-xs text-hex-zaun">{errorMessage}</p>
          )}

          <button
            type="submit"
            disabled={!canSubmit || isBusy}
            className={`w-full border-2 py-2.5 font-mono text-sm font-bold uppercase tracking-wider transition-colors ${
              isBusy
                ? "border-hex-magic bg-hex-magic/20 text-hex-magic"
                : canSubmit
                  ? "border-hex-gold bg-transparent text-hex-gold hover:bg-hex-gold hover:text-hex-bg"
                  : "cursor-not-allowed border-hex-border text-hex-border"
            }`}
          >
            {isCheckingProfile
              ? "Checking Riot Account..."
              : isPending
                ? "Saving..."
                : submitLabel}
          </button>
        </form>
      </section>
    </div>
  );
}
