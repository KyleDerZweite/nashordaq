import { useMemo } from "react";

import { useStreamerMode } from "../contexts/useStreamerMode";
import type { GambaPositionResponse } from "../types";
import { obfuscateName } from "../utils/streamerMode";
import {
  formatAmount,
  formatLocalDateTime,
  formatQuantity,
} from "../utils/format";

interface Props {
  positions: GambaPositionResponse[];
  onClose: () => void;
}

function statusTone(status: GambaPositionResponse["status"]): string {
  return status === "ACTIVE" ? "text-hex-magic" : "text-hex-bronze";
}

function formatSignedAmount(value: number): string {
  return `${value > 0 ? "+" : ""}${formatAmount(value)}`;
}

function formatCompactDateTime(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function GambaModal({ positions, onClose }: Props) {
  const { isStreamerMode } = useStreamerMode();
  const activePositions = useMemo(
    () => positions.filter((position) => position.status === "ACTIVE"),
    [positions],
  );
  const committedTotal = useMemo(
    () =>
      activePositions.reduce((sum, position) => sum + position.cash_amount, 0),
    [activePositions],
  );
  const settledPnl = useMemo(
    () =>
      positions.reduce((sum, position) => sum + (position.settled_pnl ?? 0), 0),
    [positions],
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/80 px-3 py-4 sm:px-4 sm:py-6"
      onClick={onClose}
    >
      <section
        className="relative flex max-h-[94vh] w-full max-w-none flex-col overflow-hidden border-4 border-hex-gold bg-hex-panel shadow-brutal-lg xl:w-[min(96vw,96rem)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b-4 border-hex-gold bg-hex-bg-alt px-4 py-4 sm:px-6 sm:py-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-3">
                <span className="border border-hex-border px-2 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.24em] text-hex-bronze">
                  Gamba Ledger
                </span>
                <span className="font-mono text-xs uppercase tracking-[0.18em] text-hex-bronze">
                  All active and settled random positions
                </span>
              </div>
              <h2 className="font-serif text-3xl font-bold text-hex-gold">
                Gamba Positions
              </h2>
              <p className="mt-1 font-mono text-sm text-hex-bronze">
                Live rolls, settled outcomes, and the full payout trail for each
                random investment.
              </p>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="border-2 border-hex-border px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-bronze transition-colors hover:border-hex-white hover:text-hex-white"
            >
              Close
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { label: "Positions", value: positions.length, isCount: true },
              {
                label: "Active",
                value: activePositions.length,
                isCount: true,
              },
              { label: "Committed", value: committedTotal },
              { label: "Settled P/L", value: settledPnl, isSigned: true },
            ].map((item) => (
              <div
                key={item.label}
                className="border border-hex-border bg-hex-bg-alt px-4 py-3"
              >
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                  {item.label}
                </div>
                <div className="mt-2 font-mono text-lg font-bold text-hex-gold">
                  {item.isCount
                    ? item.value
                    : `${item.isSigned ? formatSignedAmount(Number(item.value)) : formatAmount(Number(item.value))} P`}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 hidden xl:block overflow-x-auto border-2 border-hex-border">
            <table className="w-full table-fixed min-w-0">
              <colgroup>
                <col className="w-[9%]" />
                <col className="w-[18%]" />
                <col className="w-[10%]" />
                <col className="w-[10%]" />
                <col className="w-[10%]" />
                <col className="w-[18%]" />
                <col className="w-[15%]" />
                <col className="w-[10%]" />
              </colgroup>
              <thead>
                <tr className="border-b-2 border-hex-border bg-hex-bg-alt text-left">
                  {[
                    "Status",
                    "Player",
                    "Cash",
                    "Qty",
                    "Entry",
                    "Scheduled",
                    "Settled",
                    "Result",
                  ].map((column, index) => (
                    <th
                      key={column}
                      className={`px-4 py-3 font-mono text-[11px] font-bold uppercase tracking-[0.18em] text-hex-bronze ${
                        index >= 2 ? "text-right" : ""
                      }`}
                    >
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map((position) => (
                  <tr
                    key={position.id}
                    className="border-b border-hex-border/50 transition-colors hover:bg-hex-bg-alt/80"
                  >
                    <td
                      className={`px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.18em] ${statusTone(position.status)}`}
                    >
                      {position.status}
                    </td>
                    <td className="px-4 py-3 font-mono text-sm font-medium text-hex-white">
                      <span className="block truncate">
                        {isStreamerMode
                          ? obfuscateName(position.player_name)
                          : position.player_name}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-hex-gold">
                      {formatAmount(position.cash_amount)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-hex-white">
                      {formatQuantity(position.quantity)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-hex-white">
                      {formatAmount(position.entry_price)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-hex-bronze">
                      {formatCompactDateTime(position.scheduled_settlement_at)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-hex-bronze">
                      {position.settled_at
                        ? formatCompactDateTime(position.settled_at)
                        : "--"}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm font-bold text-hex-gold">
                      {position.settled_pnl !== null
                        ? `${formatSignedAmount(position.settled_pnl)} P`
                        : "--"}
                    </td>
                  </tr>
                ))}
                {positions.length === 0 && (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-8 text-center font-mono text-sm text-hex-bronze"
                    >
                      No gamba positions yet. Start a roll and the full ledger
                      will appear here.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-6 space-y-3 xl:hidden">
            {positions.map((position) => (
              <article
                key={position.id}
                className="border-2 border-hex-border bg-hex-bg-alt px-4 py-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div
                      className={`font-mono text-[11px] font-bold uppercase tracking-[0.18em] ${statusTone(position.status)}`}
                    >
                      {position.status}
                    </div>
                    <h3 className="mt-1 font-serif text-lg font-bold text-hex-white">
                      {isStreamerMode
                        ? obfuscateName(position.player_name)
                        : position.player_name}
                    </h3>
                  </div>
                  <div className="text-right font-mono text-sm font-bold text-hex-gold">
                    {formatAmount(position.cash_amount)} P
                  </div>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="border border-hex-border/70 bg-hex-bg px-3 py-2">
                    <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                      Quantity
                    </div>
                    <div className="mt-1 font-mono text-sm text-hex-white">
                      {formatQuantity(position.quantity)}
                    </div>
                  </div>
                  <div className="border border-hex-border/70 bg-hex-bg px-3 py-2">
                    <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                      Entry
                    </div>
                    <div className="mt-1 font-mono text-sm text-hex-white">
                      {formatAmount(position.entry_price)}
                    </div>
                  </div>
                  <div className="border border-hex-border/70 bg-hex-bg px-3 py-2">
                    <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                      Scheduled
                    </div>
                    <div className="mt-1 font-mono text-sm text-hex-white">
                      {formatLocalDateTime(position.scheduled_settlement_at)}
                    </div>
                  </div>
                  <div className="border border-hex-border/70 bg-hex-bg px-3 py-2">
                    <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                      Settled
                    </div>
                    <div className="mt-1 font-mono text-sm text-hex-white">
                      {position.settled_at
                        ? formatLocalDateTime(position.settled_at)
                        : "--"}
                    </div>
                  </div>
                </div>

                <div className="mt-3 border border-hex-border/70 bg-hex-bg px-3 py-2">
                  <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                    Result
                  </div>
                  <div className="mt-1 font-mono text-sm font-bold text-hex-gold">
                    {position.settled_pnl !== null
                      ? `${formatSignedAmount(position.settled_pnl)} P`
                      : "--"}
                  </div>
                </div>
              </article>
            ))}

            {positions.length === 0 && (
              <div className="border-2 border-hex-border px-4 py-8 text-center font-mono text-sm text-hex-bronze">
                No gamba positions yet. Start a roll and the full ledger will
                appear here.
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
