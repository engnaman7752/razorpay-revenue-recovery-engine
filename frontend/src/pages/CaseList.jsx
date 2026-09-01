import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { inr, shortId, STATUS_TONE, CAUSE_LABEL } from "../format.js";
import { Card, Chip, Skeleton, EmptyState, ErrorState } from "../components/ui.jsx";

const STATUSES = ["ALL", "RECOVERED", "WAITING_APPROVAL", "IN_PROGRESS", "SCHEDULED",
  "ESCALATED", "CLOSED", "DETECTED"];
const CAUSES = ["ALL", "SOFT_DECLINE", "TRANSIENT", "HARD_DECLINE", "CUSTOMER_ACTION",
  "UNRECOVERABLE"];

const COLUMNS = [
  { key: "case_id", label: "Case", sortable: false },
  { key: "amount_paise", label: "Amount", align: "right", sortable: true },
  { key: "error_reason", label: "Error reason", sortable: true },
  { key: "diagnosis", label: "Diagnosis", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "attempts", label: "Attempts", align: "right", sortable: true },
  { key: "contacts_made", label: "Contacts", align: "right", sortable: true },
  { key: "recovered_paise", label: "Recovered", align: "right", sortable: true },
];

export default function CaseList() {
  const [cases, setCases] = useState(null);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState("ALL");
  const [cause, setCause] = useState("ALL");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState({ key: "amount_paise", dir: "desc" });

  const load = () => {
    setError(null);
    api.cases().then(setCases).catch((e) => setError(e.message));
  };
  useEffect(load, []);

  const filtered = useMemo(() => {
    if (!cases) return [];
    const q = query.trim().toLowerCase();
    const rows = cases.filter((c) =>
      (status === "ALL" || c.status === status) &&
      (cause === "ALL" || c.diagnosis === cause) &&
      (!q || c.case_id.toLowerCase().includes(q)
          || (c.razorpay_order_id || "").toLowerCase().includes(q)
          || (c.error_reason || "").toLowerCase().includes(q)
          || (c.customer_id || "").toLowerCase().includes(q)));
    const { key, dir } = sort;
    return [...rows].sort((a, b) => {
      const va = a[key] ?? "", vb = b[key] ?? "";
      const cmp = typeof va === "number" ? va - vb : String(va).localeCompare(String(vb));
      return dir === "asc" ? cmp : -cmp;
    });
  }, [cases, status, cause, query, sort]);

  const toggleSort = (key) =>
    setSort((s) => ({ key, dir: s.key === key && s.dir === "desc" ? "asc" : "desc" }));

  if (error) return <ErrorState error={error} onRetry={load} />;
  if (!cases) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-9 w-full max-w-xl" />
        <Skeleton className="h-[420px]" />
      </div>
    );
  }

  const totals = filtered.reduce((acc, c) => ({
    at_risk: acc.at_risk + c.amount_paise,
    recovered: acc.recovered + c.recovered_paise,
  }), { at_risk: 0, recovered: 0 });

  return (
    <div className="space-y-3">
      {/* filters, one row above the table */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1 p-0.5 bg-raised rounded-lg border border-line overflow-x-auto">
          {CAUSES.map((c) => (
            <button key={c} onClick={() => setCause(c)}
                    className={"px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors " +
                      (cause === c ? "bg-surface text-ink shadow-card" : "text-inkmid hover:text-ink")}>
              {c === "ALL" ? "All causes" : CAUSE_LABEL[c]}
            </button>
          ))}
        </div>
        <select className="field" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s === "ALL" ? "All statuses" : s.replace("_", " ")}</option>
          ))}
        </select>
        <input className="field w-56" placeholder="Search id, order, error, customer…"
               value={query} onChange={(e) => setQuery(e.target.value)} />
        <div className="text-xs text-inkmid ml-auto tabular-nums">
          <span className="font-medium text-ink">{filtered.length}</span> of {cases.length} cases ·
          {" "}{inr(totals.recovered)} recovered of {inr(totals.at_risk)}
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-inkmid border-b border-line bg-raised">
                {COLUMNS.map((col) => (
                  <th key={col.key}
                      className={"px-4 py-2.5 font-semibold " +
                        (col.align === "right" ? "text-right " : "") +
                        (col.sortable ? "cursor-pointer select-none hover:text-ink" : "")}
                      onClick={col.sortable ? () => toggleSort(col.key) : undefined}>
                    {col.label}
                    {sort.key === col.key && (
                      <span className="ml-1 text-inkmute">{sort.dir === "desc" ? "↓" : "↑"}</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.case_id}
                    onClick={() => { window.location.hash = `#/cases/${c.case_id}`; }}
                    className="border-b border-line last:border-0 hover:bg-raised cursor-pointer transition-colors">
                  <td className="px-4 py-2.5">
                    <span className="font-mono text-[13px] text-series1">{shortId(c.case_id)}</span>
                    {c.source === "LIVE" && (
                      <Chip tone="info" className="ml-2 !text-[10px]">LIVE</Chip>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium">{inr(c.amount_paise)}</td>
                  <td className="px-4 py-2.5 text-inkmid font-mono text-[12px]">{c.error_reason}</td>
                  <td className="px-4 py-2.5">{CAUSE_LABEL[c.diagnosis] || c.diagnosis || "–"}</td>
                  <td className="px-4 py-2.5">
                    <Chip tone={STATUS_TONE[c.status]}>{c.status.replace("_", " ")}</Chip>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-inkmid">{c.attempts}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-inkmid">{c.contacts_made}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium"
                      style={c.recovered_paise > 0 ? { color: "var(--status-good)" } : undefined}>
                    {c.recovered_paise > 0 ? inr(c.recovered_paise) : "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <EmptyState icon="⌕" title="No cases match these filters">
            Try clearing the search box or switching back to “All causes”.
          </EmptyState>
        )}
      </Card>
    </div>
  );
}
