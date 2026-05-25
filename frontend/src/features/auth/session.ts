import type { AuthUser } from "./api";

const TOKEN_KEY = "token";
const USER_KEY = "auth-user";
const EVENT_NAME = "auth:changed";
const PERSONAL_KEYS = [
  "local-tickets",
  "ticket-favorites",
  "flight-recent-searches",
  "flight-last-search"
];

const notify = () => {
  window.dispatchEvent(new Event(EVENT_NAME));
};

export const getToken = () => localStorage.getItem(TOKEN_KEY);

export const getStoredUser = (): AuthUser | null => {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
};

export const setSession = (token: string, user: AuthUser) => {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  notify();
};

export const clearSession = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  PERSONAL_KEYS.forEach((key) => localStorage.removeItem(key));
  notify();
};

export const getAuthSnapshot = () => ({
  token: getToken(),
  user: getStoredUser()
});

export const onAuthChange = (handler: () => void) => {
  window.addEventListener(EVENT_NAME, handler);
  return () => window.removeEventListener(EVENT_NAME, handler);
};
