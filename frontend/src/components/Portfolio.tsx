import { useEffect, useEffectEvent, useRef, useState } from "react";

import { useStreamerMode } from "../contexts/useStreamerMode";
import type { PortfolioResponse } from "../types";
import { getStreamerSafeName } from "../utils/streamerMode";
import { formatAmount } from "../utils/format";

const SUMMARY_GRID_INTERNAL_BORDERS = 6;
const SUMMARY_LAYOUT_OVERFLOW_BUFFER = 6;

function getSummaryCellBorderClass(index: number, useTwoColumnLayout: boolean) {
  if (!useTwoColumnLayout) {
    return index === 0 ? "" : "border-l-2 border-hex-border";
  }

  const borders = [];
  if (index % 2 === 1) {
    borders.push("border-l-2");
  }
  if (index >= 2) {
    borders.push("border-t-2");
  }

  return borders.length > 0 ? `${borders.join(" ")} border-hex-border` : "";
}

interface Props {
  portfolio?: PortfolioResponse | null;
  onOpenInsights?: () => void;
}

export default function Portfolio({ portfolio, onOpenInsights }: Props) {
  const { isStreamerMode } = useStreamerMode();
  const holdings = portfolio?.holdings ?? [];
  const balance = portfolio?.balance ?? 0;
  const holdingsValue = portfolio?.holdings_value ?? 0;
  const gambaValue = portfolio?.active_gamba_value ?? 0;
  const totalValue =
    portfolio?.total_value ?? balance + holdingsValue + gambaValue;
  const summaryItems = [
    { label: "Poros", value: balance },
    { label: "Holdings", value: holdingsValue },
    { label: "Gamba", value: gambaValue },
    { label: "Total", value: totalValue },
  ];
  const summaryGridRef = useRef<HTMLDivElement | null>(null);
  const summaryCellRefs = useRef<Array<HTMLDivElement | null>>([]);
  const summaryContentRefs = useRef<Array<HTMLDivElement | null>>([]);
  const [useTwoColumnLayout, setUseTwoColumnLayout] = useState(false);

  const syncSummaryLayout = useEffectEvent(() => {
    const summaryGrid = summaryGridRef.current;
    if (!summaryGrid) {
      return;
    }

    const firstCell = summaryCellRefs.current[0];
    const cellStyles = firstCell ? window.getComputedStyle(firstCell) : null;
    const horizontalPadding = cellStyles
      ? parseFloat(cellStyles.paddingLeft) + parseFloat(cellStyles.paddingRight)
      : 32;
    const availableWidthPerStat =
      (summaryGrid.clientWidth - SUMMARY_GRID_INTERNAL_BORDERS) / 4 -
      horizontalPadding;
    const shouldUseTwoColumnLayout = summaryContentRefs.current.some((node) => {
      if (!node) {
        return false;
      }

      const renderedWidth = node.getBoundingClientRect().width;
      return (
        renderedWidth > availableWidthPerStat + SUMMARY_LAYOUT_OVERFLOW_BUFFER
      );
    });

    setUseTwoColumnLayout((current) =>
      current === shouldUseTwoColumnLayout ? current : shouldUseTwoColumnLayout,
    );
  });

  useEffect(() => {
    syncSummaryLayout();

    const summaryGrid = summaryGridRef.current;
    if (!summaryGrid) {
      return;
    }

    const resizeObserver = new ResizeObserver(() => {
      syncSummaryLayout();
    });

    resizeObserver.observe(summaryGrid);
    summaryCellRefs.current.forEach((node) => {
      if (node) {
        resizeObserver.observe(node);
      }
    });
    summaryContentRefs.current.forEach((node) => {
      if (node) {
        resizeObserver.observe(node);
      }
    });

    return () => {
      resizeObserver.disconnect();
    };
  }, [balance, holdingsValue, gambaValue, totalValue]);

  function handleKeyDown(event: React.KeyboardEvent<HTMLElement>) {
    if (!onOpenInsights) {
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpenInsights();
    }
  }

  return (
    <section
      className={`border-2 border-hex-gold-dim bg-hex-panel shadow-brutal-sm outline-none transition-colors ${
        onOpenInsights
          ? "hover:border-hex-gold focus-visible:border-hex-gold"
          : ""
      }`}
      onClick={onOpenInsights}
      onKeyDown={handleKeyDown}
      role={onOpenInsights ? "button" : undefined}
      tabIndex={onOpenInsights ? 0 : undefined}
      aria-label={onOpenInsights ? "Open portfolio insights" : undefined}
    >
      <div className="border-b-2 border-hex-gold-dim px-5 py-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-serif text-xl font-bold text-hex-gold">
            Porofolio
          </h2>
          {onOpenInsights && (
            <span className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-hex-bronze">
              Open Insights
            </span>
          )}
        </div>
      </div>

      {/* Summary numbers */}
      <div
        ref={summaryGridRef}
        className={`grid border-b-2 border-hex-border ${
          useTwoColumnLayout ? "grid-cols-2" : "grid-cols-4"
        }`}
      >
        {summaryItems.map((item, index) => (
          <div
            key={item.label}
            ref={(node) => {
              summaryCellRefs.current[index] = node;
            }}
            className={`px-4 py-3 text-center ${getSummaryCellBorderClass(index, useTwoColumnLayout)}`}
          >
            <div
              ref={(node) => {
                summaryContentRefs.current[index] = node;
              }}
              className="inline-flex flex-col items-center"
            >
              <span className="block whitespace-nowrap text-xs uppercase tracking-wider text-hex-bronze">
                {item.label}
              </span>
              <span className="whitespace-nowrap font-mono text-lg font-bold text-hex-gold">
                {formatAmount(item.value)}
              </span>
            </div>
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
                  {isStreamerMode
                    ? getStreamerSafeName(h.player_game_name, h.player_name)
                    : h.player_name}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-sm text-hex-bronze">
                  {h.quantity}
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
