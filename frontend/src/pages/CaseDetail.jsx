import { useEffect, useState } from "react";
import { api } from "../api.js";
import { inr, shortId, STATUS_TONE, CAUSE_LABEL, ts } from "../format.js";
import { Card, Chip, Meter, Skeleton, ErrorState } from "../components/ui.jsx";

/** Each graph node gets a colour + glyph so the timeline is scannable. */
const NODE_META = {
  detect:        { color: "var(--text-secondary)", glyph: "!", label: "Detected" },
  diagnose:      { color: "var(--series-3)",       glyph: "◎", label: "Diagnose" },
  decide:        { color: "var(--series-1)",       glyph: "⚖", label: "Decide" },
  guard:         { color: "var(--series-4)",       glyph: "⛨", label: "Guard" },
  execute:       { color: "var(--series-2)",       glyph: "→", label: "Execute" },
  check_outcome: { color: "var(--text-muted)",     glyph: "?", label: "Check outcome" },
  human_review:  { color: "#7a5af5",               glyph: "☺", label: "Human review" },
  close:         { color: "var(--text-muted)",     glyph: "×", label: "Close" },
};

const OUTCOME_TONE = {
  RECOVERED: "good", APPROVED: "good", ALLOWED: "good",
  FAILED: "idle", CLOSED: "idle", PENDING: "info", DETECTED: "idle",
  VETO: "critical", HARD_STOP: "critical", REJECTED: "critical",
  NEEDS_APPROVAL: "warning", WAITING_APPROVAL: "warning", ESCALATED: "warning",
};

function RankedActions({ ranked }) {
  if (!ranked?.length) return null;
  const max = Math.max(...ranked.map((r) => Math.abs(r.ev)), 1);
  return (
    <div className="mt-2.5 bg-raised rounded-lg p-2.5 space-y-1.5">
      <div className="text-[10px] uppercase tracking-wider text-inkmute font-semibold">
        Expected value ranking the agent saw
      </div>
      {ranked.map((r, i) => (
        <div key={r.action} className="flex items-center gap-2.5">
          <span className={"font-mono text-[11px] w-[132px] shrink-0 " +
                           (i === 0 ? "text-ink font-medium" : "text-inkmid")}>
            {r.action}
          </span>
          <div className="flex-1 min-w-0">
            <Meter value={Math.max(r.ev, 0)} max={max} height={4}
                   color={i === 0 ? "var(--series-1)" : "var(--neutral-mark)"} />
          </div>
          <span className="text-[11px] text-inkmid tabular-nums w-14 text-right">
            p={r.p}
          </span>
          <span className="text-[11px] tabular-nums w-16 text-right">
            {Math.round(r.ev)}
          </span>
        </div>
      ))}
    </div>
  );
}

function inputsChips(inputs) {
  if (!inputs) return [];
  const out = [];
  if (inputs.attempts != null) out.push(`attempts ${inputs.attempts}`);
  if (inputs.contacts_made != null) out.push(`contacts ${inputs.contacts_made}`);
  if (inputs.decide_loop != null) out.push(`loop ${inputs.decide_loop}`);
  if (inputs.vetoed_actions?.length) out.push(`vetoed: ${inputs.vetoed_actions.join(", ")}`);
  if (inputs.decide_mode) out.push(`mode ${inputs.decide_mode}`);
  if (inputs.learned_stats) out.push("learned priors");
  return out;
}

function toCsv(timeline) {
  const cols = ["ts", "node", "action_chosen", "reasoning", "ev_score",
    "blocked", "block_reason", "outcome", "attempt_number"];
  const esc = (v) => (v == null ? "" : `"${String(v).replaceAll('"', '""')}"`);
  return [cols.join(","), ...timeline.map((e) => cols.map((c) => esc(e[c])).join(","))].join("\n");
}

function formatReasoning(text) {
  if (!text) return null;
  const match = text.match(/(https?:\/\/[^\s)]+)/);
  if (!match) return <p className="text-sm mt-1.5">{text}</p>;

  const url = match[0];
  const parts = text.split(url);
  return (
    <div className="mt-1.5 space-y-1.5">
      <p className="text-sm">
        {parts[0]}
        <span className="text-inkmid text-xs">{parts[1] || ""}</span>
      </p>
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg bg-blue-500/15 text-blue-500 hover:bg-blue-500/25 border border-blue-500/30 transition-all"
      >
        🔗 Open Payment Link: <span className="underline font-mono">{url}</span> ↗
      </a>
    </div>
  );
}

export default function CaseDetail({ id }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);
  const [actionMsg, setActionMsg] = useState(null);

  const load = () => {
    setError(null);
    api.caseDetail(id).then(setData).catch((e) => setError(e.message));
  };
  useEffect(load, [id]);

  // Real-time SSE: auto-refresh when webhooks or recovery actions occur
  useEffect(() => {
    const base = import.meta.env.VITE_API_BASE || "";
    const es = new EventSource(base + "/api/events");
    es.addEventListener("case_update", (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (!payload.case_id || payload.case_id === id) {
          load();
        }
      } catch (err) {
        load();
      }
    });
    es.onerror = () => { es.close(); };
    return () => es.close();
  }, [id]);

  const handleSimulatePayment = async () => {
    setActionLoading("pay");
    setActionMsg(null);
    try {
      await api.simulatePayment({ case_id: id });
      setActionMsg("✓ Payment simulated! Case status updated to RECOVERED.");
      load();
    } catch (e) {
      setActionMsg("✕ Error: " + e.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleCloseCase = async () => {
    if (!window.confirm("Manually close/abandon recovery for this case?")) return;
    setActionLoading("close");
    setActionMsg(null);
    try {
      await api.closeCase(id);
      setActionMsg("✕ Case closed.");
      load();
    } catch (e) {
      setActionMsg("✕ Error: " + e.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleProcessCase = async () => {
    setActionLoading("process");
    setActionMsg(null);
    try {
      await api.processCase(id);
      setActionMsg("⚡ Agent re-evaluated case and executed recovery action.");
      load();
    } catch (e) {
      setActionMsg("✕ Error: " + e.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handlePayWithRazorpay = () => {
    if (!window.Razorpay) {
      alert("Razorpay checkout script not loaded yet");
      return;
    }

    // Pick latest retry order created by the agent if present in timeline
    let targetOrderId = data.razorpay_order_id;
    if (data.timeline) {
      for (const entry of data.timeline) {
        if (entry.reasoning && entry.reasoning.includes("retry order created:")) {
          const match = entry.reasoning.match(/retry order created:\s*(order_[A-Za-z0-9]+)/);
          if (match) targetOrderId = match[1];
        }
      }
    }

    const options = {
      key: "rzp_test_Tn6atO2fKmCFu0",
      amount: data.amount_paise,
      currency: data.currency || "INR",
      name: "Razorpay Revenue Recovery",
      description: `Paying Recovery Order ${targetOrderId}`,
      order_id: targetOrderId,
      prefill: {
        name: "Demo Customer",
        email: data.customer_id?.includes("@") ? data.customer_id : "customer@example.com",
        contact: "+919876543210",
      },
      theme: { color: "#0C2340" },
      handler: async function (response) {
        setActionMsg(`🎉 Payment succeeded on Razorpay! Payment ID: ${response.razorpay_payment_id}. Marking as RECOVERED...`);
        try {
          await api.simulatePayment({ case_id: id });
        } catch (e) {}
        load();
      },
      modal: {
        ondismiss: function () {
          setActionMsg("Razorpay checkout modal closed.");
        },
      },
    };

    try {
      const rzp = new window.Razorpay(options);
      rzp.on("payment.failed", function (response) {
        setActionMsg(`Payment failed in checkout modal: ${response.error?.description || "declined"}`);
      });
      rzp.open();
    } catch (err) {
      setActionMsg("Error opening Razorpay modal: " + err.message);
    }
  };

  if (error) return <ErrorState error={error} onRetry={load} />;
  if (!data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-[136px]" />
        <Skeleton className="h-[420px]" />
      </div>
    );
  }

  const exportCsv = () => {
    const blob = new Blob([toCsv(data.timeline || [])], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `case-${shortId(data.case_id)}-decisions.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const history = data.customer_history || {};
  const fields = [
    ["Amount", inr(data.amount_paise)],
    ["Error reason", <span className="font-mono text-[13px]">{data.error_reason}</span>],
    ["Diagnosis", CAUSE_LABEL[data.diagnosis] || data.diagnosis || "–"],
    ["Attempts", `${data.attempts} / 3`],
    ["Contacts", `${data.contacts_made} / 2`],
    ["Recovered", data.recovered_paise > 0
      ? <span style={{ color: "var(--status-good)" }}>{inr(data.recovered_paise)}</span> : "–"],
    ["Razorpay Order", data.razorpay_order_id ? <span className="font-mono text-[12px]">{data.razorpay_order_id}</span> : "–"],
    ["Customer", data.customer_id || "–"],
    ["History", history.past_success != null
      ? `${history.past_success} paid / ${history.past_failures} failed${history.opted_out ? " · opted out" : ""}`
      : "–"],
  ];
  const blockedCount = (data.timeline || []).filter((e) => e.blocked).length;

  return (
    <div className="space-y-4">
      <Card className="p-5 animate-risein">
        <div className="flex items-center gap-3 flex-wrap">
          <a href="#/cases" className="text-sm text-inkmid hover:text-ink">← All cases</a>
          <h1 className="font-semibold tracking-tight">
            Case <span className="font-mono">{shortId(data.case_id)}</span>
          </h1>
          <Chip tone={STATUS_TONE[data.status]}>{data.status.replace("_", " ")}</Chip>
          {data.source === "LIVE" && <Chip tone="info">LIVE webhook</Chip>}
          
          <div className="ml-auto flex items-center gap-2 flex-wrap">
            {["DETECTED", "IN_PROGRESS", "SCHEDULED"].includes(data.status) && (
              <>
                {data.razorpay_order_id && (
                  <button
                    onClick={handlePayWithRazorpay}
                    className="btn bg-[#0C2340] hover:bg-[#1a385f] text-white text-xs !py-1 !px-3 font-semibold shadow-sm"
                    title="Pay this specific Order ID directly using Razorpay Checkout modal"
                  >
                    💳 Pay This Order (Razorpay Modal)
                  </button>
                )}
                <button
                  onClick={handleSimulatePayment}
                  disabled={!!actionLoading}
                  className="btn btn-approve text-xs !py-1 !px-3 font-medium shadow-sm"
                  title="Simulate customer paying the link/order to mark as RECOVERED"
                >
                  {actionLoading === "pay" ? "Marking..." : "✓ Mark Customer Paid (Recover)"}
                </button>
                <button
                  onClick={handleProcessCase}
                  disabled={!!actionLoading}
                  className="btn btn-primary text-xs !py-1 !px-3 font-medium shadow-sm"
                  title="Re-run agent decision graph immediately"
                >
                  {actionLoading === "process" ? "Running..." : "⚡ Run Agent"}
                </button>
                <button
                  onClick={handleCloseCase}
                  disabled={!!actionLoading}
                  className="btn btn-ghost text-xs !py-1 !px-3 font-medium text-rose-500 hover:text-rose-600"
                  title="Abandon recovery and close case"
                >
                  {actionLoading === "close" ? "Closing..." : "✕ Close Case"}
                </button>
              </>
            )}
            <button onClick={exportCsv} className="btn-ghost text-xs !py-1 !px-3">Export CSV</button>
          </div>
        </div>

        {actionMsg && (
          <div className="mt-3 text-xs text-inkmid font-medium bg-raised/70 px-3 py-1.5 rounded-lg border border-line">
            {actionMsg}
          </div>
        )}

        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-3.5 mt-5 text-sm">
          {fields.map(([k, v]) => (
            <div key={k}>
              <dt className="text-[11px] text-inkmid uppercase tracking-wider font-semibold">{k}</dt>
              <dd className="mt-0.5 font-medium">{v}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card className="p-5">
        <div className="flex items-baseline gap-3 flex-wrap mb-5">
          <h2 className="text-sm font-semibold tracking-tight">Decision timeline</h2>
          <p className="text-xs text-inkmid">
            {data.timeline?.length || 0} audited entries — every input the agent saw, every choice, every block
          </p>
          {blockedCount > 0 && (
            <Chip tone="critical" className="ml-auto">{blockedCount} blocked by policy</Chip>
          )}
        </div>

        <ol className="relative space-y-2.5">
          <span className="absolute left-[15px] top-2 bottom-2 w-px bg-line" aria-hidden />
          {(data.timeline || []).map((e) => {
            const meta = NODE_META[e.node] || NODE_META.check_outcome;
            const ranked = e.inputs_seen?.ranked_actions;
            const chips = inputsChips(e.inputs_seen);
            return (
              <li key={e.id} className="relative pl-11">
                <span className="absolute left-0 top-1 w-8 h-8 rounded-full grid place-items-center
                                 text-[13px] font-semibold border-2"
                      style={{
                        color: e.blocked ? "var(--status-critical)" : meta.color,
                        borderColor: e.blocked ? "var(--status-critical)" : meta.color,
                        background: "var(--surface-1)",
                      }}
                      aria-hidden>
                  {e.blocked ? "⨯" : meta.glyph}
                </span>

                <div className="rounded-xl border p-3"
                     style={e.blocked
                       ? { borderColor: "var(--status-critical)", background: "var(--status-critical-bg)" }
                       : { borderColor: "var(--border)" }}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold uppercase tracking-wider">{meta.label}</span>
                    {e.action_chosen && (
                      <code className="text-[11px] bg-raised border border-line rounded px-1.5 py-0.5 font-mono">
                        {e.action_chosen}
                      </code>
                    )}
                    {e.ev_score != null && (
                      <span className="text-[11px] text-inkmid tabular-nums">
                        EV {Math.round(e.ev_score).toLocaleString("en-IN")}
                      </span>
                    )}
                    {e.outcome && <Chip tone={OUTCOME_TONE[e.outcome] || "idle"}>{e.outcome}</Chip>}
                    <span className="text-[11px] text-inkmute ml-auto tabular-nums">{ts(e.ts)}</span>
                  </div>

                  {e.blocked && (
                    <div className="text-sm font-medium mt-2" style={{ color: "var(--status-critical)" }}>
                      Blocked by policy — {e.block_reason}
                    </div>
                  )}
                  {formatReasoning(e.reasoning)}

                  {chips.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {chips.map((c) => (
                        <span key={c} className="text-[10px] font-mono text-inkmid bg-raised
                                                 border border-line rounded px-1.5 py-0.5">{c}</span>
                      ))}
                    </div>
                  )}
                  <RankedActions ranked={ranked} />
                </div>
              </li>
            );
          })}
        </ol>
      </Card>
    </div>
  );
}
