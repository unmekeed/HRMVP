import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, setToken } from "../api";
import { OrgInfo, Vacancy } from "../types";

export function VacanciesPage() {
  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [org, setOrg] = useState<OrgInfo | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [requirements, setRequirements] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.listVacancies().then(setVacancies).catch(() => {});
    api.getOrg().then(setOrg).catch(() => {});
  }, []);

  async function createVacancy(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const vacancy = await api.createVacancy({ title, description, requirements });
      navigate(`/vacancies/${vacancy.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка сети");
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <h1>AI Screening</h1>
        <div className="actions">
          {org && (
            <Link to="/settings" className="badge">
              {org.name} · {org.limits.label}
            </Link>
          )}
          <button
            className="link"
            onClick={() => {
              setToken(null);
              navigate("/login");
            }}
          >
            Выйти
          </button>
        </div>
      </header>

      <div className="page-head">
        <h2>Вакансии</h2>
        <button onClick={() => setShowForm(!showForm)}>
          {showForm ? "Отмена" : "+ Новая вакансия"}
        </button>
      </div>

      {showForm && (
        <form className="card form" onSubmit={createVacancy}>
          <input
            required
            placeholder="Название вакансии, например: Python-разработчик"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <textarea
            rows={5}
            placeholder="Описание вакансии (можно вставить текст целиком)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <textarea
            rows={5}
            placeholder={"Ключевые требования — по одному на строку:\nPython от 3 лет\nFastAPI\nPostgreSQL"}
            value={requirements}
            onChange={(e) => setRequirements(e.target.value)}
          />
          {error && <div className="error">{error}</div>}
          <button type="submit" disabled={busy}>
            Создать
          </button>
        </form>
      )}

      <div className="vacancy-list">
        {vacancies.map((v) => (
          <Link key={v.id} to={`/vacancies/${v.id}`} className="card vacancy-item">
            <div>
              <strong>{v.title}</strong>
              <div className="muted">
                {new Date(v.created_at).toLocaleDateString("ru-RU")}
              </div>
            </div>
            <span className="badge">{v.candidates_count} канд.</span>
          </Link>
        ))}
        {vacancies.length === 0 && !showForm && (
          <p className="muted">
            Пока нет вакансий. Создайте первую, чтобы загрузить резюме кандидатов.
          </p>
        )}
      </div>
    </div>
  );
}
