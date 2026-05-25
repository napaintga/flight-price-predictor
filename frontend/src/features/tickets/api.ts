import { http } from "../../shared/api/http";
import { endpoints } from "../../shared/api/endpoints";
import type { Ticket, TicketLocalHistoryResponse } from "../../shared/api/types";

export type TicketFilters = {
  flightId?: string;
  origin?: string;
  destination?: string;
  departFrom?: string;
  departTo?: string;
  sortBy?: "price_asc" | "price_desc" | "depart_asc" | "depart_desc";
};

export const fetchTickets = async (filters?: TicketFilters) => {
  const response = await http.get<Ticket[]>(endpoints.tickets, {
    params: filters
  });
  return response.data;
};

export const addTicket = async (ticket: Ticket) => {
  const response = await http.post<Ticket>(endpoints.tickets, ticket);
  return response.data;
};

export const removeTicket = async (ticketId: string) => {
  await http.delete(`${endpoints.tickets}/${encodeURIComponent(ticketId)}`);
};

export const fetchFavoriteTickets = async () => {
  const response = await http.get<Ticket[]>(endpoints.userFavorites);
  return Array.isArray(response.data) ? response.data : [];
};

export const addFavoriteTicket = async (ticket: Ticket) => {
  const response = await http.post<Ticket>(endpoints.userFavorites, ticket);
  return response.data;
};

export const removeFavoriteTicket = async (ticketId: string) => {
  await http.delete(endpoints.userFavoriteById(ticketId));
};

export const fetchTicketLocalHistory = async (ticket: Ticket) => {
  const response = await http.post<TicketLocalHistoryResponse>(
    endpoints.ticketLocalHistory,
    ticket
  );
  return response.data;
};
