import { useState } from "react";
import { useCompleteOnboarding } from "../api";

export default function OnboardingModal() {
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine] = useState("");
  const [displayName, setDisplayName] = useState("");
  const completeOnboarding = useCompleteOnboarding();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    completeOnboarding.mutate({
      game_name: gameName.trim(),
      tag_line: tagLine.trim().replace(/^#/, ""),
      display_name: displayName.trim(),
    });
  }

  const canSubmit =
    gameName.trim().length > 0 &&
    tagLine.trim().length > 0 &&
    displayName.trim().length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/90 px-4">
      <section
        className="w-full max-w-md border-4 border-hex-gold bg-hex-panel shadow-brutal-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b-4 border-hex-gold px-5 py-3">
          <h2 className="font-serif text-xl font-bold text-hex-gold">
            Complete Your Player Setup
          </h2>
          <p className="mt-1 font-mono text-xs text-hex-bronze">
            Enter your Riot account once to join the market.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-4">
          <div>
            <label className="mb-1 block font-mono text-xs uppercase tracking-wider text-hex-bronze">
              Game Name
            </label>
            <input
              type="text"
              value={gameName}
              onChange={(e) => setGameName(e.target.value)}
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
              onChange={(e) => setTagLine(e.target.value.replace(/^#/, ""))}
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
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full border-2 border-hex-border bg-hex-bg px-3 py-2 font-mono text-sm text-hex-white outline-none focus:border-hex-gold"
            />
          </div>

          {completeOnboarding.isError && (
            <p className="font-mono text-xs text-hex-zaun">
              {completeOnboarding.error.message}
            </p>
          )}

          <button
            type="submit"
            disabled={!canSubmit || completeOnboarding.isPending}
            className={`w-full border-2 py-2.5 font-mono text-sm font-bold uppercase tracking-wider transition-colors ${
              completeOnboarding.isPending
                ? "border-hex-magic bg-hex-magic/20 text-hex-magic"
                : canSubmit
                  ? "border-hex-gold bg-transparent text-hex-gold hover:bg-hex-gold hover:text-hex-bg"
                  : "cursor-not-allowed border-hex-border text-hex-border"
            }`}
          >
            {completeOnboarding.isPending ? "Saving..." : "Join Market"}
          </button>
        </form>
      </section>
    </div>
  );
}
