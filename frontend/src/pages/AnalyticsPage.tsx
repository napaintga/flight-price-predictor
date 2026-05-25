import { ActualVsPredictedChart } from "../features/analytics/components/ActualVsPredictedChart";
import { AnalyticsDashboard } from "../features/analytics/components/AnalyticsDashboard";
import { MetricsCards } from "../features/analytics/components/MetricsCards";
import {
  useAnalyticsDashboard,
  useActualVsPredicted,
  useMetrics
} from "../features/analytics/hooks";
import { Spinner } from "../shared/ui/Spinner";
import { useI18n } from "../shared/i18n";

export const AnalyticsPage = () => {
  const { t } = useI18n();
  const actualVsPredictedQuery = useActualVsPredicted();
  const metricsQuery = useMetrics();
  const dashboardQuery = useAnalyticsDashboard();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("analytics.title")}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t("analytics.subtitle")}
        </p>
      </div>
      {metricsQuery.isLoading ? (
        <Spinner />
      ) : metricsQuery.isError ? (
        <p className="text-sm text-red-500">{t("analytics.metrics.error")}</p>
      ) : (
        <MetricsCards metrics={metricsQuery.data} />
      )}
      {actualVsPredictedQuery.isLoading ? (
        <Spinner />
      ) : actualVsPredictedQuery.isError ? (
        <p className="text-sm text-red-500">{t("analytics.chart.error")}</p>
      ) : (actualVsPredictedQuery.data?.length ?? 0) === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t("analytics.empty")}
        </p>
      ) : (
        <ActualVsPredictedChart data={actualVsPredictedQuery.data ?? []} />
      )}
      {dashboardQuery.isLoading ? (
        <Spinner />
      ) : dashboardQuery.isError ? (
        <p className="text-sm text-red-500">{t("analytics.dashboard.error")}</p>
      ) : (
        <AnalyticsDashboard data={dashboardQuery.data} />
      )}
    </div>
  );
};
