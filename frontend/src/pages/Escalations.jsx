import { useEffect, useState } from "react";
import { api } from "../api.js";
import { inr, shortId, CAUSE_LABEL, ts } from "../format.js";
import { Card, SectionCard, Chip, Skeleton, EmptyState, ErrorState } from "../components/ui.jsx";

export default function Escalations({ onCountChange }) {
  const [pending, setPending] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);       // case_id currently resolving
  const [results, setResults] = useState([]);   // resolved during this session

  const refresh = () => {
    setError(null);
    return api.escalations()
      .then((r) => { setPending(r); onCountChange?.(r.length); })
      .catch((e) => setError(e.message));
  };
  useEffect(() => { refresh(); }, []);

  const resolve = async (caseId, approved) => {
    setBusy(caseId);
    try {
      const r = await api.resolveEscalation(caseId, approved);
      setResults((prev) => [{ ...r, at: new Date().toISOString() }, ...prev]);
    } catch (e) {
      setResults((prev) => [{ case_id: caseId, error: e.message }, ...prev]);
    } finally {
      setBusy(null);
      refresh();
    }
  };

  if (error) return <ErrorState error={error} onRetry={refresh} />;
  if (!pending) return <div className="space-y-3"><Skeleton className="h-40" /></div>;

  const queueValue = pending.reduce((s, e) => s + e.amount_paise, 0);

  return (
    <div className="space-y-4">
      <SectionCard
        title="Pending approvals"
        subtitle="Cases above ₹25,000 pause here before any action is taken. Approving resumes the agent from its Postgres checkpoint — the pause survives an agent restart."
        right={pending.length > 0 && (
          <div className="text-right">
            <div className="text-xl font-semibold tabular-nums">{inr(queueValue)}</div>
            <div className="text-xs text-inkmid">waiting on you</div>
          </div>
        )}>
        {pending.length === 0 ? (
          <EmptyState icon="✓" title="Queue is empty">
            Nothing is waiting for a human. High-value cases will appear here the moment
            the guard pauses one.
          </EmptyState>
        ) : (
          <ul className="space-y-2.5">
            {pending.map((e) => (
              <li key={e.case_id}
                  className="rounded-xl border p-4 flex items-center gap-4 flex-wrap animate-risein"
                  style={{ borderColor: "var(--status-warning)", background: "var(--status-warning-bg)" }}>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xl font-semibold tabular-nums">{inr(e.amount_paise)}</span>
                    <a href={`#/cases/${e.case_id}`}
                       className="font-mono text-[13px] text-series1 hover:underline">
                      {shortId(e.case_id)}
                    </a>
                    <Chip tone="warning">Waiting approval</Chip>
                  </div>
                  <div className="text-xs text-inkmid mt-1.5">
                    <span className="font-mono">{e.error_reason}</span>
                    {e.diagnosis && <> · {CAUSE_LABEL[e.diagnosis] || e.diagnosis}</>}
                    {" · "}{e.customer_id || "unknown customer"} · opened {ts(e.created_at)}
                  </div>
                </div>
                <div className="ml-auto flex gap-2">
                  <button disabled={busy === e.case_id} onClick={() => resolve(e.case_id, true)}
                          className="btn-approve">
                    {busy === e.case_id ? "Resuming…" : "Approve"}
                  </button>
                  <button disabled={busy === e.case_id} onClick={() => resolve(e.case_id, false)}
                          className="btn-ghost">Reject</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {results.length > 0 && (
        <SectionCard title="Resolved just now"
                     subtitle="Each approval resumed a paused LangGraph run from its checkpoint">
          <ul className="space-y-2 text-sm">
            {results.map((r, i) => (
              <li key={i} className="flex items-center gap-2.5 flex-wrap">
                {r.error ? (
                  <>
                    <Chip tone="critical">Failed</Chip>
                    <span className="text-inkmid">Case {shortId(r.case_id)}: {r.error}</span>
                  </>
                ) : (
                  <>
                    <Chip tone={r.approved ? "good" : "idle"}>
                      {r.approved ? "Approved" : "Rejected"}
                    </Chip>
                    <a href={`#/cases/${r.case_id}`} className="font-mono text-[13px] text-series1">
                      {shortId(r.case_id)}
                    </a>
                    <span className="text-inkmid">→ {r.final_status}</span>
                    {r.recovered_paise > 0 && (
                      <span className="font-medium tabular-nums"
                            style={{ color: "var(--status-good)" }}>
                        recovered {inr(r.recovered_paise)}
                      </span>
                    )}
                  </>
                )}
              </li>
            ))}
          </ul>
        </SectionCard>
      )}
    </div>
  );
}
