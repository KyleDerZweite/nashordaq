import { useState } from "react";

import { useStreamerMode } from "../../contexts/useStreamerMode";
import type {
  AdminOverviewResponse,
  AdminUserSummaryResponse,
  OrderResponse,
  SystemStatusResponse,
} from "../../types";
import { getStreamerSafeName } from "../../utils/streamerMode";
import { formatAmount, formatLocalDateTime } from "../../utils/format";
import OrderHistory from "../OrderHistory";
import AdminPortfolioModal from "./AdminPortfolioModal";

interface Props {
  overview?: AdminOverviewResponse;
  users: AdminUserSummaryResponse[];
  orders: OrderResponse[];
  systemStatus?: SystemStatusResponse;
}

export default function AdminDashboard({
  overview,
  users,
  orders,
  systemStatus,
}: Props) {
  const { isStreamerMode } = useStreamerMode();
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  const statCards = [
    {
      label: "Users",
      value: overview?.total_users ?? users.length,
      suffix: "",
    },
    { label: "Onboarded", value: overview?.onboarded_users ?? 0, suffix: "" },
    {
      label: "Tracked Players",
      value: overview?.tracked_players ?? 0,
      suffix: "",
    },
    {
      label: "Total Orders",
      value: overview?.total_orders ?? orders.length,
      suffix: "",
    },
    { label: "Pending", value: overview?.pending_orders ?? 0, suffix: "" },
    {
      label: "Debt Outstanding",
      value: overview?.total_debt_outstanding ?? 0,
      suffix: " P",
    },
  ];

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        {statCards.map((item) => (
          <article
            key={item.label}
            className="border-2 border-hex-gold-dim bg-hex-panel px-4 py-4 shadow-brutal-sm"
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
              {item.label}
            </p>
            <p className="mt-2 font-mono text-2xl font-bold text-hex-gold">
              {item.suffix ? formatAmount(item.value) : item.value}
              {item.suffix}
            </p>
          </article>
        ))}
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_1.85fr]">
        <section className="border-2 border-hex-gold-dim bg-hex-panel">
          <div className="border-b-2 border-hex-gold-dim px-5 py-3">
            <h2 className="font-serif text-xl font-bold text-hex-gold">
              System Status
            </h2>
          </div>
          <div className="space-y-4 px-5 py-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-1">
              {[
                {
                  label: "Market Status",
                  value: systemStatus?.market_status ?? "idle",
                },
                {
                  label: "Scheduler",
                  value: systemStatus?.scheduler_running
                    ? "Running"
                    : "Stopped",
                },
                {
                  label: "Expected Cadence",
                  value: `${systemStatus?.expected_update_interval_minutes ?? 0} min`,
                },
                {
                  label: "Last Refresh",
                  value: systemStatus?.last_market_update_at
                    ? formatLocalDateTime(systemStatus.last_market_update_at)
                    : "No successful update yet",
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="border border-hex-border px-4 py-3"
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

            <div className="border border-hex-border px-4 py-3">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                Market Treasury Snapshot
              </div>
              <div className="mt-2 grid gap-3 md:grid-cols-2 xl:grid-cols-1">
                <div>
                  <div className="font-mono text-xs text-hex-bronze">
                    Total cash balance
                  </div>
                  <div className="font-mono text-lg font-bold text-hex-gold">
                    {formatAmount(overview?.total_cash_balance ?? 0)} P
                  </div>
                </div>
                <div>
                  <div className="font-mono text-xs text-hex-bronze">
                    Admin accounts
                  </div>
                  <div className="font-mono text-lg font-bold text-hex-gold">
                    {overview?.admin_users ?? 0}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-2 border-hex-gold-dim bg-hex-panel">
          <div className="border-b-2 border-hex-gold-dim px-5 py-3">
            <h2 className="font-serif text-xl font-bold text-hex-gold">
              User Oversight
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b-2 border-hex-border text-left">
                  <th className="px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                    User
                  </th>
                  <th className="px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                    Role
                  </th>
                  <th className="px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                    Linked Player
                  </th>
                  <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                    Net Worth
                  </th>
                  <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                    Debt
                  </th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr
                    key={user.id}
                    className="border-b border-hex-border/50 transition-colors hover:bg-hex-bg-alt"
                  >
                    <td className="px-4 py-2.5 font-mono text-sm text-hex-white">
                      <div>
                        {user.linked_player_name
                          ? isStreamerMode
                            ? getStreamerSafeName(
                                user.linked_player_game_name,
                                user.linked_player_name,
                              )
                            : user.linked_player_name
                          : user.username}
                      </div>
                      {!isStreamerMode && (
                        <div className="text-[11px] text-hex-bronze">
                          {user.username}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`inline-block border px-2 py-0.5 font-mono text-xs font-bold uppercase ${
                          user.role === "admin"
                            ? "border-hex-gold text-hex-gold"
                            : "border-hex-border text-hex-bronze"
                        }`}
                      >
                        {user.role}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-sm text-hex-bronze">
                      {user.linked_player_name
                        ? isStreamerMode
                          ? getStreamerSafeName(
                              user.linked_player_game_name,
                              user.linked_player_name,
                            )
                          : user.linked_player_name
                        : "Not onboarded"}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-sm font-bold text-hex-gold">
                      {formatAmount(user.total_value)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-sm text-red-400">
                      {formatAmount(user.debt_outstanding)}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedUserId(user.id)}
                        className="border border-hex-gold px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider text-hex-gold transition-colors hover:bg-hex-gold hover:text-hex-bg"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-4 py-6 text-center font-mono text-sm text-hex-bronze"
                    >
                      No users available yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <OrderHistory
        ownOrders={orders}
        allOrders={orders}
        defaultView="all"
        allowViewToggle={false}
        title="Market Activity"
      />

      {selectedUserId !== null && (
        <AdminPortfolioModal
          userId={selectedUserId}
          onClose={() => setSelectedUserId(null)}
        />
      )}
    </div>
  );
}
