export type ChartRange = 1 | 7 | 30 | "all";

export const CHART_RANGE_OPTIONS: Array<{ label: string; value: ChartRange }> =
  [
    { label: "1D", value: 1 },
    { label: "7D", value: 7 },
    { label: "30D", value: 30 },
    { label: "All", value: "all" },
  ];

export function filterItemsByRange<T>(
  items: T[],
  range: ChartRange,
  getTimestamp: (item: T) => string,
): T[] {
  if (range === "all" || items.length === 0) {
    return items;
  }

  const latestTime = new Date(getTimestamp(items[items.length - 1])).getTime();
  const cutoffTime = latestTime - range * 24 * 60 * 60 * 1000;
  const filtered = items.filter(
    (item) => new Date(getTimestamp(item)).getTime() >= cutoffTime,
  );

  return filtered.length > 0 ? filtered : items;
}
