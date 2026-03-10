import { useMemo, useState } from "react";
import { useCreateGambaPosition, useGambaPositions } from "../api";
import {
  formatAmount,
  formatLocalDateTime,
  formatQuantity,
} from "../utils/format";

interface Props {
  balance: number;
  canTrade: boolean;
}

export default function GambaWidget({ balance, canTrade }: Props) {
  const [cashAmount, setCashAmount] = useState("");
  const { data: positions } = useGambaPositions(canTrade);
  const createGambaPosition = useCreateGambaPosition();

  const activePosition = useMemo(
    () => positions?.find((position) => position.status === "ACTIVE") ?? null,
    [positions],
  );
  const displayMultiplier = activePosition?.settlement_multiplier ?? 2;

  const parsedCashAmount = Number(cashAmount);
  const hasValidAmount =
    Number.isFinite(parsedCashAmount) && parsedCashAmount > 0;
  const canAfford = hasValidAmount && parsedCashAmount <= balance;
  const canSubmit =
    canTrade &&
    !activePosition &&
    hasValidAmount &&
    canAfford &&
    !createGambaPosition.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!canSubmit) {
      return;
    }

    createGambaPosition.mutate(
      { cash_amount: parsedCashAmount },
      {
        onSuccess: () => setCashAmount(""),
      },
    );
  }

  function handleMax() {
    setCashAmount(balance > 0 ? balance.toFixed(2) : "");
  }

  return (
    <section className="border-2 border-hex-gold-dim bg-hex-panel">
      <div className="border-b-2 border-hex-gold-dim px-5 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-serif text-xl font-bold text-hex-gold">
              Gamba Invest
            </h2>
            <p className="mt-1 font-mono text-[11px] leading-5 text-hex-bronze">
              Commit poro, get one random player, lock the position, auto-sell
              later.
            </p>
          </div>
          <div className="border border-hex-border px-2 py-1 text-right">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
              Multiplier
            </div>
            <div className="font-mono text-sm font-bold text-hex-gold">
              x
              {Number.isInteger(displayMultiplier)
                ? displayMultiplier.toFixed(0)
                : displayMultiplier}
            </div>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3 px-4 py-4">
        <div>
          <label className="mb-1 block font-mono text-xs uppercase tracking-wider text-hex-bronze">
            Poro Amount
          </label>
          <div className="flex gap-2">
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={cashAmount}
              onChange={(e) => setCashAmount(e.target.value)}
              placeholder="250.00"
              className="w-full border-2 border-hex-border bg-hex-bg px-3 py-2 font-mono text-sm text-hex-white outline-none focus:border-hex-gold"
            />
            <button
              type="button"
              onClick={handleMax}
              disabled={!canTrade || balance <= 0 || Boolean(activePosition)}
              className={`shrink-0 border-2 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                canTrade && balance > 0 && !activePosition
                  ? "border-hex-gold text-hex-gold hover:bg-hex-gold hover:text-hex-bg"
                  : "cursor-not-allowed border-hex-border text-hex-border"
              }`}
            >
              Max
            </button>
          </div>
          <p className="mt-2 font-mono text-xs text-hex-bronze">
            Available: {formatAmount(balance)} P. The full amount becomes
            fractional exposure.
          </p>
        </div>

        {activePosition && (
          <div className="border-2 border-hex-magic/50 bg-hex-bg-alt px-3 py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                  Active Gamba
                </p>
                <p className="font-serif text-lg font-bold text-hex-white">
                  {activePosition.player_name}
                </p>
              </div>
              <div className="text-right font-mono text-xs text-hex-bronze">
                <div>Auto-sell</div>
                <div className="text-hex-gold">
                  {formatLocalDateTime(activePosition.scheduled_settlement_at)}
                </div>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 border-t border-hex-border pt-3 font-mono text-xs">
              <div>
                <div className="uppercase tracking-wider text-hex-bronze">
                  Cash
                </div>
                <div className="font-bold text-hex-gold">
                  {formatAmount(activePosition.cash_amount)} P
                </div>
              </div>
              <div>
                <div className="uppercase tracking-wider text-hex-bronze">
                  Qty
                </div>
                <div className="font-bold text-hex-white">
                  {formatQuantity(activePosition.quantity)}
                </div>
              </div>
              <div>
                <div className="uppercase tracking-wider text-hex-bronze">
                  Entry
                </div>
                <div className="font-bold text-hex-white">
                  {formatAmount(activePosition.entry_price)}
                </div>
              </div>
            </div>
          </div>
        )}

        {!canTrade && (
          <p className="font-mono text-xs text-hex-bronze">
            Gamba Invest unlocks after onboarding and is disabled for
            spectators.
          </p>
        )}

        {createGambaPosition.isError && (
          <p className="font-mono text-xs text-hex-zaun">
            {createGambaPosition.error.message}
          </p>
        )}

        {!activePosition && !canAfford && hasValidAmount && (
          <p className="font-mono text-xs text-hex-zaun">
            Insufficient balance
          </p>
        )}

        <button
          type="submit"
          disabled={!canSubmit}
          className={`w-full border-2 py-2 font-mono text-xs font-bold uppercase tracking-[0.18em] transition-colors ${
            canSubmit
              ? "border-hex-gold text-hex-gold hover:bg-hex-gold hover:text-hex-bg"
              : "cursor-not-allowed border-hex-border text-hex-border"
          }`}
        >
          {createGambaPosition.isPending
            ? "Rolling..."
            : activePosition
              ? "Active Gamba Running"
              : "Start Gamba"}
        </button>
      </form>
    </section>
  );
}
