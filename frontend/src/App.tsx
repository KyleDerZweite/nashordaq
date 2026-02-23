import { useState } from "react";
import Header from "./components/Header";
import MarketGrid from "./components/MarketGrid";
import Portfolio from "./components/Portfolio";
import Leaderboard from "./components/Leaderboard";
import OrderHistory from "./components/OrderHistory";
import TradeTerminal from "./components/TradeTerminal";
import OnboardingModal from "./components/OnboardingModal";
import type { OrderSide } from "./types";
import { formatAmount } from "./utils/format";

import {
  useUser,
  usePlayers,
  usePortfolio,
  useOrders,
  useLeaderboard,
} from "./api";

interface TradeTarget {
  playerId: number;
  side: OrderSide;
}

export default function App() {
  const [trade, setTrade] = useState<TradeTarget | null>(null);

  const { data: user } = useUser();
  const onboardingComplete = user?.onboarding_complete ?? false;
  const { data: players, isLoading: playersLoading } = usePlayers();
  const { data: portfolio } = usePortfolio(onboardingComplete);
  const { data: orders } = useOrders(onboardingComplete);
  const { data: leaderboard } = useLeaderboard();

  const balance = user?.balance ?? 0;

  const tradePlayer =
    trade && players ? players.find((p) => p.id === trade.playerId) : null;

  return (
    <div className="flex min-h-screen flex-col bg-hex-bg">
      <Header balance={balance} username={user?.username} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
        {/* Market ticker bar */}
        {players && players.length > 0 && (
          <div className="mb-8 overflow-hidden border-2 border-hex-border bg-hex-bg-alt">
            <div className="flex divide-x-2 divide-hex-border">
              {players.map((p) => (
                <div key={p.id} className="flex items-center gap-3 px-5 py-2.5">
                  <span className="font-mono text-xs font-bold text-hex-white">
                    {p.display_name}
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
          <OrderHistory orders={orders ?? []} />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t-2 border-hex-border py-4 text-center font-mono text-xs text-hex-bronze">
        NASHORDAQ v0.1.0 &mdash; Fantasy League Market
      </footer>

      {/* Trade modal */}
      {trade && tradePlayer && (
        <TradeTerminal
          player={tradePlayer}
          side={trade.side}
          balance={balance}
          onClose={() => setTrade(null)}
        />
      )}

      {/* First-login onboarding modal */}
      {user && !user.onboarding_complete && <OnboardingModal />}
    </div>
  );
}
