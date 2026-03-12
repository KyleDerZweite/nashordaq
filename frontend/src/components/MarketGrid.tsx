import { useMemo, useState } from "react";
import type { PlayerSummary, OrderSide } from "../types";
import PlayerCard from "./PlayerCard";

type MarketSortField = "value" | "name";
type MarketSortDirection = "asc" | "desc";

interface Props {
  players: PlayerSummary[];
  onTrade: (playerId: number, side: OrderSide) => void;
  onOpenDetails: (playerId: number) => void;
  canTrade?: boolean;
  ownPlayerId?: number | null;
  showTradeActions?: boolean;
}

export default function MarketGrid({
  players,
  onTrade,
  onOpenDetails,
  canTrade = true,
  ownPlayerId = null,
  showTradeActions = true,
}: Props) {
  const [sortField, setSortField] = useState<MarketSortField>("value");
  const [sortDirection, setSortDirection] =
    useState<MarketSortDirection>("desc");

  const sortedPlayers = useMemo(() => {
    return [...players].sort((left, right) => {
      const directionMultiplier = sortDirection === "asc" ? 1 : -1;

      if (sortField === "value") {
        if (left.current_price !== right.current_price) {
          return (
            (left.current_price - right.current_price) * directionMultiplier
          );
        }
      }

      return (
        left.display_name.localeCompare(right.display_name, undefined, {
          sensitivity: "base",
        }) * directionMultiplier
      );
    });
  }, [players, sortDirection, sortField]);

  return (
    <section>
      <div className="mb-4 flex flex-col gap-3 border-b-2 border-hex-border pb-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col items-start gap-1 sm:flex-row sm:items-baseline sm:gap-3">
          <h2 className="font-serif text-2xl font-bold text-hex-gold">
            Market
          </h2>
          <span className="font-mono text-xs text-hex-bronze">
            {players.length} tracked players
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3 sm:justify-end">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs uppercase tracking-wider text-hex-bronze">
              Sort
            </span>
            <div className="flex border border-hex-border">
              <button
                type="button"
                onClick={() => setSortField("value")}
                className={`px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                  sortField === "value"
                    ? "bg-hex-gold text-hex-bg"
                    : "bg-transparent text-hex-bronze hover:bg-hex-panel hover:text-hex-white"
                }`}
              >
                Value
              </button>
              <button
                type="button"
                onClick={() => setSortField("name")}
                className={`border-l border-hex-border px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                  sortField === "name"
                    ? "bg-hex-gold text-hex-bg"
                    : "bg-transparent text-hex-bronze hover:bg-hex-panel hover:text-hex-white"
                }`}
              >
                Name
              </button>
            </div>
            <div className="flex border border-hex-border">
              <button
                type="button"
                onClick={() => setSortDirection("asc")}
                className={`px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                  sortDirection === "asc"
                    ? "bg-hex-gold text-hex-bg"
                    : "bg-transparent text-hex-bronze hover:bg-hex-panel hover:text-hex-white"
                }`}
              >
                Asc
              </button>
              <button
                type="button"
                onClick={() => setSortDirection("desc")}
                className={`border-l border-hex-border px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                  sortDirection === "desc"
                    ? "bg-hex-gold text-hex-bg"
                    : "bg-transparent text-hex-bronze hover:bg-hex-panel hover:text-hex-white"
                }`}
              >
                Desc
              </button>
            </div>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sortedPlayers.map((p) => (
          <PlayerCard
            key={p.id}
            player={p}
            onTrade={onTrade}
            onOpenDetails={onOpenDetails}
            canTrade={canTrade}
            isOwnStock={ownPlayerId === p.id}
            showTradeActions={showTradeActions}
          />
        ))}
      </div>
    </section>
  );
}
