import { Link } from "react-router-dom";
import type { Ticket } from "../../../shared/api/types";
import { Card } from "../../../shared/ui/Card";
import { formatCurrency, formatDateTime } from "../../../shared/utils/format";
import { useI18n } from "../../../shared/i18n";

type TicketTableProps = {
  tickets: Ticket[];
  title?: string;
  subtitle?: string;
  favoriteIds?: Set<string>;
  onToggleFavorite?: (ticket: Ticket) => void;
  onDelete?: (ticket: Ticket) => void;
  selectedTicketId?: string;
  onSelect?: (ticket: Ticket) => void;
};

export const TicketTable = ({
  tickets,
  title,
  subtitle,
  favoriteIds,
  onToggleFavorite,
  onDelete,
  selectedTicketId,
  onSelect
}: TicketTableProps) => {
  const { t } = useI18n();
  const showFavorite = Boolean(onToggleFavorite);
  const showDelete = Boolean(onDelete);
  const formatTripType = (value?: string) => {
    if (!value) return "-";
    if (value === "1") return t("search.roundTrip");
    if (value === "2") return t("search.oneWay");
    return value;
  };
  const formatTravelClass = (value?: string) => {
    if (!value) return "-";
    if (value === "1") return t("search.economy");
    if (value === "2") return t("search.premium");
    if (value === "3") return t("search.business");
    if (value === "4") return t("search.first");
    return value;
  };
  const getDetailsLink = (ticket: Ticket) => {
    if (!ticket.flightId) return null;
    const query = ticket.searchParams ? `?${ticket.searchParams}` : "";
    return `/flights/${ticket.flightId}${query}`;
  };

  return (
    <Card>
      <div className="mb-4">
        <p className="text-base font-semibold">
          {title ?? t("tickets.table.title")}
        </p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {subtitle ?? t("tickets.table.subtitle")}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-400">
            <tr>
              <th className="py-3 pl-3">{t("tickets.table.number")}</th>
              <th className="py-3 pl-3">{t("tickets.table.route")}</th>
              <th className="py-3 pl-3">{t("tickets.table.tripType")}</th>
              <th className="py-3 pl-3">{t("tickets.table.travelClass")}</th>
              <th className="py-3 pl-3 text-center">{t("tickets.table.passengers")}</th>
              <th className="py-3 pl-3">{t("tickets.table.depart")}</th>
              <th className="py-3 pl-3">{t("tickets.table.price")}</th>
              <th className="py-3 pl-3">{t("tickets.table.added")}</th>
              {showFavorite && <th className="py-3 pl-3">{t("tickets.table.favorite")}</th>}
              {showDelete && <th className="py-3 pl-3">{t("tickets.table.delete")}</th>}
            </tr>
          </thead>
          <tbody>
            {tickets.map((ticket, idx) => (
              <tr
                key={ticket.id}
                className={[
                  "border-t border-slate-100 even:bg-slate-50/70 hover:bg-slate-50 dark:border-slate-800 dark:even:bg-slate-900/40 dark:hover:bg-slate-800/60",
                  onSelect ? "cursor-pointer" : "",
                  selectedTicketId === ticket.id
                    ? "bg-sky-50/80 dark:bg-sky-950/30"
                    : ""
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => onSelect?.(ticket)}
              >
                <td className="py-3 pl-3 font-medium text-slate-800 dark:text-slate-100">
                  {idx + 1}
                </td>
                <td className="py-3 pl-3 text-slate-600 dark:text-slate-300">
                  {(() => {
                    const label =
                      ticket.origin && ticket.destination
                        ? `${ticket.originName ?? ticket.origin} -> ${ticket.destinationName ?? ticket.destination}`
                        : ticket.flightId ?? "-";
                    const link = getDetailsLink(ticket);
                    if (!link) return label;
                    return (
                      <Link
                        className="text-slate-900 hover:text-slate-700 hover:underline dark:text-slate-100 dark:hover:text-slate-200"
                        to={link}
                      >
                        {label}
                      </Link>
                    );
                  })()}
                </td>
                <td className="py-3 pl-3 text-slate-600 dark:text-slate-300">
                  {formatTripType(ticket.tripType)}
                </td>
                <td className="py-3 pl-3 text-slate-600 dark:text-slate-300">
                  {formatTravelClass(ticket.travelClass)}
                </td>
                <td className="py-3 pl-3 text-center text-slate-600 dark:text-slate-300">
                  {ticket.passengers ?? "-"}
                </td>
                <td className="py-3 pl-3 text-slate-600 dark:text-slate-300">
                  {formatDateTime(ticket.departAt)}
                </td>
                <td className="py-3 pl-3 text-slate-600 dark:text-slate-300">
                  {formatCurrency(ticket.pricePaid, ticket.currency || "USD")}
                </td>
                <td className="py-3 pl-3 text-slate-600 dark:text-slate-300">
                  {formatDateTime(ticket.createdAt)}
                </td>
                {showFavorite && (
                  <td className="py-3 pl-3">
                    <button
                      type="button"
                      className="text-lg text-amber-500"
                      aria-label={t("tickets.table.favorite")}
                      aria-pressed={favoriteIds?.has(ticket.id) ?? false}
                      title={
                        favoriteIds?.has(ticket.id)
                          ? t("tickets.favorite.remove")
                          : t("tickets.favorite.add")
                      }
                      onClick={(event) => {
                        event.stopPropagation();
                        onToggleFavorite?.(ticket);
                      }}
                    >
                      {favoriteIds?.has(ticket.id) ? "\u2605" : "\u2606"}
                    </button>
                  </td>
                )}
                {showDelete && (
                  <td className="py-3 pl-3">
                    <button
                      type="button"
                      className="text-sm font-semibold text-red-600 hover:text-red-500"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDelete?.(ticket);
                      }}
                    >
                      {t("tickets.table.delete")}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
