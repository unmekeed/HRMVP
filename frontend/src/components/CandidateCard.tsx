import {
  Candidate,
  CANDIDATE_STATUS_LABELS,
  CandidateStatus,
  VERDICT_LABELS,
} from "../types";

interface Props {
  candidate: Candidate;
  onClose: () => void;
  onStatusChange: (status: CandidateStatus) => void;
  onReanalyze: () => void;
}

export function CandidateCard({ candidate, onClose, onStatusChange, onReanalyze }: Props) {
  const c = candidate;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h3>{c.full_name || c.filename}</h3>
            <div className="muted">
              {[c.email, c.phone].filter(Boolean).join(" · ")}
            </div>
          </div>
          <button className="link" onClick={onClose}>
            ✕
          </button>
        </div>

        {c.analysis_status === "done" && c.score !== null && (
          <div className="score-row">
            <span className={`score big s${Math.floor(c.score / 25)}`}>
              {Math.round(c.score)}
            </span>
            <div>
              <strong>{VERDICT_LABELS[c.verdict] || c.verdict}</strong>
              <p>{c.summary}</p>
            </div>
          </div>
        )}
        {c.analysis_status === "error" && (
          <div className="error">
            Ошибка анализа: {c.analysis_error}{" "}
            <button className="link" onClick={onReanalyze}>
              Повторить
            </button>
          </div>
        )}
        {(c.analysis_status === "pending" || c.analysis_status === "processing") && (
          <p className="muted">Анализ выполняется…</p>
        )}

        {c.strengths.length > 0 && (
          <section>
            <h4>Сильные стороны</h4>
            <ul>
              {c.strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </section>
        )}
        {c.weaknesses.length > 0 && (
          <section>
            <h4>Слабые стороны / риски</h4>
            <ul>
              {c.weaknesses.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </section>
        )}
        {c.missing_requirements.length > 0 && (
          <section>
            <h4>Не подтверждено в резюме</h4>
            <ul>
              {c.missing_requirements.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </section>
        )}
        {c.recommendation && (
          <section>
            <h4>Рекомендация</h4>
            <p>{c.recommendation}</p>
          </section>
        )}

        <div className="modal-foot">
          <label>
            Статус кандидата:{" "}
            <select
              value={c.status}
              onChange={(e) => onStatusChange(e.target.value as CandidateStatus)}
            >
              {Object.entries(CANDIDATE_STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <span className="muted">{c.filename}</span>
        </div>
      </div>
    </div>
  );
}
