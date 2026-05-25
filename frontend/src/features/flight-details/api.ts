import { endpoints } from "../../shared/api/endpoints";
import { http, mlHttp } from "../../shared/api/http";
import { env } from "../../app/config/env";
import type {
  Flight,
  Prediction,
  PriceInsightsResponse,
  PricePoint,
  PriceSnapshot
} from "../../shared/api/types";

export type FlightDetailsParams = {
  departure_id?: string;
  arrival_id?: string;
  outbound_date?: string;
  return_date?: string;
  currency?: string;
  hl?: string;
  type?: string;
  travel_class?: string;
  adults?: string;
  no_cache?: string;
};

export const fetchFlightById = async (id: string, params?: FlightDetailsParams) => {
  const response = await http.get<Flight>(endpoints.flightById(id), {
    params
  });
  return response.data;
};


export const fetchPriceHistory = async (id: string) => {
  const response = await http.get<PricePoint[]>(endpoints.flightHistory(id));
  return response.data;
};

export type PriceHistoryParams = {
  departure_id: string;
  arrival_id: string;
  outbound_date: string;
  return_date?: string;
  currency?: string;
  hl?: string;
  gl?: string;
  type?: string;
  travel_class?: string;
  adults?: string;
  no_cache?: string;
};

export const fetchRoutePriceHistory = async (
  id: string,
  params: PriceHistoryParams
) => {
  const response = await http.get<PricePoint[]>(endpoints.flightHistory(id), {
    params
  });
  return response.data;
};

export const fetchFlightPriceSnapshots = async (
  id: string,
  params: FlightDetailsParams
) => {
  const response = await http.get<PriceSnapshot[]>(
    endpoints.flightPriceSnapshots(id),
    { params }
  );
  return response.data;
};

export const fetchPrediction = async (id: string, params?: FlightDetailsParams) => {
  const client = env.enableDirectMl ? mlHttp : http;
  const response = await client.get<Prediction>(endpoints.predict(id), {
    params
  });
  return response.data;
};

export type PriceInsightsParams = {
  departure_id: string;
  arrival_id: string;
  outbound_date: string;
  return_date?: string;
  currency?: string;
  hl?: string;
  type?: string;
  travel_class?: string;
  adults?: string;
  no_cache?: string;
};

export const fetchPriceInsights = async (params: PriceInsightsParams) => {
  const response = await http.get<PriceInsightsResponse>(endpoints.priceInsights, {
    params
  });
  return response.data;
};
