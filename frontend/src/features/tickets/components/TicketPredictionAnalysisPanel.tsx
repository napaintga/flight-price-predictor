import type {
  Ticket,
  TicketHistoryPoint,
  TicketLocalHistoryResponse
} from "../../../shared/api/types";
import { useI18n } from "../../../shared/i18n";
import { Card } from "../../../shared/ui/Card";
import { Spinner } from "../../../shared/ui/Spinner";
import { formatCurrency } from "../../../shared/utils/format";

type TicketPredictionAnalysisPanelProps = {
  ticket?: Ticket;
  history?: TicketLocalHistoryResponse;
  isLoading?: boolean;
  isError?: boolean;
};

type Analysis = {
  currency: string;
  route: string;
  tripType: string;
  currentPrice?: number;
  forecastHighest?: number;
  markerPercent: number;
  recommendationKey: "book" | "wait";
  stableUntil?: string;
  growthFrom?: string;
  growthTo?: string;
  growthAmount?: number;
  departureDate?: string;
};

const parseDate = (value?: string) => {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date;
};

const formatShortDate = (value?: string) => {
  const date = parseDate(value);
  if (!date) return "-";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric"
  });
};

const getPrice = (point?: TicketHistoryPoint) =>
  typeof point?.price === "number" ? point.price : undefined;

const maxNumber = (values: Array<number | undefined | null>) => {
  const numbers = values.filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value)
  );
  return numbers.length ? Math.max(...numbers) : undefined;
};

const minNumber = (values: Array<number | undefined | null>) => {
  const numbers = values.filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value)
  );
  return numbers.length ? Math.min(...numbers) : undefined;
};

const buildAnalysis = (
  ticket?: Ticket,
  history?: TicketLocalHistoryResponse
): Analysis | null => {
  if (!ticket || !history) return null;

  const actual = history.actual ?? [];
  const forecast = history.forecast ?? [];
  const latestActual = actual.length ? actual[actual.length - 1] : undefined;
  const currentPrice =
    history.summary.latestPrice ?? getPrice(latestActual) ?? ticket.pricePaid;
  const forecastHighest = maxNumber([
    ...forecast.map((point) => point.upper ?? point.price),
    history.summary.maxPrice,
    currentPrice
  ]);
  const localMin = minNumber([
    history.summary.minPrice,
    currentPrice,
    ...actual.map((point) => point.minPrice ?? point.price)
  ]);
  const localMax = maxNumber([
    history.summary.maxPrice,
    forecastHighest,
    currentPrice,
    ...actual.map((point) => point.maxPrice ?? point.price)
  ]);
  const range = localMin !== undefined && localMax !== undefined ? localMax - localMin : 0;
  const markerPercent =
    currentPrice !== undefined && localMin !== undefined && range > 0
      ? Math.min(Math.max(((currentPrice - localMin) / range) * 100, 0), 100)
      : 50;
  const threshold =
    currentPrice !== undefined ? Math.max(20, currentPrice * 0.05) : undefined;
  const firstGrowthIndex =
    currentPrice !== undefined && threshold !== undefined
      ? forecast.findIndex((point) => point.price >= currentPrice + threshold)
      : -1;
  const growthStart =
    firstGrowthIndex >= 0 ? forecast[firstGrowthIndex] : forecast[0];
  const growthEnd = forecast.length ? forecast[forecast.length - 1] : undefined;
  const stableUntil =
    firstGrowthIndex > 0
      ? forecast[firstGrowthIndex - 1]?.ts
      : firstGrowthIndex === 0
        ? latestActual?.ts
        : growthEnd?.ts;
  const finalForecast = getPrice(growthEnd);
  const growthAmount =
    currentPrice !== undefined && finalForecast !== undefined
      ? Math.max(finalForecast - currentPrice, 0)
      : undefined;

  return {
    currency: history.currency || ticket.currency || "USD",
    route:
      ticket.origin && ticket.destination
        ? `${ticket.originName ?? ticket.origin} -> ${ticket.destinationName ?? ticket.destination}`
        : ticket.flightId ?? "-",
    tripType: ticket.tripType === "1" ? "roundTrip" : "oneWay",
    currentPrice,
    forecastHighest,
    markerPercent,
    recommendationKey:
      growthAmount !== undefined && currentPrice !== undefined && growthAmount >= currentPrice * 0.03
        ? "book"
        : "wait",
    stableUntil,
    growthFrom: growthStart?.ts,
    growthTo: ticket.departAt ?? growthEnd?.ts,
    growthAmount,
    departureDate: ticket.departAt
  };
};

export const TicketPredictionAnalysisPanel = ({
  ticket,
  history,
  isLoading,
  isError
}: TicketPredictionAnalysisPanelProps) => {
  const { t } = useI18n();
  const analysis = buildAnalysis(ticket, history);

  if (isLoading) {
    return (
      <Card>
        <Spinner />
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <p className="text-sm text-red-500">{t("tickets.analysis.error")}</p>
      </Card>
    );
  }

  if (!analysis) {
    return (
      <Card>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t("tickets.analysis.empty")}
        </p>
      </Card>
    );
  }

  const priceLevel =
    analysis.markerPercent < 30
      ? t("tickets.analysis.level.great")
      : analysis.markerPercent < 60
        ? t("tickets.analysis.level.good")
        : analysis.markerPercent < 80
          ? t("tickets.analysis.level.fair")
          : t("tickets.analysis.level.high");

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 p-5 dark:border-slate-800">
        <div>
          <p className="text-lg font-semibold text-slate-950 dark:text-slate-50">
            {analysis.route}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t(`tickets.analysis.${analysis.tripType}`)} ·{" "}
            {t("tickets.analysis.perTraveler")}
          </p>
        </div>
        <div className="rounded-md border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-900 dark:border-slate-700 dark:text-slate-100">
          {t("tickets.analysis.sortRecommended")}
        </div>
      </div>

      <div className="grid border-b border-slate-200 dark:border-slate-800 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-4 p-5">
          <p className="text-lg font-semibold text-slate-950 dark:text-slate-50">
            {t(`tickets.analysis.recommendation.${analysis.recommendationKey}`)}
          </p>
          <div>
            <div className="relative h-3 rounded-full bg-gradient-to-r from-emerald-600 via-amber-300 via-60% to-red-600">
              <span
                className="absolute top-1/2 h-5 w-5 -translate-y-1/2 rounded-full border-4 border-slate-100 bg-orange-400 shadow dark:border-slate-900"
                style={{ left: `calc(${analysis.markerPercent}% - 10px)` }}
              />
            </div>
            <div className="mt-4 grid grid-cols-4 text-center text-sm font-medium text-slate-900 dark:text-slate-100">
              <span>{t("tickets.analysis.level.great")}</span>
              <span>{t("tickets.analysis.level.good")}</span>
              <span>{t("tickets.analysis.level.fair")}</span>
              <span>{t("tickets.analysis.level.high")}</span>
            </div>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t("tickets.analysis.currentLevel")}: {priceLevel}
          </p>
        </div>

        <div className="border-t border-slate-200 p-5 dark:border-slate-800 lg:border-l lg:border-t-0">
          <p className="text-lg font-semibold text-slate-950 dark:text-slate-50">
            {t("tickets.analysis.currentLowest")}
          </p>
          <p className="mt-3 text-2xl font-bold text-slate-950 dark:text-slate-50">
            {formatCurrency(analysis.currentPrice, analysis.currency)}
          </p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {t("tickets.analysis.perTraveler")}
          </p>
        </div>
      </div>

      <div className="grid divide-y divide-slate-200 dark:divide-slate-800 md:grid-cols-4 md:divide-x md:divide-y-0">
        <div className="p-5">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-xl font-semibold text-red-600 dark:bg-rose-950">
            ↗
          </div>
          <p className="text-sm font-semibold text-slate-950 dark:text-slate-50">
            {t("tickets.analysis.forecastHighest")}
          </p>
          <p className="mt-3 text-2xl font-bold text-slate-950 dark:text-slate-50">
            {formatCurrency(analysis.forecastHighest, analysis.currency)}
          </p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {t("tickets.analysis.perTraveler")}
          </p>
        </div>
        <div className="p-5">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-orange-100 text-xl font-semibold text-orange-600 dark:bg-orange-950">
            ↗
          </div>
          <p className="text-sm font-semibold text-slate-950 dark:text-slate-50">
            {t("tickets.analysis.until")} {formatShortDate(analysis.stableUntil)}
          </p>
          <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
            {t("tickets.analysis.stableText")}
          </p>
        </div>
        <div className="p-5">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-2xl font-semibold text-red-600 dark:bg-rose-950">
            ↑
          </div>
          <p className="text-sm font-semibold text-slate-950 dark:text-slate-50">
            {formatShortDate(analysis.growthFrom)} -{" "}
            {formatShortDate(analysis.growthTo)}
          </p>
          <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
            {t("tickets.analysis.growthText", {
              amount: formatCurrency(analysis.growthAmount, analysis.currency)
            })}
          </p>
        </div>
        <div className="p-5">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-xl font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-200">
            ✈
          </div>
          <p className="text-sm font-semibold text-slate-950 dark:text-slate-50">
            {t("tickets.analysis.departure")}
          </p>
          <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
            {formatShortDate(analysis.departureDate)}
          </p>
        </div>
      </div>
    </Card>
  );
};
