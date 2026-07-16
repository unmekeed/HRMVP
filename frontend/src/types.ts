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

export type Role = "owner" | "admin" | "recruiter";
export type PlanTier = "free" | "pro" | "enterprise";

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Владелец",
  admin: "Администратор",
  recruiter: "Рекрутер",
};

export interface OrgInfo {
  id: string;
  name: string;
  plan: PlanTier;
  role: Role;
  limits: {
    label: string;
    price: number | null;
    max_vacancies: number | null;
    monthly_analyses: number | null;
    max_members: number | null;
  };
  usage: { analyses_used: number; vacancies: number; members: number };
}

export interface OrgSummary {
  id: string;
  name: string;
  role: Role;
}

export interface PlanInfo {
  plan: PlanTier;
  label: string;
  price: number | null;
  max_vacancies: number | null;
  monthly_analyses: number | null;
  max_members: number | null;
  current: boolean;
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  name: string;
  role: Role;
}

export interface Invitation {
  id: string;
  email: string;
  role: Role;
  token: string;
  accepted: boolean;
  created_at: string;
}
