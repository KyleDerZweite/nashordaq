import type { PlayerSummary, OrderSide } from "../types";

interface Props {
  player: PlayerSummary;
  delta: number;
  onTrade: (playerId: number, side: OrderSide) => void;
}

export default function PlayerCard({ player, delta, onTrade }: Props) {
  const isPositive = delta >= 0;

  return (
    <article
      className={`group border-2 bg-hex-panel p-5 transition-shadow hover:shadow-brutal ${
        isPositive ? "border-hex-magic/40" : "border-hex-zaun/40"
      }`}
    >
      {/* Top row: name + tag */}
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-serif text-xl font-bold text-hex-white">
          {player.display_name}
        </h3>
        <span className="font-mono text-xs text-hex-bronze">
          {player.game_name}#{player.tag_line}
        </span>
      </div>

      {/* Divider */}
      <div className="mb-3 h-px w-full bg-hex-border" />

      {/* Price row */}
      <div className="flex items-end justify-between">
        <div>
          <span className="block text-xs uppercase tracking-wider text-hex-bronze">
            Price
          </span>
          <span className="font-mono text-2xl font-bold text-hex-gold">
            {player.current_price.toFixed(2)}
          </span>
        </div>
        <div className="text-right">
          <span className="block text-xs uppercase tracking-wider text-hex-bronze">
            24h
          </span>
          <span
            className={`font-mono text-lg font-bold ${
              isPositive ? "text-hex-magic" : "text-hex-zaun"
            }`}
          >
            {isPositive ? "+" : ""}
            {delta.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Mini bar indicator */}
      <div className="mt-4 h-1 w-full bg-hex-bg">
        <div
          className={`h-full transition-all ${
            isPositive ? "bg-hex-magic" : "bg-hex-zaun"
          }`}
          style={{
            width: `${Math.min(Math.abs(delta) * 15, 100)}%`,
          }}
        />
      </div>

      {/* Action row */}
      <div className="mt-4 flex gap-2">
        <button
          onClick={() => onTrade(player.id, "BUY")}
          className="flex-1 border-2 border-hex-magic bg-transparent py-1.5 font-mono text-xs font-bold uppercase tracking-wider text-hex-magic transition-colors hover:bg-hex-magic hover:text-hex-bg"
        >
          Buy
        </button>
        <button
          onClick={() => onTrade(player.id, "SELL")}
          className="flex-1 border-2 border-hex-zaun bg-transparent py-1.5 font-mono text-xs font-bold uppercase tracking-wider text-hex-zaun transition-colors hover:bg-hex-zaun hover:text-hex-bg"
        >
          Sell
        </button>
      </div>
    </article>
  );
}
