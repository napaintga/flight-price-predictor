import type { Metrics } from "../../../shared/api/types";
import { Card } from "../../../shared/ui/Card";
import { formatDateTime } from "../../../shared/utils/format";
import { useI18n } from "../../../shared/i18n";

const formatNumber = (value?: number | null, suffix = "") => {
  if (value === undefined || value === null) return "-";
  return `${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2
  }).format(value)}${suffix}`;
};

export const MetricsCards = ({ metrics }: { metrics?: Metrics }) => {
  const { t } = useI18n();

  return (
    <div className="grid gap-4 md:grid-cols-4">
      <Card>
        <p className="text-sm text-slate-500 dark:text-slate-400">MAE</p>
        <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          {formatNumber(metrics?.mae)}
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {t("analytics.metric.mae")}
        </p>
      </Card>
      <Card>
        <p className="text-sm text-slate-500 dark:text-slate-400">RMSE</p>
        <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          {formatNumber(metrics?.rmse)}
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {t("analytics.metric.rmse")}
        </p>
      </Card>
      <Card>
        <p className="text-sm text-slate-500 dark:text-slate-400">MAPE</p>
        <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          {formatNumber(metrics?.mape, "%")}
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {t("analytics.metric.mape")}
        </p>
      </Card>
      <Card>
        <p className="text-sm text-slate-500 dark:text-slate-400">R2</p>
        <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          {formatNumber(metrics?.r2)}
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {t("analytics.metric.r2")}
        </p>
      </Card>
      <Card className="md:col-span-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t("analytics.model")}
            </p>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {metrics?.modelName ?? "-"}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t("analytics.rowsUsed")}
            </p>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {formatNumber(metrics?.rowsUsed)}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t("analytics.target")}
            </p>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {metrics?.target ?? "-"}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t("analytics.updated")}
            </p>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {formatDateTime(metrics?.updatedAt)}
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
};
