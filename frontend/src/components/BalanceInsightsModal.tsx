import { useMemo, useState } from "react";
import { useBalanceInsights } from "../api";
import TimeSeriesChart, { type TimeSeriesChartDatum } from "./TimeSeriesChart";
import { formatAmount, formatLocalDateTime } from "../utils/format";
import {
  CHART_RANGE_OPTIONS,
  type ChartRange,
  filterItemsByRange,
} from "../utils/timeSeries";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

function snapshotSourceLabel(source: string): string {
  if (source === "MARKET_UPDATE") {
    return "Market update";
  }
  if (source === "CREDIT_ACTION") {
    return "Credit action";
  }
  if (source === "ONBOARDING") {
    return "Onboarding";
  }
  return source;
}

export default function BalanceInsightsModal({ isOpen, onClose }: Props) {
  const [range, setRange] = useState<ChartRange>(30);
  const { data, isLoading, isError, error } = useBalanceInsights(isOpen);
  const history = useMemo(() => data?.history ?? [], [data?.history]);
  const filteredHistory = useMemo(
    () => filterItemsByRange(history, range, (entry) => entry.recorded_at),
    [history, range],
  );
  const chartData = useMemo<TimeSeriesChartDatum[]>(
    () =>
      filteredHistory.map((entry) => ({
        id: String(entry.id),
        timestamp: entry.recorded_at,
        values: {
          balance: entry.cash_balance,
          netWorth: entry.net_worth,
        },
        meta: {
          source: snapshotSourceLabel(entry.source),
          debt: entry.debt_outstanding,
          holdings: entry.holdings_value,
        },
      })),
    [filteredHistory],
  );

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/80"
      onClick={onClose}
    >
      <section
        className="w-full max-w-4xl border-4 border-hex-gold bg-hex-panel shadow-brutal-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b-4 border-hex-gold px-5 py-3">
          <div>
            <h2 className="font-serif text-xl font-bold text-hex-gold">
              Balance Insights
            </h2>
            <p className="mt-1 font-mono text-xs uppercase tracking-[0.18em] text-hex-bronze">
              Balance, income and net worth through market updates
            </p>
          </div>
          <button
            onClick={onClose}
            className="font-mono text-lg font-bold text-hex-bronze transition-colors hover:text-hex-white"
          >
            X
          </button>
        </div>

        <div className="px-5 py-4">
          {isLoading && (
            <p className="font-mono text-sm text-hex-bronze">
              Loading balance insights...
            </p>
          )}

          {isError && (
            <p className="font-mono text-sm text-hex-zaun">{error.message}</p>
          )}

          {data && (
            <div className="space-y-5">
              <div className="grid gap-3 md:grid-cols-6">
                {[
                  {
                    label: "Balance",
                    value: `${formatAmount(data.cash_balance)} P`,
                  },
                  {
                    label: "Net Worth",
                    value: `${formatAmount(data.net_worth)} P`,
                  },
                  {
                    label: "Holdings",
                    value: `${formatAmount(data.holdings_value)} P`,
                  },
                  {
                    label: "Active Gamba",
                    value: `${formatAmount(data.active_gamba_value)} P`,
                  },
                  {
                    label: "Credit",
                    value: `${formatAmount(data.debt_outstanding)} P`,
                  },
                  {
                    label: "Income 24h",
                    value: `${formatAmount(data.playing_income_last_24h)} P`,
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="border border-hex-border bg-hex-bg-alt px-3 py-2"
                  >
                    <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                      {item.label}
                    </div>
                    <div className="mt-1 font-mono text-sm font-bold text-hex-white">
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>

              <div className="grid gap-4 lg:grid-cols-[1.45fr_0.95fr]">
                <div className="border border-hex-border px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-hex-gold">
                        Balance vs Net Worth
                      </h3>
                      <p className="mt-1 font-mono text-[11px] text-hex-bronze">
                        {filteredHistory.length} snapshots in view ·{" "}
                        {history.length} tracked total
                      </p>
                    </div>
                    <div className="flex border border-hex-border">
                      {CHART_RANGE_OPTIONS.map((option) => (
                        <button
                          key={option.label}
                          type="button"
                          onClick={() => setRange(option.value)}
                          className={`border-l border-hex-border px-4 py-2 font-mono text-xs font-bold uppercase tracking-[0.18em] transition-colors first:border-l-0 ${
                            range === option.value
                              ? "bg-hex-gold text-hex-bg"
                              : "text-hex-bronze hover:bg-hex-panel hover:text-hex-white"
                          }`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {filteredHistory.length >= 2 ? (
                    <div className="mt-4 space-y-3">
                      <TimeSeriesChart
                        data={chartData}
                        series={[
                          {
                            key: "balance",
                            label: "Balance",
                            color: "#c8aa6e",
                            strokeWidth: 3.25,
                            fillOpacity: 0.18,
                            formatValue: (value) => `${formatAmount(value)} P`,
                          },
                          {
                            key: "netWorth",
                            label: "Net Worth",
                            color: "#c8aa6e",
                            strokeWidth: 3,
                            dashArray: "8 6",
                            formatValue: (value) => `${formatAmount(value)} P`,
                          },
                        ]}
                        className="p-3"
                        emptyMessage="History will appear after market updates and credit actions create more snapshots."
                        formatAxisValue={formatAmount}
                        renderTooltipDetails={(datum) => (
                          <div className="space-y-1">
                            <div>{datum.meta?.source}</div>
                            <div>
                              Holdings{" "}
                              {formatAmount(Number(datum.meta?.holdings ?? 0))}{" "}
                              P
                            </div>
                            <div>
                              Credit{" "}
                              {formatAmount(Number(datum.meta?.debt ?? 0))} P
                            </div>
                          </div>
                        )}
                      />
                      <div className="flex flex-wrap gap-4 font-mono text-[11px] uppercase tracking-[0.18em] text-hex-bronze">
                        <span className="text-hex-gold">Solid: Balance</span>
                        <span className="text-hex-gold/80">
                          Dashed: Net Worth
                        </span>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-4 font-mono text-xs text-hex-bronze">
                      History will appear after market updates and credit
                      actions create more snapshots.
                    </p>
                  )}
                </div>

                <div className="space-y-4">
                  <div className="border border-hex-border px-4 py-3">
                    <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-hex-gold">
                      Income View
                    </h3>
                    <p className="mt-2 font-mono text-xs text-hex-bronze">
                      Last 24h: {formatAmount(data.playing_income_last_24h)} P
                    </p>
                    <p className="mt-1 font-mono text-xs text-hex-bronze">
                      Lifetime:{" "}
                      {formatAmount(data.playing_income_lifetime_total)} P
                    </p>
                  </div>

                  <div className="border border-hex-border px-4 py-3">
                    <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-hex-gold">
                      Recent Snapshots
                    </h3>
                    <div
                      className={`mt-3 space-y-2 ${
                        history.length > 5
                          ? "max-h-72 overflow-y-auto pr-1"
                          : ""
                      }`}
                    >
                      {history.length === 0 && (
                        <p className="font-mono text-xs text-hex-bronze">
                          No snapshots yet.
                        </p>
                      )}
                      {[...history].reverse().map((entry) => (
                        <div
                          key={entry.id}
                          className="border border-hex-border/60 bg-hex-bg-alt px-3 py-2"
                        >
                          <p className="font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-white">
                            {snapshotSourceLabel(entry.source)}
                          </p>
                          <p className="mt-1 font-mono text-[11px] text-hex-bronze">
                            {formatLocalDateTime(entry.recorded_at)}
                          </p>
                          <p className="mt-1 font-mono text-[11px] text-hex-bronze">
                            Balance {formatAmount(entry.cash_balance)} P · Net
                            worth {formatAmount(entry.net_worth)} P
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
