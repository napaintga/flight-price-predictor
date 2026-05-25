export const env = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000",
  mlBaseUrl: import.meta.env.VITE_ML_BASE_URL ?? "http://localhost:8000",
  enableDirectMl: import.meta.env.VITE_ENABLE_DIRECT_ML === "true"
};
