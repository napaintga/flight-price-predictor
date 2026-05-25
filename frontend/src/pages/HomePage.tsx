import { Link } from "react-router-dom";
import { Button } from "../shared/ui/Button";
import { Card } from "../shared/ui/Card";
import { useI18n } from "../shared/i18n";

export const HomePage = () => {
  const { t } = useI18n();

  return (
    <div className="space-y-6">
      <Card className="space-y-3">
        <h1 className="text-2xl font-semibold">{t("home.title")}</h1>
        <p className="text-slate-600 dark:text-slate-300">{t("home.subtitle")}</p>
        <div className="flex flex-wrap gap-3">
          <Link to="/flights">
            <Button>{t("home.browse")}</Button>
          </Link>
          <Link to="/analytics">
            <Button className="bg-slate-900 hover:bg-slate-800 dark:bg-slate-700 dark:hover:bg-slate-600">
              {t("home.analytics")}
            </Button>
          </Link>
          
        </div>
      </Card>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          {
            title: t("home.card.search"),
            body: t("home.card.search.body")
          },
          {
            title: t("home.card.predict"),
            body: t("home.card.predict.body")
          },
          {
            title: t("home.card.tickets"),
            body: t("home.card.tickets.body")
          }
        ].map((item) => (
          <Card key={item.title}>
            <p className="text-base font-semibold">{item.title}</p>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              {item.body}
            </p>
          </Card>
        ))}
      </div>
    </div>
  );
};
