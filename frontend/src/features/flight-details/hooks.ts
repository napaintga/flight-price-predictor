import { useQuery } from "@tanstack/react-query";
import {
  fetchFlightById,
  fetchPrediction,
  fetchPriceInsights,
  fetchFlightPriceSnapshots,
  fetchRoutePriceHistory,
  type FlightDetailsParams,
  type PriceHistoryParams,
  type PriceInsightsParams
} from "./api";

export const useFlightDetails = (id?: string, params?: FlightDetailsParams) =>
  useQuery({
    queryKey: ["flight", id, params],
    queryFn: () => fetchFlightById(id ?? "", params),
    enabled: Boolean(
      id &&
        params?.departure_id &&
        params?.arrival_id &&
        params?.outbound_date
    )
  });


export const usePriceHistory = (id?: string, params?: PriceHistoryParams) =>
  useQuery({
    queryKey: ["flight-history", id, params],
    queryFn: () => fetchRoutePriceHistory(id ?? "", params as PriceHistoryParams),
    enabled: Boolean(
      id &&
        params?.departure_id &&
        params?.arrival_id &&
        params?.outbound_date
    )
  });

export const usePrediction = (id?: string, params?: FlightDetailsParams) =>
  useQuery({
    queryKey: ["flight-prediction", id, params],
    queryFn: () => fetchPrediction(id ?? "", params),
    enabled: Boolean(id)
  });

export const usePriceInsights = (params?: PriceInsightsParams) =>
  useQuery({
    queryKey: ["price-insights", params],
    queryFn: () => fetchPriceInsights(params as PriceInsightsParams),
    enabled: Boolean(params)
  });

export const useFlightPriceSnapshots = (id?: string, params?: FlightDetailsParams) =>
  useQuery({
    queryKey: ["flight-price-snapshots", id, params],
    queryFn: () => fetchFlightPriceSnapshots(id ?? "", params as FlightDetailsParams),
    enabled: Boolean(
      id &&
        params?.departure_id &&
        params?.arrival_id &&
        params?.outbound_date
    )
  });
