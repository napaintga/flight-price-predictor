import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { TicketPredictionAnalysisPanel } from "../features/tickets/components/TicketPredictionAnalysisPanel";
import { TicketHistoryChart } from "../features/tickets/components/TicketHistoryChart";
import { useTicketLocalHistory } from "../features/tickets/hooks";
import {
  useFlightDetails,
  usePriceInsights,
  useFlightPriceSnapshots
} from "../features/flight-details/hooks";
import { fetchFlightById } from "../features/flight-details/api";
import type { FlightSearchParams } from "../features/flights/types";
import type { Flight } from "../shared/api/types";
import { Card } from "../shared/ui/Card";
import { Spinner } from "../shared/ui/Spinner";
import { formatCurrency, formatDateTime } from "../shared/utils/format";
import { useI18n } from "../shared/i18n";
import { addTicket, fetchTickets, removeTicket } from "../features/tickets/api";
import { getAuthSnapshot, onAuthChange } from "../features/auth/session";

const LOCAL_TICKETS_KEY = "local-tickets";

export const FlightDetailsPage = () => {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const [auth, setAuth] = useState(getAuthSnapshot());
  const isLoggedIn = Boolean(auth.token);

  const params = useParams();
  const flightId =
    params.uid || params.flightId || params.id || params.flightUid || params["*"];
  const navigate = useNavigate();

  const [searchParams] = useSearchParams();
  const debug = searchParams.get("debug") === "1";

  const readParam = (key: keyof FlightSearchParams) =>
    searchParams.get(key) || undefined;

  const urlParams: FlightSearchParams = useMemo(
    () => ({
      departure_id: readParam("departure_id"),
      arrival_id: readParam("arrival_id"),
      outbound_date: readParam("outbound_date"),
      return_date: readParam("return_date"),
      type: readParam("type"),
      travel_class: readParam("travel_class"),
      adults: readParam("adults"),
      children: readParam("children"),
      infants_in_seat: readParam("infants_in_seat"),
      infants_on_lap: readParam("infants_on_lap"),
      currency: readParam("currency"),
      hl: readParam("hl"),
      gl: readParam("gl"),
      q: readParam("q"),
      multi_city_json: readParam("multi_city_json"),
      show_hidden: readParam("show_hidden"),
      exclude_basic: readParam("exclude_basic"),
      deep_search: readParam("deep_search"),
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
      max_duration: readParam("max_duration")
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searchParams.toString()]
  );

  const effectiveParams: FlightSearchParams = useMemo(() => {
    let stored: FlightSearchParams = {};
    const raw = localStorage.getItem("flight-last-search");
    if (raw) {
      try {
        stored = JSON.parse(raw) as FlightSearchParams;
      } catch {
        stored = {};
      }
    }
    return { ...stored, ...urlParams };
  }, [urlParams]);

  const canFetch =
    Boolean(flightId) &&
    Boolean(effectiveParams.departure_id) &&
    Boolean(effectiveParams.arrival_id) &&
    Boolean(effectiveParams.outbound_date);

  const flightQuery = useFlightDetails(flightId ?? "", effectiveParams);

  const priceInsightsParams = useMemo(() => {
    if (
      !effectiveParams.departure_id ||
      !effectiveParams.arrival_id ||
      !effectiveParams.outbound_date
    ) {
      return undefined;
    }
    return {
      departure_id: effectiveParams.departure_id,
      arrival_id: effectiveParams.arrival_id,
      outbound_date: effectiveParams.outbound_date,
      return_date: effectiveParams.return_date,
      currency: effectiveParams.currency,
      hl: effectiveParams.hl ?? lang,
      type: effectiveParams.type,
      travel_class: effectiveParams.travel_class,
      adults: effectiveParams.adults
    };
  }, [effectiveParams, lang]);

  const priceInsightsQuery = usePriceInsights(priceInsightsParams);
  const priceSnapshotsQuery = useFlightPriceSnapshots(
    flightId ?? "",
    effectiveParams
  );
  const [isSaved, setIsSaved] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showForecast, setShowForecast] = useState(true);
  const searchParamsString = useMemo(
    () =>
      new URLSearchParams(
        Object.entries(effectiveParams).filter(([, v]) => Boolean(v)) as Array<
          [string, string]
        >
      ).toString(),
    [effectiveParams]
  );
  const detailFlightTicket = useMemo(() => {
    const flight = flightQuery.data;
    if (!flight) return undefined;
    const firstSegment = flight.segments?.[0];
    const lastSegment =
      flight.segments?.[
        flight.segments?.length ? flight.segments.length - 1 : 0
      ];
    const parseCount = (value?: string) => {
      if (!value) return 0;
      const parsed = Number(value);
      return Number.isNaN(parsed) ? 0 : parsed;
    };
    const passengersCount =
      parseCount(effectiveParams.adults) +
      parseCount(effectiveParams.children) +
      parseCount(effectiveParams.infants_in_seat) +
      parseCount(effectiveParams.infants_on_lap);
    return {
      id: `detail-${flight.uid ?? flight.id}`,
      flightId: String(flight.uid ?? flight.id ?? ""),
      origin: flight.origin,
      destination: flight.destination,
      originName: firstSegment?.departure_airport?.name,
      destinationName: lastSegment?.arrival_airport?.name,
      airline: flight.airline ?? undefined,
      departAt: flight.departAt,
      currency: flight.currency,
      duration: flight.duration,
      durationMinutes: flight.total_duration_minutes ?? undefined,
      stops: flight.stops,
      tripType: effectiveParams.type,
      travelClass: effectiveParams.travel_class,
      passengers: passengersCount > 0 ? passengersCount : undefined,
      searchParams: searchParamsString || undefined,
      createdAt: flight.asOf || new Date().toISOString()
    };
  }, [flightQuery.data, effectiveParams, searchParamsString]);
  const localHistoryQuery = useTicketLocalHistory(detailFlightTicket);

  const debugInfo = useMemo(
    () => ({
      flightId,
      canFetch,
      urlParams,
      effectiveParams,
      flightQuery: {
        isLoading: flightQuery.isLoading,
        isError: flightQuery.isError,
        status: flightQuery.status,
        hasData: Boolean(flightQuery.data)
      },
      flightSummary: flightQuery.data
        ? {
            uid: flightQuery.data.uid,
            origin: flightQuery.data.origin,
            destination: flightQuery.data.destination,
            price: flightQuery.data.price,
            currency: flightQuery.data.currency
          }
        : null,
      priceInsights: Boolean(priceInsightsQuery.data),
      priceSnapshotsCount: priceSnapshotsQuery.data?.length ?? 0,
      searchParamsString
    }),
    [
      flightId,
      canFetch,
      urlParams,
      effectiveParams,
      flightQuery.isLoading,
      flightQuery.isError,
      flightQuery.status,
      flightQuery.data,
      priceInsightsQuery.data,
      priceSnapshotsQuery.data,
      searchParamsString
    ]
  );

  const debugPanel = debug ? (
    <Card className="border border-amber-200 bg-amber-50/60 text-xs text-slate-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-slate-200">
      <pre className="whitespace-pre-wrap p-3">
        {JSON.stringify(debugInfo, null, 2)}
      </pre>
    </Card>
  ) : null;

  useEffect(() => {
    const unsubscribe = onAuthChange(() => {
      setAuth(getAuthSnapshot());
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    const flight = flightQuery.data;
    if (!flight) return;
    const baseId = String(flight.uid ?? flight.id ?? "flight");
    const ticketId = `L-${baseId}`;
    if (isLoggedIn) {
      let cancelled = false;
      fetchTickets({ flightId: baseId })
        .then((items) => {
          if (cancelled) return;
          const saved = items.some(
            (item) => item?.id === ticketId || item?.flightId === baseId
          );
          setIsSaved(saved);
        })
        .catch(() => {
          if (!cancelled) setIsSaved(false);
        });
      return () => {
        cancelled = true;
      };
    }

    try {
      const raw = localStorage.getItem(LOCAL_TICKETS_KEY);
      const existing = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(existing)) return;
      const saved = existing.some(
        (item) => item?.id === ticketId || item?.flightId === baseId
      );
      setIsSaved(saved);
    } catch {
      // ignore storage errors
    }
  }, [flightQuery.data, isLoggedIn]);

  if (!flightId) {
    return (
      <div className="space-y-4">
        {debugPanel}
        <p className="text-sm text-red-500">
          {t("flight.details.missingId") ?? "Missing flight id."}
        </p>
        <Link className="text-sm font-semibold text-blue-600" to="/flights">
          {t("flight.details.back") ?? "Back"}
        </Link>
      </div>
    );
  }

  if (!canFetch) {
    return (
      <div className="space-y-4">
        {debugPanel}
        <p className="text-sm text-red-500">
          {t("flight.details.missingParams") ??
            "Missing search params (departure_id, arrival_id, outbound_date). Open details from the flights list."}
        </p>
        <Link className="text-sm font-semibold text-blue-600" to="/flights">
          {t("flight.details.back") ?? "Back"}
        </Link>
      </div>
    );
  }

  if (flightQuery.isLoading) {
    return (
      <div className="space-y-4">
        {debugPanel}
        <Spinner />
      </div>
    );
  }

  if (flightQuery.isError || !flightQuery.data) {
    return (
      <div className="space-y-4">
        {debugPanel}
        <p className="text-sm text-red-500">{t("flight.details.error")}</p>
        <Link className="text-sm font-semibold text-blue-600" to="/flights">
          {t("flight.details.back")}
        </Link>
      </div>
    );
  }

  const flight = flightQuery.data;
  const displayCurrency = effectiveParams.currency || flight.currency || "USD";
  const formatPriceValue = (value: number | string | undefined) => {
    if (value === undefined || value === null) return "-";
    if (typeof value === "number") return formatCurrency(value, displayCurrency);
    const parsed = Number(String(value).replace(/[^\d.]/g, ""));
    if (!Number.isNaN(parsed)) return formatCurrency(parsed, displayCurrency);
    return String(value);
  };
  const parsePriceNumber = (value: number | string | undefined) => {
    if (value === undefined || value === null) return undefined;
    if (typeof value === "number") return value;
    const parsed = Number(String(value).replace(/[^\d.]/g, ""));
    return Number.isNaN(parsed) ? undefined : parsed;
  };
  const updateLocalTicketPrice = (updatedFlight: Flight) => {
    if (isLoggedIn) return;
    const baseId = String(updatedFlight.uid ?? updatedFlight.id ?? "flight");
    const ticketId = `L-${baseId}`;
    try {
      const raw = localStorage.getItem(LOCAL_TICKETS_KEY);
      if (!raw) return;
      const existing = JSON.parse(raw);
      if (!Array.isArray(existing)) return;
      const next = existing.map((item) => {
        if (item?.id !== ticketId && item?.flightId !== baseId) return item;
        const pricePaid = parsePriceNumber(updatedFlight.price);
        return {
          ...item,
          ...(pricePaid !== undefined ? { pricePaid } : {})
        };
      });
      localStorage.setItem(LOCAL_TICKETS_KEY, JSON.stringify(next));
    } catch {
      // ignore storage errors
    }
  };
  const handleRefresh = async () => {
    if (!flightId || !canFetch) return;
    const refreshParams = { ...effectiveParams, no_cache: "true" };
    setIsRefreshing(true);
    try {
      const flight = await fetchFlightById(flightId, refreshParams);
      const nextId = String(flight.uid ?? flight.id ?? "");
      queryClient.setQueryData(["flight", flightId, effectiveParams], flight);
      updateLocalTicketPrice(flight);
      await Promise.all([
        priceSnapshotsQuery.refetch(),
        priceInsightsQuery.refetch()
      ]);
      if (nextId && nextId !== String(flightId)) {
        const query = searchParamsString ? `?${searchParamsString}` : "";
        navigate(`/flights/${nextId}${query}`, { replace: true });
      }
    } catch {
      // ignore refresh errors
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleToggleTicket = async () => {
    const baseId = String(flight.uid ?? flight.id ?? "flight");
    const ticketId = `L-${baseId}`;
    const firstSegment = flight.segments?.[0];
    const lastSegment =
      flight.segments?.[flight.segments?.length ? flight.segments.length - 1 : 0];
    const parseCount = (value?: string) => {
      if (!value) return 0;
      const parsed = Number(value);
      return Number.isNaN(parsed) ? 0 : parsed;
    };
    const passengersCount =
      parseCount(effectiveParams.adults) +
      parseCount(effectiveParams.children) +
      parseCount(effectiveParams.infants_in_seat) +
      parseCount(effectiveParams.infants_on_lap);
    let pricePaid: number | undefined;
    if (typeof flight.price === "number") {
      pricePaid = flight.price;
    } else {
      const parsed = Number(String(flight.price).replace(/[^\d.]/g, ""));
      if (!Number.isNaN(parsed)) pricePaid = parsed;
    }
    const ticket = {
      id: ticketId,
      flightId: baseId,
      origin: flight.origin,
      destination: flight.destination,
      originName: firstSegment?.departure_airport?.name,
      destinationName: lastSegment?.arrival_airport?.name,
      airline: flight.airline ?? undefined,
      departAt: flight.departAt,
      currency: flight.currency,
      duration: flight.duration,
      durationMinutes: flight.total_duration_minutes ?? undefined,
      stops: flight.stops,
      tripType: effectiveParams.type,
      travelClass: effectiveParams.travel_class,
      passengers: passengersCount > 0 ? passengersCount : undefined,
      searchParams: searchParamsString || undefined,
      createdAt: new Date().toISOString(),
      ...(pricePaid !== undefined ? { pricePaid } : {})
    };

    if (isLoggedIn) {
      const nextSaved = !isSaved;
      setIsSaved(nextSaved);
      try {
        if (nextSaved) {
          await addTicket(ticket);
        } else {
          await removeTicket(ticket.id);
        }
      } catch {
        setIsSaved(!nextSaved);
      }
      return;
    }

    try {
      const raw = localStorage.getItem(LOCAL_TICKETS_KEY);
      const existing = raw ? JSON.parse(raw) : [];
      const list = Array.isArray(existing) ? existing : [];
      const alreadySaved = list.some(
        (item) => item?.id === ticketId || item?.flightId === baseId
      );
      const next = alreadySaved
        ? list.filter((item) => item?.id !== ticketId && item?.flightId !== baseId)
        : [ticket, ...list];
      localStorage.setItem(LOCAL_TICKETS_KEY, JSON.stringify(next));
      setIsSaved(!alreadySaved);
    } catch {
      // ignore storage errors
    }
  };

  return (
    <div className="space-y-6">
      {debugPanel}
      <div className="flex items-center justify-between">
        <Link className="text-sm font-semibold text-blue-600" to="/flights">
          {"\u2190 "}{t("flight.details.back")}
        </Link>
        <div className="flex items-center gap-4">
          <button
            type="button"
            className="text-sm font-semibold text-blue-600 disabled:opacity-60"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            {isRefreshing
              ? t("flight.details.refreshing") ?? "Refreshing..."
              : t("flight.details.refresh") ?? "Refresh prices"}
          </button>
          <button
            type="button"
            className="text-sm font-semibold text-blue-600"
            onClick={handleToggleTicket}
          >
            {isSaved
              ? t("flights.removeTicket") ?? "Remove ticket"
              : t("flights.addTicket") ?? "Add ticket"}
          </button>
          <Link
            className="text-sm font-semibold text-blue-600"
            to={`/tickets?flightId=${flight.uid ?? flight.id}`}
          >
            {t("nav.tickets")}
          </Link>
        </div>
      </div>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center gap-3 ">
          {flight.airline_logo && (
            <img
              src={flight.airline_logo}
              alt={flight.airline ?? "Airline"}
              className="h-10 w-10 rounded bg-white p-1"
            />
          )}
          <div>
            <h1 className="text-2xl font-semibold">
              {flight.origin} -- {flight.destination}
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {formatDateTime(flight.departAt)}
            </p>
          </div>
        </div>

        <div className="grid gap-2 text-sm sm:grid-cols-2">
          <div className="flex items-center justify-between">
            <span className="text-slate-500 dark:text-slate-400">
              {t("flight.details.airline")}
            </span>
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              {flight.airline ?? "-"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500 dark:text-slate-400">
              {t("flight.details.price") ?? "Price"}
            </span>
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              {formatPriceValue(flight.price)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500 dark:text-slate-400">
              {t("flight.details.duration") ?? "Duration"}
            </span>
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              {flight.duration || "-"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500 dark:text-slate-400">
              {t("flight.details.stops") ?? "Stops"}
            </span>
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              {flight.stops ?? 0}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500 dark:text-slate-400">
              {t("flight.details.type") ?? "Type"}
            </span>
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              {flight.type || "-"}
            </span>
          </div>
          {effectiveParams.return_date && (
            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400">
                {t("flight.details.return") ?? "Return"}
              </span>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {effectiveParams.return_date}
              </span>
            </div>
          )}
        </div>

        {flight.asOf && (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {t("flight.details.asOf") ?? "Prices as of"}: {flight.asOf}
          </p>
        )}
      </Card>

      <TicketHistoryChart
        ticket={detailFlightTicket}
        history={localHistoryQuery.data}
        isLoading={localHistoryQuery.isLoading}
        isError={localHistoryQuery.isError}
        showForecast={showForecast}
        onToggleForecast={() => setShowForecast((prev) => !prev)}
        title={t("flight.details.chart.title")}
        subtitle={t("flight.details.chart.subtitle")}
      />

      <TicketPredictionAnalysisPanel
        ticket={detailFlightTicket}
        history={localHistoryQuery.data}
        isLoading={localHistoryQuery.isLoading}
        isError={localHistoryQuery.isError}
      />

      {priceSnapshotsQuery.isLoading ? (
        <Spinner />
      ) : priceSnapshotsQuery.isError ? (
        <p className="text-sm text-red-500">
          {t("flight.snapshots.error") ?? "Unable to load previous prices."}
        </p>
      ) : (priceSnapshotsQuery.data?.length ?? 0) === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t("flight.snapshots.empty") ?? "No previous prices found."}
        </p>
      ) : (
        <Card className="space-y-2">
          <p className="text-base font-semibold">
            {t("flight.snapshots.title") ?? "All prices for this flight"}
          </p>
          <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
            {priceSnapshotsQuery.data?.map((item) => (
              <div
                key={item.snapshotId ?? item.asOf}
                className="flex items-center justify-between"
              >
                <span>{formatDateTime(item.asOf)}</span>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {formatPriceValue(item.price)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {flight.extensions && flight.extensions.length > 0 && (
        <Card className="space-y-2">
          <p className="text-base font-semibold">
            {t("flight.details.extensions") ?? "Extensions"}
          </p>
          <ul className="space-y-1 text-sm text-slate-600 dark:text-slate-300 ml-4">
            {flight.extensions.map((item, idx) => (
              <li key={`${item}-${idx}`} className="list-disc pl-2">
                {item}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {flight.layovers && flight.layovers.length > 0 && (
        <Card className="space-y-2">
          <p className="text-base font-semibold">
            {t("flight.details.layovers") ?? "Layovers"}
          </p>
          <div className="h-1 w-full rounded-full bg-slate-200 dark:bg-slate-800"></div>
          <ul className="space-y-1 text-sm text-slate-600 dark:text-slate-300">
            {flight.layovers.map((item, idx) => (
              <div
                key={`${item.id ?? item.name ?? idx}`}
                className="rounded-md border border-slate-200 p-3 dark:border-slate-800"
              >
                <li className="list-disc pl-4">
                  {(item.id ? `${item.id} - ` : "") + (item.name ?? "")}
                  {item.duration ? ` - ${item.duration} min` : ""}
                </li>
              </div>
            ))}
          </ul>
        </Card>
      )}

      {flight.segments && flight.segments.length > 0 && (
        <Card className="space-y-3">
          <p className="text-base font-semibold">
            {t("flight.details.segments") ?? "Segments"}
          </p>
          <div className="space-y-3">
            {flight.segments.map((seg, idx) => (
              <div
                key={`${seg.flight_number ?? idx}`}
                className="rounded-md border border-slate-200 p-3 dark:border-slate-800"
              >
                <div className="flex flex-wrap items-center gap-2">
                  {seg.airline_logo && (
                    <img
                      src={seg.airline_logo}
                      alt={seg.airline ?? "Airline"}
                      className="h-6 w-6 rounded bg-white p-1"
                    />
                  )}
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {seg.airline ?? "-"}
                  </p>
                  {seg.flight_number && (
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {seg.flight_number}
                    </span>
                  )}
                </div>
                <div className="mt-2 grid gap-1 text-sm text-slate-600 dark:text-slate-300">
                  <div>
                    {(seg.departure_airport?.id ?? "-") +
                      " - " +
                      (seg.departure_airport?.name ?? "-")}
                    {seg.departure_airport?.time
                      ? ` - ${formatDateTime(seg.departure_airport.time)}`
                      : ""}
                  </div>
                  <div>
                    {(seg.arrival_airport?.id ?? "-") +
                      " - " +
                      (seg.arrival_airport?.name ?? "-")}
                    {seg.arrival_airport?.time
                      ? ` - ${formatDateTime(seg.arrival_airport.time)}`
                      : ""}
                  </div>
                  {seg.duration !== undefined && (
                    <div>
                      {t("flight.details.segmentDuration") ?? "Duration"}: {seg.duration}
                      {" "}min
                    </div>
                  )}
                  {seg.travel_class && (
                    <div>
                      {t("flight.details.segmentClass") ?? "Class"}: {seg.travel_class}
                    </div>
                  )}
                  {seg.airplane && (
                    <div>
                      {t("flight.details.segmentPlane") ?? "Aircraft"}: {seg.airplane}
                    </div>
                  )}
                </div>
                {seg.extensions && seg.extensions.length > 0 && (
                  <ul className="mt-2 space-y-1 text-xs text-slate-500 dark:text-slate-400">
                    {seg.extensions.map((ext, extIdx) => (
                      <li key={`${ext}-${extIdx}`} className="list-disc pl-4">
                        {ext}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

     
      
    </div>
  );
};
