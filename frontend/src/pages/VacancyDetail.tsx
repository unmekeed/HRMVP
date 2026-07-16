import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, getToken } from "../api";
import { CandidateCard } from "../components/CandidateCard";
import {
  Candidate,
  CANDIDATE_STATUS_LABELS,
  CandidateStatus,
  Vacancy,
  VERDICT_LABELS,
} from "../types";

export function VacancyDetailPage() {
  const { id = "" } = useParams();
  const [vacancy, setVacancy] = useState<Vacancy | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selected, setSelected] = useState<Candidate | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    api.listCandidates(id).then(setCandidates).catch(() => {});
  }, [id]);

  useEffect(() => {
    api.getVacancy(id).then(setVacancy).catch(() => {});
    refresh();
  }, [id, refresh]);

  // Пока есть незавершённые анализы — опрашиваем список
  const hasPending = candidates.some(
    (c) => c.analysis_status === "pending" || c.analysis_status === "processing",
  );
  useEffect(() => {
    if (!hasPending) return;
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [hasPending, refresh]);

  async function upload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError("");
    try {
      await api.uploadResumes(id, Array.from(files));
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка загрузки");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function changeStatus(candidate: Candidate, status: CandidateStatus) {
    const updated = await api.updateCandidateStatus(candidate.id, status);
    setCandidates((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    if (selected?.id === updated.id) setSelected(updated);
  }

  async function downloadCsv() {
    const res = await fetch(api.exportUrl(id), {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `candidates_${vacancy?.title || id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="page">
      <header className="topbar">
        <Link to="/">← Вакансии</Link>
      </header>

      {vacancy && (
        <div className="page-head">
          <div>
            <h2>{vacancy.title}</h2>
            {vacancy.requirements && (
              <details>
                <summary className="muted">Требования</summary>
                <pre className="requirements">{vacancy.requirements}</pre>
              </details>
            )}
          </div>
          <div className="actions">
            <button
              onClick={() => fileInput.current?.click()}
              disabled={uploading}
            >
              {uploading ? "Загрузка…" : "+ Загрузить резюме"}
            </button>
            <button className="secondary" onClick={downloadCsv}>
              Экспорт CSV
            </button>
          </div>
        </div>
      )}

      <input
        ref={fileInput}
        type="file"
        multiple
        accept=".pdf,.docx,.txt,.md"
        style={{ display: "none" }}
        onChange={(e) => upload(e.target.files)}
      />
      {error && <div className="error">{error}</div>}

      <table className="candidates">
        <thead>
          <tr>
            <th>#</th>
            <th>Кандидат</th>
            <th>Балл</th>
            <th>Вердикт</th>
            <th>Статус</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c, i) => (
            <tr key={c.id} onClick={() => setSelected(c)} className="row">
              <td>{i + 1}</td>
              <td>
                <strong>{c.full_name || c.filename}</strong>
                <div className="muted">{c.email}</div>
              </td>
              <td>
                {c.analysis_status === "done" && c.score !== null ? (
                  <span className={`score s${Math.floor(c.score / 25)}`}>
                    {Math.round(c.score)}
                  </span>
                ) : c.analysis_status === "error" ? (
                  <span className="error-badge" title={c.analysis_error}>
                    ошибка
                  </span>
                ) : (
                  <span className="muted">анализ…</span>
                )}
              </td>
              <td>{VERDICT_LABELS[c.verdict] || "—"}</td>
              <td onClick={(e) => e.stopPropagation()}>
                <select
                  value={c.status}
                  onChange={(e) => changeStatus(c, e.target.value as CandidateStatus)}
                >
                  {Object.entries(CANDIDATE_STATUS_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </td>
              <td className="muted">{c.filename}</td>
            </tr>
          ))}
          {candidates.length === 0 && (
            <tr>
              <td colSpan={6} className="muted center">
                Загрузите резюме (PDF, DOCX или TXT) — система проанализирует их
                автоматически и отсортирует кандидатов по соответствию.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {selected && (
        <CandidateCard
          candidate={selected}
          onClose={() => setSelected(null)}
          onStatusChange={(status) => changeStatus(selected, status)}
          onReanalyze={async () => {
            const updated = await api.reanalyze(selected.id);
            setSelected(updated);
            refresh();
          }}
        />
      )}
    </div>
  );
}
