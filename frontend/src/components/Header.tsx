import { useState } from "react";
import { useStreamerMode } from "../contexts/useStreamerMode";
import { formatAmount } from "../utils/format";
import { getStreamerSafeName } from "../utils/streamerMode";

export default function Header({
  balance,
  netWorth = 0,
  username,
  playerDisplayName,
  playerGameName,
  canEditProfile = false,
  canToggleAdminView = false,
  adminViewMode = "spectator",
  onOpenBalanceInsights,
  onEditProfile,
  onToggleAdminView,
}: {
  balance: number;
  netWorth?: number;
  username?: string;
  playerDisplayName?: string;
  playerGameName?: string;
  canEditProfile?: boolean;
  canToggleAdminView?: boolean;
  adminViewMode?: "spectator" | "admin";
  onOpenBalanceInsights?: () => void;
  onEditProfile?: () => void;
  onToggleAdminView?: () => void;
}) {
  const { isStreamerMode, toggleStreamerMode } = useStreamerMode();
  const initial = username ? username[0].toUpperCase() : "?";
  const [menuOpen, setMenuOpen] = useState(false);

  function handleEditProfile() {
    setMenuOpen(false);
    onEditProfile?.();
  }

  return (
    <header className="border-b-4 border-hex-gold bg-hex-bg-alt">
      <div className="mx-auto flex max-w-[88rem] items-center justify-between px-6 py-4">
        {/* Brand */}
        <div className="flex items-baseline gap-3">
          <h1 className="font-serif text-4xl font-black tracking-tight text-hex-gold">
            NASHORDAQ
          </h1>
          <span className="hidden text-xs font-medium uppercase tracking-[0.3em] text-hex-bronze sm:inline">
            Fantasy Market
          </span>
        </div>

        {/* Account bar */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onOpenBalanceInsights}
              className="min-w-44 border-2 border-hex-gold-dim px-3.5 py-1.5 text-left shadow-brutal-sm transition-colors hover:border-hex-gold hover:bg-hex-bg-alt/70"
            >
              <div className="text-xs uppercase tracking-wider text-hex-bronze">
                Balance
              </div>
              <p className="font-mono text-lg font-bold text-hex-gold">
                {formatAmount(balance)}
                <span className="ml-1 text-xs text-hex-bronze">P</span>
              </p>
              <p className="mt-1 font-mono text-[11px] text-hex-bronze">
                Net worth {formatAmount(netWorth)} P
              </p>
            </button>
          </div>
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((current) => !current)}
              className="h-10 w-10 border-2 border-hex-gold bg-hex-panel text-center font-serif text-lg leading-9 font-bold text-hex-gold transition-colors hover:bg-hex-gold hover:text-hex-bg"
            >
              {initial}
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-12 z-20 w-64 border-2 border-hex-gold-dim bg-hex-panel p-3 shadow-brutal-lg">
                <div className="border-b border-hex-border pb-3">
                  <p className="font-mono text-xs uppercase tracking-wider text-hex-bronze">
                    Signed in as
                  </p>
                  <p className="mt-1 break-all font-mono text-sm font-bold text-hex-white">
                    {username ?? "Unknown User"}
                  </p>
                  {(playerDisplayName || playerGameName) && (
                    <p className="mt-2 font-mono text-xs text-hex-bronze">
                      Summoner:{" "}
                      {isStreamerMode
                        ? getStreamerSafeName(playerGameName, playerDisplayName)
                        : (playerDisplayName ?? playerGameName)}
                    </p>
                  )}
                </div>

                <button
                  type="button"
                  onClick={toggleStreamerMode}
                  className="mt-3 w-full border border-hex-border px-3 py-2 text-left font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze transition-colors hover:border-hex-gold hover:text-hex-gold"
                >
                  Streamer Mode: {isStreamerMode ? "On" : "Off"}
                </button>

                {canToggleAdminView && (
                  <button
                    type="button"
                    onClick={onToggleAdminView}
                    className="mt-3 w-full border border-hex-border px-3 py-2 text-left font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze transition-colors hover:border-hex-gold hover:text-hex-gold"
                  >
                    View Mode:{" "}
                    {adminViewMode === "admin" ? "Admin" : "Spectator"}
                  </button>
                )}

                <button
                  type="button"
                  onClick={handleEditProfile}
                  disabled={!canEditProfile}
                  className={`mt-3 w-full border px-3 py-2 text-left font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                    canEditProfile
                      ? "border-hex-gold text-hex-gold hover:bg-hex-gold hover:text-hex-bg"
                      : "cursor-not-allowed border-hex-border text-hex-border"
                  }`}
                >
                  Edit Summoner Profile
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
