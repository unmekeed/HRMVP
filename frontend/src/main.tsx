import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { getToken } from "./api";
import { LoginPage } from "./pages/Login";
import { VacanciesPage } from "./pages/Vacancies";
import { VacancyDetailPage } from "./pages/VacancyDetail";
import "./styles.css";

function RequireAuth({ children }: { children: React.ReactElement }) {
  return getToken() ? children : <Navigate to="/login" replace />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <VacanciesPage />
            </RequireAuth>
          }
        />
        <Route
          path="/vacancies/:id"
          element={
            <RequireAuth>
              <VacancyDetailPage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
