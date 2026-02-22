import { useState } from "react";
import type { PlayerSummary, OrderSide } from "../types";
import { usePlaceOrder } from "../api";
import { formatAmount } from "../utils/format";

interface Props {
  player: PlayerSummary;
  side: OrderSide;
  balance: number;
  onClose: () => void;
}

export default function TradeTerminal({
  player,
  side,
  balance,
  onClose,
}: Props) {
  const [quantity, setQuantity] = useState(1);
  const placeOrder = usePlaceOrder();

  const estimatedTotal = player.current_price * quantity;
  const canAfford = side === "BUY" ? balance >= estimatedTotal : true;
  const isBuy = side === "BUY";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    placeOrder.mutate(
      { player_id: player.id, side, quantity },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/80"
      onClick={onClose}
    >
      <section
        className={`w-full max-w-md border-4 bg-hex-panel shadow-brutal-lg ${
          isBuy ? "border-hex-magic" : "border-hex-zaun"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className={`flex items-center justify-between border-b-4 px-5 py-3 ${
            isBuy ? "border-hex-magic" : "border-hex-zaun"
          }`}
        >
          <h2 className="font-serif text-xl font-bold text-hex-gold">
            {side} &mdash; {player.display_name}
          </h2>
          <button
            onClick={onClose}
            className="font-mono text-lg font-bold text-hex-bronze transition-colors hover:text-hex-white"
          >
            X
          </button>
        </div>

        {/* Player info */}
        <div className="flex items-baseline justify-between border-b-2 border-hex-border px-5 py-3">
          <span className="font-mono text-xs text-hex-bronze">
            {player.game_name}#{player.tag_line}
          </span>
          <span className="font-mono text-lg font-bold text-hex-gold">
            {formatAmount(player.current_price)}
            <span className="ml-1 text-xs text-hex-bronze">G / share</span>
          </span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-4">
          {/* Quantity */}
          <div>
            <label className="mb-1 block font-mono text-xs uppercase tracking-wider text-hex-bronze">
              Quantity
            </label>
            <input
              type="number"
              min={1}
              value={quantity}
              onChange={(e) => setQuantity(Math.max(1, Number(e.target.value)))}
              autoFocus
              className="w-full border-2 border-hex-border bg-hex-bg px-3 py-2 font-mono text-sm text-hex-white outline-none focus:border-hex-gold"
            />
          </div>

          {/* Estimate */}
          <div className="flex items-baseline justify-between border-t-2 border-hex-border pt-3">
            <span className="font-mono text-xs uppercase tracking-wider text-hex-bronze">
              Est. Total
            </span>
            <span
              className={`font-mono text-lg font-bold ${canAfford ? "text-hex-gold" : "text-hex-zaun"}`}
            >
              {formatAmount(estimatedTotal)}
              <span className="ml-1 text-xs text-hex-bronze">G</span>
            </span>
          </div>

          {/* Error */}
          {placeOrder.isError && (
            <p className="font-mono text-xs text-hex-zaun">
              {placeOrder.error.message}
            </p>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={!canAfford || placeOrder.isPending}
            className={`w-full border-2 py-2.5 font-mono text-sm font-bold uppercase tracking-wider transition-colors ${
              placeOrder.isPending
                ? "border-hex-magic bg-hex-magic/20 text-hex-magic"
                : canAfford
                  ? isBuy
                    ? "border-hex-magic bg-transparent text-hex-magic hover:bg-hex-magic hover:text-hex-bg"
                    : "border-hex-zaun bg-transparent text-hex-zaun hover:bg-hex-zaun hover:text-hex-bg"
                  : "cursor-not-allowed border-hex-border text-hex-border"
            }`}
          >
            {placeOrder.isPending
              ? "Submitting..."
              : `${side} ${quantity} share${quantity > 1 ? "s" : ""}`}
          </button>

          {!canAfford && side === "BUY" && (
            <p className="font-mono text-xs text-hex-zaun">
              Insufficient balance
            </p>
          )}
        </form>
      </section>
    </div>
  );
}
