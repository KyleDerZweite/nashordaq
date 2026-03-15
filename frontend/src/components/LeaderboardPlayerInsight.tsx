import { useLeaderboardPlayerPortfolio } from "../api";
import { useStreamerMode } from "../contexts/useStreamerMode";
import { getStreamerSafeName } from "../utils/streamerMode";
import { formatAmount } from "../utils/format";

interface Props {
  userId: number;
  displayName: string;
  gameName: string;
  totalValue: number;
  rank: number;
  onClose: () => void;
}

export default function LeaderboardPlayerInsight({
  userId,
  displayName,
  gameName,
  totalValue,
  rank,
  onClose,
}: Props) {
  const { isStreamerMode } = useStreamerMode();
  const { data: portfolio, isLoading } = useLeaderboardPlayerPortfolio(userId);

  const name = isStreamerMode
    ? getStreamerSafeName(gameName, displayName)
    : displayName;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/80 px-3 py-4 sm:px-4 sm:py-6"
      onClick={onClose}
    >
      <section
        className="relative flex max-h-[94vh] w-full max-w-2xl flex-col overflow-hidden border-4 border-hex-gold bg-hex-panel shadow-brutal-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b-4 border-hex-gold bg-hex-bg-alt px-4 py-4 sm:px-6 sm:py-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="mb-2 flex items-center gap-3">
                <span
                  className={`inline-block h-7 w-7 border-2 text-center text-xs leading-6 font-bold ${
                    rank === 1
                      ? "border-hex-gold bg-hex-gold text-hex-bg"
                      : rank === 2
                        ? "border-hex-bronze text-hex-bronze"
                        : rank === 3
                          ? "border-[#CD7F32] text-[#CD7F32]"
                          : "border-hex-border text-hex-border"
                  }`}
                >
                  {rank}
                </span>
                <span className="border border-hex-border px-2 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.24em] text-hex-bronze">
                  Portfolio
                </span>
              </div>
              <h2 className="font-serif text-2xl font-bold text-hex-gold">
                {name}
              </h2>
              <p className="mt-1 font-mono text-sm text-hex-bronze">
                Net worth: {formatAmount(totalValue)} P
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
          {isLoading && (
            <p className="py-8 text-center font-mono text-sm text-hex-bronze">
              Loading...
            </p>
          )}

          {portfolio && portfolio.holdings.length === 0 && (
            <p className="py-8 text-center font-mono text-sm text-hex-bronze">
              No holdings.
            </p>
          )}

          {portfolio && portfolio.holdings.length > 0 && (
            <div className="overflow-x-auto border-2 border-hex-border">
              <table className="w-full">
                <thead>
                  <tr className="border-b-2 border-hex-border bg-hex-bg-alt text-left">
                    {["Stock", "Qty", "Avg Buy", "Price", "Value", "P&L"].map(
                      (col, i) => (
                        <th
                          key={col}
                          className={`px-4 py-3 font-mono text-[11px] font-bold uppercase tracking-[0.18em] text-hex-bronze ${i > 0 ? "text-right" : ""}`}
                        >
                          {col}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {portfolio.holdings.map((h) => {
                    const pnlColor =
                      h.unrealized_pnl > 0
                        ? "text-hex-piltover"
                        : h.unrealized_pnl < 0
                          ? "text-hex-zaun"
                          : "text-hex-bronze";
                    return (
                      <tr
                        key={h.player_id}
                        className="border-b border-hex-border/50 transition-colors hover:bg-hex-bg-alt/80"
                      >
                        <td className="px-4 py-3 font-mono text-sm font-medium text-hex-white">
                          <span className="block truncate">
                            {isStreamerMode
                              ? getStreamerSafeName(
                                  h.player_game_name,
                                  h.player_name,
                                )
                              : h.player_name}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-sm text-hex-white">
                          {h.quantity}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-sm text-hex-bronze">
                          {formatAmount(h.average_buy_price)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-sm text-hex-white">
                          {formatAmount(h.current_price)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-sm text-hex-gold">
                          {formatAmount(h.market_value)}
                        </td>
                        <td
                          className={`px-4 py-3 text-right font-mono text-sm font-bold ${pnlColor}`}
                        >
                          {h.unrealized_pnl > 0 ? "+" : ""}
                          {formatAmount(h.unrealized_pnl)}
                          <span className="ml-1 text-[11px] font-normal">
                            ({h.unrealized_pnl_pct > 0 ? "+" : ""}
                            {h.unrealized_pnl_pct.toFixed(1)}%)
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
