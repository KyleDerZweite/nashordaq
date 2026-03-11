import { useMemo, useState } from "react";
import type { OrderResponse } from "../types";
import { useCancelOrder } from "../api";
import OrderDetailsModal from "./OrderDetailsModal";
import { formatAmount, formatQuantity } from "../utils/format";

interface Props {
  ownOrders: OrderResponse[];
  allOrders: OrderResponse[];
  defaultView?: OrderHistoryView;
}

type OrderHistoryView = "own" | "all";

export default function OrderHistory({
  ownOrders,
  allOrders,
  defaultView = "own",
}: Props) {
  const cancelOrder = useCancelOrder();
  const [view, setView] = useState<OrderHistoryView>(defaultView);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [filterQuery, setFilterQuery] = useState("");

  const orders = useMemo(
    () => (view === "own" ? ownOrders : allOrders),
    [allOrders, ownOrders, view],
  );

  const normalizedFilterQuery = filterQuery.trim().toLocaleLowerCase();
  const filteredOrders = useMemo(() => {
    if (normalizedFilterQuery.length === 0) {
      return orders;
    }

    return orders.filter((order) => {
      const stockMatch = order.player_name
        .toLocaleLowerCase()
        .includes(normalizedFilterQuery);
      const playerMatch = (order.user_name ?? "")
        .toLocaleLowerCase()
        .includes(normalizedFilterQuery);

      return stockMatch || playerMatch;
    });
  }, [normalizedFilterQuery, orders]);

  const showScrollbar = filteredOrders.length > 30;

  return (
    <section className="border-2 border-hex-gold-dim bg-hex-panel">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-hex-gold-dim px-5 py-3">
        <h2 className="font-serif text-xl font-bold text-hex-gold">
          Recent Orders
        </h2>
        <div className="flex flex-wrap items-center justify-end gap-3">
          <label className="flex items-center gap-2 border border-hex-border bg-hex-bg-alt px-3 py-1.5">
            <span className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-hex-bronze">
              Filter
            </span>
            <input
              type="text"
              value={filterQuery}
              onChange={(event) => setFilterQuery(event.target.value)}
              placeholder={view === "all" ? "Stock or player" : "Stock"}
              className="min-w-40 bg-transparent font-mono text-xs text-hex-white outline-none placeholder:text-hex-border"
            />
            {filterQuery && (
              <button
                type="button"
                onClick={() => setFilterQuery("")}
                className="font-mono text-xs font-bold uppercase tracking-wider text-hex-bronze transition-colors hover:text-hex-white"
              >
                Clear
              </button>
            )}
          </label>

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
            {filteredOrders.map((o) => (
              <tr
                key={o.id}
                className="cursor-pointer border-b border-hex-border/50 transition-colors hover:bg-hex-bg-alt"
                onClick={() => setSelectedOrderId(o.id)}
              >
                <td className="px-4 py-2.5 font-mono text-xs text-hex-bronze">
                  #{o.id}
                </td>
                <td className="px-4 py-2.5 font-mono text-sm text-hex-white">
                  {o.player_name}
                  {o.source === "GAMBA" && (
                    <span className="ml-2 inline-block border border-hex-gold-dim px-1.5 py-0.5 align-middle font-mono text-[10px] font-bold uppercase tracking-wider text-hex-gold">
                      Gamba
                    </span>
                  )}
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
                  {formatQuantity(o.quantity)}
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
                    o.source === "MANUAL" &&
                    (o.status === "PENDING" ||
                      (o.status === "EXECUTED" && o.side === "BUY")) && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          cancelOrder.mutate(o.id);
                        }}
                        disabled={cancelOrder.isPending}
                        className="font-mono text-xs font-bold text-hex-zaun transition-colors hover:text-hex-white"
                      >
                        {o.status === "PENDING" ? "Cancel" : "Revert"}
                      </button>
                    )}
                </td>
              </tr>
            ))}
            {filteredOrders.length === 0 && (
              <tr>
                <td
                  colSpan={view === "all" ? 8 : 7}
                  className="px-4 py-6 text-center font-mono text-sm text-hex-bronze"
                >
                  {orders.length === 0
                    ? view === "own"
                      ? "No own orders yet."
                      : "No recent market orders yet."
                    : "No orders match the current filter."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {cancelOrder.isError && (
        <p className="border-t border-hex-border/50 px-4 py-2 font-mono text-xs text-hex-zaun">
          {cancelOrder.error.message}
        </p>
      )}

      {selectedOrderId !== null && (
        <OrderDetailsModal
          orderId={selectedOrderId}
          onClose={() => setSelectedOrderId(null)}
        />
      )}
    </section>
  );
}
