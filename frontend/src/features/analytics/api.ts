import { http } from "../../shared/api/http";
import { endpoints } from "../../shared/api/endpoints";
import type {
  ActualVsPredictedPoint,
  AnalyticsDashboard,
  Metrics
} from "../../shared/api/types";

export const fetchActualVsPredicted = async () => {
  const response = await http.get<ActualVsPredictedPoint[]>(
    endpoints.analyticsActualVsPred
  );
  return response.data;
};

export const fetchMetrics = async () => {
  const response = await http.get<Metrics>(endpoints.analyticsMetrics);
  return response.data;
};

export const fetchAnalyticsDashboard = async () => {
  const response = await http.get<AnalyticsDashboard>(
    endpoints.analyticsDashboard
  );
  return response.data;
};
