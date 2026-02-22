import { useState } from "react";
import Header from "./components/Header";
import MarketGrid from "./components/MarketGrid";
import Portfolio from "./components/Portfolio";
import Leaderboard from "./components/Leaderboard";
import OrderHistory from "./components/OrderHistory";
import TradeTerminal from "./components/TradeTerminal";
import type { OrderSide } from "./types";
import {
  MOCK_PLAYERS,
  MOCK_DELTAS,
  MOCK_LEADERBOARD,
  MOCK_HOLDINGS,
  MOCK_ORDERS,
  MOCK_BALANCE,
} from "./mock/data";

interface TradeTarget {
  playerId: number;
  side: OrderSide;
}

export default function App() {
  const [trade, setTrade] = useState<TradeTarget | null>(null);

  const tradePlayer = trade
    ? MOCK_PLAYERS.find((p) => p.id === trade.playerId)
    : null;

  return (
    <div className="min-h-screen bg-hex-bg">
      <Header balance={MOCK_BALANCE} />

      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Market ticker bar */}
        <div className="mb-8 overflow-hidden border-2 border-hex-border bg-hex-bg-alt">
          <div className="flex divide-x-2 divide-hex-border">
            {MOCK_PLAYERS.map((p) => {
              const d = MOCK_DELTAS[p.id] ?? 0;
              const pos = d >= 0;
              return (
                <div key={p.id} className="flex items-center gap-3 px-5 py-2.5">
                  <span className="font-mono text-xs font-bold text-hex-white">
                    {p.display_name}
                  </span>
                  <span className="font-mono text-sm font-bold text-hex-gold">
                    {p.current_price.toFixed(2)}
                  </span>
                  <span
                    className={`font-mono text-xs font-bold ${pos ? "text-hex-magic" : "text-hex-zaun"}`}
                  >
                    {pos ? "+" : ""}
                    {d.toFixed(2)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Main grid: market + sidebar */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Market takes 2 cols */}
          <div className="lg:col-span-2">
            <MarketGrid
              players={MOCK_PLAYERS}
              deltas={MOCK_DELTAS}
              onTrade={(playerId, side) => setTrade({ playerId, side })}
            />
          </div>

          {/* Sidebar */}
          <div className="flex flex-col gap-6">
            <Portfolio holdings={MOCK_HOLDINGS} balance={MOCK_BALANCE} />
            <Leaderboard entries={MOCK_LEADERBOARD} />
          </div>
        </div>

        {/* Order history */}
        <div className="mt-6">
          <OrderHistory orders={MOCK_ORDERS} />
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
          balance={MOCK_BALANCE}
          onClose={() => setTrade(null)}
        />
      )}
    </div>
  );
}
