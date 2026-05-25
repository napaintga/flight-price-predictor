import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import axios from "axios";
import { login } from "../features/auth/api";
import { getToken, setSession } from "../features/auth/session";
import { Card } from "../shared/ui/Card";
import { Input } from "../shared/ui/Input";
import { Button } from "../shared/ui/Button";
import { useI18n } from "../shared/i18n";

export const LoginPage = () => {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (getToken()) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await login({ email, password });
      setSession(data.token, data.user);
      navigate("/");
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail = (err.response?.data as { detail?: string })?.detail;
        setError(detail ?? t("auth.error.default"));
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(t("auth.error.default"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="mx-auto max-w-md space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">{t("auth.login.title")}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {t("auth.login.subtitle")}
        </p>
      </div>
      <form className="space-y-4" onSubmit={handleSubmit}>
        <label className="block space-y-1 text-sm font-medium">
          <span>{t("auth.email")}</span>
          <Input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label className="block space-y-1 text-sm font-medium">
          <span>{t("auth.password")}</span>
          <Input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <Button type="submit" disabled={loading}>
          {loading ? t("auth.login.loading") : t("auth.login.action")}
        </Button>
      </form>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        {t("auth.noAccount")}{" "}
        <Link className="font-semibold text-blue-600" to="/register">
          {t("auth.toRegister")}
        </Link>
      </p>
    </Card>
  );
};
