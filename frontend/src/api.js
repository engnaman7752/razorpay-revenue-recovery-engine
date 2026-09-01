// Thin fetch helpers. All data comes from the backend's /api endpoints.
// VITE_API_BASE (set at build time, e.g. on Vercel) points at a remote
// backend; empty default keeps same-origin behavior (vite proxy / nginx).
const BASE = import.meta.env.VITE_API_BASE || "";

async function get(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const api = {
  metrics: () => get("/api/metrics"),
  cases: () => get("/api/cases"),
  caseDetail: (id) => get(`/api/cases/${id}`),
  escalations: () => get("/api/escalations"),
  resolveEscalation: (id, approved) =>
    post(`/api/escalations/${id}/resolve`, { approved }),
};
