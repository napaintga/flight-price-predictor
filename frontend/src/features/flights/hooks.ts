import { useQuery } from "@tanstack/react-query";
import { fetchFlights, fetchFlightDetails, fetchFlightPriceHistory, fetchFlightPrediction } from "./api";
import type { FlightSearchParams } from "./types";

const canSearchFlights = (params?: FlightSearchParams) => {
  if (!params) return false;
  return Boolean(params.departure_id && params.arrival_id && params.outbound_date);
};

export const useFlights = (params?: FlightSearchParams) =>
  useQuery({
    queryKey: ["flights", params?.departure_id, params?.arrival_id, params?.outbound_date, params],
    queryFn: () => fetchFlights(params),
    enabled: canSearchFlights(params),
    staleTime: 60_000,
  });

/**
 * Details by flight identifier (uid or id depending on your API).
 * Must be called unconditionally in component, but request can be disabled via enabled flag.
 */
export const useFlightDetails = (
  flightIdOrUid: string,
  params?: FlightSearchParams,
  options?: { enabled?: boolean }
) =>
  useQuery({
    queryKey: ["flight-details", flightIdOrUid, params?.departure_id, params?.arrival_id, params?.outbound_date, params],
    queryFn: () => fetchFlightDetails(flightIdOrUid, params),
    enabled: (options?.enabled ?? true) && Boolean(flightIdOrUid) && canSearchFlights(params),
    staleTime: 60_000,
  });

export const useFlightPriceHistory = (
  flightIdOrUid: string,
  params?: FlightSearchParams,
  options?: { enabled?: boolean }
) =>
  useQuery({
    queryKey: ["flight-price-history", flightIdOrUid, params?.departure_id, params?.arrival_id, params?.outbound_date, params],
    queryFn: () => fetchFlightPriceHistory(flightIdOrUid, params),
    enabled: (options?.enabled ?? true) && Boolean(flightIdOrUid) && canSearchFlights(params),
    staleTime: 60_000,
  });

export const useFlightPrediction = (
  flightIdOrUid: string,
  params?: FlightSearchParams,
  options?: { enabled?: boolean }
) =>
  useQuery({
    queryKey: ["flight-prediction", flightIdOrUid, params],
    queryFn: () => fetchFlightPrediction(flightIdOrUid, params),
    enabled: (options?.enabled ?? true) && Boolean(flightIdOrUid),
    staleTime: 60_000,
  });
