import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { FlightCard } from "../features/flights/components/FlightCard";
import { FlightSearchForm } from "../features/flights/components/FlightSearchForm";
import { useFlightPriceHistory, useFlights } from "../features/flights/hooks";
import { PriceHistoryChart } from "../features/flight-details/components/PriceHistoryChart";
import type { FlightSearchParams } from "../features/flights/types";
import { fetchTickets } from "../features/tickets/api";
import type { Flight, Ticket } from "../shared/api/types";
import { Card } from "../shared/ui/Card";
import { Spinner } from "../shared/ui/Spinner";
import { useI18n } from "../shared/i18n";
import { getAuthSnapshot, onAuthChange } from "../features/auth/session";

export const FlightsPage = () => {
  const { t } = useI18n();
  const [auth, setAuth] = useState(getAuthSnapshot());
  const isLoggedIn = Boolean(auth.token);
  const [savedTickets, setSavedTickets] = useState<Ticket[]>([]);
  const [loadBestChart, setLoadBestChart] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const paramsString = searchParams.toString();

  const readParam = (key: keyof FlightSearchParams) =>
    searchParams.get(key) || undefined;

  const currentParams: FlightSearchParams = {
    q: readParam("q"),
    departure_id: readParam("departure_id"),
    arrival_id: readParam("arrival_id"),
    gl: readParam("gl"),
    hl: readParam("hl"),
    currency: readParam("currency"),
    type: readParam("type"),
    outbound_date: readParam("outbound_date"),
    return_date: readParam("return_date"),
    travel_class: readParam("travel_class"),
    multi_city_json: readParam("multi_city_json"),
    show_hidden: readParam("show_hidden"),
    exclude_basic: readParam("exclude_basic"),
    deep_search: readParam("deep_search"),
    adults: readParam("adults"),
    children: readParam("children"),
    infants_in_seat: readParam("infants_in_seat"),
    infants_on_lap: readParam("infants_on_lap"),
    sort_by: readParam("sort_by"),
    stops: readParam("stops"),
    exclude_airlines: readParam("exclude_airlines"),
    include_airlines: readParam("include_airlines"),
    bags: readParam("bags"),
    max_price: readParam("max_price"),
    outbound_times: readParam("outbound_times"),
    return_times: readParam("return_times"),
    emissions: readParam("emissions"),
    layover_duration: readParam("layover_duration"),
    exclude_conns: readParam("exclude_conns"),
    max_duration: readParam("max_duration"),
  };

  const { data, isLoading, isError } = useFlights(currentParams);

  // ✅ IMPORTANT: backend may return either an array or an object { flights: [...] }
  const flights = useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    const maybeObj = data as any;
    return Array.isArray(maybeObj.flights) ? maybeObj.flights : [];
  }, [data]);

  // Optional: show "asOf" if backend returns it
  const asOf = useMemo(() => {
    if (!data || Array.isArray(data)) return undefined;
    return (data as any).asOf as string | undefined;
  }, [data]);

  const savedIds = useMemo(() => {
    const set = new Set<string>();
    savedTickets.forEach((ticket) => {
      if (ticket.id) set.add(ticket.id);
      if (ticket.flightId) set.add(ticket.flightId);
    });
    return set;
  }, [savedTickets]);
  const bestFlight = useMemo(
    () => flights.find((flight: Flight) => flight.best) ?? flights[0],
    [flights]
  );
  const bestFlightHistoryQuery = useFlightPriceHistory(
    String(bestFlight?.uid ?? bestFlight?.id ?? ""),
    currentParams,
    { enabled: loadBestChart && Boolean(bestFlight) }
  );

  useEffect(() => {
    const unsubscribe = onAuthChange(() => {
      setAuth(getAuthSnapshot());
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (!isLoggedIn) {
      setSavedTickets([]);
      return;
    }
    let cancelled = false;
    fetchTickets()
      .then((items) => {
        if (!cancelled) setSavedTickets(items);
      })
      .catch(() => {
        if (!cancelled) setSavedTickets([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isLoggedIn]);

  useEffect(() => {
    if (paramsString.length > 0) return;

    const stored = localStorage.getItem("flight-last-search");
    if (!stored) return;

    try {
      const parsed = JSON.parse(stored) as FlightSearchParams;
      const entries = Object.entries(parsed).filter(
        ([, value]) => value !== undefined && value !== ""
      );
      if (entries.length > 0) {
        setSearchParams(entries);
      }
    } catch {
      // Ignore malformed storage.
    }
  }, [paramsString, setSearchParams]);

  const handleSearch = (params: FlightSearchParams) => {
    const entries = Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== ""
    );
    setLoadBestChart(false);
    setSearchParams(entries);
  };

  const handleTicketSavedChange = (ticket: Ticket, nextSaved: boolean) => {
    setSavedTickets((prev) => {
      if (nextSaved) {
        if (prev.some((item) => item.id === ticket.id)) return prev;
        return [ticket, ...prev];
      }
      return prev.filter((item) => item.id !== ticket.id);
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("flights.title")}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t("flights.subtitle")}
        </p>
        {asOf && (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {t("flights.pricesAsOf") ?? "Prices as of"}: {asOf}
          </p>
        )}
      </div>

      <FlightSearchForm defaultValues={currentParams} onSearch={handleSearch} />

      {isLoading && <Spinner />}

      {isError && <p className="text-sm text-red-500">{t("flights.error")}</p>}

      {!isLoading && !isError && flights.length === 0 && (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t("flights.empty")}
        </p>
      )}

      {!isLoading && !isError && bestFlight && !loadBestChart && (
        <Card className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-base font-semibold">
              {t("flights.bestChart.title")}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t("flights.bestChart.subtitle")}
            </p>
          </div>
          <button
            type="button"
            className="rounded-md bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-700"
            onClick={() => setLoadBestChart(true)}
          >
            {t("flights.bestChart.load")}
          </button>
        </Card>
      )}

      {!isLoading && !isError && bestFlight && loadBestChart && (
        <>
          {bestFlightHistoryQuery.isLoading ? (
            <Spinner />
          ) : bestFlightHistoryQuery.isError ? (
            <Card>
              <p className="text-sm text-red-500">
                {t("flight.history.error")}
              </p>
            </Card>
          ) : (bestFlightHistoryQuery.data?.length ?? 0) === 0 ? (
            <Card>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {t("flight.history.empty")}
              </p>
            </Card>
          ) : (
            <PriceHistoryChart
              data={bestFlightHistoryQuery.data ?? []}
              currency={bestFlight.currency}
              title={t("flights.bestChart.title")}
              subtitle={t("flights.bestChart.subtitle")}
            />
          )}
        </>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {flights.map((flight: any) => (
          <FlightCard
            key={flight.uid ?? flight.id}
            flight={flight}
            predictionParams={currentParams}
            enablePrediction={false}
            savedIds={isLoggedIn ? savedIds : undefined}
            onTicketSavedChange={handleTicketSavedChange}
          />
        ))}
      </div>
    </div>
  );
};
