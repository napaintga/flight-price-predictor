import {
  Label,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { ActualVsPredictedPoint } from "../../../shared/api/types";
import { Card } from "../../../shared/ui/Card";
import { formatCurrency, formatDateTime } from "../../../shared/utils/format";
import { useI18n } from "../../../shared/i18n";

const formatAxis = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
};

type ActualVsPredictedChartProps = {
  data: ActualVsPredictedPoint[];
};

export const ActualVsPredictedChart = ({
  data
}: ActualVsPredictedChartProps) => {
  const { t } = useI18n();

  return (
    <Card className="h-80">
      <div className="mb-4">
        <p className="text-base font-semibold">
          {t("analytics.actualVsPredicted")}
        </p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t("analytics.actualVsPredicted.subtitle")}
        </p>
      </div>
      <ResponsiveContainer width="100%" height="80%">
        <LineChart data={data} margin={{ top: 8, right: 18, bottom: 30, left: 26 }}>
          <XAxis dataKey="ts" tickFormatter={formatAxis}>
            <Label
              value={t("analytics.axis.date")}
              offset={-20}
              position="insideBottom"
              fill="#475569"
              fontSize={12}
              fontWeight={600}
            />
          </XAxis>
          <YAxis tickFormatter={(value) => formatCurrency(Number(value))}>
            <Label
              value={t("analytics.axis.price")}
              angle={-90}
              position="insideLeft"
              offset={-12}
              dy={35}
              fill="#475569"
              fontSize={12}
              fontWeight={600}
            />
          </YAxis>
          <Tooltip
            labelFormatter={(label) => formatDateTime(label)}
            formatter={(value: number) => formatCurrency(value)}
          />
          <Line
            type="monotone"
            dataKey="actual"
            name={t("analytics.actual")}
            stroke="#1d3e21"
            strokeWidth={2}
          />
          <Line
            type="monotone"
            dataKey="predicted"
            name={t("analytics.predicted")}
            stroke="#2563eb"
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
};
