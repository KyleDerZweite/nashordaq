import type { HoldingResponse } from "../types";
import { formatAmount } from "../utils/format";

interface Props {
  holdings: HoldingResponse[];
  balance: number;
}

export default function Portfolio({ holdings, balance }: Props) {
  const holdingsTotal = holdings.reduce((s, h) => s + h.market_value, 0);
  const totalValue = balance + holdingsTotal;

  return (
    <section className="border-2 border-hex-gold-dim bg-hex-panel">
      <div className="border-b-2 border-hex-gold-dim px-5 py-3">
        <h2 className="font-serif text-xl font-bold text-hex-gold">
          Portfolio
        </h2>
      </div>

      {/* Summary numbers */}
      <div className="grid grid-cols-3 divide-x-2 divide-hex-border border-b-2 border-hex-border">
        {[
          { label: "Cash", value: balance },
          { label: "Holdings", value: holdingsTotal },
          { label: "Total", value: totalValue },
        ].map((item) => (
          <div key={item.label} className="px-4 py-3 text-center">
            <span className="block text-xs uppercase tracking-wider text-hex-bronze">
              {item.label}
            </span>
            <span className="font-mono text-lg font-bold text-hex-gold">
              {formatAmount(item.value)}
            </span>
          </div>
        ))}
      </div>

      {/* Holdings table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b-2 border-hex-border text-left">
              <th className="px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                Player
              </th>
              <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                Qty
              </th>
              <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                Buy
              </th>
              <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                Current
              </th>
              <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                Value
              </th>
              <th className="px-4 py-2 text-right font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze">
                P/L
              </th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <tr
                key={h.player_id}
                className="border-b border-hex-border/50 transition-colors hover:bg-hex-bg-alt"
              >
                <td className="px-4 py-2.5 font-mono text-sm font-medium text-hex-white">
                  {h.player_name}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-sm text-hex-bronze">
                  {h.quantity}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-sm text-hex-gold">
                  {formatAmount(h.average_buy_price)}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-sm text-hex-gold">
                  {formatAmount(h.current_price)}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-sm font-bold text-hex-magic">
                  {formatAmount(h.market_value)}
                </td>
                <td
                  className={`px-4 py-2.5 text-right font-mono text-sm font-bold ${
                    h.unrealized_pnl > 0
                      ? "text-emerald-400"
                      : h.unrealized_pnl < 0
                        ? "text-red-400"
                        : "text-hex-bronze"
                  }`}
                >
                  {h.unrealized_pnl > 0 ? "+" : ""}
                  {formatAmount(h.unrealized_pnl)}
                  <span className="ml-1 text-xs opacity-80">
                    ({h.unrealized_pnl > 0 ? "+" : ""}
                    {formatAmount(h.unrealized_pnl_pct)}%)
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
