import { useMemo } from "react";

import { useStreamerMode } from "../contexts/useStreamerMode";
import type { HoldingResponse, OrderSide, PortfolioResponse } from "../types";
import { getStreamerSafeName } from "../utils/streamerMode";
import { formatAmount } from "../utils/format";

interface Props {
  portfolio?: PortfolioResponse | null;
  canTrade?: boolean;
  gambaEnabled?: boolean;
  onTrade?: (playerId: number, side: OrderSide) => void;
  onClose: () => void;
}

function pnlTone(value: number): string {
  if (value > 0) {
    return "text-emerald-400";
  }
  if (value < 0) {
    return "text-red-400";
  }
  return "text-hex-bronze";
}

function formatSignedAmount(value: number): string {
  return `${value > 0 ? "+" : ""}${formatAmount(value)}`;
}

function formatSignedPercent(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function PortfolioInsightRow({
  holding,
  canTrade,
  onTrade,
  isStreamerMode,
}: {
  holding: HoldingResponse;
  canTrade: boolean;
  onTrade?: (playerId: number, side: OrderSide) => void;
  isStreamerMode: boolean;
}) {
  return (
    <tr className="border-b border-hex-border/50 transition-colors hover:bg-hex-bg-alt/80">
      <td className="px-4 py-3 font-mono text-sm font-medium text-hex-white">
        {isStreamerMode
          ? getStreamerSafeName(holding.player_game_name, holding.player_name)
          : holding.player_name}
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm text-hex-bronze">
        {holding.quantity}
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm text-hex-gold">
        {formatAmount(holding.average_buy_price)}
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm text-hex-gold">
        {formatAmount(holding.cost_basis)}
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm text-hex-gold">
        {formatAmount(holding.current_price)}
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm font-bold text-hex-magic">
        {formatAmount(holding.market_value)}
      </td>
      <td
        className={`px-4 py-3 text-right font-mono text-sm font-bold ${pnlTone(
          holding.unrealized_pnl,
        )}`}
      >
        {formatSignedAmount(holding.unrealized_pnl)}
        <span className="ml-1 text-xs opacity-80">
          ({formatSignedPercent(holding.unrealized_pnl_pct)})
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={() => onTrade?.(holding.player_id, "BUY")}
            disabled={!canTrade}
            className={`border px-3 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.18em] transition-colors ${
              canTrade
                ? "border-hex-magic text-hex-magic hover:bg-hex-magic hover:text-hex-bg"
                : "cursor-not-allowed border-hex-border text-hex-border"
            }`}
          >
            Buy
          </button>
          <button
            type="button"
            onClick={() => onTrade?.(holding.player_id, "SELL")}
            disabled={!canTrade}
            className={`border px-3 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.18em] transition-colors ${
              canTrade
                ? "border-hex-zaun text-hex-zaun hover:bg-hex-zaun hover:text-hex-bg"
                : "cursor-not-allowed border-hex-border text-hex-border"
            }`}
          >
            Sell
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function PortfolioInsightsModal({
  portfolio,
  canTrade = false,
  gambaEnabled = true,
  onTrade,
  onClose,
}: Props) {
  const { isStreamerMode } = useStreamerMode();
  const holdings = useMemo(
    () => portfolio?.holdings ?? [],
    [portfolio?.holdings],
  );
  const summaryItems = useMemo(
    () => [
      { label: "Cash", value: portfolio?.balance ?? 0 },
      { label: "Holdings", value: portfolio?.holdings_value ?? 0 },
      ...(gambaEnabled
        ? [{ label: "Gamba", value: portfolio?.active_gamba_value ?? 0 }]
        : []),
      { label: "Debt", value: portfolio?.debt_outstanding ?? 0 },
      { label: "Net Total", value: portfolio?.total_value ?? 0 },
      { label: "Positions", value: holdings.length, isCount: true },
    ],
    [
      gambaEnabled,
      holdings.length,
      portfolio?.active_gamba_value,
      portfolio?.balance,
      portfolio?.debt_outstanding,
      portfolio?.holdings_value,
      portfolio?.total_value,
    ],
  );
  const totalCostBasis = useMemo(
    () => holdings.reduce((sum, holding) => sum + holding.cost_basis, 0),
    [holdings],
  );
  const totalUnrealizedPnl = useMemo(
    () => holdings.reduce((sum, holding) => sum + holding.unrealized_pnl, 0),
    [holdings],
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/85 px-4 py-6"
      onClick={onClose}
    >
      <section
        className="relative flex max-h-[92vh] w-full max-w-7xl flex-col overflow-hidden border-4 border-hex-gold bg-hex-panel shadow-brutal-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b-4 border-hex-gold bg-hex-bg-alt px-6 py-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-3">
                <span className="border border-hex-border px-2 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.24em] text-hex-bronze">
                  Portfolio Insights
                </span>
                <span className="font-mono text-xs uppercase tracking-[0.18em] text-hex-bronze">
                  Detailed holdings and trade shortcuts
                </span>
              </div>
              <h2 className="font-serif text-3xl font-bold text-hex-gold">
                Porofolio Breakdown
              </h2>
              <p className="mt-1 font-mono text-sm text-hex-bronze">
                Cost basis, live mark, unrealized P/L, and direct buy or sell
                actions for each position.
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

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
          <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
            {summaryItems.map((item) => (
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
                    : `${formatAmount(Number(item.value))} P`}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="border border-hex-border px-4 py-3">
              <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-hex-gold">
                Exposure
              </h3>
              <p className="mt-2 font-mono text-xs text-hex-bronze">
                Total cost basis: {formatAmount(totalCostBasis)} P
              </p>
              <p
                className={`mt-1 font-mono text-xs ${pnlTone(totalUnrealizedPnl)}`}
              >
                Unrealized P/L: {formatSignedAmount(totalUnrealizedPnl)} P
              </p>
            </div>

            <div className="border border-hex-border px-4 py-3">
              <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-hex-gold">
                Trading
              </h3>
              <p className="mt-2 font-mono text-xs text-hex-bronze">
                Use the action buttons in each row to jump straight into the
                order ticket for that holding.
              </p>
              {!canTrade && (
                <p className="mt-1 font-mono text-xs text-hex-bronze">
                  Trading actions unlock after onboarding as a player.
                </p>
              )}
            </div>
          </div>

          <div className="mt-6 overflow-x-auto border-2 border-hex-border">
            <table className="w-full min-w-[62rem]">
              <thead>
                <tr className="border-b-2 border-hex-border bg-hex-bg-alt text-left">
                  {[
                    "Player",
                    "Qty",
                    "Avg Buy",
                    "Cost Basis",
                    "Current",
                    "Market Value",
                    "Unrealized",
                    "Actions",
                  ].map((column, index) => (
                    <th
                      key={column}
                      className={`px-4 py-3 font-mono text-[11px] font-bold uppercase tracking-[0.18em] text-hex-bronze ${
                        index > 0 && index < 7 ? "text-right" : ""
                      } ${index === 7 ? "text-right" : ""}`}
                    >
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {holdings.map((holding) => (
                  <PortfolioInsightRow
                    key={holding.player_id}
                    holding={holding}
                    canTrade={canTrade}
                    onTrade={onTrade}
                    isStreamerMode={isStreamerMode}
                  />
                ))}
                {holdings.length === 0 && (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-8 text-center font-mono text-sm text-hex-bronze"
                    >
                      No holdings yet. Once you buy a stock, the full position
                      breakdown will appear here.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
