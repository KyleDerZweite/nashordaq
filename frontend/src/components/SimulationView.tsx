import { useMemo, useState } from "react";
import {
  useSimulationDefaults,
  useSimulationPlayerMatches,
  useRunSimulation,
  usePlayers,
} from "../api";
import type {
  SimulationDefaultsResponse,
  SimulationParameterSet,
  SimulationResponse,
  SimulationStep,
} from "../types";
import TimeSeriesChart from "./TimeSeriesChart";
import type {
  TimeSeriesChartDatum,
  TimeSeriesChartSeries,
} from "./TimeSeriesChart";
import { formatAmount } from "../utils/format";

type ScenarioMode = "synthetic" | "replay";

const SERIES_COLORS = [
  "#c8aa6e",
  "#22d3ee",
  "#a78bfa",
  "#fb923c",
  "#4ade80",
  "#f87171",
];

const PARAM_LABELS: Record<string, string> = {
  pricing_alpha: "Alpha (base volatility)",
  pricing_loss_move_multiplier: "Loss move multiplier",
  pricing_max_effective_streak: "Max effective streak",
  pricing_positive_lp_soft_cap: "Positive LP soft cap",
  pricing_negative_lp_soft_cap: "Negative LP soft cap",
  pricing_positive_lp_excess_efficiency: "Positive LP excess efficiency",
  pricing_negative_lp_excess_efficiency: "Negative LP excess efficiency",
  pricing_win_streak_lp_ratio_default: "Gain dampener default",
};

const PARAM_STEPS: Record<string, number> = {
  pricing_alpha: 0.01,
  pricing_loss_move_multiplier: 0.05,
  pricing_max_effective_streak: 1,
  pricing_positive_lp_soft_cap: 1,
  pricing_negative_lp_soft_cap: 1,
  pricing_positive_lp_excess_efficiency: 0.05,
  pricing_negative_lp_excess_efficiency: 0.05,
  pricing_win_streak_lp_ratio_default: 0.05,
};

function buildChartData(response: SimulationResponse): {
  data: TimeSeriesChartDatum[];
  series: TimeSeriesChartSeries[];
} {
  if (response.results.length === 0 || response.results[0].steps.length === 0) {
    return { data: [], series: [] };
  }

  const stepCount = response.results[0].steps.length;
  const baseTime = new Date("2026-01-01T00:00:00Z").getTime();

  const data: TimeSeriesChartDatum[] = [];

  // Add starting point
  const startValues: Record<string, number> = {};
  response.results.forEach((traj, idx) => {
    startValues[`set-${idx}`] = traj.steps[0].price_before;
  });
  data.push({
    id: "start",
    timestamp: new Date(baseTime).toISOString(),
    values: startValues,
    meta: { matchLabel: "Start" },
  });

  for (let i = 0; i < stepCount; i++) {
    const values: Record<string, number> = {};
    response.results.forEach((traj, idx) => {
      values[`set-${idx}`] = traj.steps[i].price_after;
    });
    data.push({
      id: `step-${i}`,
      timestamp: new Date(baseTime + (i + 1) * 3600000).toISOString(),
      values,
      meta: {
        matchLabel: `Match ${i + 1}`,
        deltaLp: response.results[0].steps[i].delta_lp,
        win: response.results[0].steps[i].win,
      },
    });
  }

  const series: TimeSeriesChartSeries[] = response.results.map((traj, idx) => ({
    key: `set-${idx}`,
    label: traj.label,
    color: SERIES_COLORS[idx % SERIES_COLORS.length],
    strokeWidth: idx === 0 ? 3 : 2,
    dashArray: idx > 0 ? "6 4" : undefined,
    fillOpacity: idx === 0 ? 0.12 : undefined,
    formatValue: (v: number) => `${formatAmount(v)} P`,
  }));

  return { data, series };
}

interface ParamEditorProps {
  label: string;
  params: SimulationParameterSet;
  defaults: SimulationDefaultsResponse | undefined;
  onChange: (params: SimulationParameterSet) => void;
}

function ParamEditor({ label, params, defaults, onChange }: ParamEditorProps) {
  const paramKeys = Object.keys(PARAM_LABELS);

  return (
    <div className="border border-hex-border bg-hex-bg-alt px-4 py-3">
      <h3 className="font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-gold">
        {label}
      </h3>
      <div className="mt-3 grid gap-2">
        {paramKeys.map((key) => {
          const override =
            (params as unknown as Record<string, number | null | undefined>)[
              key
            ] ?? null;
          const fallback = defaults
            ? (defaults as unknown as Record<string, number>)[key]
            : undefined;
          const displayValue = override ?? fallback ?? "";
          return (
            <div key={key} className="flex items-center gap-3">
              <label className="min-w-52 font-mono text-[11px] text-hex-bronze">
                {PARAM_LABELS[key]}
              </label>
              <input
                type="number"
                step={PARAM_STEPS[key] ?? 0.01}
                value={displayValue}
                onChange={(e) => {
                  const raw = e.target.value;
                  const next = raw === "" ? null : Number(raw);
                  onChange({
                    ...params,
                    [key]: next,
                  } as SimulationParameterSet);
                }}
                className="w-28 border border-hex-border bg-hex-bg px-2 py-1 font-mono text-xs text-hex-white focus:border-hex-gold focus:outline-none"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function SimulationView({ onClose }: { onClose: () => void }) {
  const { data: defaults } = useSimulationDefaults();
  const { data: players } = usePlayers();
  const runSimulation = useRunSimulation();

  const [mode, setMode] = useState<ScenarioMode>("synthetic");
  const [syntheticText, setSyntheticText] = useState(
    "20, 18, -15, 22, -20, -18, -16, 25, 20, -14",
  );
  const [startingPrice, setStartingPrice] = useState(25);
  const [startingStreak, setStartingStreak] = useState(0);
  const [replayPlayerId, setReplayPlayerId] = useState<number | null>(null);

  const { data: playerMatches } = useSimulationPlayerMatches(
    mode === "replay" ? replayPlayerId : null,
  );

  const [paramSets, setParamSets] = useState<SimulationParameterSet[]>([
    { label: "Baseline" },
    { label: "Comparison" },
  ]);

  const [result, setResult] = useState<SimulationResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"chart" | "table">("chart");
  const [tableSetIndex, setTableSetIndex] = useState(0);

  function handleRun() {
    if (mode === "synthetic") {
      const parts = syntheticText
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s !== "");
      const matches = parts.map((s) => {
        const lp = parseInt(s, 10);
        return { delta_lp: isNaN(lp) ? 0 : lp, win: (isNaN(lp) ? 0 : lp) > 0 };
      });
      if (matches.length === 0) return;
      runSimulation.mutate(
        {
          matches,
          starting_price: startingPrice,
          starting_streak: startingStreak,
          parameter_sets: paramSets,
        },
        { onSuccess: setResult },
      );
    } else if (replayPlayerId !== null) {
      runSimulation.mutate(
        {
          player_id: replayPlayerId,
          starting_price: startingPrice,
          starting_streak: startingStreak,
          parameter_sets: paramSets,
        },
        { onSuccess: setResult },
      );
    }
  }

  const chartData = useMemo(
    () => (result ? buildChartData(result) : null),
    [result],
  );

  const activeSteps: SimulationStep[] =
    result && result.results[tableSetIndex]
      ? result.results[tableSetIndex].steps
      : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-serif text-2xl font-bold text-hex-gold">
            Market Simulation
          </h2>
          <p className="mt-1 font-mono text-xs text-hex-bronze">
            Test pricing parameter changes against synthetic or real match
            scenarios
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="border-2 border-hex-border px-4 py-2 font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-bronze transition-colors hover:border-hex-white hover:text-hex-white"
        >
          Back to Market
        </button>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        {/* Left panel: Scenario + Parameters */}
        <div className="space-y-4 xl:col-span-1">
          {/* Scenario */}
          <div className="border border-hex-border bg-hex-bg-alt px-4 py-3">
            <h3 className="font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-gold">
              Scenario
            </h3>

            <div className="mt-3 flex border border-hex-border">
              <button
                type="button"
                onClick={() => setMode("synthetic")}
                className={`flex-1 px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                  mode === "synthetic"
                    ? "bg-hex-gold text-hex-bg"
                    : "text-hex-bronze hover:text-hex-white"
                }`}
              >
                Synthetic
              </button>
              <button
                type="button"
                onClick={() => setMode("replay")}
                className={`flex-1 border-l border-hex-border px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                  mode === "replay"
                    ? "bg-hex-gold text-hex-bg"
                    : "text-hex-bronze hover:text-hex-white"
                }`}
              >
                Replay
              </button>
            </div>

            {mode === "synthetic" ? (
              <div className="mt-3 space-y-2">
                <label className="font-mono text-[11px] text-hex-bronze">
                  LP deltas (comma-separated, positive = win, negative = loss)
                </label>
                <textarea
                  value={syntheticText}
                  onChange={(e) => setSyntheticText(e.target.value)}
                  rows={3}
                  className="w-full border border-hex-border bg-hex-bg px-2 py-1.5 font-mono text-xs text-hex-white focus:border-hex-gold focus:outline-none"
                  placeholder="20, 18, -15, 22, -20"
                />
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="font-mono text-[11px] text-hex-bronze">
                      Starting price
                    </label>
                    <input
                      type="number"
                      step={1}
                      value={startingPrice}
                      onChange={(e) => setStartingPrice(Number(e.target.value))}
                      className="mt-1 w-full border border-hex-border bg-hex-bg px-2 py-1 font-mono text-xs text-hex-white focus:border-hex-gold focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="font-mono text-[11px] text-hex-bronze">
                      Starting streak
                    </label>
                    <input
                      type="number"
                      step={1}
                      value={startingStreak}
                      onChange={(e) =>
                        setStartingStreak(Number(e.target.value))
                      }
                      className="mt-1 w-full border border-hex-border bg-hex-bg px-2 py-1 font-mono text-xs text-hex-white focus:border-hex-gold focus:outline-none"
                    />
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-3 space-y-2">
                <label className="font-mono text-[11px] text-hex-bronze">
                  Select player to replay
                </label>
                <select
                  value={replayPlayerId ?? ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    setReplayPlayerId(val ? Number(val) : null);
                  }}
                  className="w-full border border-hex-border bg-hex-bg px-2 py-1.5 font-mono text-xs text-hex-white focus:border-hex-gold focus:outline-none"
                >
                  <option value="">-- Select player --</option>
                  {(players ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name} ({p.game_name})
                    </option>
                  ))}
                </select>
                {playerMatches && (
                  <p className="font-mono text-[11px] text-hex-bronze">
                    {playerMatches.length} matches available
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Parameters */}
          {paramSets.map((ps, idx) => (
            <ParamEditor
              key={idx}
              label={ps.label}
              params={ps}
              defaults={defaults}
              onChange={(updated) => {
                const next = [...paramSets];
                next[idx] = updated;
                setParamSets(next);
              }}
            />
          ))}

          {/* Run */}
          <button
            type="button"
            onClick={handleRun}
            disabled={runSimulation.isPending}
            className="w-full border-2 border-hex-gold bg-hex-gold/10 px-4 py-3 font-mono text-sm font-bold uppercase tracking-[0.18em] text-hex-gold transition-colors hover:bg-hex-gold hover:text-hex-bg disabled:opacity-50"
          >
            {runSimulation.isPending ? "Running..." : "Run Simulation"}
          </button>

          {runSimulation.isError && (
            <p className="font-mono text-xs text-red-400">
              {runSimulation.error.message}
            </p>
          )}
        </div>

        {/* Right panel: Results */}
        <div className="space-y-4 xl:col-span-2">
          {!result && (
            <div className="flex h-96 items-center justify-center border border-dashed border-hex-border bg-hex-bg text-center font-mono text-sm text-hex-bronze">
              Configure a scenario and parameters, then run the simulation.
            </div>
          )}

          {result && chartData && (
            <>
              {/* Tab bar */}
              <div className="flex border-b-2 border-hex-border">
                <button
                  type="button"
                  onClick={() => setActiveTab("chart")}
                  className={`px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                    activeTab === "chart"
                      ? "border-b-2 border-hex-gold text-hex-gold"
                      : "text-hex-bronze hover:text-hex-white"
                  }`}
                >
                  Chart
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("table")}
                  className={`px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                    activeTab === "table"
                      ? "border-b-2 border-hex-gold text-hex-gold"
                      : "text-hex-bronze hover:text-hex-white"
                  }`}
                >
                  Step Data
                </button>
              </div>

              {activeTab === "chart" && (
                <TimeSeriesChart
                  data={chartData.data}
                  series={chartData.series}
                  formatAxisValue={(v) => `${v.toFixed(1)} P`}
                  xTickFormatter={() => ""}
                  tooltipTitleFormatter={() => ""}
                  renderTooltipDetails={(datum) => (
                    <div>
                      <div className="font-bold text-hex-white">
                        {String(datum.meta?.matchLabel ?? "")}
                      </div>
                      {datum.meta?.deltaLp !== undefined && (
                        <div className="mt-1">
                          LP: {datum.meta.win ? "+" : ""}
                          {String(datum.meta.deltaLp)}
                          {" | "}
                          {datum.meta.win ? "Win" : "Loss"}
                        </div>
                      )}
                    </div>
                  )}
                />
              )}

              {activeTab === "table" && (
                <div>
                  {/* Set selector */}
                  {result.results.length > 1 && (
                    <div className="mb-3 flex gap-2">
                      {result.results.map((traj, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => setTableSetIndex(idx)}
                          className={`px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider transition-colors ${
                            tableSetIndex === idx
                              ? "bg-hex-gold text-hex-bg"
                              : "border border-hex-border text-hex-bronze hover:text-hex-white"
                          }`}
                        >
                          {traj.label}
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="max-h-[32rem] overflow-auto border border-hex-border">
                    <table className="w-full text-left font-mono text-xs">
                      <thead className="sticky top-0 bg-hex-bg-alt text-hex-bronze">
                        <tr>
                          <th className="px-3 py-2">#</th>
                          <th className="px-3 py-2">LP</th>
                          <th className="px-3 py-2">W/L</th>
                          <th className="px-3 py-2">Streak</th>
                          <th className="px-3 py-2">Eff LP</th>
                          <th className="px-3 py-2">Streak Mult</th>
                          <th className="px-3 py-2">Price Before</th>
                          <th className="px-3 py-2">Price After</th>
                          <th className="px-3 py-2">Move</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeSteps.map((step: SimulationStep) => (
                          <tr
                            key={step.match_index}
                            className="border-t border-hex-border/50 text-hex-white hover:bg-hex-bg-alt/50"
                          >
                            <td className="px-3 py-1.5 text-hex-bronze">
                              {step.match_index + 1}
                            </td>
                            <td
                              className={`px-3 py-1.5 ${step.win ? "text-emerald-400" : "text-red-400"}`}
                            >
                              {step.win ? "+" : ""}
                              {step.delta_lp}
                            </td>
                            <td className="px-3 py-1.5">
                              {step.win ? "W" : "L"}
                            </td>
                            <td className="px-3 py-1.5">
                              {step.streak_before} {"->"} {step.streak_after}
                            </td>
                            <td className="px-3 py-1.5">
                              {step.effective_delta_lp.toFixed(2)}
                            </td>
                            <td className="px-3 py-1.5">
                              {step.streak_multiplier.toFixed(2)}x
                            </td>
                            <td className="px-3 py-1.5">
                              {formatAmount(step.price_before)}
                            </td>
                            <td className="px-3 py-1.5">
                              {formatAmount(step.price_after)}
                            </td>
                            <td
                              className={`px-3 py-1.5 font-bold ${step.price_move > 0 ? "text-emerald-400" : step.price_move < 0 ? "text-red-400" : "text-hex-bronze"}`}
                            >
                              {step.price_move > 0 ? "+" : ""}
                              {formatAmount(step.price_move)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
