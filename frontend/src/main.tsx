import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { QueryProvider } from "./app/providers/QueryProvider";
import { Router } from "./app/providers/Router";
import { I18nProvider } from "./shared/i18n";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <I18nProvider>
      <QueryProvider>
        <Router />
      </QueryProvider>
    </I18nProvider>
  </React.StrictMode>
);
