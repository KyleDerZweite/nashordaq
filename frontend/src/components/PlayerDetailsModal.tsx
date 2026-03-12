import { useMemo, useState } from "react";
import TimeSeriesChart, { type TimeSeriesChartDatum } from "./TimeSeriesChart";
import { useStreamerMode } from "../contexts/useStreamerMode";
import { usePlayer } from "../api";
import type { OrderSide, PriceHistoryEntry } from "../types";
import { obfuscateName, obfuscateRiotHandle } from "../utils/streamerMode";
import {
  formatAmount,
  formatLocalDate,
  formatLocalDateTime,
  parseBackendUtcTimestamp,
} from "../utils/format";
import {
  CHART_RANGE_OPTIONS,
  type ChartRange,
  filterItemsByRange,
} from "../utils/timeSeries";

type ChartResolution = "daily" | "all";
type TrendDirection = "up" | "down" | "flat";

const OPGG_PLATFORM = "euw";

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

function buildOpGgSummonerUrl(gameName: string, tagLine: string): string {
  return `https://op.gg/lol/summoners/${OPGG_PLATFORM}/${encodeURIComponent(`${gameName}-${tagLine}`)}`;
}

function OutgoingLinkIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="square"
      strokeLinejoin="miter"
    >
      <rect x="3" y="7" width="10" height="10" />
      <rect x="7" y="3" width="10" height="10" />
    </svg>
  );
}

export default function PlayerDetailsModal({
  playerId,
  canTrade = false,
  isOwnStock = false,
  onTrade,
  onClose,
}: Props) {
  const { isStreamerMode } = useStreamerMode();
  const [range, setRange] = useState<ChartRange>(30);
  const [resolution, setResolution] = useState<ChartResolution>("daily");
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
    () =>
      filterItemsByRange(
        resolution === "daily" ? dailyHistory : rawHistory,
        range,
        (entry) => entry.recorded_at,
      ),
    [dailyHistory, rawHistory, range, resolution],
  );

  const chartData = useMemo<TimeSeriesChartDatum[]>(
    () =>
      chartHistory.map((entry) => ({
        id: entry.recorded_at,
        timestamp: entry.recorded_at,
        values: { price: entry.price },
        meta: { lpAbs: entry.lp_abs },
      })),
    [chartHistory],
  );

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

  const opGgUrl = useMemo(() => {
    if (!player) {
      return null;
    }

    return buildOpGgSummonerUrl(player.game_name, player.tag_line);
  }, [player]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/85 px-4 py-6"
      onClick={onClose}
    >
      <section
        className="relative flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden border-4 border-hex-gold bg-hex-panel shadow-brutal-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b-4 border-hex-gold bg-hex-bg-alt px-6 py-5">
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
                {player
                  ? isStreamerMode
                    ? obfuscateName(player.display_name)
                    : player.display_name
                  : "Loading player..."}
              </h2>
              {player && opGgUrl && !isStreamerMode ? (
                <a
                  href={opGgUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-flex flex-wrap items-center gap-2 font-mono text-sm text-hex-bronze underline decoration-hex-magic decoration-2 underline-offset-4 transition-colors hover:text-hex-white"
                  title="Open this summoner on OP.GG"
                >
                  <span className="text-hex-magic">
                    <OutgoingLinkIcon />
                  </span>
                  <span>{`${player.game_name}#${player.tag_line}`}</span>
                </a>
              ) : player && isStreamerMode ? (
                <p className="mt-1 font-mono text-sm text-hex-bronze">
                  {obfuscateRiotHandle(player.game_name, player.tag_line)}
                </p>
              ) : (
                <p className="mt-1 font-mono text-sm text-hex-bronze">
                  Fetching complete market history
                </p>
              )}
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
                <section className="border-2 border-hex-border bg-hex-bg-alt">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-hex-border px-5 py-4">
                    <div>
                      <h3 className="font-serif text-2xl font-bold text-hex-white">
                        Price History
                      </h3>
                      <p className="font-mono text-xs uppercase tracking-[0.18em] text-hex-bronze">
                        {resolution === "daily"
                          ? "Daily close prices"
                          : "Every recorded data point"}{" "}
                        · {chartHistory.length} entries in view
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="flex border border-hex-border">
                        {(
                          [
                            { label: "Daily", value: "daily" },
                            { label: "All", value: "all" },
                          ] as const
                        ).map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => setResolution(option.value)}
                            className={`border-l border-hex-border px-3 py-2 font-mono text-xs font-bold uppercase tracking-[0.18em] transition-colors first:border-l-0 ${
                              resolution === option.value
                                ? "bg-hex-gold text-hex-bg"
                                : "text-hex-bronze hover:bg-hex-panel hover:text-hex-white"
                            }`}
                          >
                            {option.label}
                          </button>
                        ))}
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
                        {formatSignedAmount(metrics.rangeChange)} P
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
                        {resolution === "daily"
                          ? "Daily closes in this view"
                          : "Data points in this view"}
                      </div>
                    </div>
                  </div>

                  <div className="px-5 py-5">
                    <TimeSeriesChart
                      data={chartData}
                      series={[
                        {
                          key: "price",
                          label: "Price",
                          color: "#d8c48a",
                          strokeWidth: 3.5,
                          fillOpacity: 0.28,
                          formatValue: (value) => `${formatAmount(value)} P`,
                        },
                      ]}
                      className="p-4"
                      emptyMessage="More history is needed before the chart can draw a real trend line."
                      formatAxisValue={formatAmount}
                      renderTooltipDetails={(datum) => (
                        <div className="space-y-1">
                          <div>LP {datum.meta?.lpAbs}</div>
                        </div>
                      )}
                    />
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
                    Last Market Change
                  </div>
                  <div className="mt-3 font-mono text-sm font-bold uppercase tracking-[0.16em] text-hex-white">
                    {player.last_updated
                      ? formatLocalDateTime(player.last_updated)
                      : "Awaiting first live update"}
                  </div>
                  <div className="mt-2 font-mono text-xs leading-5 text-hex-bronze">
                    This reflects the last stored player price change. Global
                    market service freshness is shown in the footer.
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
