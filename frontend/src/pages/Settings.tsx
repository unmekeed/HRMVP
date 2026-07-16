import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import {
  Invitation,
  Member,
  OrgInfo,
  PlanInfo,
  Role,
  ROLE_LABELS,
} from "../types";

function limitText(n: number | null): string {
  return n === null ? "∞" : String(n);
}

export function SettingsPage() {
  const [org, setOrg] = useState<OrgInfo | null>(null);
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<Role>("recruiter");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const canManage = org && (org.role === "owner" || org.role === "admin");

  function reload() {
    api.getOrg().then(setOrg).catch(() => {});
    api.listPlans().then(setPlans).catch(() => {});
    api.listMembers().then(setMembers).catch(() => {});
    api.listInvitations().then(setInvitations).catch(() => setInvitations([]));
  }

  useEffect(reload, []);

  async function upgrade(plan: string) {
    setError("");
    try {
      await api.changePlan(plan);
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ошибка");
    }
  }

  async function invite(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      const inv = await api.createInvitation(inviteEmail, inviteRole);
      setInviteEmail("");
      setMsg(`Приглашение создано. Токен: ${inv.token}`);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка");
    }
  }

  async function setRole(m: Member, role: string) {
    try {
      await api.changeMemberRole(m.id, role);
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ошибка");
    }
  }

  async function remove(m: Member) {
    if (!confirm(`Удалить ${m.email} из команды?`)) return;
    try {
      await api.removeMember(m.id);
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ошибка");
    }
  }

  if (!org) return <div className="page">Загрузка…</div>;

  return (
    <div className="page">
      <header className="topbar">
        <Link to="/">← Вакансии</Link>
      </header>

      <h2>{org.name}</h2>
      <p className="muted">
        Ваша роль: {ROLE_LABELS[org.role]} · Тариф: {org.limits.label}
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="card" style={{ borderColor: "var(--accent)" }}>{msg}</div>}

      {/* использование */}
      <section className="card">
        <h3>Использование</h3>
        <div className="usage-grid">
          <Usage
            label="Вакансии"
            used={org.usage.vacancies}
            limit={org.limits.max_vacancies}
          />
          <Usage
            label="Анализы за период"
            used={org.usage.analyses_used}
            limit={org.limits.monthly_analyses}
          />
          <Usage
            label="Участники"
            used={org.usage.members}
            limit={org.limits.max_members}
          />
        </div>
      </section>

      {/* тарифы */}
      <section>
        <h3>Тарифы</h3>
        <div className="plans">
          {plans.map((p) => (
            <div key={p.plan} className={`card plan ${p.current ? "current" : ""}`}>
              <strong>{p.label}</strong>
              <div className="price">
                {p.price === null ? "по запросу" : p.price === 0 ? "бесплатно" : `$${p.price}/мес`}
              </div>
              <ul className="muted">
                <li>Вакансий: {limitText(p.max_vacancies)}</li>
                <li>Анализов/период: {limitText(p.monthly_analyses)}</li>
                <li>Участников: {limitText(p.max_members)}</li>
              </ul>
              {p.current ? (
                <span className="badge">Текущий</span>
              ) : org.role === "owner" ? (
                <button onClick={() => upgrade(p.plan)}>Перейти</button>
              ) : (
                <span className="muted">только владелец</span>
              )}
            </div>
          ))}
        </div>
        <p className="muted">
          MVP: смена тарифа без реальной оплаты. В проде здесь — Stripe Checkout.
        </p>
      </section>

      {/* участники */}
      <section>
        <h3>Участники команды</h3>
        <table className="candidates">
          <thead>
            <tr>
              <th>Участник</th>
              <th>Роль</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id}>
                <td>
                  <strong>{m.name || m.email}</strong>
                  <div className="muted">{m.email}</div>
                </td>
                <td>
                  {canManage && m.role !== "owner" ? (
                    <select value={m.role} onChange={(e) => setRole(m, e.target.value)}>
                      <option value="recruiter">Рекрутер</option>
                      <option value="admin">Администратор</option>
                    </select>
                  ) : (
                    ROLE_LABELS[m.role]
                  )}
                </td>
                <td>
                  {canManage && m.role !== "owner" && (
                    <button className="link" onClick={() => remove(m)}>
                      Удалить
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {canManage && (
          <form className="form card" onSubmit={invite} style={{ marginTop: 12 }}>
            <h4>Пригласить участника</h4>
            <input
              type="email"
              required
              placeholder="email@example.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
            />
            <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value as Role)}>
              <option value="recruiter">Рекрутер</option>
              <option value="admin">Администратор</option>
            </select>
            <button type="submit">Создать приглашение</button>
          </form>
        )}

        {invitations.length > 0 && (
          <div className="card" style={{ marginTop: 12 }}>
            <h4>Ожидают принятия</h4>
            <ul>
              {invitations.map((i) => (
                <li key={i.id}>
                  {i.email} ({ROLE_LABELS[i.role]}) — токен: <code>{i.token}</code>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}

function Usage({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const pct = limit ? Math.min(100, Math.round((100 * used) / limit)) : 0;
  return (
    <div>
      <div className="usage-label">
        {label}: <strong>{used}</strong> / {limit === null ? "∞" : limit}
      </div>
      {limit !== null && (
        <div className="bar">
          <div className="bar-fill" style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}
