import { useMemo, useState } from "react";
import { useCreateGambaPosition, useGambaPositions } from "../api";
import { useStreamerMode } from "../contexts/useStreamerMode";
import GambaModal from "./GambaModal";
import { getStreamerSafeName } from "../utils/streamerMode";
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
  const { isStreamerMode } = useStreamerMode();
  const [cashAmount, setCashAmount] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const { data: positions } = useGambaPositions(canTrade);
  const createGambaPosition = useCreateGambaPosition();

  const activePositions = useMemo(
    () => positions?.filter((position) => position.status === "ACTIVE") ?? [],
    [positions],
  );
  const summaryPositions = useMemo(
    () =>
      activePositions.length > 0
        ? activePositions.slice(0, 3)
        : (positions ?? []).slice(0, 3),
    [activePositions, positions],
  );
  const committedTotal = useMemo(
    () =>
      activePositions.reduce(
        (total, position) => total + position.cash_amount,
        0,
      ),
    [activePositions],
  );
  const parsedCashAmount = Number(cashAmount);
  const hasValidAmount =
    Number.isFinite(parsedCashAmount) && parsedCashAmount > 0;
  const canAfford = hasValidAmount && parsedCashAmount <= balance;
  const canSubmit =
    canTrade && hasValidAmount && canAfford && !createGambaPosition.isPending;

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
              x2 &ndash; 4
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
              disabled={!canTrade || balance <= 0}
              className={`shrink-0 border-2 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                canTrade && balance > 0
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

        {(positions?.length ?? 0) > 0 && (
          <div className="space-y-3 border-2 border-hex-magic/50 bg-hex-bg-alt px-3 py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                  {activePositions.length > 0
                    ? "Active Gambas"
                    : "Recent Gambas"}
                </p>
                <p className="font-serif text-lg font-bold text-hex-white">
                  {activePositions.length > 0
                    ? `${activePositions.length} running`
                    : `${positions?.length ?? 0} total`}
                </p>
              </div>
              <div className="text-right font-mono text-xs text-hex-bronze">
                <div>
                  {activePositions.length > 0 ? "Committed" : "History"}
                </div>
                <div className="text-hex-gold">
                  {activePositions.length > 0
                    ? `${formatAmount(committedTotal)} P`
                    : `${positions?.length ?? 0} slips`}
                </div>
              </div>
            </div>

            <div className="overflow-hidden border border-hex-border">
              <table className="w-full table-fixed">
                <thead>
                  <tr className="border-b border-hex-border bg-hex-bg text-left">
                    <th className="px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-hex-bronze">
                      Player
                    </th>
                    <th className="px-3 py-2 text-right font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-hex-bronze">
                      Cash
                    </th>
                    <th className="px-3 py-2 text-right font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-hex-bronze">
                      Exit
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {summaryPositions.map((position) => (
                    <tr
                      key={position.id}
                      className="border-b border-hex-border/50 last:border-b-0"
                    >
                      <td className="px-3 py-2 font-mono text-xs text-hex-white">
                        <div className="truncate font-semibold">
                          {isStreamerMode
                            ? getStreamerSafeName(
                                position.player_game_name,
                                position.player_name,
                              )
                            : position.player_name}
                        </div>
                        <div className="truncate text-[11px] text-hex-bronze">
                          {formatQuantity(position.quantity)} @{" "}
                          {formatAmount(position.entry_price)}
                          {" · "}
                          <span className="text-hex-gold">
                            x{position.settlement_multiplier.toFixed(1)}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-xs font-bold text-hex-gold">
                        {formatAmount(position.cash_amount)} P
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-[11px] text-hex-bronze">
                        {formatLocalDateTime(position.scheduled_settlement_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between gap-3 border-t border-hex-border pt-3">
              <p className="font-mono text-[11px] text-hex-bronze">
                {activePositions.length > 0
                  ? activePositions.length > summaryPositions.length
                    ? `Showing ${summaryPositions.length} of ${activePositions.length} active gambas.`
                    : `All ${activePositions.length} active gambas shown.`
                  : `Showing the latest ${summaryPositions.length} gamba records.`}
              </p>
              <button
                type="button"
                onClick={() => setIsModalOpen(true)}
                className="border border-hex-gold px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-[0.18em] text-hex-gold transition-colors hover:bg-hex-gold hover:text-hex-bg"
              >
                View All
              </button>
            </div>
          </div>
        )}

        {!canTrade && (
          <p className="font-mono text-xs text-hex-bronze">
            Gamba Invest unlocks after onboarding and is disabled for admin
            accounts.
          </p>
        )}

        {createGambaPosition.isError && (
          <p className="font-mono text-xs text-hex-zaun">
            {createGambaPosition.error.message}
          </p>
        )}

        {!canAfford && hasValidAmount && (
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
            : activePositions.length > 0
              ? `Start Another Gamba (${activePositions.length} Active)`
              : "Start Gamba"}
        </button>
      </form>

      {isModalOpen && (
        <GambaModal
          positions={positions ?? []}
          onClose={() => setIsModalOpen(false)}
        />
      )}
    </section>
  );
}
