import { useState } from "react";
import { useStreamerMode } from "../contexts/useStreamerMode";
import { formatAmount } from "../utils/format";
import { getStreamerSafeName } from "../utils/streamerMode";

export default function Header({
  balance,
  netWorth = 0,
  displayName,
  playerDisplayName,
  playerGameName,
  canEditProfile = false,
  canToggleAdminView = false,
  adminViewMode = "participant",
  isDemo = false,
  showSimulation = false,
  onOpenBalanceInsights,
  onEditProfile,
  onOpenSimulation,
  onToggleAdminView,
  onLogout,
  isLoggingOut = false,
}: {
  balance: number;
  netWorth?: number;
  displayName?: string;
  playerDisplayName?: string;
  playerGameName?: string;
  canEditProfile?: boolean;
  canToggleAdminView?: boolean;
  adminViewMode?: "participant" | "admin";
  isDemo?: boolean;
  showSimulation?: boolean;
  onOpenBalanceInsights?: () => void;
  onEditProfile?: () => void;
  onOpenSimulation?: () => void;
  onToggleAdminView?: () => void;
  onLogout: () => void;
  isLoggingOut?: boolean;
}) {
  const { isStreamerMode, toggleStreamerMode } = useStreamerMode();
  const initial = displayName ? displayName[0].toUpperCase() : "?";
  const [menuOpen, setMenuOpen] = useState(false);

  function handleEditProfile() {
    setMenuOpen(false);
    onEditProfile?.();
  }

  return (
    <header className="border-b-4 border-hex-gold bg-hex-bg-alt">
      <div className="mx-auto flex max-w-[88rem] flex-col items-start gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
        {/* Brand */}
        <div className="flex items-baseline gap-3">
          <h1 className="font-serif text-3xl font-black sm:text-4xl tracking-tight text-hex-gold">
            NASHORDAQ
          </h1>
          <span className="hidden text-xs font-medium uppercase tracking-[0.3em] text-hex-bronze sm:inline">
            Fantasy Market
          </span>
          {isDemo && (
            <span className="border border-hex-gold bg-hex-gold/10 px-2 py-0.5 font-mono text-xs font-bold uppercase tracking-wider text-hex-gold">
              DEMO
            </span>
          )}
        </div>

        {/* Account bar */}
        <div className="flex w-full items-center justify-between gap-4 lg:w-auto lg:gap-6">
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
              aria-label="Account menu"
              aria-expanded={menuOpen}
              className="h-10 w-10 shrink-0 border-2 border-hex-gold bg-hex-panel text-center font-serif text-lg leading-9 font-bold text-hex-gold transition-colors hover:bg-hex-gold hover:text-hex-bg"
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
                    {displayName ?? "Unknown User"}
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
                    onClick={() => {
                      setMenuOpen(false);
                      onToggleAdminView?.();
                    }}
                    className="mt-3 w-full border border-hex-border px-3 py-2 text-left font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze transition-colors hover:border-hex-gold hover:text-hex-gold"
                  >
                    View Mode:{" "}
                    {adminViewMode === "admin" ? "Admin" : "Participant"}
                  </button>
                )}

                {canToggleAdminView && (
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      onOpenSimulation?.();
                    }}
                    className={`mt-3 w-full border px-3 py-2 text-left font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                      showSimulation
                        ? "border-hex-gold bg-hex-gold text-hex-bg"
                        : "border-hex-border text-hex-bronze hover:border-hex-gold hover:text-hex-gold"
                    }`}
                  >
                    Simulation Lab
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
                <button
                  type="button"
                  onClick={onLogout}
                  disabled={isLoggingOut}
                  className="mt-3 w-full border border-hex-gold px-3 py-2 text-left font-mono text-xs font-bold uppercase tracking-wider text-hex-gold transition-colors hover:bg-hex-gold hover:text-hex-bg disabled:cursor-wait disabled:opacity-50"
                >
                  {isLoggingOut ? "Signing out..." : "Sign out"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
