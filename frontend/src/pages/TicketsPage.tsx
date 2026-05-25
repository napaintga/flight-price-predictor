import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  TicketFilters as TicketFiltersComponent
} from "../features/tickets/components/TicketFilters";
import { TicketPredictionAnalysisPanel } from "../features/tickets/components/TicketPredictionAnalysisPanel";
import { TicketTable } from "../features/tickets/components/TicketTable";
import { useTicketLocalHistory } from "../features/tickets/hooks";
import {
  addTicket,
  addFavoriteTicket,
  fetchTickets,
  fetchFavoriteTickets,
  removeFavoriteTicket,
  removeTicket,
  type TicketFilters
} from "../features/tickets/api";
import type { FlightDetailsParams } from "../features/flight-details/api";
import { fetchFlightById } from "../features/flight-details/api";
import type { Ticket } from "../shared/api/types";
import { Card } from "../shared/ui/Card";
import { useI18n } from "../shared/i18n";
import { getAuthSnapshot, onAuthChange } from "../features/auth/session";

export const TicketsPage = () => {
  const { t } = useI18n();
  const FAVORITES_KEY = "ticket-favorites";
  const LOCAL_TICKETS_KEY = "local-tickets";
  const [auth, setAuth] = useState(getAuthSnapshot());
  const isLoggedIn = Boolean(auth.token);
  const [searchParams] = useSearchParams();
  const paramFlightId = searchParams.get("flightId") ?? undefined;
  const [filters, setFilters] = useState<TicketFilters>({});
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [favorites, setFavorites] = useState<Ticket[]>([]);
  const [localTickets, setLocalTickets] = useState<Ticket[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string>();
  const favoriteIds = useMemo(
    () => new Set(favorites.map((ticket) => ticket.id)),
    [favorites]
  );
  const filteredLocalTickets = useMemo(() => {
    const parseFilterDate = (value?: string, endOfDay: boolean = false) => {
      if (!value) return undefined;
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return undefined;
      if (endOfDay) {
        date.setHours(23, 59, 59, 999);
      }
      return date;
    };
    let result = localTickets;
    if (filters.flightId) {
      const needle = filters.flightId.toLowerCase();
      result = result.filter((ticket) =>
        (ticket.flightId ?? "").toLowerCase().includes(needle)
      );
    }
    if (filters.origin) {
      const needle = filters.origin.toLowerCase();
      result = result.filter((ticket) =>
        (ticket.origin ?? "").toLowerCase().includes(needle) ||
        (ticket.originName ?? "").toLowerCase().includes(needle)
      );
    }
    if (filters.destination) {
      const needle = filters.destination.toLowerCase();
      result = result.filter((ticket) =>
        (ticket.destination ?? "").toLowerCase().includes(needle) ||
        (ticket.destinationName ?? "").toLowerCase().includes(needle)
      );
    }
    const fromDate = parseFilterDate(filters.departFrom);
    if (fromDate) {
      result = result.filter((ticket) => {
        const depart = new Date(ticket.departAt ?? "");
        return !Number.isNaN(depart.getTime()) && depart >= fromDate;
      });
    }
    const toDate = parseFilterDate(filters.departTo, true);
    if (toDate) {
      result = result.filter((ticket) => {
        const depart = new Date(ticket.departAt ?? "");
        return !Number.isNaN(depart.getTime()) && depart <= toDate;
      });
    }
    if (filters.sortBy) {
      const parsePrice = (value?: number) =>
        typeof value === "number" ? value : Number.POSITIVE_INFINITY;
      const parseDepart = (fallback: number, value?: string) => {
        const dt = new Date(value ?? "");
        return Number.isNaN(dt.getTime()) ? fallback : dt.getTime();
      };
      const sorted = [...result];
      sorted.sort((a, b) => {
        switch (filters.sortBy) {
          case "price_asc":
            return parsePrice(a.pricePaid) - parsePrice(b.pricePaid);
          case "price_desc":
            return parsePrice(b.pricePaid) - parsePrice(a.pricePaid);
          case "depart_asc":
            return (
              parseDepart(Number.POSITIVE_INFINITY, a.departAt) -
              parseDepart(Number.POSITIVE_INFINITY, b.departAt)
            );
          case "depart_desc":
            return (
              parseDepart(Number.NEGATIVE_INFINITY, b.departAt) -
              parseDepart(Number.NEGATIVE_INFINITY, a.departAt)
            );
          default:
            return 0;
        }
      });
      return sorted;
    }
    return result;
  }, [localTickets, filters]);
  const selectedTicket = useMemo(
    () =>
      filteredLocalTickets.find((ticket) => ticket.id === selectedTicketId) ??
      filteredLocalTickets[0],
    [filteredLocalTickets, selectedTicketId]
  );
  const selectedHistoryQuery = useTicketLocalHistory(selectedTicket);

  useEffect(() => {
    if (paramFlightId && !filters.flightId) {
      setFilters((prev) => ({ ...prev, flightId: paramFlightId }));
    }
  }, [paramFlightId, filters.flightId]);

  useEffect(() => {
    if (filteredLocalTickets.length === 0) {
      setSelectedTicketId(undefined);
      return;
    }
    if (!selectedTicketId || !filteredLocalTickets.some((ticket) => ticket.id === selectedTicketId)) {
      setSelectedTicketId(filteredLocalTickets[0].id);
    }
  }, [filteredLocalTickets, selectedTicketId]);

  useEffect(() => {
    const unsubscribe = onAuthChange(() => {
      setAuth(getAuthSnapshot());
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (isLoggedIn) {
      let cancelled = false;
      fetchTickets()
        .then((items) => {
          if (!cancelled) setLocalTickets(items);
        })
        .catch(() => {
          if (!cancelled) setLocalTickets([]);
        });
      return () => {
        cancelled = true;
      };
    }

    try {
      const raw = localStorage.getItem(LOCAL_TICKETS_KEY);
      setLocalTickets(raw ? (JSON.parse(raw) as Ticket[]) : []);
    } catch {
      setLocalTickets([]);
    }
  }, [isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) {
      try {
        const raw = localStorage.getItem(FAVORITES_KEY);
        setFavorites(raw ? (JSON.parse(raw) as Ticket[]) : []);
      } catch {
        setFavorites([]);
      }
      return;
    }

    let cancelled = false;
    fetchFavoriteTickets()
      .then((items) => {
        if (!cancelled) setFavorites(items);
      })
      .catch(() => {
        if (!cancelled) setFavorites([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isLoggedIn]);

  useEffect(() => {
    if (isLoggedIn) return;
    try {
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
    } catch {
      // ignore storage errors
    }
  }, [favorites, isLoggedIn]);

  useEffect(() => {
    if (isLoggedIn) return;
    try {
      localStorage.setItem(LOCAL_TICKETS_KEY, JSON.stringify(localTickets));
    } catch {
      // ignore storage errors
    }
  }, [localTickets, isLoggedIn]);

  const toggleFavorite = async (ticket: Ticket) => {
    const exists = favorites.some((item) => item.id === ticket.id);
    if (!isLoggedIn) {
      setFavorites((prev) => {
        if (exists) {
          return prev.filter((item) => item.id !== ticket.id);
        }
        return [...prev, ticket];
      });
      return;
    }

    setFavorites((prev) => {
      if (exists) {
        return prev.filter((item) => item.id !== ticket.id);
      }
      return [ticket, ...prev];
    });
    try {
      if (exists) {
        await removeFavoriteTicket(ticket.id);
      } else {
        await addFavoriteTicket(ticket);
      }
    } catch {
      fetchFavoriteTickets()
        .then((items) => setFavorites(items))
        .catch(() => setFavorites([]));
    }
  };

  const deleteTicket = (ticket: Ticket) => {
    setLocalTickets((prev) => prev.filter((item) => item.id !== ticket.id));
    if (favoriteIds.has(ticket.id)) {
      setFavorites((prev) => prev.filter((item) => item.id !== ticket.id));
      if (isLoggedIn) {
        removeFavoriteTicket(ticket.id).catch(() => {
          // ignore server errors
        });
      }
    }
    if (isLoggedIn) {
      removeTicket(ticket.id).catch(() => {
        // ignore server errors
      });
    }
  };
  const parsePriceNumber = (value: number | string | undefined) => {
    if (value === undefined || value === null) return undefined;
    if (typeof value === "number") return value;
    const parsed = Number(String(value).replace(/[^\d.]/g, ""));
    return Number.isNaN(parsed) ? undefined : parsed;
  };
  const buildTicketParams = (ticket: Ticket): FlightDetailsParams | null => {
    if (!ticket.searchParams) return null;
    const params = Object.fromEntries(
      new URLSearchParams(ticket.searchParams)
    ) as Record<string, string>;
    if (!params.departure_id || !params.arrival_id || !params.outbound_date) {
      return null;
    }
    return { ...params, no_cache: "true" };
  };
  const refreshTickets = async () => {
    if (localTickets.length === 0) return;
    setIsRefreshing(true);
    try {
      const updated = await Promise.all(
        localTickets.map(async (ticket) => {
          if (!ticket.flightId) return ticket;
          const params = buildTicketParams(ticket);
          if (!params) return ticket;
          try {
            const flight = await fetchFlightById(ticket.flightId, params);
            const pricePaid = parsePriceNumber(flight.price);
            return {
              ...ticket,
              ...(pricePaid !== undefined ? { pricePaid } : {})
            };
          } catch {
            return ticket;
          }
        })
      );
      setLocalTickets(updated);
      setFavorites((prev) =>
        prev.map((item) => {
          const match = updated.find(
            (ticket) =>
              ticket.id === item.id || ticket.flightId === item.flightId
          );
          return match ?? item;
        })
      );
      if (isLoggedIn) {
        await Promise.all(
          updated.map(async (ticket) => {
            try {
              await addTicket(ticket);
            } catch {
              // ignore backend errors
            }
          })
        );
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{t("tickets.title")}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t("tickets.subtitle")}
          </p>
        </div>
        <button
          type="button"
          className="text-sm font-semibold text-blue-600 disabled:opacity-60"
          onClick={refreshTickets}
          disabled={isRefreshing || localTickets.length === 0}
        >
          {isRefreshing
            ? t("tickets.refreshing") ?? "Refreshing..."
            : t("tickets.refresh") ?? "Refresh prices"}
        </button>
      </div>
      {favorites.length > 0 ? (
        <TicketTable
          tickets={favorites}
          title={t("tickets.favorites.title")}
          subtitle={t("tickets.favorites.subtitle")}
          favoriteIds={favoriteIds}
          onToggleFavorite={toggleFavorite}
        />
      ) : (
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t("tickets.favorites.empty")}
          </p>
        </Card>
      )}
      <TicketFiltersComponent defaultValues={filters} onApply={setFilters} />
      {filteredLocalTickets.length === 0 && (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t("tickets.empty")}
        </p>
      )}
      {filteredLocalTickets.length > 0 && (
        <>
          <TicketPredictionAnalysisPanel
            ticket={selectedTicket}
            history={selectedHistoryQuery.data}
            isLoading={selectedHistoryQuery.isLoading}
            isError={selectedHistoryQuery.isError}
          />
          <TicketTable
            tickets={filteredLocalTickets}
            favoriteIds={favoriteIds}
            onToggleFavorite={toggleFavorite}
            onDelete={deleteTicket}
            selectedTicketId={selectedTicket?.id}
            onSelect={(ticket) => setSelectedTicketId(ticket.id)}
          />
        </>
      )}
    </div>
  );
};
