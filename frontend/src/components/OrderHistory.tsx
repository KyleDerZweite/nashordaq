import type { OrderResponse } from "../types";

interface Props {
  orders: OrderResponse[];
}

export default function OrderHistory({ orders }: Props) {
  return (
    <section className="border-2 border-hex-gold-dim bg-hex-panel">
      <div className="border-b-2 border-hex-gold-dim px-5 py-3">
        <h2 className="font-serif text-xl font-bold text-hex-gold">
          Recent Orders
        </h2>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b-2 border-hex-border text-left">
              {["ID", "Player", "Side", "Qty", "Price", "Status"].map((col) => (
                <th
                  key={col}
                  className={`px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze ${
                    ["Qty", "Price"].includes(col) ? "text-right" : ""
                  }`}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr
                key={o.id}
                className="border-b border-hex-border/50 transition-colors hover:bg-hex-bg-alt"
              >
                <td className="px-4 py-2.5 font-mono text-xs text-hex-bronze">
                  #{o.id}
                </td>
                <td className="px-4 py-2.5 font-mono text-sm text-hex-white">
                  {o.player_name}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-block border-2 px-2 py-0.5 font-mono text-xs font-bold ${
                      o.side === "BUY"
                        ? "border-hex-magic text-hex-magic"
                        : "border-hex-zaun text-hex-zaun"
                    }`}
                  >
                    {o.side}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-sm text-hex-bronze">
                  {o.quantity}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-sm text-hex-gold">
                  {o.execution_price?.toFixed(2) ?? "--"}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-block border px-2 py-0.5 font-mono text-xs font-bold uppercase ${
                      o.status === "EXECUTED"
                        ? "border-hex-magic/50 text-hex-magic"
                        : o.status === "PENDING"
                          ? "border-hex-gold-dim text-hex-gold"
                          : "border-hex-zaun/50 text-hex-zaun"
                    }`}
                  >
                    {o.status}
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
