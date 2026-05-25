import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "../../../shared/ui/Button";
import { Input } from "../../../shared/ui/Input";
import type { FlightSearchParams } from "../types";
import { searchAirports, type CountryMatch } from "../airports";
import { fetchSearchHistory } from "../api";
import { formatPassengers, useI18n } from "../../../shared/i18n";
import { getAuthSnapshot, onAuthChange } from "../../auth/session";

const emptyToUndefined = (value: unknown) => {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length === 0 ? undefined : trimmed;
  }
  return value;
};

const schema = z.object({
  departure_id: z.preprocess(emptyToUndefined, z.string().max(200).optional()),
  arrival_id: z.preprocess(emptyToUndefined, z.string().max(200).optional()),
  type: z.preprocess(emptyToUndefined, z.enum(["2"]).optional()),
  outbound_date: z.preprocess(emptyToUndefined, z.string().optional()),
  return_date: z.preprocess(emptyToUndefined, z.string().optional()),
  travel_class: z.preprocess(emptyToUndefined, z.enum(["1", "3"]).optional()),
  adults: z.preprocess(emptyToUndefined, z.string().optional())
});

type FormValues = z.infer<typeof schema>;

type FlightSearchFormProps = {
  defaultValues?: FlightSearchParams;
  onSearch: (params: FlightSearchParams) => void;
};

type RecentSearch = {
  key: string;
  params: FlightSearchParams;
};

type SelectionLabel = {
  label: string;
  value: string;
};

const RECENT_STORAGE_KEY = "flight-recent-searches";
const LAST_SEARCH_KEY = "flight-last-search";
const DEPARTURE_COUNTRIES = ["GB", "PL"] as const;
const ARRIVAL_COUNTRIES = ["IT", "FR"] as const;
const DEPARTURE_VALUES = new Set(["GB", "PL", "LHR", "LGW", "MAN", "KRK", "WMI", "WAW", "RZE", "KTW", "WRO"]);
const ARRIVAL_VALUES = new Set(["IT", "FR", "FCO", "MXP", "VCE", "CDG", "ORY", "MRS", "NCE"]);

const normalizeType = (_value?: string): FormValues["type"] => "2";
const normalizeTravelClass = (value?: string): FormValues["travel_class"] =>
  value === "3" ? "3" : "1";
const isSearchValueAllowed = (value: string | undefined, allowedValues: Set<string>) => {
  const text = value?.trim();
  if (!text) return true;
  return text
    .split(",")
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean)
    .every((item) => allowedValues.has(item));
};

export const FlightSearchForm = ({
  defaultValues,
  onSearch
}: FlightSearchFormProps) => {
  const { t, lang } = useI18n();
  const [auth, setAuth] = useState(getAuthSnapshot());
  const isLoggedIn = Boolean(auth.token);
  const { register, handleSubmit, setValue, watch, reset } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      departure_id: defaultValues?.departure_id ?? "",
      arrival_id: defaultValues?.arrival_id ?? "",
      type: normalizeType(defaultValues?.type),
      outbound_date: defaultValues?.outbound_date ?? "",
      return_date: "",
      travel_class: normalizeTravelClass(defaultValues?.travel_class),
      adults: defaultValues?.adults ?? "1"
    }
  });

  const [suggestions, setSuggestions] = useState<{
    departure: Awaited<ReturnType<typeof searchAirports>>;
    arrival: Awaited<ReturnType<typeof searchAirports>>;
  }>({
    departure: { groups: [], countries: [] },
    arrival: { groups: [], countries: [] }
  });

  const [loading, setLoading] = useState<{ departure: boolean; arrival: boolean }>(
    { departure: false, arrival: false }
  );

  const [activeField, setActiveField] = useState<"departure" | "arrival" | null>(null);

  const [recent, setRecent] = useState<RecentSearch[]>([]);

  const [departureLabel, setDepartureLabel] = useState<SelectionLabel | null>(null);
  const [arrivalLabel, setArrivalLabel] = useState<SelectionLabel | null>(null);

  // Стани для вибраної країни
  const [selectedDepartureCountry, setSelectedDepartureCountry] = useState<CountryMatch | null>(null);
  const [selectedArrivalCountry, setSelectedArrivalCountry] = useState<CountryMatch | null>(null);

  const isRoundTrip = false;
  const departureValue = watch("departure_id") ?? "";
  const arrivalValue = watch("arrival_id") ?? "";

  const departureRegister = register("departure_id");
  const arrivalRegister = register("arrival_id");
  const swapDisabled = true;

  // Функція для повної назви країни
  const getCountryName = (code?: string) => {
    if (!code) return "";
    try {
      const display = new Intl.DisplayNames([lang || "en"], { type: "region" });
      return display.of(code.toUpperCase()) ?? code.toUpperCase();
    } catch {
      return code.toUpperCase();
    }
  };

  const buildParams = (values: FormValues): FlightSearchParams => ({
    departure_id: isSearchValueAllowed(values.departure_id, DEPARTURE_VALUES) ? values.departure_id : undefined,
    arrival_id: isSearchValueAllowed(values.arrival_id, ARRIVAL_VALUES) ? values.arrival_id : undefined,
    type: "2",
    outbound_date: values.outbound_date,
    return_date: undefined,
    travel_class: normalizeTravelClass(values.travel_class),
    adults: values.adults
  });

  const buildRecentKey = (params: FlightSearchParams) => [
    `from:${params.departure_id ?? ""}`,
    `to:${params.arrival_id ?? ""}`,
    `type:${params.type ?? ""}`,
    `out:${params.outbound_date ?? ""}`,
    `ret:${params.return_date ?? ""}`,
    `class:${params.travel_class ?? ""}`,
    `adults:${params.adults ?? ""}`
  ].join("|");

  const normalizeHistoryParams = (
    params: Record<string, unknown>
  ): FlightSearchParams => {
    const normalized: FlightSearchParams = {};
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null) return;
      (normalized as Record<string, string>)[key] = String(value);
    });
    return normalized;
  };

  useEffect(() => {
    const unsubscribe = onAuthChange(() => {
      setAuth(getAuthSnapshot());
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (isLoggedIn) {
      let cancelled = false;
      fetchSearchHistory(6)
        .then((items) => {
          if (cancelled) return;
          const mapped = items
            .map((item) => {
              const params = normalizeHistoryParams(item.params ?? {});
              return { key: buildRecentKey(params), params };
            })
            .filter((item) =>
              isSearchValueAllowed(item.params.departure_id, DEPARTURE_VALUES) &&
              isSearchValueAllowed(item.params.arrival_id, ARRIVAL_VALUES)
            )
            .filter((item) => item.key.trim().length > 0)
            .slice(0, 6);
          setRecent(mapped);
        })
        .catch(() => {
          if (!cancelled) setRecent([]);
        });
      return () => {
        cancelled = true;
      };
    }

    const stored = localStorage.getItem(RECENT_STORAGE_KEY);
    if (!stored) {
      setRecent([]);
      return;
    }
    try {
      const parsed = JSON.parse(stored) as unknown;
          if (Array.isArray(parsed) && parsed.length > 0 && "params" in parsed[0]) {
        setRecent(
          (parsed as RecentSearch[])
            .filter((item) =>
              isSearchValueAllowed(item.params.departure_id, DEPARTURE_VALUES) &&
              isSearchValueAllowed(item.params.arrival_id, ARRIVAL_VALUES)
            )
            .slice(0, 6)
        );
        return;
      }
      if (Array.isArray(parsed)) {
        const converted = (parsed as { from?: string; to?: string }[])
          .map((item) => {
            const params: FlightSearchParams = {
              departure_id: item.from ?? "",
              arrival_id: item.to ?? ""
            };
            return {
              key: buildRecentKey(params),
              params
            };
          })
          .filter((item) =>
            isSearchValueAllowed(item.params.departure_id, DEPARTURE_VALUES) &&
            isSearchValueAllowed(item.params.arrival_id, ARRIVAL_VALUES)
          )
          .slice(0, 6);
        setRecent(converted);
        return;
      }
    } catch {
      // Ignore malformed storage.
    }
    setRecent([]);
  }, [isLoggedIn]);

  // Відновлення вибраної країни при зміні значення поля
  useEffect(() => {
    const code = departureValue;
    if (code && !code.includes(",")) {
      const found = suggestions.departure.countries.find(c => c.code === code);
      setSelectedDepartureCountry(found || null);
    } else {
      setSelectedDepartureCountry(null);
    }
  }, [departureValue, suggestions.departure]);

  useEffect(() => {
    const code = arrivalValue;
    if (code && !code.includes(",")) {
      const found = suggestions.arrival.countries.find(c => c.code === code);
      setSelectedArrivalCountry(found || null);
    } else {
      setSelectedArrivalCountry(null);
    }
  }, [arrivalValue, suggestions.arrival]);

  useEffect(() => {
    const handle = setTimeout(() => {
      void (async () => {
        if (activeField === "departure") {
          setLoading((prev) => ({ ...prev, departure: true }));
          const results = await searchAirports(departureValue, DEPARTURE_COUNTRIES);
          setSuggestions((prev) => ({ ...prev, departure: results }));
          setLoading((prev) => ({ ...prev, departure: false }));
        }
        if (activeField === "arrival") {
          setLoading((prev) => ({ ...prev, arrival: true }));
          const results = await searchAirports(arrivalValue, ARRIVAL_COUNTRIES);
          setSuggestions((prev) => ({ ...prev, arrival: results }));
          setLoading((prev) => ({ ...prev, arrival: false }));
        }
      })();
    }, 200);

    return () => clearTimeout(handle);
  }, [activeField, arrivalValue, departureValue]);

  useEffect(() => {
    if (!isRoundTrip) {
      setValue("return_date", "", { shouldValidate: true });
    }
  }, [isRoundTrip, setValue]);

  useEffect(() => {
    if (!defaultValues) {
      return;
    }
    reset({
      departure_id: defaultValues.departure_id ?? "",
      arrival_id: defaultValues.arrival_id ?? "",
      type: normalizeType(defaultValues.type),
      outbound_date: defaultValues.outbound_date ?? "",
      return_date: "",
      travel_class: normalizeTravelClass(defaultValues.travel_class),
      adults: defaultValues.adults ?? "1"
    });
    setDepartureLabel(null);
    setArrivalLabel(null);
    setSelectedDepartureCountry(null);
    setSelectedArrivalCountry(null);
  }, [defaultValues, reset]);

  const saveRecent = (params: FlightSearchParams) => {
    if (!params.departure_id && !params.arrival_id) return;
    const key = buildRecentKey(params);
    const normalized: RecentSearch = { key, params };
    const next = [
      normalized,
      ...recent.filter(item => item.key !== key)
    ].slice(0, 6);
    setRecent(next);
    if (!isLoggedIn) {
      localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(next));
    }
  };

  const onSubmit = (values: FormValues) => {
    const params = buildParams(values);
    onSearch(params);
    saveRecent(params);
    localStorage.setItem(LAST_SEARCH_KEY, JSON.stringify(params));
  };

  // Стилі (можна винести в окремий файл)
  const suggestionClass = "absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white text-sm shadow-lg dark:border-slate-700 dark:bg-slate-900";
  const rowClass = "flex w-full items-center justify-between gap-3 border-b border-slate-100 px-3 py-3 text-left hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800";
  const addButtonClass = "inline-flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-200";
  const iconBadgeClass = "flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-200";
  const planeIcon = (
    <svg viewBox="0 0 24 24" className="h-4 w-4 text-slate-500 dark:text-slate-300" fill="currentColor" aria-hidden="true">
      <path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1v1l3-.5 3 .5v-1l-2-1v-5.5l8 2.5Z" />
    </svg>
  );

  const renderSuggestions = (field: "departure" | "arrival", value: string) => {
    const groups = suggestions[field].groups;
    const countries = suggestions[field].countries;
    const isLoading = loading[field];

    if (
      activeField !== field ||
      value.trim().length < 1 ||
      (groups.length === 0 && countries.length === 0 && !isLoading)
    ) {
      return null;
    }

    const countryFlag = (code: string) =>
      code.toUpperCase().replace(/./g, (char) => String.fromCodePoint(127397 + char.charCodeAt(0)));

    const selectedCountry = field === "departure" ? selectedDepartureCountry : selectedArrivalCountry;
    const setSelectedCountry = field === "departure" ? setSelectedDepartureCountry : setSelectedArrivalCountry;

    return (
      <div className={suggestionClass}>
        {isLoading && (
          <div className="px-3 py-3 text-xs text-slate-500 dark:text-slate-400">
            {t("search.loading")}...
          </div>
        )}

        {countries.length > 0 && (
          <div className="border-b border-slate-100 dark:border-slate-800">
            <div className="bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-300">
              {t("search.countries")}
            </div>

            {/* Вибрана країна зверху */}
            {selectedCountry && (
              <div
                className="
                  px-3 py-3 flex items-center justify-between
                  bg-blue-50/70 dark:bg-blue-950/30
                  border-b border-blue-200 dark:border-blue-800
                  text-blue-900 dark:text-blue-100
                "
              >
                <div className="flex items-center gap-3">
                  <span className={iconBadgeClass}>{countryFlag(selectedCountry.code)}</span>
                  <div>
                    <p className="text-sm font-semibold">{selectedCountry.name}</p>
                    <p className="text-xs opacity-80">{selectedCountry.code}</p>
                  </div>
                </div>

                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setSelectedCountry(null);
                    setValue(field === "departure" ? "departure_id" : "arrival_id", "", { shouldValidate: true });
                    if (field === "departure") setDepartureLabel(null);
                    else setArrivalLabel(null);
                  }}
                  className="
                    text-blue-700 hover:text-blue-900
                    dark:text-blue-300 dark:hover:text-blue-100
                    text-xl leading-none px-2 py-1
                  "
                >
                  ×
                </button>
              </div>
            )}

            {/* Список країн */}
            {countries.map((country: CountryMatch) => (
              <button
                key={`${field}-country-${country.code}`}
                type="button"
                className={`
                  ${rowClass}
                  ${selectedCountry?.code === country.code ? "bg-blue-50/50 dark:bg-blue-950/20" : ""}
                `}
                onMouseDown={(event) => {
                  event.preventDefault();
                  setSelectedCountry(country);
                  setValue(
                    field === "departure" ? "departure_id" : "arrival_id",
                    country.code,
                    { shouldValidate: true }
                  );
                  if (field === "departure") {
                    setDepartureLabel({ label: country.name, value: country.code });
                  } else {
                    setArrivalLabel({ label: country.name, value: country.code });
                  }
                  setActiveField(null);
                }}
              >
                <div className="flex items-center gap-3 flex-1">
                  <span className={iconBadgeClass}>{countryFlag(country.code)}</span>
                  <div>
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                      {country.name}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {country.code}
                    </p>
                  </div>
                </div>

                {selectedCountry?.code !== country.code && (
                  <span className={addButtonClass}>+</span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Групи аеропортів */}
        {groups.map((group) => (
          <div key={`${field}-${group.city}-${group.country ?? ""}`}>
            <div className="bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-300">
              {group.city}
              {group.country ? ` · ${getCountryName(group.country)}` : ""}
            </div>

            {group.airports.length > 1 && (
              <button
                key={`${field}-${group.city}-all`}
                type="button"
                className={rowClass}
                onMouseDown={(event) => {
                  event.preventDefault();
                  const combined = group.airports.map(a => a.iata).join(",");
                  setValue(
                    field === "departure" ? "departure_id" : "arrival_id",
                    combined,
                    { shouldValidate: true }
                  );
                  if (field === "departure") {
                    setDepartureLabel({ label: `${group.city} (${t("search.allAirports")})`, value: combined });
                  } else {
                    setArrivalLabel({ label: `${group.city} (${t("search.allAirports")})`, value: combined });
                  }
                  setActiveField(null);
                }}
              >
                <div className="flex items-center gap-3">
                  <span className={iconBadgeClass}>{group.country?.toUpperCase() ?? "CT"}</span>
                  <div>
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                      {t("search.allAirports", { city: group.city })}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {t("search.allAirports.count", { count: group.airports.length })}
                    </p>
                  </div>
                </div>
                <span className={addButtonClass}>+</span>
              </button>
            )}

            {group.airports.map((airport) => (
              <button
                key={`${field}-${airport.iata}-${airport.name}`}
                type="button"
                className={rowClass}
                onMouseDown={(event) => {
                  event.preventDefault();
                  setValue(
                    field === "departure" ? "departure_id" : "arrival_id",
                    airport.iata,
                    { shouldValidate: true }
                  );
                  const label = airport.city ? `${airport.name}` : airport.name;
                  if (field === "departure") {
                    setDepartureLabel({ label, value: airport.iata });
                  } else {
                    setArrivalLabel({ label, value: airport.iata });
                  }
                  setActiveField(null);
                }}
              >
                <div className="flex items-center gap-3">
                  {planeIcon}
                  <div>
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                      {airport.iata} · {airport.name}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {airport.city ? `${airport.city} · ` : ""}
                      {airport.country ? getCountryName(airport.country) : ""}
                    </p>
                  </div>
                </div>
                <span className={addButtonClass}>+</span>
              </button>
            ))}
          </div>
        ))}
      </div>
    );
  };

  const chipClass = "inline-flex items-center gap-2 rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-900 dark:text-blue-200";
  const inputBase = "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";
  const dateInputClass = "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";
  const selectClass = "rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800";

  return (
    <form
      className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      onSubmit={handleSubmit(onSubmit)}
    >
      <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600 dark:text-slate-300">
        <select className={selectClass} {...register("type")}>
          <option value="2">{t("search.oneWay")}</option>
        </select>
        <select className={selectClass} {...register("travel_class")}>
          <option value="1">{t("search.economy")}</option>
          <option value="3">{t("search.business")}</option>
        </select>
        <select className={selectClass} {...register("adults")}>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((count) => (
            <option key={count} value={String(count)}>
              {formatPassengers(count, lang)}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-3 lg:grid-cols-[1.2fr_auto_1.2fr]">
        <div className="relative">
          <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
            {t("search.from")}
          </label>
          {departureLabel && departureLabel.value === departureValue && (
            <span className={`${chipClass} absolute left-[40px] top-[-8px]
`}>
              {departureLabel.label}
            </span>
          )}
          <Input
            placeholder={t("search.placeholder")}
            className={`${inputBase} h-12 ${departureLabel ? "pt-6" : ""}`}
            value={departureValue}
            onChange={(event) => {
              setValue("departure_id", event.target.value, { shouldDirty: true, shouldValidate: true });
              setDepartureLabel(null);
            }}
            onFocus={() => setActiveField("departure")}
            onBlur={(event) => {
              departureRegister.onBlur(event);
              setActiveField(null);
            }}
          />
          {renderSuggestions("departure", departureValue)}
        </div>

        <div className="flex items-end justify-center">
          <button
            type="button"
            disabled={swapDisabled}
            onClick={() => {
              setValue("departure_id", arrivalValue, { shouldValidate: true });
              setValue("arrival_id", departureValue, { shouldValidate: true });
              setDepartureLabel(null);
              setArrivalLabel(null);
            }}
            className={[
              "h-10 rounded-md border px-3 text-xs font-semibold uppercase tracking-wide",
              swapDisabled
                ? "cursor-not-allowed border-slate-200 text-slate-300 dark:border-slate-700 dark:text-slate-600"
                : "border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            ].join(" ")}
          >
            {t("search.swap")}
          </button>
        </div>

        <div className="relative">
          <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
            {t("search.to")}
          </label>
          {arrivalLabel && arrivalLabel.value === arrivalValue && (
            <span className={`${chipClass} absolute left-[30px] top-[-8px]`}>
              {arrivalLabel.label}
            </span>
          )}
          <Input
            placeholder={t("search.placeholder")}
            className={`${inputBase} h-12 ${arrivalLabel ? "pt-6" : ""}`}
            value={arrivalValue}
            onChange={(event) => {
              setValue("arrival_id", event.target.value, { shouldDirty: true, shouldValidate: true });
              setArrivalLabel(null);
            }}
            onFocus={() => setActiveField("arrival")}
            onBlur={(event) => {
              arrivalRegister.onBlur(event);
              setActiveField(null);
            }}
          />
          {renderSuggestions("arrival", arrivalValue)}
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
            {t("search.depart")}
          </label>
          <input className={dateInputClass} type="date" {...register("outbound_date")} />
        </div>

        {isRoundTrip && (
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
              {t("search.return")}
            </label>
            <input className={dateInputClass} type="date" {...register("return_date")} />
          </div>
        )}
      </div>

      {recent.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 dark:border-slate-700 dark:bg-slate-800">
            {t("search.recent")}:
          </span>
          {recent.map((item, index) => {
            const params = item.params;
            const fromLabel = params.departure_id || "Any";
            const toLabel = params.arrival_id || "Any";
            const dateLabel = params.outbound_date
              ? ` ${params.outbound_date}${params.return_date ? ` -> ${params.return_date}` : ""}`
              : "";
            return (
              <button
                key={`${item.key}-${index}`}
                type="button"
                onClick={() => {
                  setValue("departure_id", params.departure_id ?? "", { shouldValidate: true });
                  setValue("arrival_id", params.arrival_id ?? "", { shouldValidate: true });
                  setValue("type", normalizeType(params.type), { shouldValidate: true });
                  setValue("outbound_date", params.outbound_date ?? "", { shouldValidate: true });
                  setValue("return_date", "", { shouldValidate: true });
                  setValue("travel_class", normalizeTravelClass(params.travel_class), { shouldValidate: true });
                  setValue("adults", params.adults ?? "1", { shouldValidate: true });
                  setDepartureLabel(null);
                  setArrivalLabel(null);
                  setSelectedDepartureCountry(null);
                  setSelectedArrivalCountry(null);
                }}
                className="rounded-full border border-slate-200 px-3 py-1 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {fromLabel} → {toLabel}
                {dateLabel}
              </button>
            );
          })}
        </div>
      )}

      <Button type="submit" className="w-32">
        {t("search.search")}
      </Button>
    </form>
  );
};




