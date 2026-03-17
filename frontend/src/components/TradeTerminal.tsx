import { useState } from "react";
import { useStreamerMode } from "../contexts/useStreamerMode";
import type { PlayerSummary, OrderSide } from "../types";
import { usePlaceOrder } from "../api";
import { getStreamerSafeName } from "../utils/streamerMode";
import { formatAmount } from "../utils/format";

interface Props {
  player: PlayerSummary;
  side: OrderSide;
  balance: number;
  ownedQuantity: number;
  isOwnStock?: boolean;
  onClose: () => void;
}

export default function TradeTerminal({
  player,
  side,
  balance,
  ownedQuantity,
  isOwnStock = false,
  onClose,
}: Props) {
  const { isStreamerMode } = useStreamerMode();
  const [quantity, setQuantity] = useState(1);
  const placeOrder = usePlaceOrder();

  const isBuy = side === "BUY";
  const hasInitialUpdate = player.last_updated !== null;

  const LIQUIDITY_DEPTH = 1000;
  const impactPct = quantity / LIQUIDITY_DEPTH;
  const avgFillPrice = isBuy
    ? player.current_price * (1 + impactPct / 2)
    : player.current_price * (1 - impactPct / 2);
  const priceAfterTrade = isBuy
    ? player.current_price * (1 + impactPct)
    : Math.max(player.current_price * (1 - impactPct), 1);

  // Solve P*Q*(1 + Q/(2D)) = B for Q using the quadratic formula.
  const maxBuyQuantity =
    player.current_price > 0
      ? Math.floor(
          LIQUIDITY_DEPTH *
            (-1 +
              Math.sqrt(
                1 + (2 * balance) / (player.current_price * LIQUIDITY_DEPTH),
              )),
        )
      : 0;
  const maxSellQuantity = ownedQuantity;
  const effectiveMaxBuyQuantity = isOwnStock ? 0 : maxBuyQuantity;
  const maxQuantity = isBuy ? effectiveMaxBuyQuantity : maxSellQuantity;
  const estimatedTotal = avgFillPrice * quantity;
  const canAfford = balance >= estimatedTotal;
  const showImpact = impactPct >= 0.005;
  const exceedsHoldings = !isBuy && quantity > maxSellQuantity;
  const canSubmit =
    quantity >= 1 &&
    (!isBuy || hasInitialUpdate) &&
    (isBuy
      ? canAfford && !isOwnStock
      : !exceedsHoldings && maxSellQuantity > 0);

  function handleQuantityChange(value: string) {
    const nextQuantity = Number(value);

    if (!Number.isFinite(nextQuantity)) {
      setQuantity(1);
      return;
    }

    setQuantity(Math.max(1, Math.floor(nextQuantity)));
  }

  function handleSetMax() {
    if (maxQuantity < 1) {
      return;
    }

    setQuantity(maxQuantity);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!canSubmit) {
      return;
    }

    placeOrder.mutate(
      { player_id: player.id, side, quantity },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-hex-bg/80"
      onClick={onClose}
    >
      <section
        className="w-full max-w-md border-4 border-hex-gold bg-hex-panel shadow-brutal-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b-4 border-hex-gold px-5 py-3">
          <h2 className="font-serif text-xl font-bold text-hex-gold">
            {side} &mdash;{" "}
            {isStreamerMode
              ? getStreamerSafeName(player.game_name, player.display_name)
              : player.display_name}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="border-2 border-hex-border px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-[0.18em] text-hex-bronze transition-colors hover:border-hex-white hover:text-hex-white"
          >
            Close
          </button>
        </div>

        {/* Player info */}
        <div className="flex items-baseline justify-between border-b-2 border-hex-border px-5 py-3">
          <span className="font-mono text-xs text-hex-bronze">
            {isStreamerMode
              ? player.game_name
              : `${player.game_name}#${player.tag_line}`}
          </span>
          <span className="font-mono text-lg font-bold text-hex-gold">
            {formatAmount(player.current_price)}
            <span className="ml-1 text-xs text-hex-bronze">P / share</span>
          </span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-4">
          {/* Quantity */}
          <div>
            <label className="mb-1 block font-mono text-xs uppercase tracking-wider text-hex-bronze">
              Quantity
            </label>
            <div className="flex gap-2">
              <input
                type="number"
                min={1}
                value={quantity}
                onChange={(e) => handleQuantityChange(e.target.value)}
                autoFocus
                className="w-full border-2 border-hex-border bg-hex-bg px-3 py-2 font-mono text-sm text-hex-white outline-none focus:border-hex-gold"
              />
              <button
                type="button"
                onClick={handleSetMax}
                disabled={maxQuantity < 1}
                className={`shrink-0 border-2 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                  maxQuantity >= 1
                    ? isBuy
                      ? "border-hex-gold text-hex-gold hover:bg-hex-gold hover:text-hex-bg"
                      : "border-hex-bronze text-hex-bronze hover:bg-hex-bronze hover:text-hex-bg"
                    : "cursor-not-allowed border-hex-border text-hex-border"
                }`}
              >
                Max {isBuy ? "Buy" : "Sell"}
              </button>
            </div>
            <p className="mt-2 font-mono text-xs text-hex-bronze">
              {isBuy
                ? `Affordable now: ${effectiveMaxBuyQuantity} share${effectiveMaxBuyQuantity === 1 ? "" : "s"}`
                : `Owned now: ${maxSellQuantity} share${maxSellQuantity === 1 ? "" : "s"}`}
            </p>
          </div>

          {/* Estimate */}
          <div className="space-y-2 border-t-2 border-hex-border pt-3">
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-xs uppercase tracking-wider text-hex-bronze">
                Avg Fill Price
              </span>
              <span className="font-mono text-sm text-hex-white">
                {formatAmount(avgFillPrice)}
                <span className="ml-1 text-xs text-hex-bronze">P</span>
              </span>
            </div>
            {showImpact && (
              <>
                <div className="flex items-baseline justify-between">
                  <span className="font-mono text-xs uppercase tracking-wider text-hex-bronze">
                    Market Impact
                  </span>
                  <span
                    className={`font-mono text-xs font-bold ${isBuy ? "text-hex-magic" : "text-hex-zaun"}`}
                  >
                    {isBuy ? "+" : "-"}
                    {(impactPct * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="font-mono text-xs uppercase tracking-wider text-hex-bronze">
                    Price After
                  </span>
                  <span className="font-mono text-xs text-hex-bronze">
                    {formatAmount(priceAfterTrade)}
                    <span className="ml-1">P</span>
                  </span>
                </div>
              </>
            )}
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-xs uppercase tracking-wider text-hex-bronze">
                Est. Total
              </span>
              <span
                className={`font-mono text-lg font-bold ${canAfford ? "text-hex-gold" : "text-hex-zaun"}`}
              >
                {formatAmount(estimatedTotal)}
                <span className="ml-1 text-xs text-hex-bronze">P</span>
              </span>
            </div>
          </div>

          {/* Error */}
          {placeOrder.isError && (
            <p className="font-mono text-xs text-hex-zaun">
              {placeOrder.error.message}
            </p>
          )}

          {isBuy && !hasInitialUpdate && (
            <p className="font-mono text-xs text-hex-bronze">
              Buying is locked until this stock receives its first market
              update.
            </p>
          )}

          {isBuy && isOwnStock && (
            <p className="font-mono text-xs text-hex-bronze">
              You cannot buy your own stock.
            </p>
          )}

          {!isBuy && maxSellQuantity < 1 && (
            <p className="font-mono text-xs text-hex-bronze">
              You do not currently own any shares of this stock.
            </p>
          )}

          {!isBuy && exceedsHoldings && maxSellQuantity > 0 && (
            <p className="font-mono text-xs text-hex-zaun">
              You can sell at most {maxSellQuantity} share
              {maxSellQuantity === 1 ? "" : "s"}.
            </p>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={!canSubmit || placeOrder.isPending}
            className={`w-full border-2 py-2.5 font-mono text-sm font-bold uppercase tracking-wider transition-colors ${
              placeOrder.isPending
                ? "border-hex-magic bg-hex-magic/20 text-hex-magic"
                : canSubmit
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

          {!canAfford && isBuy && !isOwnStock && (
            <p className="font-mono text-xs text-hex-zaun">
              Insufficient balance
            </p>
          )}
        </form>
      </section>
    </div>
  );
}
