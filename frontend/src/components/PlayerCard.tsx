import type { PlayerSummary, OrderSide } from "../types";
import { formatAmount } from "../utils/format";

interface Props {
  player: PlayerSummary;
  onTrade: (playerId: number, side: OrderSide) => void;
  canTrade?: boolean;
}

export default function PlayerCard({
  player,
  onTrade,
  canTrade = true,
}: Props) {
  const canBuy = canTrade && player.last_updated !== null;
  const trendIndicator =
    player.trend === "up"
      ? { arrow: "▲", color: "text-emerald-400", label: "Rising" }
      : player.trend === "down"
        ? { arrow: "▼", color: "text-red-400", label: "Falling" }
        : { arrow: "■", color: "text-hex-bronze", label: "Flat" };

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
          <div className="flex items-center gap-2">
            <span className="font-mono text-2xl font-bold text-hex-gold">
              {formatAmount(player.current_price)}
            </span>
            <span
              className={`font-mono text-sm font-bold ${trendIndicator.color}`}
              title={trendIndicator.label}
            >
              {trendIndicator.arrow}
            </span>
          </div>
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
          disabled={!canBuy}
          onClick={() => onTrade(player.id, "BUY")}
          className={`flex-1 border-2 py-1.5 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
            canBuy
              ? "border-hex-magic bg-transparent text-hex-magic hover:bg-hex-magic hover:text-hex-bg"
              : "cursor-not-allowed border-hex-border text-hex-border"
          }`}
        >
          {!canTrade ? "Spectator" : canBuy ? "Buy" : "Awaiting Update"}
        </button>
        <button
          disabled={!canTrade}
          onClick={() => onTrade(player.id, "SELL")}
          className={`flex-1 border-2 py-1.5 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
            canTrade
              ? "border-hex-zaun bg-transparent text-hex-zaun hover:bg-hex-zaun hover:text-hex-bg"
              : "cursor-not-allowed border-hex-border text-hex-border"
          }`}
        >
          Sell
        </button>
      </div>

      {player.last_updated === null && (
        <p className="mt-3 font-mono text-xs text-hex-bronze">
          Buying unlocks after the first market update.
        </p>
      )}
    </article>
  );
}
