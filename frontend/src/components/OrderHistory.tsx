import { useMemo, useState } from "react";
import type { OrderResponse } from "../types";
import { useCancelOrder } from "../api";
import { formatAmount } from "../utils/format";

interface Props {
  ownOrders: OrderResponse[];
  allOrders: OrderResponse[];
}

type OrderHistoryView = "own" | "all";

export default function OrderHistory({ ownOrders, allOrders }: Props) {
  const cancelOrder = useCancelOrder();
  const [view, setView] = useState<OrderHistoryView>("own");

  const orders = useMemo(
    () => (view === "own" ? ownOrders : allOrders),
    [allOrders, ownOrders, view],
  );

  const showScrollbar = orders.length > 30;

  return (
    <section className="border-2 border-hex-gold-dim bg-hex-panel">
      <div className="flex items-center justify-between border-b-2 border-hex-gold-dim px-5 py-3">
        <h2 className="font-serif text-xl font-bold text-hex-gold">
          Recent Orders
        </h2>
        <button
          type="button"
          onClick={() =>
            setView((current) => (current === "own" ? "all" : "own"))
          }
          className="border border-hex-gold px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider text-hex-gold transition-colors hover:bg-hex-gold hover:text-hex-bg"
        >
          {view === "own" ? "Show All" : "Show Own"}
        </button>
      </div>

      <div
        className={`overflow-x-auto ${showScrollbar ? "max-h-[48rem] overflow-y-auto" : ""}`}
      >
        <table className="w-full">
          <thead>
            <tr className="border-b-2 border-hex-border text-left">
              {[
                "ID",
                "Stock",
                ...(view === "all" ? ["Player"] : []),
                "Side",
                "Qty",
                "Price",
                "Status",
                "",
              ].map((col) => (
                <th
                  key={col || "action"}
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
                {view === "all" && (
                  <td className="px-4 py-2.5 font-mono text-sm text-hex-bronze">
                    {o.user_name ?? "--"}
                  </td>
                )}
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
                  {o.execution_price != null
                    ? formatAmount(o.execution_price)
                    : "--"}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-block border px-2 py-0.5 font-mono text-xs font-bold uppercase ${
                      o.status === "EXECUTED"
                        ? "border-hex-magic/50 text-hex-magic"
                        : o.status === "PENDING"
                          ? "border-hex-gold-dim text-hex-gold"
                          : o.status === "REVERTED"
                            ? "border-hex-bronze/50 text-hex-bronze"
                            : "border-hex-zaun/50 text-hex-zaun"
                    }`}
                  >
                    {o.status}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  {view === "own" &&
                    (o.status === "PENDING" ||
                      (o.status === "EXECUTED" && o.side === "BUY")) && (
                      <button
                        onClick={() => cancelOrder.mutate(o.id)}
                        disabled={cancelOrder.isPending}
                        className="font-mono text-xs font-bold text-hex-zaun transition-colors hover:text-hex-white"
                      >
                        {o.status === "PENDING" ? "Cancel" : "Revert"}
                      </button>
                    )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {cancelOrder.isError && (
        <p className="border-t border-hex-border/50 px-4 py-2 font-mono text-xs text-hex-zaun">
          {cancelOrder.error.message}
        </p>
      )}
    </section>
  );
}
