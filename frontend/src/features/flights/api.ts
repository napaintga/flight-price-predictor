import { http } from "../../shared/api/http";
import { endpoints } from "../../shared/api/endpoints";
import type { Flight, Prediction } from "../../shared/api/types";
import type { FlightSearchParams } from "./types";

const cleanParams = (params?: FlightSearchParams) => {
  if (!params) return undefined;

  const entries = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== ""
  );

  return entries.length > 0 ? Object.fromEntries(entries) : undefined;
};

/** Backend may return either Flight[] OR { flights: Flight[], ...meta } */
type FlightsResponse =
  | Flight[]
  | {
      flights: Flight[];
      asOf?: string;
      fromCache?: boolean;
      snapshotId?: number | null;
      searchKey?: string;
      count?: number;
    };

const extractFlightsArray = (data: FlightsResponse): Flight[] => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray((data as any).flights)) return (data as any).flights;
  return [];
};

export const fetchFlights = async (params?: FlightSearchParams): Promise<Flight[]> => {
  const cleaned = cleanParams(params);

  const response = await http.get<FlightsResponse>(endpoints.flights, {
    params: cleaned,
  });

  return extractFlightsArray(response.data);
};

export type SearchHistoryItem = {
  id: number;
  params: Record<string, unknown>;
  createdAt: string;
};

export const fetchSearchHistory = async (
  limit: number = 6
): Promise<SearchHistoryItem[]> => {
  const response = await http.get<SearchHistoryItem[]>(
    endpoints.userSearchHistory,
    { params: { limit } }
  );
  return Array.isArray(response.data) ? response.data : [];
};

/**
 * Details endpoint:
 * - If your backend is /api/flights/{flight_uid} => flightIdOrUid is uid
 * - If backend also supports /api/flights/{flight_id} => flightIdOrUid can be "0", "1", ...
 *
 * IMPORTANT: details requires the SAME search params in query string (departure_id, arrival_id, outbound_date, etc)
 */
export const fetchFlightDetails = async (
  flightIdOrUid: string,
  params?: FlightSearchParams
): Promise<Flight> => {
  const cleaned = cleanParams(params);

  const response = await http.get<Flight>(
    `${endpoints.flights}/${encodeURIComponent(flightIdOrUid)}`,
    { params: cleaned }
  );

  return response.data;
};

/**
 * Price history:
 * backend expected: GET /api/flights/{id_or_uid}/price-history?departure_id=...&arrival_id=...&outbound_date=...
 * returns: [{ ts: string, price: number }, ...]
 */
export type PricePoint = { ts: string; price: number };

export const fetchFlightPriceHistory = async (
  flightIdOrUid: string,
  params?: FlightSearchParams
): Promise<PricePoint[]> => {
  const cleaned = cleanParams(params);

  const response = await http.get<PricePoint[]>(
    `${endpoints.flights}/${encodeURIComponent(flightIdOrUid)}/price-history`,
    { params: cleaned }
  );

  return Array.isArray(response.data) ? response.data : [];
};

/**
 * Prediction:
 * backend expected: GET /api/predictions/flight/{id_or_uid}
 * If your backend doesn't have it yet, it will 404 (you can add a stub endpoint)
 */
export type PredictionResponse = Prediction & {
  flightUid?: string;
  confidence?: number | null;
  model?: string;
  updatedAt?: string;
};

export const fetchFlightPrediction = async (
  flightIdOrUid: string,
  params?: FlightSearchParams
): Promise<PredictionResponse> => {
  const cleaned = cleanParams(params);

  const response = await http.get<PredictionResponse>(
    `${endpoints.predictions}/flight/${encodeURIComponent(flightIdOrUid)}`,
    { params: cleaned }
  );
  return response.data;
};
