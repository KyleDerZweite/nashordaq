import {
  useId,
  useMemo,
  useRef,
  useState,
  type PointerEvent,
  type ReactNode,
} from "react";
import {
  formatLocalDateShort,
  formatLocalDateTime,
  parseBackendUtcTimestamp,
} from "../utils/format";

const CHART_WIDTH = 900;
const CHART_HEIGHT = 360;
const PADDING_LEFT = 92;
const PADDING_RIGHT = 28;
const PADDING_TOP = 28;
const PADDING_BOTTOM = 58;
const GRID_STEPS = 4;

type MetaValue = string | number | boolean | null | undefined;

export interface TimeSeriesChartDatum {
  id: string;
  timestamp: string;
  values: Record<string, number>;
  meta?: Record<string, MetaValue>;
}

export interface TimeSeriesChartSeries {
  key: string;
  label: string;
  color: string;
  dashArray?: string;
  strokeWidth?: number;
  fillOpacity?: number;
  formatValue?: (value: number) => string;
}

interface TimeSeriesChartProps {
  data: TimeSeriesChartDatum[];
  series: TimeSeriesChartSeries[];
  className?: string;
  emptyMessage?: string;
  formatAxisValue?: (value: number) => string;
  tooltipTitleFormatter?: (timestamp: string) => string;
  xTickFormatter?: (timestamp: string) => string;
  renderTooltipDetails?: (datum: TimeSeriesChartDatum) => ReactNode;
}

interface ChartPoint {
  datum: TimeSeriesChartDatum;
  x: number;
  yByKey: Record<string, number>;
}

interface ChartGeometry {
  baselineY: number;
  tickValues: Array<{ value: number; y: number }>;
  xTickIndexes: number[];
  points: ChartPoint[];
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function getNearestPointIndex(points: ChartPoint[], x: number): number {
  let nearestIndex = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;

  points.forEach((point, index) => {
    const distance = Math.abs(point.x - x);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = index;
    }
  });

  return nearestIndex;
}

function buildLinePath(points: ChartPoint[], seriesKey: string): string {
  return points
    .map((point, index) => {
      const y = point.yByKey[seriesKey];
      return `${index === 0 ? "M" : "L"}${point.x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function buildAreaPath(
  points: ChartPoint[],
  seriesKey: string,
  baselineY: number,
): string {
  if (points.length === 0) {
    return "";
  }

  const linePath = buildLinePath(points, seriesKey);
  const lastPoint = points[points.length - 1];
  return `${linePath} L${lastPoint.x.toFixed(2)} ${baselineY.toFixed(2)} L${points[0].x.toFixed(2)} ${baselineY.toFixed(2)} Z`;
}

function createChartGeometry(
  data: TimeSeriesChartDatum[],
  series: TimeSeriesChartSeries[],
): ChartGeometry | null {
  if (data.length === 0 || series.length === 0) {
    return null;
  }

  const values = series.flatMap((item) =>
    data.map((datum) => datum.values[item.key]).filter(Number.isFinite),
  );
  if (values.length === 0) {
    return null;
  }

  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const rawRange = rawMax - rawMin;
  const padding =
    rawRange === 0
      ? Math.max(1, Math.abs(rawMax) * 0.08, 0.5)
      : rawRange * 0.08;
  const minValue = rawMin - padding;
  const maxValue = rawMax + padding;
  const valueRange = Math.max(1, maxValue - minValue);
  const usableWidth = CHART_WIDTH - PADDING_LEFT - PADDING_RIGHT;
  const usableHeight = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const timestamps = data.map((datum) =>
    parseBackendUtcTimestamp(datum.timestamp).getTime(),
  );
  const minTime = Math.min(...timestamps);
  const maxTime = Math.max(...timestamps);
  const timeRange = Math.max(1, maxTime - minTime);
  const baselineY = CHART_HEIGHT - PADDING_BOTTOM;

  const points = data.map((datum, index) => {
    const timestamp = timestamps[index];
    const x =
      data.length === 1
        ? CHART_WIDTH / 2
        : PADDING_LEFT + ((timestamp - minTime) / timeRange) * usableWidth;
    const yByKey = Object.fromEntries(
      series.map((item) => {
        const value = datum.values[item.key];
        const y = baselineY - ((value - minValue) / valueRange) * usableHeight;
        return [item.key, y];
      }),
    );

    return { datum, x, yByKey };
  });

  const tickValues = Array.from({ length: GRID_STEPS + 1 }, (_, index) => {
    const ratio = index / GRID_STEPS;
    const value = maxValue - valueRange * ratio;
    const y = PADDING_TOP + usableHeight * ratio;
    return { value, y };
  });

  const xTickIndexes = Array.from(
    new Set(
      [0, 0.25, 0.5, 0.75, 1]
        .map((step) => Math.round((data.length - 1) * step))
        .filter((index) => index >= 0 && index < data.length),
    ),
  );

  return {
    baselineY,
    tickValues,
    xTickIndexes,
    points,
  };
}

function getPlotMetrics(svgRect: DOMRect) {
  const svgAspect = CHART_WIDTH / CHART_HEIGHT;
  const elemAspect = svgRect.width / svgRect.height;
  if (elemAspect > svgAspect) {
    const plotWidth = svgRect.height * svgAspect;
    return {
      plotWidth,
      plotHeight: svgRect.height,
      offsetX: (svgRect.width - plotWidth) / 2,
      offsetY: 0,
    };
  }
  const plotHeight = svgRect.width / svgAspect;
  return {
    plotWidth: svgRect.width,
    plotHeight,
    offsetX: 0,
    offsetY: (svgRect.height - plotHeight) / 2,
  };
}

export default function TimeSeriesChart({
  data,
  series,
  className,
  emptyMessage = "Not enough data to render this chart yet.",
  formatAxisValue,
  tooltipTitleFormatter = formatLocalDateTime,
  xTickFormatter = formatLocalDateShort,
  renderTooltipDetails,
}: TimeSeriesChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const gradientId = useId().replace(/:/g, "");
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltipState, setTooltipState] = useState<{
    x: number;
    y: number;
    flipX: boolean;
    flipY: boolean;
  } | null>(null);

  const geometry = useMemo(
    () => createChartGeometry(data, series),
    [data, series],
  );

  const activePoint =
    geometry && hoveredIndex !== null
      ? geometry.points[clamp(hoveredIndex, 0, geometry.points.length - 1)]
      : null;

  function getSvgX(event: PointerEvent<SVGSVGElement>): number {
    const rect = event.currentTarget.getBoundingClientRect();
    const { plotWidth, offsetX } = getPlotMetrics(rect);
    const relativeX =
      ((event.clientX - rect.left - offsetX) / plotWidth) * CHART_WIDTH;
    return clamp(relativeX, PADDING_LEFT, CHART_WIDTH - PADDING_RIGHT);
  }

  function updateHoverState(event: PointerEvent<SVGSVGElement>) {
    if (!geometry) {
      return;
    }

    const nextHoveredIndex = getNearestPointIndex(
      geometry.points,
      getSvgX(event),
    );
    setHoveredIndex(nextHoveredIndex);

    const point =
      geometry.points[clamp(nextHoveredIndex, 0, geometry.points.length - 1)];
    const anchorY = Math.min(...series.map((item) => point.yByKey[item.key]));
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const svgRect = event.currentTarget.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const metrics = getPlotMetrics(svgRect);
    setTooltipState({
      x:
        svgRect.left -
        containerRect.left +
        metrics.offsetX +
        (point.x / CHART_WIDTH) * metrics.plotWidth,
      y:
        svgRect.top -
        containerRect.top +
        metrics.offsetY +
        (anchorY / CHART_HEIGHT) * metrics.plotHeight,
      flipX: point.x > CHART_WIDTH * 0.7,
      flipY: anchorY < CHART_HEIGHT * 0.35,
    });
  }

  function handlePointerLeave() {
    setHoveredIndex(null);
    setTooltipState(null);
  }

  if (data.length < 2 || !geometry) {
    return (
      <div className="flex h-80 items-center justify-center border border-dashed border-hex-border bg-hex-bg text-center font-mono text-sm text-hex-bronze">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative border border-hex-border/70 bg-hex-bg-alt ${className ?? ""}`}
    >
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        className="h-[22rem] w-full select-none"
        onPointerMove={updateHoverState}
        onPointerLeave={handlePointerLeave}
      >
        <defs>
          {series
            .filter((item) => item.fillOpacity)
            .map((item) => (
              <linearGradient
                key={item.key}
                id={`${gradientId}-${item.key}`}
                x1="0"
                x2="0"
                y1="0"
                y2="1"
              >
                <stop
                  offset="0%"
                  stopColor={item.color}
                  stopOpacity={item.fillOpacity}
                />
                <stop offset="100%" stopColor={item.color} stopOpacity="0.02" />
              </linearGradient>
            ))}
        </defs>

        <rect
          x="0"
          y="0"
          width={CHART_WIDTH}
          height={CHART_HEIGHT}
          fill="#0a1a32"
        />

        {geometry.tickValues.map((tick) => (
          <g key={`${tick.y}-${tick.value}`}>
            <line
              x1={PADDING_LEFT}
              x2={CHART_WIDTH - PADDING_RIGHT}
              y1={tick.y}
              y2={tick.y}
              stroke="rgba(160,155,140,0.16)"
              strokeDasharray="5 8"
            />
            <text
              x={PADDING_LEFT - 14}
              y={tick.y + 5}
              textAnchor="end"
              fill="#a09b8c"
              fontSize="14"
              fontFamily="JetBrains Mono, monospace"
            >
              {formatAxisValue
                ? formatAxisValue(tick.value)
                : tick.value.toFixed(2)}
            </text>
          </g>
        ))}

        {geometry.xTickIndexes.map((index) => {
          const point = geometry.points[index];
          return (
            <g key={`${point.datum.id}-tick`}>
              <line
                x1={point.x}
                x2={point.x}
                y1={PADDING_TOP}
                y2={geometry.baselineY}
                stroke="rgba(30,45,61,0.42)"
                strokeDasharray="2 8"
              />
              <text
                x={point.x}
                y={CHART_HEIGHT - 16}
                textAnchor="middle"
                fill="#a09b8c"
                fontSize="13"
                fontFamily="JetBrains Mono, monospace"
              >
                {xTickFormatter(point.datum.timestamp)}
              </text>
            </g>
          );
        })}

        {series
          .filter((item) => item.fillOpacity)
          .map((item) => (
            <path
              key={`${item.key}-fill`}
              d={buildAreaPath(geometry.points, item.key, geometry.baselineY)}
              fill={`url(#${gradientId}-${item.key})`}
            />
          ))}

        {series.map((item) => (
          <path
            key={item.key}
            d={buildLinePath(geometry.points, item.key)}
            fill="none"
            stroke={item.color}
            strokeWidth={item.strokeWidth ?? 3}
            strokeDasharray={item.dashArray}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}

        {activePoint && (
          <line
            x1={activePoint.x}
            x2={activePoint.x}
            y1={PADDING_TOP}
            y2={geometry.baselineY}
            stroke="rgba(200,170,110,0.4)"
            strokeDasharray="5 5"
          />
        )}

        {activePoint &&
          series.map((item) => (
            <circle
              key={`${item.key}-${activePoint.datum.id}`}
              cx={activePoint.x}
              cy={activePoint.yByKey[item.key]}
              r="4.5"
              fill="#091428"
              stroke={item.color}
              strokeWidth="2.5"
            />
          ))}
      </svg>

      {activePoint && tooltipState && (
        <div
          className="pointer-events-none absolute w-56 border-2 border-hex-gold/80 bg-hex-panel/97 px-4 py-3 shadow-brutal-sm"
          style={{
            left: `${tooltipState.x}px`,
            top: `${tooltipState.y}px`,
            transform: `translate(${tooltipState.flipX ? "calc(-100% - 14px)" : "14px"}, ${tooltipState.flipY ? "14px" : "calc(-100% - 14px)"})`,
          }}
        >
          <div className="font-mono text-[13px] uppercase tracking-[0.12em] text-hex-bronze">
            {tooltipTitleFormatter(activePoint.datum.timestamp)}
          </div>
          <div className="mt-3 space-y-2">
            {series.map((item) => {
              const value = activePoint.datum.values[item.key];
              return (
                <div
                  key={`${activePoint.datum.id}-${item.key}`}
                  className="flex items-start justify-between gap-4 font-mono text-sm text-hex-white"
                >
                  <span
                    className="uppercase tracking-[0.12em]"
                    style={{ color: item.color }}
                  >
                    {item.label}
                  </span>
                  <span>
                    {(
                      item.formatValue ??
                      formatAxisValue ??
                      ((nextValue: number) => nextValue.toFixed(2))
                    )(value)}
                  </span>
                </div>
              );
            })}
          </div>
          {renderTooltipDetails && (
            <div className="mt-3 border-t border-hex-border pt-3 font-mono text-[13px] leading-6 text-hex-bronze">
              {renderTooltipDetails(activePoint.datum)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
