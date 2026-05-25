import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useI18n } from "../../shared/i18n";
import { logout } from "../../features/auth/api";
import {
  clearSession,
  getAuthSnapshot,
  onAuthChange
} from "../../features/auth/session";

const navItems = [
  { key: "nav.home", to: "/" },
  { key: "nav.flights", to: "/flights" },
  { key: "nav.tickets", to: "/tickets" },
  { key: "nav.analytics", to: "/analytics" }
];

export const AppLayout = () => {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [auth, setAuth] = useState(getAuthSnapshot());
  const navigate = useNavigate();
  const { lang, setLang, t } = useI18n();

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    if (stored === "dark" || stored === "light") {
      setTheme(stored);
      document.documentElement.classList.toggle("dark", stored === "dark");
      return;
    }
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
    const next = prefersDark ? "dark" : "light";
    setTheme(next);
    document.documentElement.classList.toggle("dark", prefersDark);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  useEffect(() => {
    const unsubscribe = onAuthChange(() => {
      setAuth(getAuthSnapshot());
    });
    return unsubscribe;
  }, []);

  const toggleLang = () => {
    setLang(lang === "en" ? "uk" : "en");
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // ignore server errors; still clear session locally
    }
    clearSession();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-4 py-4">
          <div>
            <p className="text-lg font-semibold text-blue-700 dark:text-blue-400">
              {t("app.title")}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t("app.subtitle")}
            </p>
          </div>
          <nav className="flex flex-wrap gap-2 text-sm font-medium">
            {navItems.map((item) => (
              <NavLink
                key={item.key}
                to={item.to}
                className={({ isActive }) =>
                  [
                    "rounded-md px-3 py-2 transition",
                    isActive
                      ? "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                      : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                  ]
                    .filter(Boolean)
                    .join(" ")
                }
              >
                {t(item.key)}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            {!auth.token ? (
              <>
                <NavLink
                  to="/login"
                  className={({ isActive }) =>
                    [
                      "rounded-md border px-3 py-2 text-xs font-semibold shadow-sm transition",
                      isActive
                        ? "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-200"
                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                    ]
                      .filter(Boolean)
                      .join(" ")
                  }
                >
                  {t("nav.login")}
                </NavLink>
                <NavLink
                  to="/register"
                  className={({ isActive }) =>
                    [
                      "rounded-md border px-3 py-2 text-xs font-semibold shadow-sm transition",
                      isActive
                        ? "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-200"
                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                    ]
                      .filter(Boolean)
                      .join(" ")
                  }
                >
                  {t("nav.register")}
                </NavLink>
              </>
            ) : (
              <>
                {auth.user?.email && (
                  <span className="hidden text-xs font-medium text-slate-500 dark:text-slate-400 md:inline">
                    {auth.user.email}
                  </span>
                )}
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                >
                  {t("auth.logout")}
                </button>
              </>
            )}
            <button
              type="button"
              onClick={toggleLang}
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              {lang === "en" ? t("lang.uk") : t("lang.en")}
            </button>
            <button
              type="button"
              onClick={toggleTheme}
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              {theme === "dark" ? t("theme.light") : t("theme.dark")}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
};
