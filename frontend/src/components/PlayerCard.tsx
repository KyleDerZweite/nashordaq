import type { PlayerSummary, OrderSide } from "../types";
import { formatAmount } from "../utils/format";

interface Props {
  player: PlayerSummary;
  onTrade: (playerId: number, side: OrderSide) => void;
}

export default function PlayerCard({ player, onTrade }: Props) {
  return (
    <article className="group border-2 border-hex-gold-dim/40 bg-hex-panel p-5 transition-shadow hover:shadow-brutal">
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
            {formatAmount(player.current_price)}
          </span>
        </div>
        {player.last_updated && (
          <div className="text-right">
            <span className="block text-xs uppercase tracking-wider text-hex-bronze">
              Updated
            </span>
            <span className="font-mono text-xs text-hex-bronze">
              {new Date(player.last_updated).toLocaleTimeString()}
            </span>
          </div>
        )}
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
