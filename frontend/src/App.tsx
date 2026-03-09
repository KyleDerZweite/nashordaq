import { useMemo, useState } from "react";
import Header from "./components/Header";
import MarketGrid from "./components/MarketGrid";
import Portfolio from "./components/Portfolio";
import Leaderboard from "./components/Leaderboard";
import OrderHistory from "./components/OrderHistory";
import PlayerProfileModal from "./components/PlayerProfileModal";
import PlayerDetailsModal from "./components/PlayerDetailsModal";
import TradeTerminal from "./components/TradeTerminal";
import OnboardingModal from "./components/OnboardingModal";
import type { OrderSide } from "./types";
import { formatAmount } from "./utils/format";

import {
  useUser,
  usePlayers,
  usePortfolio,
  useOrders,
  useRecentOrders,
  useLeaderboard,
  useUpdateUserProfile,
} from "./api";

interface TradeTarget {
  playerId: number;
  side: OrderSide;
}

type TickerSortMode = "value" | "name";

export default function App() {
  const [trade, setTrade] = useState<TradeTarget | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [tickerSortMode, setTickerSortMode] = useState<TickerSortMode>("value");
  const [isProfileEditorOpen, setIsProfileEditorOpen] = useState(false);

  const { data: user } = useUser();
  const onboardingComplete = user?.onboarding_complete ?? false;
  const { data: players, isLoading: playersLoading } = usePlayers();
  const { data: portfolio } = usePortfolio(onboardingComplete);
  const { data: orders } = useOrders(onboardingComplete);
  const { data: recentOrders } = useRecentOrders(onboardingComplete);
  const { data: leaderboard } = useLeaderboard();
  const updateUserProfile = useUpdateUserProfile();

  const balance = user?.balance ?? 0;
  const isSpectator = user?.role === "spectator";
  const canTrade =
    Boolean(user) && user?.role === "player" && onboardingComplete;

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

  return (
    <div className="flex min-h-screen flex-col bg-hex-bg">
      <Header
        balance={balance}
        username={user?.username}
        playerDisplayName={linkedPlayer?.display_name}
        canEditProfile={Boolean(linkedPlayer) && !isSpectator}
        onEditProfile={() => setIsProfileEditorOpen(true)}
      />

      <main className="mx-auto w-full max-w-[88rem] flex-1 px-6 py-8">
        {/* Market ticker bar */}
        {players && players.length > 0 && (
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
                <div key={p.id} className="flex items-center gap-3 px-5 py-2.5">
                  <span className="font-mono text-xs font-bold text-hex-white">
                    {p.display_name}
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
                    {p.trend === "up" ? "▲" : p.trend === "down" ? "▼" : "■"}
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
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Market takes 2 cols */}
          <div className="lg:col-span-2">
            <MarketGrid
              players={players ?? []}
              onTrade={(playerId, side) => setTrade({ playerId, side })}
              onOpenDetails={(playerId) => setSelectedPlayerId(playerId)}
              canTrade={canTrade}
              ownPlayerId={user?.linked_player_id ?? null}
            />
          </div>

          {/* Sidebar */}
          <div className="flex flex-col gap-6">
            <Portfolio holdings={portfolio?.holdings ?? []} balance={balance} />
            <Leaderboard entries={leaderboard ?? []} />
          </div>
        </div>

        {/* Order history */}
        <div className="mt-6">
          <OrderHistory
            ownOrders={orders ?? []}
            allOrders={recentOrders ?? []}
          />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t-2 border-hex-border py-4 text-center font-mono text-xs text-hex-bronze">
        NASHORDAQ v0.1.0 &mdash; Fantasy League Market
      </footer>

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

      {selectedPlayerId !== null && (
        <PlayerDetailsModal
          playerId={selectedPlayerId}
          canTrade={canTrade}
          isOwnStock={user?.linked_player_id === selectedPlayerId}
          onTrade={(side) => {
            setSelectedPlayerId(null);
            setTrade({ playerId: selectedPlayerId, side });
          }}
          onClose={() => setSelectedPlayerId(null)}
        />
      )}

      {isProfileEditorOpen && linkedPlayer && (
        <PlayerProfileModal
          key={`${linkedPlayer.id}-${linkedPlayer.game_name}-${linkedPlayer.tag_line}-${linkedPlayer.display_name}`}
          title="Update Your Summoner Profile"
          description="Change your Riot game name, tag line, or display name."
          submitLabel="Save Changes"
          initialValues={{
            game_name: linkedPlayer.game_name,
            tag_line: linkedPlayer.tag_line,
            display_name: linkedPlayer.display_name,
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
      {isSpectator && (
        <div className="pointer-events-none fixed bottom-4 right-4 border-2 border-hex-border bg-hex-panel px-3 py-2 font-mono text-xs uppercase tracking-wider text-hex-bronze">
          Spectator Mode
        </div>
      )}

      {user && !user.onboarding_complete && !isSpectator && <OnboardingModal />}
    </div>
  );
}
