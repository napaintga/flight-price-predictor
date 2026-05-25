import { useState } from "react";
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import type { Flight } from "../../../shared/api/types";
import { Card } from "../../../shared/ui/Card";
import { formatCurrency, formatDateTime } from "../../../shared/utils/format";
import { useI18n } from "../../../shared/i18n";
import type { Ticket } from "../../../shared/api/types";
import type { FlightSearchParams } from "../types";
import { useFlightPrediction } from "../hooks";
import { addTicket, removeTicket } from "../../tickets/api";
import { getAuthSnapshot, onAuthChange } from "../../auth/session";

export const FlightCard = ({
  flight,
  predictionParams,
  enablePrediction = false,
  savedIds,
  onTicketSavedChange
}: {
  flight: Flight;
  predictionParams?: FlightSearchParams;
  enablePrediction?: boolean;
  savedIds?: Set<string>;
  onTicketSavedChange?: (ticket: Ticket, nextSaved: boolean) => void;
}) => {
  const location = useLocation();
  const { t } = useI18n();
  const baseId = String(flight.uid ?? flight.id ?? "flight");
  const ticketId = `L-${baseId}`;
  const [auth, setAuth] = useState(getAuthSnapshot());
  const isLoggedIn = Boolean(auth.token);
  const firstSegment = flight.segments?.[0];
  const lastSegment = flight.segments?.[flight.segments?.length ? flight.segments.length - 1 : 0];
  const displayPrice =
    typeof flight.price === "number"
      ? formatCurrency(flight.price, flight.currency || "USD")
      : String(flight.price);
  const currentPrice =
    typeof flight.price === "number"
      ? flight.price
      : Number(String(flight.price).replace(/[^\d.]/g, ""));
  const predictionQuery = useFlightPrediction(baseId, predictionParams, {
    enabled: enablePrediction && Boolean(baseId)
  });
  const predictedPrice = predictionQuery.data?.predictedPrice;
  const hasPrediction =
    typeof predictedPrice === "number" &&
    Number.isFinite(predictedPrice) &&
    Number.isFinite(currentPrice);
  const isPriceGrowing = hasPrediction ? predictedPrice > currentPrice : false;
  const recommendationText = hasPrediction
    ? isPriceGrowing
      ? t("prediction.buyShort")
      : t("prediction.waitShort")
    : undefined;
  const searchParams = new URLSearchParams(location.search);
  const searchParamsString = searchParams.toString();
  const tripType = searchParams.get("type") ?? undefined;
  const travelClass = searchParams.get("travel_class") ?? undefined;
  const parseCount = (value: string | null) => {
    if (!value) return 0;
    const parsed = Number(value);
    return Number.isNaN(parsed) ? 0 : parsed;
  };
  const passengersCount =
    parseCount(searchParams.get("adults")) +
    parseCount(searchParams.get("children")) +
    parseCount(searchParams.get("infants_in_seat")) +
    parseCount(searchParams.get("infants_on_lap"));

  const LOCAL_TICKETS_KEY = "local-tickets";
  const [isSaved, setIsSaved] = useState(() => {
    if (savedIds) {
      return savedIds.has(ticketId) || savedIds.has(baseId);
    }
    try {
      const raw = localStorage.getItem(LOCAL_TICKETS_KEY);
      const existing = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(existing)) return false;
      return existing.some(
        (item) => item?.id === ticketId || item?.flightId === baseId
      );
    } catch {
      return false;
    }
  });

  useEffect(() => {
    const unsubscribe = onAuthChange(() => {
      setAuth(getAuthSnapshot());
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (!savedIds) return;
    setIsSaved(savedIds.has(ticketId) || savedIds.has(baseId));
  }, [savedIds, ticketId, baseId]);

  const handleToggleTicket = async () => {
    const now = new Date();
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
      tripType,
      travelClass,
      passengers: passengersCount > 0 ? passengersCount : undefined,
      searchParams: searchParamsString || undefined,
      createdAt: now.toISOString(),
      ...(pricePaid !== undefined ? { pricePaid } : {})
    };

    if (isLoggedIn) {
      const nextSaved = !isSaved;
      setIsSaved(nextSaved);
      onTicketSavedChange?.(ticket, nextSaved);
      try {
        if (nextSaved) {
          await addTicket(ticket);
        } else {
          await removeTicket(ticket.id);
        }
      } catch {
        const rollback = !nextSaved;
        setIsSaved(rollback);
        onTicketSavedChange?.(ticket, rollback);
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
        ? list.filter(
            (item) => item?.id !== ticketId && item?.flightId !== baseId
          )
        : [ticket, ...list];
      localStorage.setItem(LOCAL_TICKETS_KEY, JSON.stringify(next));
      setIsSaved(!alreadySaved);
    } catch {
      // ignore storage errors
    }
  };

  return (
    <Card className="flex flex-row gap-4 items-start">
      {/* Logo */}
      <div className="w-16 h-16 flex items-center justify-center flex-shrink-0 mt-3 dark:bg-slate-100 rounded-md">
        {flight.airline_logo ? (
          <img
            src={flight.airline_logo}
            alt={flight.airline || "Airline logo"}
            className="max-w-full max-h-full object-contain"
          />
        ) : (
          <div className="w-full h-full bg-slate-200 dark:bg-slate-800 flex items-center justify-center text-xs text-slate-500">
            No logo
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex w-full flex-col gap-3">
        <div className="flex justify-between gap-3">
          <div>
          {flight.best && (
            <div className="inline-block bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full mb-2">
              Best price
            </div>
          )}

          <div className="flex items-center gap-3">
            <p className="text-lg font-semibold">
              {flight.origin} - {flight.destination}
            </p>

            <span className="text-sm font-medium text-slate-800 dark:text-slate-100">
              {displayPrice}
            </span>
            {recommendationText && (
              <span
                className={[
                  "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold",
                  isPriceGrowing
                    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200"
                    : "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-200"
                ].join(" ")}
                title={formatCurrency(predictedPrice, flight.currency || "USD")}
              >
                <span aria-hidden="true">{isPriceGrowing ? "↑" : "↓"}</span>
                <span>{recommendationText}</span>
              </span>
            )}
          </div>

          <p className="text-sm text-slate-500 mt-1">
            {formatDateTime(flight.departAt)}
          </p>
          </div>

          <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleToggleTicket}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 text-base font-semibold text-emerald-700 transition hover:border-emerald-300 hover:text-emerald-600 dark:border-slate-700 dark:text-emerald-300"
            title={isSaved ? t("flights.removeTicket") : t("flights.addTicket")}
            aria-label={isSaved ? t("flights.removeTicket") : t("flights.addTicket")}
          >
            {isSaved ? "-" : "+"}
          </button>
          <Link
            to={`/flights/${flight.uid ?? flight.id}${location.search}`}
            className="text-sm font-semibold text-blue-950 hover:text-sky-800 whitespace-nowrap dark:text-blue-100 dark:hover:text-sky-100"
          >
            View details
          </Link>
          </div>
        </div>

      </div>
    </Card>
  );
};
