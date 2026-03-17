import { useEffect, useMemo, useState } from "react";
import BalanceInsightsModal from "./components/BalanceInsightsModal";
import AdminDashboard from "./components/admin/AdminDashboard";
import Header from "./components/Header";
import BankModal from "./components/BankModal";
import SimulationView from "./components/SimulationView";
import FlyingPoro from "./components/FlyingPoro";
import MarketGrid from "./components/MarketGrid";
import Portfolio from "./components/Portfolio";
import PortfolioInsightsModal from "./components/PortfolioInsightsModal";
import Leaderboard from "./components/Leaderboard";
import GambaWidget from "./components/GambaWidget";
import OrderHistory from "./components/OrderHistory";
import PlayerProfileModal from "./components/PlayerProfileModal";
import PlayerDetailsModal from "./components/PlayerDetailsModal";
import TradeTerminal from "./components/TradeTerminal";
import OnboardingModal from "./components/OnboardingModal";
import { useStreamerMode } from "./contexts/useStreamerMode";
import type { OrderSide } from "./types";
import { formatAmount, formatLocalDateTime } from "./utils/format";
import { getStreamerSafeName } from "./utils/streamerMode";

import {
  useBankSummary,
  useAdminOverview,
  useAdminPlayerInsights,
  useAdminSystemStatus,
  useAdminUsers,
  useUser,
  usePlayers,
  usePortfolio,
  useOrders,
  useRecentOrders,
  useLeaderboard,
  useSystemStatus,
  useUpdateUserProfile,
} from "./api";

interface TradeTarget {
  playerId: number;
  side: OrderSide;
}

type TickerSortMode = "value" | "name";
type AdminViewMode = "spectator" | "admin";

const ADMIN_VIEW_MODE_STORAGE_KEY = "nashordaq.adminViewMode";

function getInitialAdminViewMode(): AdminViewMode {
  if (typeof window === "undefined") {
    return "spectator";
  }

  const storedValue = window.localStorage.getItem(ADMIN_VIEW_MODE_STORAGE_KEY);
  return storedValue === "admin" ? "admin" : "spectator";
}

export default function App() {
  const { isStreamerMode } = useStreamerMode();
  const [trade, setTrade] = useState<TradeTarget | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [tickerSortMode, setTickerSortMode] = useState<TickerSortMode>("value");
  const [isProfileEditorOpen, setIsProfileEditorOpen] = useState(false);
  const [isBalanceInsightsOpen, setIsBalanceInsightsOpen] = useState(false);
  const [isBankModalOpen, setIsBankModalOpen] = useState(false);
  const [isPortfolioInsightsOpen, setIsPortfolioInsightsOpen] = useState(false);
  const [adminViewMode, setAdminViewMode] = useState<AdminViewMode>(
    getInitialAdminViewMode,
  );
  const [showSimulation, setShowSimulation] = useState(false);

  const { data: user } = useUser();
  const onboardingComplete = user?.onboarding_complete ?? false;
  const isAdmin = user?.role === "admin";
  const { data: players, isLoading: playersLoading } = usePlayers();
  const { data: portfolio } = usePortfolio(onboardingComplete && !isAdmin);
  const { data: orders } = useOrders(Boolean(user) && !isAdmin);
  const { data: recentOrders } = useRecentOrders(
    Boolean(user) && (!isAdmin || adminViewMode === "spectator"),
  );
  const { data: leaderboard } = useLeaderboard();
  const { data: systemStatus } = useSystemStatus();
  const { data: adminOverview } = useAdminOverview(isAdmin);
  const { data: adminUsers } = useAdminUsers(isAdmin);
  const { data: adminSystemStatus } = useAdminSystemStatus(isAdmin);
  const { data: adminPlayerInsights } = useAdminPlayerInsights(
    isAdmin && adminViewMode === "admin",
  );
  const updateUserProfile = useUpdateUserProfile();

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(ADMIN_VIEW_MODE_STORAGE_KEY, adminViewMode);
  }, [adminViewMode]);

  const balance = user?.balance ?? 0;
  const canTrade =
    Boolean(user) && user?.role === "player" && onboardingComplete;
  const canManageBank = canTrade;
  const effectiveAdminViewMode: AdminViewMode = isAdmin
    ? adminViewMode
    : "spectator";
  const isAdminSpectator = isAdmin && effectiveAdminViewMode === "spectator";
  const { data: bankSummary } = useBankSummary(canManageBank);

  const tradePlayer =
    trade && players ? players.find((p) => p.id === trade.playerId) : null;
  const tradeHolding =
    tradePlayer && portfolio
      ? portfolio.holdings.find(
          (holding) => holding.player_id === tradePlayer.id,
        )
      : null;
  const linkedPlayer =
    user?.linked_player_id && players
      ? players.find((player) => player.id === user.linked_player_id)
      : null;

  const sortedTickerPlayers = useMemo(() => {
    if (!players) {
      return [];
    }

    return [...players].sort((left, right) => {
      if (tickerSortMode === "value") {
        if (right.current_price !== left.current_price) {
          return right.current_price - left.current_price;
        }

        return left.display_name.localeCompare(right.display_name, undefined, {
          sensitivity: "base",
        });
      }

      return left.display_name.localeCompare(right.display_name, undefined, {
        sensitivity: "base",
      });
    });
  }, [players, tickerSortMode]);

  const resolvedSystemStatus = isAdmin ? adminSystemStatus : systemStatus;
  const marketStatusTone = resolvedSystemStatus?.market_status ?? "idle";
  const marketStatusLabel =
    marketStatusTone === "healthy"
      ? "Healthy"
      : marketStatusTone === "degraded"
        ? "Delayed"
        : "Idle";
  const marketStatusBeaconClass =
    marketStatusTone === "healthy"
      ? "border-hex-gold-dim bg-hex-gold shadow-[0_0_10px_rgba(200,170,110,0.45)]"
      : marketStatusTone === "degraded"
        ? "border-red-700 bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.35)]"
        : "border-hex-border bg-hex-bronze shadow-none";

  let marketStatusDetail = "Checking market service...";
  if (resolvedSystemStatus) {
    if (resolvedSystemStatus.last_market_update_at) {
      marketStatusDetail = `Last successful market refresh ${formatLocalDateTime(resolvedSystemStatus.last_market_update_at)}. Expected cadence about every ${resolvedSystemStatus.expected_update_interval_minutes} min.`;
    } else if (resolvedSystemStatus.tracked_player_count === 0) {
      marketStatusDetail =
        "No tracked players yet. Market polling will begin once the first player is onboarded.";
    } else {
      marketStatusDetail =
        "Awaiting the first successful market refresh from Riot.";
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-hex-bg">
      <Header
        balance={balance}
        netWorth={
          portfolio?.total_value ??
          bankSummary?.debt_adjusted_net_worth ??
          balance
        }
        displayName={user?.display_name}
        playerDisplayName={linkedPlayer?.display_name}
        playerGameName={linkedPlayer?.game_name}
        canEditProfile={Boolean(linkedPlayer) && !isAdmin}
        canToggleAdminView={isAdmin}
        adminViewMode={effectiveAdminViewMode}
        onOpenBalanceInsights={() => setIsBalanceInsightsOpen(true)}
        onEditProfile={() => setIsProfileEditorOpen(true)}
        showSimulation={showSimulation}
        onOpenSimulation={() => setShowSimulation(true)}
        onToggleAdminView={() =>
          setAdminViewMode((current) =>
            current === "admin" ? "spectator" : "admin",
          )
        }
      />

      <main className="mx-auto w-full max-w-[88rem] flex-1 px-6 py-8">
        {showSimulation ? (
          <SimulationView onClose={() => setShowSimulation(false)} />
        ) : (
          <>
            {/* Market ticker bar */}
            {players &&
              players.length > 0 &&
              (!isAdmin || isAdminSpectator) && (
                <div className="mb-8 overflow-hidden border-2 border-hex-border bg-hex-bg-alt">
                  <div className="flex items-center justify-between border-b-2 border-hex-border px-4 py-2">
                    <span className="font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                      Market Snapshot
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs uppercase tracking-wider text-hex-bronze">
                        Sort
                      </span>
                      <div className="flex border border-hex-border">
                        <button
                          type="button"
                          onClick={() => setTickerSortMode("value")}
                          className={`px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                            tickerSortMode === "value"
                              ? "bg-hex-gold text-hex-bg"
                              : "bg-transparent text-hex-bronze hover:bg-hex-panel hover:text-hex-white"
                          }`}
                        >
                          Value
                        </button>
                        <button
                          type="button"
                          onClick={() => setTickerSortMode("name")}
                          className={`border-l border-hex-border px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                            tickerSortMode === "name"
                              ? "bg-hex-gold text-hex-bg"
                              : "bg-transparent text-hex-bronze hover:bg-hex-panel hover:text-hex-white"
                          }`}
                        >
                          Name
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex divide-x-2 divide-hex-border overflow-x-auto">
                    {sortedTickerPlayers.map((p) => (
                      <div
                        key={p.id}
                        className="flex items-center gap-3 px-5 py-2.5"
                      >
                        <span className="font-mono text-xs font-bold text-hex-white">
                          {isStreamerMode
                            ? getStreamerSafeName(p.game_name, p.display_name)
                            : p.display_name}
                        </span>
                        <span
                          className={`font-mono text-xs font-bold ${
                            p.trend === "up"
                              ? "text-emerald-400"
                              : p.trend === "down"
                                ? "text-red-400"
                                : "text-hex-bronze"
                          }`}
                          title={
                            p.trend === "up"
                              ? "Rising"
                              : p.trend === "down"
                                ? "Falling"
                                : "Flat"
                          }
                        >
                          {p.trend === "up"
                            ? "▲"
                            : p.trend === "down"
                              ? "▼"
                              : "■"}
                        </span>
                        <span className="font-mono text-sm font-bold text-hex-gold">
                          {formatAmount(p.current_price)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            {/* Loading state */}
            {playersLoading && (
              <p className="py-12 text-center font-mono text-sm text-hex-bronze">
                Loading market data...
              </p>
            )}

            {/* Main grid: market + sidebar */}
            {isAdmin ? (
              isAdminSpectator ? (
                <>
                  <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    <div className="lg:col-span-2">
                      <MarketGrid
                        players={players ?? []}
                        onTrade={() => undefined}
                        onOpenDetails={(playerId) =>
                          setSelectedPlayerId(playerId)
                        }
                        canTrade={false}
                        ownPlayerId={null}
                        showTradeActions={false}
                      />
                    </div>

                    <div className="flex flex-col gap-6">
                      <section className="border-2 border-hex-gold-dim bg-hex-panel px-5 py-4">
                        <h2 className="font-serif text-xl font-bold text-hex-gold">
                          Spectator Mode
                        </h2>
                        <p className="mt-2 font-mono text-sm leading-6 text-hex-bronze">
                          Admin is viewing the player-facing market shell in
                          read-only mode. Trading, selling, gamba, and other
                          player actions stay disabled here.
                        </p>
                        <div className="mt-4 grid gap-3 font-mono text-xs text-hex-bronze">
                          <div className="border border-hex-border bg-hex-bg-alt px-3 py-2">
                            Market status:{" "}
                            {adminSystemStatus?.market_status ?? "idle"}
                          </div>
                          <div className="border border-hex-border bg-hex-bg-alt px-3 py-2">
                            Scheduler:{" "}
                            {adminSystemStatus?.scheduler_running
                              ? "Running"
                              : "Stopped"}
                          </div>
                        </div>
                      </section>

                      <Leaderboard entries={leaderboard ?? []} />
                    </div>
                  </div>

                  <div className="mt-6">
                    <OrderHistory
                      ownOrders={recentOrders ?? []}
                      allOrders={recentOrders ?? []}
                      defaultView="all"
                      allowViewToggle={false}
                    />
                  </div>
                </>
              ) : (
                <div className="space-y-8">
                  <AdminDashboard
                    overview={adminOverview}
                    users={adminUsers ?? []}
                    systemStatus={adminSystemStatus}
                    playerInsights={adminPlayerInsights ?? []}
                  />
                </div>
              )
            ) : (
              <>
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                  <div className="lg:col-span-2">
                    <MarketGrid
                      players={players ?? []}
                      onTrade={(playerId, side) => setTrade({ playerId, side })}
                      onOpenDetails={(playerId) =>
                        setSelectedPlayerId(playerId)
                      }
                      canTrade={canTrade}
                      ownPlayerId={user?.linked_player_id ?? null}
                    />
                  </div>

                  <div className="flex flex-col gap-6">
                    <Portfolio
                      portfolio={portfolio}
                      onOpenInsights={() => setIsPortfolioInsightsOpen(true)}
                    />
                    <Leaderboard entries={leaderboard ?? []} />
                    <GambaWidget balance={balance} canTrade={canTrade} />
                  </div>
                </div>

                <div className="mt-6">
                  <OrderHistory
                    ownOrders={orders ?? []}
                    allOrders={recentOrders ?? []}
                    defaultView="own"
                  />
                </div>
              </>
            )}
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-hex-border bg-hex-bg-alt py-2 font-mono text-[10px] text-hex-bronze">
        <div className="mx-auto flex max-w-[88rem] flex-col gap-2 px-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="uppercase tracking-[0.16em] text-hex-gold/85">
            NASHORDAQ v0.1.0
          </div>

          <div className="flex items-center gap-2 sm:max-w-2xl sm:justify-end sm:text-right">
            <div className="flex items-center gap-2 uppercase tracking-[0.18em] text-hex-white/90">
              <span
                aria-hidden="true"
                className={`inline-block h-2 w-2 border ${marketStatusBeaconClass}`}
              />
              <span>{marketStatusLabel}</span>
            </div>
            <div className="leading-4 text-hex-bronze/90">
              {marketStatusDetail}
            </div>
          </div>
        </div>
      </footer>

      {selectedPlayerId !== null && (
        <PlayerDetailsModal
          playerId={selectedPlayerId}
          canTrade={canTrade}
          isOwnStock={user?.linked_player_id === selectedPlayerId}
          onTrade={(side) => {
            setTrade({ playerId: selectedPlayerId, side });
          }}
          onClose={() => setSelectedPlayerId(null)}
        />
      )}

      {/* Trade modal */}
      {trade && tradePlayer && canTrade && (
        <TradeTerminal
          player={tradePlayer}
          side={trade.side}
          balance={balance}
          ownedQuantity={tradeHolding?.quantity ?? 0}
          isOwnStock={user?.linked_player_id === tradePlayer.id}
          onClose={() => setTrade(null)}
        />
      )}

      {isBalanceInsightsOpen && (
        <BalanceInsightsModal
          isOpen={isBalanceInsightsOpen}
          onClose={() => setIsBalanceInsightsOpen(false)}
          canOpenBank={canManageBank}
          debtOutstanding={bankSummary?.debt_outstanding ?? 0}
          rescueLoanAvailable={bankSummary?.rescue_loan_available ?? false}
          onOpenBank={() => {
            setIsBalanceInsightsOpen(false);
            setIsBankModalOpen(true);
          }}
        />
      )}

      {isPortfolioInsightsOpen && (
        <PortfolioInsightsModal
          portfolio={portfolio}
          canTrade={canTrade}
          onTrade={(playerId, side) => setTrade({ playerId, side })}
          onClose={() => setIsPortfolioInsightsOpen(false)}
        />
      )}

      {isBankModalOpen && (
        <BankModal
          canManageBank={canManageBank}
          onClose={() => setIsBankModalOpen(false)}
        />
      )}

      {isProfileEditorOpen && linkedPlayer && (
        <PlayerProfileModal
          key={`${linkedPlayer.id}-${linkedPlayer.game_name}-${linkedPlayer.tag_line}`}
          title="Update Your Summoner Profile"
          description="Change your Riot game name or tag line."
          submitLabel="Save Changes"
          initialValues={{
            game_name: linkedPlayer.game_name,
            tag_line: linkedPlayer.tag_line,
          }}
          isPending={updateUserProfile.isPending}
          errorMessage={
            updateUserProfile.isError
              ? updateUserProfile.error.message
              : undefined
          }
          onSubmit={(body) => {
            updateUserProfile.mutate(body, {
              onSuccess: () => setIsProfileEditorOpen(false),
            });
          }}
          onClose={() => setIsProfileEditorOpen(false)}
        />
      )}

      {/* First-login onboarding modal */}
      {isAdmin && (
        <div className="pointer-events-none fixed bottom-4 right-4 border-2 border-hex-border bg-hex-panel px-3 py-2 font-mono text-xs uppercase tracking-wider text-hex-bronze">
          {effectiveAdminViewMode === "admin"
            ? "Admin View"
            : "Admin Spectator"}
        </div>
      )}

      {user && !user.onboarding_complete && !isAdmin && <OnboardingModal />}

      <FlyingPoro enabled={canTrade} />
    </div>
  );
}
