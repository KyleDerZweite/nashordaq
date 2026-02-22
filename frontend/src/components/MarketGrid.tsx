import type { PlayerSummary, OrderSide } from "../types";
import PlayerCard from "./PlayerCard";

interface Props {
  players: PlayerSummary[];
  onTrade: (playerId: number, side: OrderSide) => void;
}

export default function MarketGrid({ players, onTrade }: Props) {
  return (
    <section>
      <div className="mb-4 flex items-baseline justify-between border-b-2 border-hex-border pb-2">
        <h2 className="font-serif text-2xl font-bold text-hex-gold">Market</h2>
        <span className="font-mono text-xs text-hex-bronze">
          {players.length} tracked players
        </span>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {players.map((p) => (
          <PlayerCard key={p.id} player={p} onTrade={onTrade} />
        ))}
      </div>
    </section>
  );
}
