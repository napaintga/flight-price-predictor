import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppLayout } from "../layout/AppLayout";
import { AnalyticsPage } from "../../pages/AnalyticsPage";
import { FlightDetailsPage } from "../../pages/FlightDetailsPage";
import { FlightsPage } from "../../pages/FlightsPage";
import { HomePage } from "../../pages/HomePage";
import { LoginPage } from "../../pages/LoginPage";
import { NotFoundPage } from "../../pages/NotFoundPage";
import { RegisterPage } from "../../pages/RegisterPage";
import { TicketsPage } from "../../pages/TicketsPage";

export const Router = () => (
  <BrowserRouter>
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/flights" element={<FlightsPage />} />
        <Route path="/flights/:id" element={<FlightDetailsPage />} />
        <Route path="/tickets" element={<TicketsPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  </BrowserRouter>
);
