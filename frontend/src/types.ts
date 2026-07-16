export type VacancyStatus = "active" | "closed" | "archived";
export type CandidateStatus =
  | "new"
  | "reviewed"
  | "shortlist"
  | "interview"
  | "offer"
  | "rejected";
export type AnalysisStatus = "pending" | "processing" | "done" | "error";

export interface Vacancy {
  id: string;
  title: string;
  description: string;
  requirements: string;
  status: VacancyStatus;
  created_at: string;
  candidates_count: number;
}

export interface Candidate {
  id: string;
  vacancy_id: string;
  filename: string;
  full_name: string;
  email: string;
  phone: string;
  analysis_status: AnalysisStatus;
  analysis_error: string;
  score: number | null;
  verdict: string;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  matched_requirements: string[];
  missing_requirements: string[];
  recommendation: string;
  status: CandidateStatus;
  created_at: string;
}

export const CANDIDATE_STATUS_LABELS: Record<CandidateStatus, string> = {
  new: "Новый",
  reviewed: "Просмотрен",
  shortlist: "Шорт-лист",
  interview: "Интервью",
  offer: "Оффер",
  rejected: "Отказ",
};

export const VERDICT_LABELS: Record<string, string> = {
  strong_match: "Отличное соответствие",
  good_match: "Хорошее соответствие",
  partial_match: "Частичное соответствие",
  weak_match: "Слабое соответствие",
};
