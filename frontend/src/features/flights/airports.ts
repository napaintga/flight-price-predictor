export type AirportRecord = {
  iata: string;
  name: string;
  city?: string;
  country?: string; // ISO 3166-1 alpha-2 code
  lat: number;
  lon: number;
};

type AirportGroup = {
  city: string;
  country?: string;
  airports: AirportRecord[];
};

export type CountryMatch = {
  code: string;
  name: string;
};

const airportsCache: AirportRecord[] = [
 
  // Польща
  { iata: "KRK", name: "John Paul II Kraków-Balice", city: "Kraków", country: "PL", lat: 50.0777, lon: 19.7848 },
  { iata: "WMI", name: "Warsaw Modlin", city: "Warsaw", country: "PL", lat: 52.4511, lon: 20.6518 },
  { iata: "WAW", name: "Warsaw Chopin", city: "Warsaw", country: "PL", lat: 52.1657, lon: 20.9671 },
  { iata: "RZE", name: "Rzeszów–Jasionka", city: "Rzeszów", country: "PL", lat: 50.1100, lon: 22.0189 },
  { iata: "KTW", name: "Katowice Wojciech Korfanty", city: "Katowice", country: "PL", lat: 50.4743, lon: 19.0800 },
  { iata: "WRO", name: "Copernicus Airport Wrocław", city: "Wrocław", country: "PL", lat: 51.1079, lon: 16.8862 },

  // Франція
  { iata: "CDG", name: "Charles de Gaulle", city: "Paris", country: "FR", lat: 49.0097, lon: 2.5479 },
  { iata: "ORY", name: "Orly", city: "Paris", country: "FR", lat: 48.7262, lon: 2.3652 },
  { iata: "MRS", name: "Marseille Provence", city: "Marseille", country: "FR", lat: 43.4393, lon: 5.2510 },
  { iata: "NCE", name: "Nice Côte d'Azur", city: "Nice", country: "FR", lat: 43.6584, lon: 7.2159 },


  // Великобританія
  { iata: "LHR", name: "London Heathrow", city: "London", country: "GB", lat: 51.4700, lon: -0.4543 },
  { iata: "LGW", name: "London Gatwick", city: "London", country: "GB", lat: 51.1481, lon: -0.1903 },
  { iata: "MAN", name: "Manchester", city: "Manchester", country: "GB", lat: 53.3537, lon: -2.2750 },

  // Іспанія
  { iata: "MAD", name: "Adolfo Suárez Madrid–Barajas", city: "Madrid", country: "ES", lat: 40.4936, lon: -3.5670 },
  { iata: "BCN", name: "Barcelona–El Prat", city: "Barcelona", country: "ES", lat: 41.2974, lon: 2.0833 },

  // Італія
  { iata: "FCO", name: "Leonardo da Vinci–Fiumicino", city: "Rome", country: "IT", lat: 41.8045, lon: 12.2509 },
  { iata: "MXP", name: "Milan Malpensa", city: "Milan", country: "IT", lat: 45.6306, lon: 8.7281 },
  { iata: "VCE", name: "Venice Marco Polo", city: "Venice", country: "IT", lat: 45.5053, lon: 12.3519 },

];

export const loadAirports = async (): Promise<AirportRecord[]> => airportsCache;

const filterByCountries = (
  airports: AirportRecord[],
  allowedCountries?: readonly string[]
) => {
  if (!allowedCountries?.length) return airports;
  const allowed = new Set(allowedCountries.map((country) => country.toUpperCase()));
  return airports.filter((airport) => airport.country && allowed.has(airport.country.toUpperCase()));
};

const getCountryName = (code?: string): string => {
  if (!code) return "";
  try {
    const display = new Intl.DisplayNames(["en"], { type: "region" });
    return display.of(code.toUpperCase()) ?? code.toUpperCase();
  } catch {
    return code.toUpperCase();
  }
};

export const searchAirports = async (
  query: string,
  allowedCountries?: readonly string[]
): Promise<{ groups: AirportGroup[]; countries: CountryMatch[] }> => {
  const trimmed = query.trim();
  if (trimmed.length < 1) {
    return { groups: [], countries: [] };
  }

  const airports = filterByCountries(await loadAirports(), allowedCountries);
  const needle = trimmed.toLowerCase();

  // Фільтр аеропортів
  const matches = airports.filter((airport) => {
    const haystack = [
      airport.iata?.toLowerCase() ?? "",
      airport.name?.toLowerCase() ?? "",
      airport.city?.toLowerCase() ?? "",
      airport.country?.toLowerCase() ?? "",
      getCountryName(airport.country).toLowerCase(),
    ].join(" ");
    return haystack.includes(needle);
  });

  // Групування
  const grouped = new Map<string, AirportGroup>();
  for (const airport of matches.slice(0, 120)) {
    const city = airport.city || airport.name || airport.iata;
    const key = `${city}-${airport.country ?? "unknown"}`;
    if (!grouped.has(key)) {
      grouped.set(key, {
        city,
        country: airport.country,
        airports: [],
      });
    }
    grouped.get(key)!.airports.push(airport);
  }

  // Країни, що матчать (по коду або повній назві)
  const countriesSet = new Map<string, string>();
  for (const airport of airports) {
    if (!airport.country) continue;
    const code = airport.country.toUpperCase();
    const name = getCountryName(code);
    if (
      code.toLowerCase().includes(needle) ||
      name.toLowerCase().includes(needle)
    ) {
      countriesSet.set(code, name);
    }
  }

  const countries: CountryMatch[] = Array.from(countriesSet.entries())
    .map(([code, name]) => ({ code, name }))
    .sort((a, b) => a.name.localeCompare(b.name))
    .slice(0, 10);

  return {
    groups: Array.from(grouped.values()).slice(0, 12),
    countries,
  };
};

export const findNearestAirport = async (
  position: { lat: number; lng: number },
  countryCode?: string
): Promise<{ airport: AirportRecord; distance: number } | null> => {
  const airports = await loadAirports();
  if (!airports.length) return null;

  const candidates = countryCode
    ? airports.filter(
        (a) => a.country?.toLowerCase() === countryCode.toLowerCase()
      )
    : airports;

  let best: AirportRecord | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;

  const toRadians = (deg: number) => (deg * Math.PI) / 180;

  const distanceKm = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) => {
    const R = 6371;
    const dLat = toRadians(b.lat - a.lat);
    const dLon = toRadians(b.lng - a.lng);
    const lat1 = toRadians(a.lat);
    const lat2 = toRadians(b.lat);
    const valA =
      Math.sin(dLat / 2) ** 2 +
      Math.sin(dLon / 2) ** 2 * Math.cos(lat1) * Math.cos(lat2);
    const c = 2 * Math.atan2(Math.sqrt(valA), Math.sqrt(1 - valA));
    return R * c;
  };

  for (const airport of candidates) {
    const dist = distanceKm(position, { lat: airport.lat, lng: airport.lon });
    if (dist < bestDistance) {
      bestDistance = dist;
      best = airport;
    }
  }

  return best && bestDistance <= 300 ? { airport: best, distance: bestDistance } : null;
};
