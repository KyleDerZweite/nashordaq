import { useMemo, useState } from "react";
import { usePlayer } from "../api";
import type { OrderSide, PriceHistoryEntry } from "../types";
import {
  formatAmount,
  formatLocalDate,
  formatLocalDateShort,
  formatLocalDateTime,
  parseBackendUtcTimestamp,
} from "../utils/format";

type ChartRange = 30 | 90 | "all";
type TrendDirection = "up" | "down" | "flat";

interface Props {
  playerId: number;
  canTrade?: boolean;
  isOwnStock?: boolean;
  onTrade?: (side: OrderSide) => void;
  onClose: () => void;
}

interface MomentumSummary {
  windowSize: number;
  delta: number;
  recentChange: number;
  previousChange: number;
}

const RANGE_OPTIONS: Array<{ label: string; value: ChartRange }> = [
  { label: "30D", value: 30 },
  { label: "90D", value: 90 },
  { label: "All", value: "all" },
];

function formatSignedAmount(value: number): string {
  return `${value > 0 ? "+" : value < 0 ? "-" : ""}${formatAmount(Math.abs(value))}`;
}

function formatSignedPercent(value: number): string {
  return `${value > 0 ? "+" : value < 0 ? "-" : ""}${Math.abs(
    value,
  ).toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function buildBaseHistory(
  history: PriceHistoryEntry[],
  fallback: PriceHistoryEntry,
): PriceHistoryEntry[] {
  if (history.length === 0) {
    return [fallback];
  }

  return [...history].sort(
    (left, right) =>
      parseBackendUtcTimestamp(left.recorded_at).getTime() -
      parseBackendUtcTimestamp(right.recorded_at).getTime(),
  );
}

function buildDailySeries(history: PriceHistoryEntry[]): PriceHistoryEntry[] {
  const byDay = new Map<string, PriceHistoryEntry>();

  history.forEach((entry) => {
    byDay.set(entry.recorded_at.slice(0, 10), entry);
  });

  return Array.from(byDay.values()).sort(
    (left, right) =>
      parseBackendUtcTimestamp(left.recorded_at).getTime() -
      parseBackendUtcTimestamp(right.recorded_at).getTime(),
  );
}

function filterSeriesByRange(
  history: PriceHistoryEntry[],
  range: ChartRange,
): PriceHistoryEntry[] {
  if (range === "all" || history.length === 0) {
    return history;
  }

  const latestTime = parseBackendUtcTimestamp(
    history[history.length - 1].recorded_at,
  ).getTime();
  const cutoffTime = latestTime - range * 24 * 60 * 60 * 1000;
  const filtered = history.filter(
    (entry) =>
      parseBackendUtcTimestamp(entry.recorded_at).getTime() >= cutoffTime,
  );

  return filtered.length > 0 ? filtered : history;
}

function getTrendDirection(change: number): TrendDirection {
  if (change > 0) {
    return "up";
  }
  if (change < 0) {
    return "down";
  }
  return "flat";
}

function calculateMomentum(
  history: PriceHistoryEntry[],
): MomentumSummary | null {
  const windowSize = Math.min(7, Math.floor(history.length / 2));

  if (windowSize < 2) {
    return null;
  }

  const previousWindow = history.slice(-windowSize * 2, -windowSize);
  const recentWindow = history.slice(-windowSize);
  const previousChange =
    previousWindow[previousWindow.length - 1].price - previousWindow[0].price;
  const recentChange =
    recentWindow[recentWindow.length - 1].price - recentWindow[0].price;

  return {
    windowSize,
    delta: recentChange - previousChange,
    recentChange,
    previousChange,
  };
}

function buildChartGeometry(history: PriceHistoryEntry[]) {
  const width = 820;
  const height = 340;
  const paddingLeft = 30;
  const paddingRight = 42;
  const paddingTop = 28;
  const paddingBottom = 54;
  const prices = history.map((entry) => entry.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const priceSpan = maxPrice - minPrice || 1;
  const usableWidth = width - paddingLeft - paddingRight;
  const usableHeight = height - paddingTop - paddingBottom;

  const points = history.map((entry, index) => {
    const x =
      history.length === 1
        ? width / 2
        : paddingLeft + (usableWidth * index) / (history.length - 1);
    const y =
      height -
      paddingBottom -
      ((entry.price - minPrice) / priceSpan) * usableHeight;

    return { x, y, entry };
  });

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x} ${point.y}`)
    .join(" ");
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${height - paddingBottom} L ${points[0].x} ${height - paddingBottom} Z`;
  const tickIndexes = Array.from(
    new Set([0, Math.floor((points.length - 1) / 2), points.length - 1]),
  );

  return {
    width,
    height,
    paddingLeft,
    paddingRight,
    paddingTop,
    paddingBottom,
    minPrice,
    maxPrice,
    points,
    linePath,
    areaPath,
    tickIndexes,
  };
}

export default function PlayerDetailsModal({
  playerId,
  canTrade = false,
  isOwnStock = false,
  onTrade,
  onClose,
}: Props) {
  const [range, setRange] = useState<ChartRange>(30);
  const { data: player, isLoading, isError, error } = usePlayer(playerId);

  const fallbackEntry = useMemo<PriceHistoryEntry | null>(() => {
    if (!player) {
      return null;
    }

    return {
      price: player.current_price,
      lp_abs: player.lp_abs,
      recorded_at: player.last_updated ?? new Date().toISOString(),
    };
  }, [player]);

  const rawHistory = useMemo(() => {
    if (!player || !fallbackEntry) {
      return [];
    }

    return buildBaseHistory(player.price_history, fallbackEntry);
  }, [fallbackEntry, player]);

  const dailyHistory = useMemo(
    () => buildDailySeries(rawHistory),
    [rawHistory],
  );
  const chartHistory = useMemo(
    () => filterSeriesByRange(dailyHistory, range),
    [dailyHistory, range],
  );

  const chartGeometry = useMemo(() => {
    if (chartHistory.length < 2) {
      return null;
    }

    return buildChartGeometry(chartHistory);
  }, [chartHistory]);

  const metrics = useMemo(() => {
    if (!player || rawHistory.length === 0) {
      return null;
    }

    const ath = rawHistory.reduce((best, entry) =>
      entry.price > best.price ? entry : best,
    );
    const atl = rawHistory.reduce((best, entry) =>
      entry.price < best.price ? entry : best,
    );
    const selectedHistory =
      chartHistory.length > 0 ? chartHistory : dailyHistory;
    const rangeStart = selectedHistory[0];
    const rangeEnd = selectedHistory[selectedHistory.length - 1];
    const rangeChange = rangeEnd.price - rangeStart.price;
    const rangePercent =
      rangeStart.price === 0 ? 0 : (rangeChange / rangeStart.price) * 100;
    const lpChange = rangeEnd.lp_abs - rangeStart.lp_abs;
    const momentum = calculateMomentum(selectedHistory);

    return {
      ath,
      atl,
      rangeStart,
      rangeEnd,
      rangeChange,
      rangePercent,
      lpChange,
      direction: getTrendDirection(rangeChange),
      momentum,
      dayCount: selectedHistory.length,
    };
  }, [chartHistory, dailyHistory, player, rawHistory]);

  const trendCopy = useMemo(() => {
    if (!metrics) {
      return null;
    }

    if (metrics.direction === "up") {
      return {
        headline: "Bullish trajectory",
        body: `Added ${formatAmount(metrics.rangeChange)} P over the selected window (${formatSignedPercent(metrics.rangePercent)}).`,
        tone: "text-emerald-400",
      };
    }

    if (metrics.direction === "down") {
      return {
        headline: "Bearish trajectory",
        body: `Lost ${formatAmount(Math.abs(metrics.rangeChange))} P over the selected window (${formatSignedPercent(metrics.rangePercent)}).`,
        tone: "text-red-400",
      };
    }

    return {
      headline: "Sideways trade",
      body: "Price has stayed nearly flat over the selected range.",
      tone: "text-hex-bronze",
    };
  }, [metrics]);

  const momentumCopy = useMemo(() => {
    if (!metrics?.momentum) {
      return "Not enough daily history yet to judge acceleration.";
    }

    const { delta, recentChange, previousChange, windowSize } =
      metrics.momentum;
    const recentDirection = getTrendDirection(recentChange);

    if (Math.abs(delta) < 0.01) {
      return `Momentum is steady versus the previous ${windowSize}-day block.`;
    }

    if (recentDirection === "up") {
      return delta > 0
        ? `Increasing faster by ${formatAmount(Math.abs(delta))} P versus the previous ${windowSize}-day block.`
        : `Still increasing, but slower by ${formatAmount(Math.abs(delta))} P versus the previous ${windowSize}-day block.`;
    }

    if (recentDirection === "down") {
      return delta < 0
        ? `Decreasing faster by ${formatAmount(Math.abs(delta))} P versus the previous ${windowSize}-day block.`
        : `Still decreasing, but stabilizing by ${formatAmount(Math.abs(delta))} P versus the previous ${windowSize}-day block.`;
    }

    const previousDirection = getTrendDirection(previousChange);
    return previousDirection === "down"
      ? `The slide is easing by ${formatAmount(Math.abs(delta))} P versus the previous ${windowSize}-day block.`
      : `Movement is picking up by ${formatAmount(Math.abs(delta))} P versus the previous ${windowSize}-day block.`;
  }, [metrics]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/85 px-4 py-6"
      onClick={onClose}
    >
      <section
        className="relative flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden border-4 border-hex-gold-dim bg-hex-panel shadow-brutal-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b-4 border-hex-gold-dim bg-hex-bg-alt px-6 py-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-3">
                <span className="border border-hex-border px-2 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.24em] text-hex-bronze">
                  Player Details
                </span>
                {player && trendCopy && (
                  <span
                    className={`font-mono text-xs font-bold uppercase tracking-[0.18em] ${trendCopy.tone}`}
                  >
                    {trendCopy.headline}
                  </span>
                )}
              </div>
              <h2 className="font-serif text-3xl font-bold text-hex-gold">
                {player?.display_name ?? "Loading player..."}
              </h2>
              <p className="mt-1 font-mono text-sm text-hex-bronze">
                {player
                  ? `${player.game_name}#${player.tag_line}`
                  : "Fetching complete market history"}
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-3">
              {player && (
                <div className="border-2 border-hex-border bg-hex-bg px-4 py-3 text-right">
                  <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-bronze">
                    Current Price
                  </div>
                  <div className="font-mono text-2xl font-bold text-hex-gold">
                    {formatAmount(player.current_price)}
                  </div>
                </div>
              )}

              {player && canTrade && onTrade && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => onTrade("BUY")}
                    disabled={player.last_updated === null || isOwnStock}
                    className={`border-2 px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.18em] transition-colors ${
                      player.last_updated !== null && !isOwnStock
                        ? "border-hex-magic text-hex-magic hover:bg-hex-magic hover:text-hex-bg"
                        : "cursor-not-allowed border-hex-border text-hex-border"
                    }`}
                  >
                    {isOwnStock ? "Own Stock" : "Buy"}
                  </button>
                  <button
                    type="button"
                    onClick={() => onTrade("SELL")}
                    className="border-2 border-hex-zaun px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-zaun transition-colors hover:bg-hex-zaun hover:text-hex-bg"
                  >
                    Sell
                  </button>
                </div>
              )}

              <button
                type="button"
                onClick={onClose}
                className="border-2 border-hex-border px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-bronze transition-colors hover:border-hex-white hover:text-hex-white"
              >
                Close
              </button>
            </div>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
          {isLoading && (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(18rem,1fr)]">
              <div className="animate-pulse border-2 border-hex-border bg-hex-bg-alt p-6">
                <div className="h-5 w-40 bg-hex-border/60" />
                <div className="mt-6 h-72 bg-hex-border/40" />
              </div>
              <div className="space-y-4">
                {[0, 1, 2, 3].map((item) => (
                  <div
                    key={item}
                    className="animate-pulse border-2 border-hex-border bg-hex-bg-alt p-5"
                  >
                    <div className="h-4 w-24 bg-hex-border/60" />
                    <div className="mt-3 h-8 w-32 bg-hex-border/40" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {isError && (
            <div className="border-2 border-hex-zaun bg-hex-bg px-5 py-4 font-mono text-sm text-hex-zaun">
              {error.message}
            </div>
          )}

          {player && metrics && trendCopy && (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(18rem,1fr)]">
              <div className="space-y-6">
                <section className="overflow-hidden border-2 border-hex-border bg-hex-bg-alt">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-hex-border px-5 py-4">
                    <div>
                      <h3 className="font-serif text-2xl font-bold text-hex-white">
                        Price History
                      </h3>
                      <p className="font-mono text-xs uppercase tracking-[0.18em] text-hex-bronze">
                        Daily close view for 30 days, 90 days, or all available
                        history
                      </p>
                    </div>

                    <div className="flex border border-hex-border">
                      {RANGE_OPTIONS.map((option) => (
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

                  <div className="grid gap-4 border-b-2 border-hex-border px-5 py-4 sm:grid-cols-3">
                    <div>
                      <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-bronze">
                        Range Move
                      </div>
                      <div
                        className={`mt-2 font-mono text-2xl font-bold ${
                          metrics.direction === "up"
                            ? "text-emerald-400"
                            : metrics.direction === "down"
                              ? "text-red-400"
                              : "text-hex-gold"
                        }`}
                      >
                        {formatSignedAmount(metrics.rangeChange)} G
                      </div>
                      <div className="font-mono text-xs text-hex-bronze">
                        {formatSignedPercent(metrics.rangePercent)}
                      </div>
                    </div>
                    <div>
                      <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-bronze">
                        LP Shift
                      </div>
                      <div className="mt-2 font-mono text-2xl font-bold text-hex-gold">
                        {metrics.lpChange > 0 ? "+" : ""}
                        {metrics.lpChange}
                      </div>
                      <div className="font-mono text-xs text-hex-bronze">
                        Ranked momentum over view
                      </div>
                    </div>
                    <div>
                      <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-bronze">
                        Data Coverage
                      </div>
                      <div className="mt-2 font-mono text-2xl font-bold text-hex-gold">
                        {metrics.dayCount}
                      </div>
                      <div className="font-mono text-xs text-hex-bronze">
                        Daily closes in this view
                      </div>
                    </div>
                  </div>

                  <div className="px-5 py-5">
                    {chartGeometry ? (
                      <div className="overflow-hidden rounded-sm border border-hex-border bg-[linear-gradient(180deg,rgba(14,17,22,0.88)_0%,rgba(8,10,14,0.95)_100%)] p-4">
                        <svg
                          viewBox={`0 0 ${chartGeometry.width} ${chartGeometry.height}`}
                          className="h-96 w-full"
                        >
                          <defs>
                            <linearGradient
                              id="player-detail-fill"
                              x1="0"
                              x2="0"
                              y1="0"
                              y2="1"
                            >
                              <stop
                                offset="0%"
                                stopColor="rgba(219,170,68,0.45)"
                              />
                              <stop
                                offset="100%"
                                stopColor="rgba(219,170,68,0.04)"
                              />
                            </linearGradient>
                          </defs>

                          {[0, 0.25, 0.5, 0.75, 1].map((step) => {
                            const y =
                              chartGeometry.paddingTop +
                              (chartGeometry.height -
                                chartGeometry.paddingTop -
                                chartGeometry.paddingBottom) *
                                step;

                            return (
                              <line
                                key={step}
                                x1={chartGeometry.paddingLeft}
                                x2={
                                  chartGeometry.width -
                                  chartGeometry.paddingRight
                                }
                                y1={y}
                                y2={y}
                                stroke="rgba(162,140,87,0.18)"
                                strokeDasharray="4 8"
                              />
                            );
                          })}

                          <path
                            d={chartGeometry.areaPath}
                            fill="url(#player-detail-fill)"
                          />
                          <path
                            d={chartGeometry.linePath}
                            fill="none"
                            stroke="#dbab44"
                            strokeWidth="4"
                            strokeLinejoin="round"
                            strokeLinecap="round"
                          />

                          {chartGeometry.points.map((point, index) =>
                            index === 0 ||
                            index === chartGeometry.points.length - 1 ? (
                              <g key={`${point.entry.recorded_at}-${index}`}>
                                <circle
                                  cx={point.x}
                                  cy={point.y}
                                  r="5"
                                  fill="#0b0d11"
                                  stroke="#dbab44"
                                  strokeWidth="3"
                                />
                              </g>
                            ) : null,
                          )}

                          <text
                            x={chartGeometry.paddingLeft}
                            y={18}
                            fill="#d4b06a"
                            fontSize="12"
                            fontFamily="monospace"
                          >
                            High {formatAmount(chartGeometry.maxPrice)}
                          </text>
                          <text
                            x={chartGeometry.paddingLeft}
                            y={chartGeometry.height - 26}
                            fill="#8f7a52"
                            fontSize="12"
                            fontFamily="monospace"
                          >
                            Low {formatAmount(chartGeometry.minPrice)}
                          </text>

                          {chartGeometry.tickIndexes.map((tickIndex) => {
                            const point = chartGeometry.points[tickIndex];

                            return (
                              <text
                                key={`${point.entry.recorded_at}-label`}
                                x={
                                  tickIndex === 0
                                    ? point.x + 8
                                    : tickIndex ===
                                        chartGeometry.points.length - 1
                                      ? point.x - 8
                                      : point.x
                                }
                                y={chartGeometry.height - 10}
                                textAnchor={
                                  tickIndex === 0
                                    ? "start"
                                    : tickIndex ===
                                        chartGeometry.points.length - 1
                                      ? "end"
                                      : "middle"
                                }
                                fill="#8f7a52"
                                fontSize="11"
                                fontFamily="monospace"
                              >
                                {formatLocalDateShort(point.entry.recorded_at)}
                              </text>
                            );
                          })}
                        </svg>
                      </div>
                    ) : (
                      <div className="flex h-80 items-center justify-center border border-dashed border-hex-border bg-hex-bg text-center font-mono text-sm text-hex-bronze">
                        More history is needed before the chart can draw a real
                        trend line.
                      </div>
                    )}
                  </div>
                </section>

                <section className="grid gap-4 md:grid-cols-2">
                  <div className="border-2 border-emerald-500/40 bg-emerald-500/5 p-5">
                    <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-emerald-400">
                      Trend Read
                    </div>
                    <div
                      className={`mt-3 font-serif text-2xl font-bold ${trendCopy.tone}`}
                    >
                      {trendCopy.headline}
                    </div>
                    <p className="mt-2 font-mono text-sm leading-6 text-hex-white">
                      {trendCopy.body}
                    </p>
                  </div>

                  <div className="border-2 border-hex-border bg-hex-bg p-5">
                    <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-bronze">
                      Momentum Read
                    </div>
                    <div className="mt-3 font-serif text-2xl font-bold text-hex-gold">
                      Acceleration
                    </div>
                    <p className="mt-2 font-mono text-sm leading-6 text-hex-white">
                      {momentumCopy}
                    </p>
                  </div>
                </section>
              </div>

              <aside className="space-y-4">
                <section className="border-2 border-hex-border bg-hex-bg-alt p-5">
                  <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-bronze">
                    All-Time High
                  </div>
                  <div className="mt-3 font-mono text-3xl font-bold text-emerald-400">
                    {formatAmount(metrics.ath.price)}
                  </div>
                  <div className="mt-2 font-mono text-xs leading-5 text-hex-bronze">
                    Hit on {formatLocalDate(metrics.ath.recorded_at)}
                  </div>
                </section>

                <section className="border-2 border-hex-border bg-hex-bg-alt p-5">
                  <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-bronze">
                    All-Time Low
                  </div>
                  <div className="mt-3 font-mono text-3xl font-bold text-red-400">
                    {formatAmount(metrics.atl.price)}
                  </div>
                  <div className="mt-2 font-mono text-xs leading-5 text-hex-bronze">
                    Hit on {formatLocalDate(metrics.atl.recorded_at)}
                  </div>
                </section>

                <section className="border-2 border-hex-border bg-hex-bg-alt p-5">
                  <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-bronze">
                    Current Ranked LP
                  </div>
                  <div className="mt-3 font-mono text-3xl font-bold text-hex-gold">
                    {player.lp_abs}
                  </div>
                  <div className="mt-2 font-mono text-xs leading-5 text-hex-bronze">
                    Previous checkpoint {player.previous_lp_abs} LP
                  </div>
                </section>

                <section className="border-2 border-hex-border bg-hex-bg-alt p-5">
                  <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-bronze">
                    Market Streak
                  </div>
                  <div className="mt-3 font-mono text-3xl font-bold text-hex-gold">
                    {player.streak}
                  </div>
                  <div className="mt-2 font-mono text-xs leading-5 text-hex-bronze">
                    From {formatLocalDate(metrics.rangeStart.recorded_at)} to{" "}
                    {formatLocalDate(metrics.rangeEnd.recorded_at)}
                  </div>
                </section>

                <section className="border-2 border-hex-border bg-hex-bg p-5">
                  <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-bronze">
                    Latest Update
                  </div>
                  <div className="mt-3 font-mono text-sm font-bold uppercase tracking-[0.16em] text-hex-white">
                    {player.last_updated
                      ? formatLocalDateTime(player.last_updated)
                      : "Awaiting first live update"}
                  </div>
                  <div className="mt-2 font-mono text-xs leading-5 text-hex-bronze">
                    This view recalculates ATH, ATL, trend direction, and chart
                    slices from the stored market history.
                  </div>
                </section>
              </aside>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
