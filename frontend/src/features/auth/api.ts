import { http } from "../../shared/api/http";
import { endpoints } from "../../shared/api/endpoints";

export type AuthUser = {
  id: string;
  email: string;
  createdAt?: string;
};

export type AuthResponse = {
  token: string;
  expiresAt?: string;
  user: AuthUser;
};

export const login = async (payload: {
  email: string;
  password: string;
}): Promise<AuthResponse> => {
  const { data } = await http.post<AuthResponse>(endpoints.authLogin, payload);
  return data;
};

export const register = async (payload: {
  email: string;
  password: string;
}): Promise<AuthResponse> => {
  const { data } = await http.post<AuthResponse>(endpoints.authRegister, payload);
  return data;
};

export const getMe = async (): Promise<AuthUser> => {
  const { data } = await http.get<{ user: AuthUser }>(endpoints.authMe);
  return data.user;
};

export const logout = async (): Promise<void> => {
  await http.post(endpoints.authLogout);
};
