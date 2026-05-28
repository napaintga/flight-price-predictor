import { useQuery } from "@tanstack/react-query";
import { fetchTicketLocalHistory, fetchTickets, type TicketFilters } from "./api";
import type { Ticket } from "../../shared/api/types";

export const useTickets = (filters?: TicketFilters) =>
  useQuery({
    queryKey: ["tickets", filters],
    queryFn: () => fetchTickets(filters)
  });

export const useTicketLocalHistory = (ticket?: Ticket) =>
  useQuery({
    queryKey: [
      "ticket-local-history",
      ticket?.id,
      ticket?.flightId,
      ticket?.departAt,
      ticket?.airline,
      ticket?.durationMinutes,
      ticket?.stops,
      ticket?.travelClass,
      ticket?.tripType,
      ticket?.passengers,
      ticket?.searchParams,
      ticket?.pricePaid
    ],
    queryFn: () => fetchTicketLocalHistory(ticket as Ticket),
    enabled: Boolean(
      ticket?.id &&
        ((ticket?.origin && ticket?.destination) || ticket?.searchParams)
    ),
    placeholderData: (previous) => previous,
    staleTime: 5 * 60_000
  });
