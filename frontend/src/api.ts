const TOKEN_KEY = "ais_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    setToken(null);
    window.location.href = "/login";
    throw new ApiError(401, "Не авторизован");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  register: (email: string, password: string, name: string) =>
    request<{ access_token: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  listVacancies: () => request<import("./types").Vacancy[]>("/api/vacancies"),
  createVacancy: (payload: { title: string; description: string; requirements: string }) =>
    request<import("./types").Vacancy>("/api/vacancies", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getVacancy: (id: string) => request<import("./types").Vacancy>(`/api/vacancies/${id}`),
  deleteVacancy: (id: string) =>
    request<void>(`/api/vacancies/${id}`, { method: "DELETE" }),
  listCandidates: (vacancyId: string) =>
    request<import("./types").Candidate[]>(`/api/vacancies/${vacancyId}/candidates`),
  uploadResumes: (vacancyId: string, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<import("./types").Candidate[]>(
      `/api/vacancies/${vacancyId}/resumes`,
      { method: "POST", body: form },
    );
  },
  updateCandidateStatus: (id: string, status: string) =>
    request<import("./types").Candidate>(`/api/candidates/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  reanalyze: (id: string) =>
    request<import("./types").Candidate>(`/api/candidates/${id}/reanalyze`, {
      method: "POST",
    }),
  exportUrl: (vacancyId: string) => `/api/vacancies/${vacancyId}/export`,

  // organizations / billing / members
  getOrg: () => request<import("./types").OrgInfo>("/api/org"),
  listOrgs: () => request<import("./types").OrgSummary[]>("/api/orgs"),
  switchOrg: (orgId: string) =>
    request<import("./types").OrgInfo>("/api/org/switch", {
      method: "POST",
      body: JSON.stringify({ org_id: orgId }),
    }),
  listPlans: () => request<import("./types").PlanInfo[]>("/api/org/plans"),
  changePlan: (plan: string) =>
    request<import("./types").OrgInfo>("/api/org/plan", {
      method: "POST",
      body: JSON.stringify({ plan }),
    }),
  listMembers: () => request<import("./types").Member[]>("/api/org/members"),
  changeMemberRole: (membershipId: string, role: string) =>
    request<import("./types").Member>(`/api/org/members/${membershipId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  removeMember: (membershipId: string) =>
    request<void>(`/api/org/members/${membershipId}`, { method: "DELETE" }),
  listInvitations: () =>
    request<import("./types").Invitation[]>("/api/org/invitations"),
  createInvitation: (email: string, role: string) =>
    request<import("./types").Invitation>("/api/org/invitations", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),
  acceptInvitation: (token: string) =>
    request<import("./types").OrgInfo>("/api/invitations/accept", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
};
