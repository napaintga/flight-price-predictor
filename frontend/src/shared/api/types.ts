export type Flight = {
  id: number;
  uid: string;

  origin: string;
  destination: string;
  departAt: string;
  arrivalAt: string;

  airline?: string | null;
  airline_logo?: string | null;

  price: number | string;
  currency: string;

  duration: string;
  total_duration_minutes?: number | null;
  stops: number;
  best: boolean;
  type: string;

  booking_token?: string | null;
  extensions?: string[];
  layovers?: Array<{
    duration?: number;
    name?: string;
    id?: string;
  }>;
  carbon_emissions?: {
    this_flight?: number;
    typical_for_this_route?: number;
    difference_percent?: number;
  };
  segments?: Array<{
    airline?: string;
    airline_logo?: string;
    flight_number?: string;
    travel_class?: string;
    duration?: number;
    legroom?: string;
    airplane?: string;
    extensions?: string[];
    departure_airport?: {
      name?: string;
      id?: string;
      time?: string;
    };
    arrival_airport?: {
      name?: string;
      id?: string;
      time?: string;
    };
  }>;

  // meta:
  asOf: string;
  fromCache: boolean;
  searchKey: string;
  snapshotId: number | null;
};


export type PricePoint = { ts: string; price: number };

export type PriceSnapshot = {
  asOf: string;
  price: number | string;
  currency?: string;
  snapshotId?: number | null;
  source?: "db" | "local_csv" | string;
  sourceFile?: string;
  matchMode?: string;
};

export type PriceInsights = {
  lowest_price?: number;
  price_level?: string;
  typical_price_range?: number[];
  price_history?: [number, number][];
  [key: string]: unknown;
};

export type PriceInsightsResponse = {
  price_insights?: PriceInsights;
  currency?: string;
  search_parameters?: Record<string, unknown>;
  flights_count?: {
    best?: number;
    other?: number;
  };
};


export type Prediction = {
  flightId: string;
  predictedPrice: number | null;
  lower?: number;
  upper?: number;
  currency?: string;
  modelName?: string;
  modelMae?: number;
  modelRmse?: number;
  modelR2?: number;
  createdAt: string;
  horizonDays?: number | null;
  source?: string;
  predictions?: PredictionOption[];
};

export type PredictionOption = {
  modelName: string;
  model?: string;
  predictedPrice: number | null;
  lower?: number;
  upper?: number;
  currency?: string;
  modelMae?: number | null;
  modelRmse?: number | null;
  modelR2?: number | null;
};

export type Ticket = {
  id: string;
  flightId: string;
  userId?: string;
  pricePaid?: number;
  currency?: string;
  origin?: string;
  destination?: string;
  originName?: string;
  destinationName?: string;
  airline?: string;
  departAt?: string;
  duration?: string;
  durationMinutes?: number;
  stops?: number;
  tripType?: string;
  travelClass?: string;
  passengers?: number;
  searchParams?: string;
  createdAt: string;
};

export type TicketHistoryPoint = {
  ts: string;
  price: number;
  minPrice?: number;
  maxPrice?: number;
  sampleCount?: number;
  sourceDate?: string;
  sourceFile?: string;
  matchMode?: string;
  airlines?: string[];
  lower?: number;
  upper?: number;
  isForecast?: boolean;
};

export type TicketHistoryForecastMeta = {
  source: string;
  modelName?: string;
  generatedAt: string;
  horizonDays?: number;
};

export type TicketHistorySummary = {
  filesScanned: number;
  matchedSnapshots: number;
  matchedDays: number;
  availableDays: string[];
  departureDate?: string | null;
  latestPrice?: number | null;
  minPrice?: number | null;
  maxPrice?: number | null;
  averagePrice?: number | null;
  lastCapturedAt?: string | null;
};

export type TicketLocalHistoryResponse = {
  ticketId?: string;
  currency: string;
  actual: TicketHistoryPoint[];
  forecast: TicketHistoryPoint[];
  forecastMeta?: TicketHistoryForecastMeta | null;
  summary: TicketHistorySummary;
  matching: {
    origin?: string | null;
    destination?: string | null;
    travelClass?: string | null;
    tripType?: string | null;
    passengers?: number | null;
    strategy?: string | null;
  };
};

export type ActualVsPredictedPoint = {
  ts: string;
  actual: number;
  predicted: number;
};

export type Metrics = {
  mae?: number;
  rmse?: number;
  mape?: number;
  r2?: number;
  modelName?: string;
  updatedAt?: string;
  rowsUsed?: number;
  trainRows?: number;
  testRows?: number;
  target?: string;
};

export type AnalyticsModelRow = {
  folder: string;
  modelName: string;
  mae?: number | null;
  rmse?: number | null;
  r2?: number | null;
  mape?: number | null;
  rowsUsed?: number | null;
  trainRows?: number | null;
  testRows?: number | null;
  target?: string;
  updatedAt?: string;
};

export type AnalyticsFeatureImportance = {
  feature: string;
  importance?: number | null;
  share?: number | null;
};

export type AnalyticsErrorGroup = {
  label: string;
  records: number;
  avgActual?: number | null;
  avgPredicted?: number | null;
  mae?: number | null;
  mape?: number | null;
  bias?: number | null;
};

export type AnalyticsRecommendationMix = {
  label: string;
  records: number;
  avgGapPct?: number | null;
  avgActual?: number | null;
};

export type AnalyticsInsight = {
  title: string;
  value: string;
  body: string;
};

export type AnalyticsDashboard = {
  sampleSize: number;
  modelRanking: AnalyticsModelRow[];
  featureImportance: AnalyticsFeatureImportance[];
  errorByPriceBucket: AnalyticsErrorGroup[];
  errorByTravelClass: AnalyticsErrorGroup[];
  errorByAirline: AnalyticsErrorGroup[];
  errorByRoute: AnalyticsErrorGroup[];
  recommendationMix: AnalyticsRecommendationMix[];
  summary: {
    avgActual?: number | null;
    avgPredicted?: number | null;
    medianError?: number | null;
    rowsAnalyzed?: number | null;
    modelsFound?: number | null;
  };
  insights: AnalyticsInsight[];
};
