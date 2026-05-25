import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { PricePoint } from "../../../shared/api/types";
import { formatCurrency, formatDateTime } from "../../../shared/utils/format";
import { Card } from "../../../shared/ui/Card";
import { useI18n } from "../../../shared/i18n";

const formatAxis = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
};

type PriceHistoryChartProps = {
  data: PricePoint[];
  currency?: string;
  title?: string;
  subtitle?: string;
};

export const PriceHistoryChart = ({
  data,
  currency,
  title,
  subtitle
}: PriceHistoryChartProps) => {
  const { t } = useI18n();
  const displayCurrency = currency || "USD";

  return (
    <Card className="h-80">
      <div className="mb-4">
        <p className="text-base font-semibold">
          {title ?? t("priceHistory.title")}
        </p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {subtitle ?? t("priceHistory.subtitle")}
        </p>
      </div>
      <ResponsiveContainer width="100%" height="80%">
        <LineChart data={data}>
          <XAxis dataKey="ts" tickFormatter={formatAxis} />
          <YAxis tickFormatter={(value) => formatCurrency(Number(value), displayCurrency)} />
          <Tooltip
            labelFormatter={(label) => formatDateTime(label)}
            formatter={(value: number) => formatCurrency(value, displayCurrency)}
          />
          <Line type="monotone" dataKey="price" stroke="#2563eb" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
};
