import { useMemo, useState } from "react";

import type { AdminPlayerInsightResponse } from "../../types";
import { useStreamerMode } from "../../contexts/useStreamerMode";
import { formatAmount, formatLocalDateTime } from "../../utils/format";
import { getStreamerSafeName } from "../../utils/streamerMode";

interface Props {
  insights: AdminPlayerInsightResponse[];
}

function formatNullableAmount(value: number | null) {
  return value === null ? "--" : formatAmount(value);
}

function formatNullablePercent(value: number | null) {
  if (value === null) {
    return "--";
  }

  return `${(value * 100).toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function toneForSignedNumber(value: number) {
  if (value > 0) {
    return "text-emerald-400";
  }
  if (value < 0) {
    return "text-red-400";
  }
  return "text-hex-bronze";
}

export default function AdminPlayerInsightsPanel({ insights }: Props) {
  const { isStreamerMode } = useStreamerMode();
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(
    insights[0]?.player_id ?? null,
  );

  const selectedInsight = useMemo(() => {
    if (insights.length === 0) {
      return null;
    }

    return (
      insights.find((entry) => entry.player_id === selectedPlayerId) ??
      insights[0]
    );
  }, [insights, selectedPlayerId]);

  return (
    <section className="border-2 border-hex-gold-dim bg-hex-panel">
      <div className="border-b-2 border-hex-gold-dim px-5 py-3">
        <h2 className="font-serif text-xl font-bold text-hex-gold">
          Player Database Insights
        </h2>
        <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.18em] text-hex-bronze">
          Live pricing factors, linked-user rewards, and stored market state per
          tracked player
        </p>
      </div>

      {insights.length === 0 || selectedInsight === null ? (
        <div className="px-5 py-6 font-mono text-sm text-hex-bronze">
          No tracked players available yet.
        </div>
      ) : (
        <div className="grid gap-0 xl:grid-cols-[22rem_minmax(0,1fr)]">
          <aside className="border-b-2 border-hex-border xl:border-r-2 xl:border-b-0">
            <div className="max-h-[70rem] overflow-y-auto">
              {insights.map((entry) => {
                const playerLabel = isStreamerMode
                  ? getStreamerSafeName(entry.game_name, entry.display_name)
                  : entry.display_name;
                const isSelected =
                  entry.player_id === selectedInsight.player_id;

                return (
                  <button
                    key={entry.player_id}
                    type="button"
                    onClick={() => setSelectedPlayerId(entry.player_id)}
                    className={`block w-full border-b border-hex-border/60 px-4 py-4 text-left transition-colors ${
                      isSelected ? "bg-hex-bg-alt" : "hover:bg-hex-bg-alt/60"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-serif text-lg font-bold text-hex-white">
                          {playerLabel}
                        </div>
                        {!isStreamerMode && (
                          <div className="mt-1 font-mono text-[11px] text-hex-bronze">
                            {entry.game_name}#{entry.tag_line}
                          </div>
                        )}
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-sm font-bold text-hex-gold">
                          {formatAmount(entry.current_price)} P
                        </div>
                        <div
                          className={`font-mono text-[11px] ${toneForSignedNumber(entry.lp_delta)}`}
                        >
                          LP {entry.lp_delta > 0 ? "+" : ""}
                          {entry.lp_delta}
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-[11px] text-hex-bronze">
                      <div>Streak {entry.streak}</div>
                      <div className="text-right">
                        Ratio {entry.estimated_lp_ratio_clamped.toFixed(2)}
                      </div>
                      <div>
                        PI {formatAmount(entry.playing_income_lifetime_total)} P
                      </div>
                      <div className="text-right">
                        Poro {formatAmount(entry.poro_rewards_total)} P
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </aside>

          <div className="space-y-6 px-5 py-5">
            <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {[
                {
                  label: "Current Price",
                  value: `${formatAmount(selectedInsight.current_price)} P`,
                },
                {
                  label: "LP Abs",
                  value: `${selectedInsight.lp_abs}`,
                },
                {
                  label: "LP Delta",
                  value: `${selectedInsight.lp_delta > 0 ? "+" : ""}${selectedInsight.lp_delta}`,
                  tone: toneForSignedNumber(selectedInsight.lp_delta),
                },
                {
                  label: "Gamma",
                  value: selectedInsight.gamma_factor.toFixed(3),
                },
                {
                  label: "Stored Streak",
                  value: `${selectedInsight.streak}`,
                },
                {
                  label: "Effective Streak",
                  value: `${selectedInsight.effective_positive_streak}`,
                },
                {
                  label: "LP Ratio",
                  value: `${selectedInsight.estimated_lp_ratio_clamped.toFixed(2)}`,
                },
                {
                  label: "Streak Multiplier",
                  value: selectedInsight.estimated_streak_multiplier.toFixed(3),
                },
              ].map((item) => (
                <article
                  key={item.label}
                  className="border border-hex-border bg-hex-bg-alt px-4 py-3"
                >
                  <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                    {item.label}
                  </div>
                  <div
                    className={`mt-2 font-mono text-lg font-bold ${item.tone ?? "text-hex-gold"}`}
                  >
                    {item.value}
                  </div>
                </article>
              ))}
            </section>

            <section className="grid gap-6 xl:grid-cols-2">
              <article className="border border-hex-border px-4 py-4">
                <h3 className="font-serif text-lg font-bold text-hex-gold">
                  Estimated Pricing Inputs
                </h3>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {[
                    {
                      label: "Avg LP / Win",
                      value: formatNullableAmount(
                        selectedInsight.avg_lp_gain_on_win,
                      ),
                    },
                    {
                      label: "Avg LP / Loss",
                      value: formatNullableAmount(
                        selectedInsight.avg_lp_loss_on_loss,
                      ),
                    },
                    {
                      label: "Raw LP Ratio",
                      value:
                        selectedInsight.estimated_lp_ratio_raw === null
                          ? "--"
                          : selectedInsight.estimated_lp_ratio_raw.toFixed(3),
                    },
                    {
                      label: "Clamped LP Ratio",
                      value:
                        selectedInsight.estimated_lp_ratio_clamped.toFixed(3),
                    },
                    {
                      label: "Wins Snapshot",
                      value: `${selectedInsight.ranked_wins_snapshot ?? "--"}`,
                    },
                    {
                      label: "Losses Snapshot",
                      value: `${selectedInsight.ranked_losses_snapshot ?? "--"}`,
                    },
                    {
                      label: "Estimated Win Rate",
                      value: formatNullablePercent(
                        selectedInsight.estimated_win_rate,
                      ),
                    },
                    {
                      label: "Win Rate Multiplier",
                      value:
                        selectedInsight.estimated_win_rate_multiplier === null
                          ? "--"
                          : selectedInsight.estimated_win_rate_multiplier.toFixed(
                              3,
                            ),
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="border border-hex-border/60 bg-hex-bg-alt px-3 py-2"
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
              </article>

              <article className="border border-hex-border px-4 py-4">
                <h3 className="font-serif text-lg font-bold text-hex-gold">
                  Linked User Snapshot
                </h3>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {[
                    {
                      label: "Linked Username",
                      value: selectedInsight.linked_username ?? "Not linked",
                    },
                    {
                      label: "Net Worth",
                      value:
                        selectedInsight.linked_user_net_worth === null
                          ? "--"
                          : `${formatAmount(selectedInsight.linked_user_net_worth)} P`,
                    },
                    {
                      label: "Cash",
                      value:
                        selectedInsight.linked_user_balance === null
                          ? "--"
                          : `${formatAmount(selectedInsight.linked_user_balance)} P`,
                    },
                    {
                      label: "Holdings",
                      value:
                        selectedInsight.linked_user_holdings_value === null
                          ? "--"
                          : `${formatAmount(selectedInsight.linked_user_holdings_value)} P`,
                    },
                    {
                      label: "Active Gamba",
                      value:
                        selectedInsight.linked_user_active_gamba_value === null
                          ? "--"
                          : `${formatAmount(selectedInsight.linked_user_active_gamba_value)} P`,
                    },
                    {
                      label: "Debt",
                      value:
                        selectedInsight.linked_user_debt_outstanding === null
                          ? "--"
                          : `${formatAmount(selectedInsight.linked_user_debt_outstanding)} P`,
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="border border-hex-border/60 bg-hex-bg-alt px-3 py-2"
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
              </article>
            </section>

            <section className="grid gap-6 xl:grid-cols-3">
              <article className="border border-hex-border px-4 py-4">
                <h3 className="font-serif text-lg font-bold text-hex-gold">
                  Market Positioning
                </h3>
                <div className="mt-4 space-y-3 font-mono text-sm">
                  <div className="flex items-center justify-between text-hex-white">
                    <span className="text-hex-bronze">Shareholders</span>
                    <span>{selectedInsight.shareholder_count}</span>
                  </div>
                  <div className="flex items-center justify-between text-hex-white">
                    <span className="text-hex-bronze">Total Shares Held</span>
                    <span>{selectedInsight.total_shares_held}</span>
                  </div>
                  <div className="flex items-center justify-between text-hex-white">
                    <span className="text-hex-bronze">Active Gambas</span>
                    <span>{selectedInsight.active_gamba_positions}</span>
                  </div>
                  <div className="flex items-center justify-between text-hex-white">
                    <span className="text-hex-bronze">Active Gamba Cash</span>
                    <span>
                      {formatAmount(selectedInsight.active_gamba_cash)} P
                    </span>
                  </div>
                </div>
              </article>

              <article className="border border-hex-border px-4 py-4">
                <h3 className="font-serif text-lg font-bold text-hex-gold">
                  Playing Income
                </h3>
                <div className="mt-4 space-y-3 font-mono text-sm">
                  <div className="flex items-center justify-between text-hex-white">
                    <span className="text-hex-bronze">Games Rewarded</span>
                    <span>{selectedInsight.playing_income_game_count}</span>
                  </div>
                  <div className="flex items-center justify-between text-hex-white">
                    <span className="text-hex-bronze">Lifetime Total</span>
                    <span>
                      {formatAmount(
                        selectedInsight.playing_income_lifetime_total,
                      )}{" "}
                      P
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-hex-white">
                    <span className="text-hex-bronze">Avg / Game</span>
                    <span>
                      {selectedInsight.playing_income_average_per_game === null
                        ? "--"
                        : `${formatAmount(selectedInsight.playing_income_average_per_game)} P`}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-hex-white">
                    <span className="text-hex-bronze">Last 24h</span>
                    <span>
                      {formatAmount(selectedInsight.playing_income_last_24h)} P
                    </span>
                  </div>
                </div>
              </article>

              <article className="border border-hex-border px-4 py-4">
                <h3 className="font-serif text-lg font-bold text-hex-gold">
                  Poro Rewards
                </h3>
                <div className="mt-4 space-y-3 font-mono text-sm">
                  <div className="flex items-center justify-between text-hex-white">
                    <span className="text-hex-bronze">Claims</span>
                    <span>{selectedInsight.poro_claim_count}</span>
                  </div>
                  <div className="flex items-center justify-between text-hex-white">
                    <span className="text-hex-bronze">Lifetime Total</span>
                    <span>
                      {formatAmount(selectedInsight.poro_rewards_total)} P
                    </span>
                  </div>
                </div>
              </article>
            </section>

            <section className="grid gap-6 xl:grid-cols-2">
              <article className="border border-hex-border px-4 py-4">
                <h3 className="font-serif text-lg font-bold text-hex-gold">
                  Recent Playing Income Entries
                </h3>
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-hex-border text-left">
                        <th className="px-2 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                          Match
                        </th>
                        <th className="px-2 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                          Result
                        </th>
                        <th className="px-2 py-2 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                          Amount
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedInsight.recent_playing_income_entries.map(
                        (entry) => (
                          <tr
                            key={entry.match_id}
                            className="border-b border-hex-border/50"
                          >
                            <td className="px-2 py-2 font-mono text-xs text-hex-white">
                              <div>{entry.match_id}</div>
                              <div className="text-[11px] text-hex-bronze">
                                {formatLocalDateTime(entry.match_completed_at)}
                              </div>
                            </td>
                            <td className="px-2 py-2 font-mono text-xs text-hex-bronze">
                              {entry.match_result}
                            </td>
                            <td className="px-2 py-2 text-right font-mono text-xs font-bold text-hex-gold">
                              {formatAmount(entry.amount)} P
                            </td>
                          </tr>
                        ),
                      )}
                      {selectedInsight.recent_playing_income_entries.length ===
                        0 && (
                        <tr>
                          <td
                            colSpan={3}
                            className="px-2 py-4 text-center font-mono text-sm text-hex-bronze"
                          >
                            No playing income records yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </article>

              <article className="border border-hex-border px-4 py-4">
                <h3 className="font-serif text-lg font-bold text-hex-gold">
                  Recent Poro Rewards
                </h3>
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-hex-border text-left">
                        <th className="px-2 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                          Spawn
                        </th>
                        <th className="px-2 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                          Status
                        </th>
                        <th className="px-2 py-2 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                          Reward
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedInsight.recent_poro_rewards.map((reward) => (
                        <tr
                          key={reward.spawn_id}
                          className="border-b border-hex-border/50"
                        >
                          <td className="px-2 py-2 font-mono text-xs text-hex-white">
                            <div>{reward.spawn_id}</div>
                            <div className="text-[11px] text-hex-bronze">
                              {formatLocalDateTime(reward.spawned_at)}
                            </div>
                          </td>
                          <td className="px-2 py-2 font-mono text-xs text-hex-bronze">
                            {reward.status}
                          </td>
                          <td className="px-2 py-2 text-right font-mono text-xs font-bold text-hex-gold">
                            {formatAmount(reward.reward_amount)} P
                          </td>
                        </tr>
                      ))}
                      {selectedInsight.recent_poro_rewards.length === 0 && (
                        <tr>
                          <td
                            colSpan={3}
                            className="px-2 py-4 text-center font-mono text-sm text-hex-bronze"
                          >
                            No poro history for the linked user.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </article>
            </section>
          </div>
        </div>
      )}
    </section>
  );
}
