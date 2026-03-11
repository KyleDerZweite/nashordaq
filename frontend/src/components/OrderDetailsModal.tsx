import { useOrderDetail } from "../api";
import {
  formatAmount,
  formatLocalDateTime,
  formatQuantity,
} from "../utils/format";

interface Props {
  orderId: number;
  onClose: () => void;
}

function adjustmentLabel(reason: string | null): string {
  if (reason === "HOLD_DURATION") {
    return "Hold Penalty / Benefit";
  }
  if (reason === "GAMBA_MULTIPLIER") {
    return "Gamba Adjustment";
  }
  return "Adjustment";
}

export default function OrderDetailsModal({ orderId, onClose }: Props) {
  const { data: order, isLoading, isError, error } = useOrderDetail(orderId);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-hex-bg/80"
      onClick={onClose}
    >
      <section
        className="w-full max-w-2xl border-4 border-hex-gold bg-hex-panel shadow-brutal-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b-4 border-hex-gold px-5 py-3">
          <div>
            <h2 className="font-serif text-xl font-bold text-hex-gold">
              Order Details
            </h2>
            <p className="mt-1 font-mono text-xs uppercase tracking-[0.18em] text-hex-bronze">
              #{orderId}
            </p>
          </div>
          <button
            onClick={onClose}
            className="border-2 border-hex-border px-4 py-3 font-mono text-xs font-bold uppercase tracking-[0.18em] text-hex-bronze transition-colors hover:border-hex-white hover:text-hex-white"
          >
            Close
          </button>
        </div>

        <div className="px-5 py-4">
          {isLoading && (
            <p className="font-mono text-sm text-hex-bronze">
              Loading order details...
            </p>
          )}

          {isError && (
            <p className="font-mono text-sm text-hex-zaun">{error.message}</p>
          )}

          {order && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {[
                  { label: "Stock", value: order.player_name },
                  { label: "Side", value: order.side },
                  { label: "Qty", value: formatQuantity(order.quantity) },
                  { label: "Source", value: order.source },
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

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2 border border-hex-border px-4 py-3">
                  <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-hex-gold">
                    Timing
                  </h3>
                  <p className="font-mono text-xs text-hex-bronze">
                    Created: {formatLocalDateTime(order.created_at)}
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Executed:{" "}
                    {order.executed_at
                      ? formatLocalDateTime(order.executed_at)
                      : "--"}
                  </p>
                </div>

                <div className="space-y-2 border border-hex-border px-4 py-3">
                  <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-hex-gold">
                    Values
                  </h3>
                  <p className="font-mono text-xs text-hex-bronze">
                    Final execution price:{" "}
                    {order.execution_price != null
                      ? `${formatAmount(order.execution_price)} P`
                      : "--"}
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Final total:{" "}
                    {order.total_value != null
                      ? `${formatAmount(order.total_value)} P`
                      : "--"}
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Entry value:{" "}
                    {order.entry_total_value != null
                      ? `${formatAmount(order.entry_total_value)} P`
                      : "--"}
                  </p>
                  <p className="font-mono text-xs text-hex-bronze">
                    Market exit value:{" "}
                    {order.gross_total_value != null
                      ? `${formatAmount(order.gross_total_value)} P`
                      : "--"}
                  </p>
                </div>
              </div>

              <div className="border border-hex-border px-4 py-3">
                <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-hex-gold">
                  Adjustment
                </h3>
                <div className="mt-2 grid gap-2 md:grid-cols-2">
                  <p className="font-mono text-xs text-hex-bronze">
                    {adjustmentLabel(order.adjustment_reason)}
                  </p>
                  <p
                    className={`text-right font-mono text-sm font-bold ${
                      (order.adjustment_value ?? 0) > 0
                        ? "text-emerald-400"
                        : (order.adjustment_value ?? 0) < 0
                          ? "text-red-400"
                          : "text-hex-bronze"
                    }`}
                  >
                    {order.adjustment_value == null
                      ? "--"
                      : `${order.adjustment_value > 0 ? "+" : ""}${formatAmount(order.adjustment_value)} P`}
                  </p>
                </div>
                {order.adjustment_reason == null && (
                  <p className="mt-2 font-mono text-xs text-hex-bronze">
                    No additional hold or strategy modifier was applied to this
                    order.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
