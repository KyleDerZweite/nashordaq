import { useAdminUserPortfolio } from "../../api";
import { formatAmount, formatLocalDateTime } from "../../utils/format";

interface Props {
  userId: number;
  onClose: () => void;
}

export default function AdminPortfolioModal({ userId, onClose }: Props) {
  const { data, isLoading, isError, error } = useAdminUserPortfolio(userId);

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
              User Portfolio
            </h2>
            {data && (
              <p className="mt-1 font-mono text-xs uppercase tracking-[0.18em] text-hex-bronze">
                {data.username} ·{" "}
                {data.linked_player_name ?? "No linked player"}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="border-2 border-hex-border px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-bronze transition-colors hover:border-hex-white hover:text-hex-white"
          >
            Close
          </button>
        </div>

        <div className="px-5 py-4">
          {isLoading && (
            <p className="font-mono text-sm text-hex-bronze">
              Loading portfolio...
            </p>
          )}

          {isError && (
            <p className="font-mono text-sm text-hex-zaun">{error.message}</p>
          )}

          {data && (
            <div className="space-y-5">
              <div className="grid gap-3 md:grid-cols-4">
                {[
                  { label: "Role", value: data.role },
                  {
                    label: "Joined",
                    value: formatLocalDateTime(data.created_at),
                  },
                  {
                    label: "Onboarding",
                    value: data.onboarding_complete ? "Complete" : "Pending",
                  },
                  {
                    label: "Linked Player",
                    value: data.linked_player_name ?? "None",
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

              <div className="grid gap-3 md:grid-cols-4">
                {[
                  { label: "Balance", value: data.portfolio.balance },
                  { label: "Holdings", value: data.portfolio.holdings_value },
                  { label: "Gamba", value: data.portfolio.active_gamba_value },
                  { label: "Net Worth", value: data.portfolio.total_value },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="border border-hex-border px-4 py-3"
                  >
                    <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-hex-bronze">
                      {item.label}
                    </div>
                    <div className="mt-1 font-mono text-lg font-bold text-hex-gold">
                      {formatAmount(item.value)} P
                    </div>
                  </div>
                ))}
              </div>

              <div className="overflow-x-auto border border-hex-border">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-hex-border text-left">
                      <th className="px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                        Player
                      </th>
                      <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                        Qty
                      </th>
                      <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                        Cost Basis
                      </th>
                      <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                        Market Value
                      </th>
                      <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                        Unrealized P/L
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.portfolio.holdings.map((holding) => (
                      <tr
                        key={holding.player_id}
                        className="border-b border-hex-border/50"
                      >
                        <td className="px-4 py-2.5 font-mono text-sm text-hex-white">
                          {holding.player_name}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-sm text-hex-bronze">
                          {holding.quantity}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-sm text-hex-bronze">
                          {formatAmount(holding.cost_basis)}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-sm font-bold text-hex-gold">
                          {formatAmount(holding.market_value)}
                        </td>
                        <td
                          className={`px-4 py-2.5 text-right font-mono text-sm font-bold ${
                            holding.unrealized_pnl > 0
                              ? "text-emerald-400"
                              : holding.unrealized_pnl < 0
                                ? "text-red-400"
                                : "text-hex-bronze"
                          }`}
                        >
                          {holding.unrealized_pnl > 0 ? "+" : ""}
                          {formatAmount(holding.unrealized_pnl)}
                        </td>
                      </tr>
                    ))}
                    {data.portfolio.holdings.length === 0 && (
                      <tr>
                        <td
                          colSpan={5}
                          className="px-4 py-6 text-center font-mono text-sm text-hex-bronze"
                        >
                          No holdings for this user.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
