import { Link } from "react-router-dom";
import { Card } from "../shared/ui/Card";

export const NotFoundPage = () => (
  <Card className="space-y-3">
    <h1 className="text-2xl font-semibold">Page not found</h1>
    <p className="text-sm text-slate-600">
      The page you requested does not exist.
    </p>
    <Link className="text-sm font-semibold text-blue-600" to="/">
      Go home
    </Link>
  </Card>
);
