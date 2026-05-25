import axios from "axios";
import { env } from "../../app/config/env";

export const http = axios.create({
  baseURL: env.apiBaseUrl,
  headers: {
    "Content-Type": "application/json"
  }
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  }
);

export const mlHttp = axios.create({
  baseURL: env.mlBaseUrl,
  headers: {
    "Content-Type": "application/json"
  }
});

mlHttp.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

mlHttp.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  }
);
