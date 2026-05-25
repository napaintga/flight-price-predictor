import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type {
  Ticket,
  TicketHistoryPoint,
  TicketLocalHistoryResponse
} from "../../../shared/api/types";
import { useI18n } from "../../../shared/i18n";
import { Card } from "../../../shared/ui/Card";
import { Spinner } from "../../../shared/ui/Spinner";
import { formatCurrency, formatDateTime } from "../../../shared/utils/format";

type TicketHistoryChartProps = {
  ticket?: Ticket;
  history?: TicketLocalHistoryResponse;
  isLoading?: boolean;
  isError?: boolean;
  showForecast: boolean;
  onToggleForecast: () => void;
  title?: string;
  subtitle?: string;
  allowForecastToggle?: boolean;
};

type ChartRow = {
  ts: string;
  actual?: number;
  forecast?: number;
  trend?: number;
  minPrice?: number;
  maxPrice?: number;
  sampleCount?: number;
  sourceDate?: string;
  sourceFile?: string;
  matchMode?: string;
  lower?: number;
  upper?: number;
};

type ForecastChartRow = {
  ts: string;
  actual?: number;
  forecast?: number;
  lower?: number;
  upper?: number;
};

const formatAxis = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
};

const buildTitle = (ticket?: Ticket) => {
  if (!ticket) return "-";
  if (ticket.origin && ticket.destination) {
    return `${ticket.originName ?? ticket.origin} -> ${ticket.destinationName ?? ticket.destination}`;
  }
  return ticket.flightId ?? "-";
};

const mergeChartData = (
  actual: TicketHistoryPoint[],
  forecast: TicketHistoryPoint[],
  showForecast: boolean
) => {
  const rows = new Map<string, ChartRow>();
  const upsert = (ts: string) => {
    const existing = rows.get(ts);
    if (existing) return existing;
    const next: ChartRow = { ts };
    rows.set(ts, next);
    return next;
  };

  actual.forEach((point) => {
    const row = upsert(point.ts);
    row.actual = point.price;
    row.minPrice = point.minPrice;
    row.maxPrice = point.maxPrice;
    row.sampleCount = point.sampleCount;
    row.sourceDate = point.sourceDate;
    row.sourceFile = point.sourceFile;
    row.matchMode = point.matchMode;
  });

  if (showForecast && actual.length > 0) {
    const lastActual = actual[actual.length - 1];
    upsert(lastActual.ts).forecast = lastActual.price;
    forecast.forEach((point) => {
      const row = upsert(point.ts);
      row.forecast = point.price;
      row.lower = point.lower;
      row.upper = point.upper;
    });
  }

  return Array.from(rows.values()).sort((left, right) =>
    left.ts.localeCompare(right.ts)
  );
};

const buildTrendData = (actual: TicketHistoryPoint[]): ChartRow[] => {
  if (actual.length === 0) return [];
  if (actual.length === 1) {
    return [{ ts: actual[0].ts, actual: actual[0].price, trend: actual[0].price }];
  }

  const firstDate = new Date(actual[0].ts).getTime();
  const points = actual.map((point, index) => {
    const date = new Date(point.ts).getTime();
    const x = Number.isNaN(date) ? index : (date - firstDate) / 86_400_000;
    return { x, point };
  });
  const xMean = points.reduce((sum, item) => sum + item.x, 0) / points.length;
  const yMean =
    points.reduce((sum, item) => sum + item.point.price, 0) / points.length;
  const denominator = points.reduce(
    (sum, item) => sum + (item.x - xMean) ** 2,
    0
  );
  const slope =
    denominator === 0
      ? 0
      : points.reduce(
          (sum, item) => sum + (item.x - xMean) * (item.point.price - yMean),
          0
        ) / denominator;
  const intercept = yMean - slope * xMean;

  return points.map(({ x, point }) => ({
    ts: point.ts,
    actual: point.price,
    trend: Math.max(intercept + slope * x, 1)
  }));
};

const buildForecastOnlyData = (
  actual: TicketHistoryPoint[],
  forecast: TicketHistoryPoint[]
): ForecastChartRow[] => {
  if (actual.length === 0 || forecast.length === 0) return [];
  const lastActual = actual[actual.length - 1];
  return [
    { ts: lastActual.ts, actual: lastActual.price, forecast: lastActual.price },
    ...forecast.map((point) => ({
      ts: point.ts,
      forecast: point.price,
      lower: point.lower,
      upper: point.upper
    }))
  ].sort((left, right) => left.ts.localeCompare(right.ts));
};

export const TicketHistoryChart = ({
  ticket,
  history,
  isLoading,
  isError,
  showForecast,
  onToggleForecast,
  title,
  subtitle,
  allowForecastToggle = true
}: TicketHistoryChartProps) => {
  const { t } = useI18n();
  const displayCurrency = history?.currency || ticket?.currency || "USD";
  const actual = history?.actual ?? [];
  const forecast = history?.forecast ?? [];
  const chartData = useMemo(
    () => mergeChartData(actual, forecast, showForecast),
    [actual, forecast, showForecast]
  );
  const trendData = useMemo(() => buildTrendData(actual), [actual]);
  const forecastOnlyData = useMemo(
    () => buildForecastOnlyData(actual, forecast),
    [actual, forecast]
  );

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold">
            {title ?? t("tickets.chart.title")}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {ticket
              ? `${buildTitle(ticket)} | ${subtitle ?? t("tickets.chart.subtitle")}`
              : t("tickets.chart.emptySelection")}
          </p>
        </div>
        {allowForecastToggle && (
          <button
            type="button"
            className="rounded-full border border-slate-200 px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:border-sky-300 hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-200"
            onClick={onToggleForecast}
            disabled={!history || forecast.length === 0}
          >
            {showForecast
              ? t("tickets.chart.forecast.hide")
              : t("tickets.chart.forecast.show")}
          </button>
        )}
      </div>

      {!ticket ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t("tickets.chart.emptySelection")}
        </p>
      ) : isLoading ? (
        <Spinner />
      ) : isError ? (
        <p className="text-sm text-red-500">{t("tickets.chart.error")}</p>
      ) : !history || actual.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t("tickets.chart.emptyData")}
        </p>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-slate-900/60">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                {t("tickets.chart.metric.latest")}
              </p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {formatCurrency(history.summary.latestPrice ?? undefined, displayCurrency)}
              </p>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-slate-900/60">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                {t("tickets.chart.metric.days")}
              </p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {history.summary.matchedDays}
              </p>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-slate-900/60">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                {t("tickets.chart.metric.range")}
              </p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {history.summary.minPrice !== null &&
                history.summary.minPrice !== undefined &&
                history.summary.maxPrice !== null &&
                history.summary.maxPrice !== undefined
                  ? `${formatCurrency(history.summary.minPrice, displayCurrency)} - ${formatCurrency(history.summary.maxPrice, displayCurrency)}`
                  : "-"}
              </p>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-3 dark:bg-slate-900/60">
              <p className="text-xs uppercase tracking-wide text-slate-500">
                {t("tickets.chart.metric.lastSeen")}
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
                {formatDateTime(history.summary.lastCapturedAt ?? undefined)}
              </p>
            </div>
          </div>

          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.18} />
                <XAxis dataKey="ts" tickFormatter={formatAxis} />
                <YAxis
                  tickFormatter={(value) =>
                    formatCurrency(Number(value), displayCurrency)
                  }
                />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload || payload.length === 0) return null;
                    const row = payload[0]?.payload as ChartRow | undefined;
                    return (
                      <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm shadow-lg dark:border-slate-700 dark:bg-slate-950">
                        <p className="font-semibold text-slate-900 dark:text-slate-100">
                          {formatDateTime(label)}
                        </p>
                        {row?.actual !== undefined && (
                          <p className="mt-2 text-slate-700 dark:text-slate-200">
                            {t("tickets.chart.legend.actual")}:{" "}
                            {formatCurrency(row.actual, displayCurrency)}
                          </p>
                        )}
                        {row?.forecast !== undefined && showForecast && (
                          <p className="text-slate-700 dark:text-slate-200">
                            {t("tickets.chart.legend.forecast")}:{" "}
                            {formatCurrency(row.forecast, displayCurrency)}
                          </p>
                        )}
                        {row?.minPrice !== undefined && row?.maxPrice !== undefined && (
                          <p className="text-slate-500 dark:text-slate-400">
                            {t("tickets.chart.tooltip.spread")}:{" "}
                            {formatCurrency(row.minPrice, displayCurrency)} -{" "}
                            {formatCurrency(row.maxPrice, displayCurrency)}
                          </p>
                        )}
                        {row?.sampleCount !== undefined && (
                          <p className="text-slate-500 dark:text-slate-400">
                            {t("tickets.chart.tooltip.samples", {
                              count: row.sampleCount
                            })}
                          </p>
                        )}
                        {row?.sourceDate && (
                          <p className="text-slate-500 dark:text-slate-400">
                            {t("tickets.chart.tooltip.sourceDay")}: {row.sourceDate}
                          </p>
                        )}
                        {row?.sourceFile && (
                          <p className="break-all text-slate-500 dark:text-slate-400">
                            {t("tickets.chart.tooltip.sourceFile")}: {row.sourceFile}
                          </p>
                        )}
                        {row?.matchMode && (
                          <p className="text-slate-500 dark:text-slate-400">
                            {t("tickets.chart.tooltip.match")}: {row.matchMode}
                          </p>
                        )}
                      </div>
                    );
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="actual"
                  name={t("tickets.chart.legend.actual")}
                  stroke="#0f766e"
                  strokeWidth={3}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
                {showForecast && forecast.length > 0 && (
                  <Line
                    type="monotone"
                    dataKey="forecast"
                    name={t("tickets.chart.legend.forecast")}
                    stroke="#f59e0b"
                    strokeWidth={2}
                    strokeDasharray="6 4"
                    dot={{ r: 2 }}
                    activeDot={{ r: 4 }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="min-h-72 rounded-md border border-slate-200 p-4 dark:border-slate-800">
              <div className="mb-3">
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {t("tickets.chart.extra.trend.title")}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {t("tickets.chart.extra.trend.subtitle")}
                </p>
              </div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.16} />
                    <XAxis dataKey="ts" tickFormatter={formatAxis} />
                    <YAxis
                      tickFormatter={(value) =>
                        formatCurrency(Number(value), displayCurrency)
                      }
                    />
                    <Tooltip
                      labelFormatter={(label) => formatDateTime(label)}
                      formatter={(value: number, name: string) => [
                        formatCurrency(value, displayCurrency),
                        name
                      ]}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="actual"
                      name={t("tickets.chart.legend.actual")}
                      stroke="#0f766e"
                      strokeWidth={2}
                      dot={{ r: 2 }}
                    />
                    <Line
                      type="linear"
                      dataKey="trend"
                      name={t("tickets.chart.extra.trend.legend")}
                      stroke="#7c3aed"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="min-h-72 rounded-md border border-slate-200 p-4 dark:border-slate-800">
              <div className="mb-3">
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {t("tickets.chart.extra.forecast.title")}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {t("tickets.chart.extra.forecast.subtitle")}
                </p>
              </div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={forecastOnlyData}>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.16} />
                    <XAxis dataKey="ts" tickFormatter={formatAxis} />
                    <YAxis
                      tickFormatter={(value) =>
                        formatCurrency(Number(value), displayCurrency)
                      }
                    />
                    <Tooltip
                      labelFormatter={(label) => formatDateTime(label)}
                      formatter={(value: number, name: string) => [
                        formatCurrency(value, displayCurrency),
                        name
                      ]}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="actual"
                      name={t("tickets.chart.legend.actual")}
                      stroke="#0f766e"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="forecast"
                      name={t("tickets.chart.legend.forecast")}
                      stroke="#f59e0b"
                      strokeWidth={3}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="min-h-72 rounded-md border border-slate-200 p-4 dark:border-slate-800">
              <div className="mb-3">
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {t("tickets.chart.extra.range.title")}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {t("tickets.chart.extra.range.subtitle")}
                </p>
              </div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={forecastOnlyData}>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.16} />
                    <XAxis dataKey="ts" tickFormatter={formatAxis} />
                    <YAxis
                      tickFormatter={(value) =>
                        formatCurrency(Number(value), displayCurrency)
                      }
                    />
                    <Tooltip
                      labelFormatter={(label) => formatDateTime(label)}
                      formatter={(value: number, name: string) => [
                        formatCurrency(value, displayCurrency),
                        name
                      ]}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="forecast"
                      name={t("tickets.chart.legend.forecast")}
                      stroke="#2563eb"
                      strokeWidth={3}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="lower"
                      name={t("tickets.chart.extra.range.lower")}
                      stroke="#94a3b8"
                      strokeDasharray="5 4"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="upper"
                      name={t("tickets.chart.extra.range.upper")}
                      stroke="#94a3b8"
                      strokeDasharray="5 4"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="space-y-1 text-sm text-slate-500 dark:text-slate-400">
            <p>
              {t("tickets.chart.strategy")}: {history.matching.strategy}
            </p>
            <p>
              {t("tickets.chart.days")}: {history.summary.availableDays.join(", ") || "-"}
            </p>
            <p>
              {t("tickets.chart.forecast.meta")}:{" "}
              {history.forecastMeta
                ? `${history.forecastMeta.modelName ?? history.forecastMeta.source} | ${formatDateTime(history.forecastMeta.generatedAt)}`
                : t("prediction.na")}
            </p>
          </div>
        </>
      )}
    </Card>
  );
};
