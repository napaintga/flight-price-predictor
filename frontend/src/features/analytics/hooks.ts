import { useQuery } from "@tanstack/react-query";
import {
  fetchActualVsPredicted,
  fetchAnalyticsDashboard,
  fetchMetrics
} from "./api";

export const useActualVsPredicted = () =>
  useQuery({
    queryKey: ["analytics", "actual-vs-predicted"],
    queryFn: fetchActualVsPredicted,
    staleTime: 5 * 60_000
  });

export const useMetrics = () =>
  useQuery({
    queryKey: ["analytics", "metrics"],
    queryFn: fetchMetrics,
    staleTime: 5 * 60_000
  });

export const useAnalyticsDashboard = () =>
  useQuery({
    queryKey: ["analytics", "dashboard"],
    queryFn: fetchAnalyticsDashboard,
    staleTime: 5 * 60_000
  });
