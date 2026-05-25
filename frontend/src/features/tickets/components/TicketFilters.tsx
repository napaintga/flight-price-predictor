import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { TicketFilters as TicketFiltersFields }  from "../api";
import { Button } from "../../../shared/ui/Button";
import { Input } from "../../../shared/ui/Input";
import { useI18n } from "../../../shared/i18n";

const sortBySchema = z.preprocess(
  (value) => (value === "" ? undefined : value),
  z.enum(["price_asc", "price_desc", "depart_asc", "depart_desc"]).optional()
);

const schema = z.object({
  flightId: z.string().optional(),
  origin: z.string().optional(),
  destination: z.string().optional(),
  departFrom: z.string().optional(),
  departTo: z.string().optional(),
  sortBy: sortBySchema
});

type FormValues = z.infer<typeof schema>;

type TicketFiltersProps = {
  defaultValues?: TicketFiltersFields;
  onApply: (filters: TicketFiltersFields) => void;
};

export const TicketFilters = ({
  defaultValues,
  onApply
}: TicketFiltersProps) => {
  const { t } = useI18n();
  const { register, handleSubmit } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues
  });

  const onSubmit = (values: FormValues) => {
    onApply({
      origin: values.origin?.trim() || undefined,
      destination: values.destination?.trim() || undefined,
      departFrom: values.departFrom || undefined,
      departTo: values.departTo || undefined,
      sortBy: values.sortBy
    });
  };

  return (
    <form
      className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-6 dark:border-slate-800 dark:bg-slate-900"
      onSubmit={handleSubmit(onSubmit)}
    >
      <Input placeholder={t("tickets.filters.origin")} {...register("origin")} />
      <Input placeholder={t("tickets.filters.destination")} {...register("destination")} />
      <Input type="date" {...register("departFrom")} />
      <Input type="date" {...register("departTo")} />
      <select
        {...register("sortBy")}
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      >
        <option value="">{t("tickets.filters.sort")}</option>
        <option value="price_asc">{t("tickets.filters.sort.priceAsc")}</option>
        <option value="price_desc">{t("tickets.filters.sort.priceDesc")}</option>
        <option value="depart_asc">{t("tickets.filters.sort.departAsc")}</option>
        <option value="depart_desc">{t("tickets.filters.sort.departDesc")}</option>
      </select>
      <Button type="submit" className="md:col-span-6">
        {t("tickets.filters.apply")}
      </Button>
    </form>
  );
};
