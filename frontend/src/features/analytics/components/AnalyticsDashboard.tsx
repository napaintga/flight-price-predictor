import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type {
  AnalyticsDashboard as AnalyticsDashboardData,
  AnalyticsErrorGroup,
  AnalyticsModelRow
} from "../../../shared/api/types";
import { Card } from "../../../shared/ui/Card";
import { formatCurrency } from "../../../shared/utils/format";
import { useI18n } from "../../../shared/i18n";

type AnalyticsDashboardProps = {
  data?: AnalyticsDashboardData;
};

const COLORS = ["#0f766e", "#2563eb", "#ca8a04", "#dc2626", "#7c3aed"];

const formatNumber = (value?: number | null, digits = 0) => {
  if (value === undefined || value === null) return "-";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits
  }).format(value);
};

const formatPct = (value?: number | null) =>
  value === undefined || value === null ? "-" : `${formatNumber(value, 1)}%`;

const formatMetric = (value?: number | null) =>
  value === undefined || value === null ? "-" : formatNumber(value, 1);

const metricTooltip = (value: unknown, name: string) => [
  typeof value === "number" ? formatNumber(value, 1) : String(value ?? "-"),
  name
];

const sortByMae = (rows: AnalyticsErrorGroup[]) =>
  [...rows].sort((a, b) => (b.mae ?? 0) - (a.mae ?? 0));

type Translate = (key: string, vars?: Record<string, string | number>) => string;

const translateRecommendation = (label: string, t: Translate) => {
  if (label === "buy now") return t("analytics.recommendation.buyNow");
  if (label === "neutral") return t("analytics.recommendation.neutral");
  if (label === "wait") return t("analytics.recommendation.wait");
  return label;
};

const translateBucket = (label: string, t: Translate) => {
  const normalized = label.toLowerCase();
  if (normalized === "very low") return t("analytics.bucket.veryLow");
  if (normalized === "low") return t("analytics.bucket.low");
  if (normalized === "medium") return t("analytics.bucket.medium");
  if (normalized === "high") return t("analytics.bucket.high");
  if (normalized === "very high") return t("analytics.bucket.veryHigh");
  return label;
};

const ModelTable = ({
  rows,
  t
}: {
  rows: AnalyticsModelRow[];
  t: Translate;
}) => (
  <Card className="overflow-hidden">
    <div className="mb-3">
      <p className="text-base font-semibold">{t("analytics.leaderboard")}</p>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        {t("analytics.leaderboard.subtitle")}
      </p>
    </div>
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
          <tr className="border-b border-slate-200 dark:border-slate-800">
            <th className="py-2 pr-3">{t("analytics.model")}</th>
            <th className="py-2 pr-3">MAE</th>
            <th className="py-2 pr-3">RMSE</th>
            <th className="py-2 pr-3">MAPE</th>
            <th className="py-2 pr-3">R2</th>
            <th className="py-2 pr-3">{t("analytics.rows")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 8).map((row, index) => (
            <tr
              key={row.folder}
              className="border-b border-slate-100 last:border-0 dark:border-slate-800"
            >
              <td className="py-2 pr-3 font-semibold text-slate-900 dark:text-slate-100">
                {index + 1}. {row.modelName}
              </td>
              <td className="py-2 pr-3">{formatMetric(row.mae)}</td>
              <td className="py-2 pr-3">{formatMetric(row.rmse)}</td>
              <td className="py-2 pr-3">{formatPct(row.mape)}</td>
              <td className="py-2 pr-3">{formatNumber(row.r2, 3)}</td>
              <td className="py-2 pr-3">{formatNumber(row.rowsUsed)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </Card>
);

const ErrorTable = ({
  title,
  subtitle,
  rows,
  t
}: {
  title: string;
  subtitle: string;
  rows: AnalyticsErrorGroup[];
  t: Translate;
}) => (
  <Card>
    <div className="mb-3">
      <p className="text-base font-semibold">{title}</p>
      <p className="text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>
    </div>
    <div className="space-y-2">
      {sortByMae(rows)
        .slice(0, 6)
        .map((row) => (
          <div
            key={row.label}
            className="grid grid-cols-[1fr_auto] gap-3 rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800"
          >
            <div>
              <p className="font-semibold text-slate-900 dark:text-slate-100">
                {row.label}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t("analytics.records", { count: formatNumber(row.records) })} · MAPE{" "}
                {formatPct(row.mape)}
              </p>
            </div>
            <div className="text-right">
              <p className="font-semibold text-slate-900 dark:text-slate-100">
                {formatMetric(row.mae)}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t("analytics.bias")} {formatMetric(row.bias)}
              </p>
            </div>
          </div>
        ))}
    </div>
  </Card>
);

export const AnalyticsDashboard = ({ data }: AnalyticsDashboardProps) => {
  const { t } = useI18n();

  if (!data) return null;

  const modelChart = data.modelRanking.slice(0, 7).map((row) => ({
    name: row.modelName,
    mae: row.mae ?? 0,
    rmse: row.rmse ?? 0
  }));
  const featureChart = data.featureImportance.slice(0, 10).map((row) => ({
    name: row.feature,
    importance: row.share ?? row.importance ?? 0
  }));
  const priceBucketChart = sortByMae(data.errorByPriceBucket).map((row) => ({
    name: translateBucket(row.label, t),
    mae: row.mae ?? 0,
    mape: row.mape ?? 0
  }));
  const recommendationChart = data.recommendationMix.map((row) => ({
    name: translateRecommendation(row.label, t),
    value: row.records,
    gap: row.avgGapPct
  }));
  const recommendationTotal = recommendationChart.reduce(
    (sum, row) => sum + row.value,
    0
  );

  const avgActual =
    data.summary.avgActual === undefined || data.summary.avgActual === null
      ? "-"
      : formatCurrency(data.summary.avgActual);
  const avgPredicted =
    data.summary.avgPredicted === undefined || data.summary.avgPredicted === null
      ? "-"
      : formatCurrency(data.summary.avgPredicted);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t("analytics.analyzedRows")}
          </p>
          <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            {formatNumber(data.summary.rowsAnalyzed)}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t("analytics.modelsFound")}
          </p>
          <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            {formatNumber(data.summary.modelsFound)}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t("analytics.avgActual")}
          </p>
          <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            {avgActual}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t("analytics.avgPredicted")}
          </p>
          <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            {avgPredicted}
          </p>
        </Card>
      </div>

     
      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="h-96">
          <div className="mb-4">
            <p className="text-base font-semibold">
              {t("analytics.modelComparison")}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t("analytics.modelComparison.subtitle")}
            </p>
          </div>
          <ResponsiveContainer width="100%" height="78%">
            <BarChart
              data={modelChart}
              margin={{ left: 8, right: 16, bottom: 90 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />

              <XAxis
                dataKey="name"
                interval={0}
                height={1}
                tick={(props) => {
                  const { x, y, payload } = props;

                  return (
                    <text
                      x={x}
                      y={y}
                      dy={10}
                      textAnchor="end"
                      dominantBaseline="middle"
                      fontSize={11}
                      fill="#666"
                      transform={`rotate(-28 ${x} ${y})`}
                    >
                      {payload.value}
                    </text>
                  );
                }}
              />

              <YAxis tickFormatter={(value) => formatNumber(Number(value))} />
              <Tooltip formatter={metricTooltip} />

              <Bar dataKey="mae" fill="#0f766e" name="MAE" radius={[4, 4, 0, 0]} />
              <Bar dataKey="rmse" fill="#2563eb" name="RMSE" radius={[4, 4, 0, 0]} />
            </BarChart>
</ResponsiveContainer>
        </Card>

        <Card className="h-96">
          <div className="mb-4">
            <p className="text-base font-semibold">
              {t("analytics.featureImportance")}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t("analytics.featureImportance.subtitle")}
            </p>
          </div>
          <ResponsiveContainer width="100%" height="78%">
            <BarChart
              data={featureChart}
              layout="vertical"
              margin={{ left: 36, right: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={(value) => `${formatNumber(Number(value), 1)}%`} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 12 }} width={104} />
              <Tooltip formatter={metricTooltip} />
              <Bar dataKey="importance" fill="#ca8a04" name={t("analytics.importanceShare")} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="h-80">
          <div className="mb-4">
            <p className="text-base font-semibold">
              {t("analytics.errorByPrice")}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t("analytics.errorByPrice.subtitle")}
            </p>
          </div>
          <ResponsiveContainer width="100%" height="76%">
            <BarChart data={priceBucketChart} margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={(value) => formatNumber(Number(value))} />
              <Tooltip formatter={metricTooltip} />
              <Bar dataKey="mae" fill="#dc2626" name="MAE" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="h-80">
          <div className="mb-4">
            <p className="text-base font-semibold">
              {t("analytics.recommendationMix")}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t("analytics.recommendationMix.subtitle")}
            </p>
          </div>
          <div className="grid h-[76%] grid-cols-[minmax(0,1fr)_minmax(120px,160px)] items-center gap-3">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={recommendationChart}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="48%"
                  outerRadius="72%"
                  paddingAngle={2}
                  labelLine={false}
                >
                  {recommendationChart.map((entry, index) => (
                    <Cell
                      key={entry.name}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number, name: string) => [
                    formatNumber(value),
                    name
                  ]}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2 text-sm">
              {recommendationChart.map((entry, index) => {
                const percent =
                  recommendationTotal > 0
                    ? (entry.value / recommendationTotal) * 100
                    : 0;
                return (
                  <div
                    key={entry.name}
                    className="flex items-center justify-between gap-2"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                        style={{ backgroundColor: COLORS[index % COLORS.length] }}
                      />
                      <span className="truncate text-slate-600 dark:text-slate-300">
                        {entry.name}
                      </span>
                    </span>
                    <span className="flex-shrink-0 font-semibold text-slate-900 dark:text-slate-100">
                      {formatPct(percent)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <ErrorTable
          title={t("analytics.travelClassRisk")}
          subtitle={t("analytics.travelClassRisk.subtitle")}
          rows={data.errorByTravelClass}
          t={t}
        />
        <ErrorTable
          title={t("analytics.airlineRisk")}
          subtitle={t("analytics.airlineRisk.subtitle")}
          rows={data.errorByAirline}
          t={t}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <ErrorTable
          title={t("analytics.routeRisk")}
          subtitle={t("analytics.routeRisk.subtitle")}
          rows={data.errorByRoute}
          t={t}
        />
        <ModelTable rows={data.modelRanking} t={t} />
      </div>

      <Card>
        <p className="text-base font-semibold">
          {t("analytics.conclusions")}
        </p>
        <div className="mt-3 grid gap-3 text-sm text-slate-600 dark:text-slate-300 md:grid-cols-3">
          <div className="rounded-md border border-slate-200 p-3 dark:border-slate-800">
            <p className="font-semibold text-slate-900 dark:text-slate-100">
              {t("analytics.conclusion.confidence")}
            </p>
            <p className="mt-1">
              {t("analytics.conclusion.confidence.body")}
            </p>
          </div>
          <div className="rounded-md border border-slate-200 p-3 dark:border-slate-800">
            <p className="font-semibold text-slate-900 dark:text-slate-100">
              {t("analytics.conclusion.expensive")}
            </p>
            <p className="mt-1">
              {t("analytics.conclusion.expensive.body")}
            </p>
          </div>
          <div className="rounded-md border border-slate-200 p-3 dark:border-slate-800">
            <p className="font-semibold text-slate-900 dark:text-slate-100">
              {t("analytics.conclusion.history")}
            </p>
            <p className="mt-1">
              {t("analytics.conclusion.history.body")}
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
};
