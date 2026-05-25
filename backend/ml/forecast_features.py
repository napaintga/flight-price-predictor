"""Selected columns for flight price forecasting."""

TARGET_COLUMN = "price"

FEATURE_IMPORTANCE_SOURCE = {
    "travel_class": 0.519,
    "stops": 0.153,
    "airline": 0.150,
    "days_to_departure": 0.038,
    "origin": 0.032,
    "duration_minutes": 0.028,
    "distance_km": 0.020,
    "depart_hour": 0.017,
    "destination": 0.014,
    "recent_price_trend_per_day": 0.010,
    "arrival_time": 0.006,
    "search_month": 0.006,
    "depart_dow": 0.006,
    "depart_month": 0.003,
}

NUMERIC_FEATURES = [
    "days_to_departure",
    "stops",
    "duration_minutes",
    "distance_km",
    "depart_hour",
    "recent_price_trend_per_day",
]

CATEGORICAL_FEATURES = [
    "travel_class",
    "airline",
    "origin",
    "destination",
    "arrival_time",
    "search_month",
    "depart_dow",
    "depart_month",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES

REMOVED_FEATURES = [
    "flight_id",
    "departure_date",
    "departure_time",
    "passengers_total",
    "trip_type",
    "origin_type",
    "destination_type",
    "depart_is_weekend",
    "depart_season",
    "search_dow",
    "search_is_weekend",
    "search_season",
    "price_per_km",
    "price_per_hour",
    "revenue_proxy",
    "price_segment",
]

FEATURE_SELECTION_NOTES = [
    "Keep depart_hour instead of departure_time because depart_hour is more precise.",
    "Keep depart_dow instead of depart_is_weekend because weekend is derived from day of week.",
    "Keep search_month instead of search_season because season is derived from month.",
    "Keep arrival_time because it describes arrival convenience, not departure time.",
    "Remove price-derived columns to avoid target leakage.",
    "Add recent_price_trend_per_day as a causal local-history feature based only on previous observations.",
]
