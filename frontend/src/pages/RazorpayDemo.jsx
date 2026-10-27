import { useState, useEffect } from "react";
import { api } from "../api.js";
import { Card, SectionCard, Chip } from "../components/ui.jsx";
import { inr, ts, STATUS_TONE } from "../format.js";

const PRESETS = [
  {
    id: "insufficient_fund",
    name: "Scenario 1: Insufficient Funds",
    amount: 249900,
    amountLabel: "₹2,499",
    reason: "insufficient_fund",
    desc: "Hard decline. AI evaluates high EV for fresh Payment Link and reaches out directly.",
    tag: "Auto-Recover Link",
    color: "#2a78d6",
  },
  {
    id: "high_value_review",
    name: "Scenario 2: High-Value Case (>₹25,000)",
    amount: 2800000,
    amountLabel: "₹28,000",
    reason: "insufficient_fund",
    desc: "Exceeds ₹25,000 threshold. AI pauses safely at Human Review for manager signoff.",
    tag: "Human-in-the-Loop",
    color: "#eb6834",
  },
  {
    id: "gateway_timeout",
    name: "Scenario 3: Gateway Network Timeout",
    amount: 499900,
    amountLabel: "₹4,999",
    reason: "gateway_timeout",
    desc: "Temporary bank downtime. AI schedules exponential backoff without bothering customer.",
    tag: "Scheduled Retry",
    color: "#1baf7a",
  },
];

export default function RazorpayDemo() {
  const [loading, setLoading] = useState(false);
  const [activeScenario, setActiveScenario] = useState(PRESETS[0].id);
  const [customAmount, setCustomAmount] = useState(2499);
  const [customReason, setCustomReason] = useState("insufficient_fund");
  const [customEmail, setCustomEmail] = useState("customer@demo.com");
  const [feed, setFeed] = useState([]);
  const [activeEvent, setActiveEvent] = useState(null);
  const [statusMessage, setStatusMessage] = useState("");

  // Load existing live cases on mount
  useEffect(() => {
    api.cases()
      .then((cases) => {
        const liveCases = cases.filter((c) => c.source === "LIVE");
        setFeed(liveCases.slice(0, 10));
      })
      .catch(() => {});
  }, []);

  // Launch official Razorpay standard checkout popup
  const launchOfficialRazorpayModal = () => {
    if (typeof window.Razorpay === "undefined") {
      setStatusMessage("Razorpay checkout.js script is still loading. Please retry in 2 seconds.");
      return;
    }

    const options = {
      key: "rzp_test_Tn6atO2fKmCFu0",
      amount: customAmount * 100,
      currency: "INR",
      name: "Acme Payments Demo",
      description: "Live Checkout Test · Revenue Recovery Demo",
      image: "https://razorpay.com/favicon.png",
      handler: function (response) {
        setStatusMessage(`Payment successful in Razorpay! Payment ID: ${response.razorpay_payment_id}`);
      },
      modal: {
        ondismiss: function () {
          setStatusMessage("Checkout modal dismissed. You can also trigger an automated failure scenario below.");
        },
      },
      prefill: {
        name: "Demo Customer",
        email: customEmail,
        contact: "+919876543210",
      },
      theme: {
        color: "#0C2340",
      },
    };

    try {
      const rzp = new window.Razorpay(options);
      rzp.on("payment.failed", function (response) {
        setStatusMessage(`Payment failed in Razorpay modal: ${response.error.description}`);
      });
      rzp.open();
    } catch (err) {
      setStatusMessage(`Error launching Razorpay modal: ${err.message}`);
    }
  };

  // Trigger simulated payment failure
  const handleSimulate = async (scenarioPreset) => {
    setLoading(true);
    setStatusMessage("");
    setActiveEvent(null);

    const payload = scenarioPreset
      ? {
          amount_paise: scenarioPreset.amount,
          error_reason: scenarioPreset.reason,
          customer_id: "judge@razorpay.com",
        }
      : {
          amount_paise: customAmount * 100,
          error_reason: customReason,
          customer_id: customEmail,
        };

    try {
      const res = await api.simulateFailure(payload);
      setActiveEvent({
        type: "payment.failed",
        paymentId: res.payment_id,
        orderId: res.razorpay_order_id,
        amount: res.amount_paise,
        error: res.error_reason,
        status: res.status,
        caseId: res.case_id,
        decision: res.decision,
      });

      // Prepend to feed
      setFeed((prev) => [res, ...prev.filter((p) => p.case_id !== res.case_id)]);
      setStatusMessage(
        res.status === "WAITING_APPROVAL"
          ? "⚠️ Payment failed! Case requires Human Approval (>₹25k). Check the Approvals tab!"
          : "✅ Payment failed! AI intercepted, diagnosed error, and triggered recovery action."
      );
    } catch (err) {
      setStatusMessage(`Simulation error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Simulate customer paying the recovery link
  const handleSimulatePayment = async (caseId) => {
    setLoading(true);
    try {
      const res = await api.simulatePayment({ case_id: caseId });
      setFeed((prev) =>
        prev.map((item) => (item.case_id === caseId ? { ...item, status: "RECOVERED", recovered_paise: item.amount_paise } : item))
      );
      if (activeEvent && activeEvent.caseId === caseId) {
        setActiveEvent((prev) => ({ ...prev, status: "RECOVERED" }));
      }
      setStatusMessage("🎉 Payment recovered! Case status updated to RECOVERED across the engine.");
    } catch (err) {
      setStatusMessage(`Error recording payment: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-line">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight">Razorpay Live Demo & Payment Simulator</h1>
          </div>
          <p className="text-xs text-inkmid mt-1">
            Simulate live checkout failures and watch the AI engine diagnose, govern, and recover payments in real time.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="chip !bg-blue-500/10 !text-blue-500 text-xs font-mono">
            API Key: rzp_test_Tn6...
          </span>
          <button
            onClick={launchOfficialRazorpayModal}
            className="btn btn-primary bg-[#0C2340] hover:bg-[#1a385f] text-white text-xs font-semibold px-4 py-2"
          >
            💳 Open Real Razorpay Modal
          </button>
        </div>
      </div>

      {statusMessage && (
        <div className="p-3 rounded-lg border border-line bg-raised text-sm flex items-center justify-between animate-risein">
          <span>{statusMessage}</span>
          <button onClick={() => setStatusMessage("")} className="text-xs text-inkmute hover:text-ink">
            Dismiss
          </button>
        </div>
      )}

      {/* Grid: Simulator & Scenarios (Left) + Razorpay Merchant Dashboard Feed (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Demo Scenarios (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <SectionCard
            title="⚡ 1-Click Presentation Scenarios"
            subtitle="Click any scenario to trigger the exact failure event during a live demo."
          >
            <div className="space-y-3 mt-3">
              {PRESETS.map((preset) => (
                <div
                  key={preset.id}
                  onClick={() => setActiveScenario(preset.id)}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                    activeScenario === preset.id
                      ? "border-series1 bg-surface shadow-sm"
                      : "border-line bg-sunken/40 hover:bg-surface/80"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold text-sm">{preset.name}</div>
                      <div className="text-xs text-inkmid mt-1">{preset.desc}</div>
                    </div>
                    <span className="chip text-[11px] font-mono shrink-0" style={{ color: preset.color, borderColor: preset.color }}>
                      {preset.amountLabel}
                    </span>
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-line/60 flex items-center justify-between">
                    <span className="text-[11px] text-inkmute font-medium">{preset.tag}</span>
                    <button
                      disabled={loading}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSimulate(preset);
                      }}
                      className="btn btn-primary text-xs !py-1 !px-3"
                    >
                      {loading ? "Running..." : "Simulate This"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>

          {/* Custom Trigger */}
          <SectionCard title="🛠️ Custom Failure Parameters" subtitle="Specify custom amount and failure reason.">
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-inkmid font-medium mb-1">Amount (₹)</label>
                <input
                  type="number"
                  value={customAmount}
                  onChange={(e) => setCustomAmount(Number(e.target.value))}
                  className="field w-full"
                  min="1"
                />
              </div>

              <div>
                <label className="block text-inkmid font-medium mb-1">Customer Email</label>
                <input
                  type="email"
                  value={customEmail}
                  onChange={(e) => setCustomEmail(e.target.value)}
                  className="field w-full"
                />
              </div>

              <div>
                <label className="block text-inkmid font-medium mb-1">Failure Reason Code</label>
                <select
                  value={customReason}
                  onChange={(e) => setCustomReason(e.target.value)}
                  className="field w-full"
                >
                  <option value="insufficient_fund">insufficient_fund (Hard Decline)</option>
                  <option value="card_expired">card_expired (Hard Decline)</option>
                  <option value="gateway_timeout">gateway_timeout (Transient Soft Decline)</option>
                  <option value="do_not_honor">do_not_honor (Unrecoverable)</option>
                </select>
              </div>

              <button
                disabled={loading}
                onClick={() => handleSimulate(null)}
                className="btn btn-ghost w-full justify-center text-xs mt-2"
              >
                {loading ? "Simulating..." : "Trigger Custom Failure"}
              </button>
            </div>
          </SectionCard>
        </div>

        {/* Right Column: Simulated Razorpay Merchant Dashboard Feed (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Active Live Event Callout (if just simulated) */}
          {activeEvent && (
            <Card className="p-4 border-series1 bg-series1/5 animate-risein">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-red-600 dark:text-red-400">
                      Live Payment Intercepted
                    </span>
                  </div>
                  <div className="text-base font-bold mt-1">
                    {inr(activeEvent.amount)} · {activeEvent.error}
                  </div>
                  <div className="text-xs text-inkmid font-mono mt-0.5">
                    ID: {activeEvent.paymentId} · Case: {activeEvent.caseId?.slice(0, 8)}
                  </div>
                </div>

                <div className="text-right">
                  <Chip tone={STATUS_TONE[activeEvent.status] || "idle"}>{activeEvent.status}</Chip>
                </div>
              </div>

              {activeEvent.decision?.timeline && (
                <div className="mt-3 pt-3 border-t border-line/60 text-xs">
                  <div className="font-semibold text-inkmute mb-1">Agent Action Sequence:</div>
                  <div className="flex flex-wrap gap-1.5">
                    {activeEvent.decision.timeline.map((step, idx) => (
                      <span key={idx} className="chip bg-raised border border-line text-[11px] font-mono">
                        {step.node} ➔ {step.action || step.outcome || "ok"}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-3 flex items-center justify-between pt-2">
                <a
                  href={`#/cases/${activeEvent.caseId}`}
                  className="text-xs font-semibold text-series1 hover:underline"
                >
                  Inspect Full Decision Trace ➔
                </a>

                {activeEvent.status !== "RECOVERED" && (
                  <button
                    disabled={loading}
                    onClick={() => handleSimulatePayment(activeEvent.caseId)}
                    className="btn btn-approve text-xs !py-1 !px-3 font-medium"
                  >
                    Simulate Customer Paid (Recover)
                  </button>
                )}
              </div>
            </Card>
          )}

          {/* Razorpay Merchant Payments Feed Card */}
          <Card className="overflow-hidden">
            <div className="p-4 bg-[#0C2340] text-white flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-6 h-6 rounded bg-[#3395FF] text-white font-black text-xs grid place-items-center">
                  R
                </div>
                <div>
                  <div className="text-xs font-bold tracking-tight">Razorpay Merchant Dashboard</div>
                  <div className="text-[10px] text-white/70">Live Test Payments Feed & Webhook Dispatcher</div>
                </div>
              </div>
              <span className="text-[10px] bg-white/10 px-2 py-0.5 rounded text-white/90 font-mono">
                Test Mode Active
              </span>
            </div>

            <div className="divide-y divide-line max-h-[560px] overflow-y-auto">
              {feed.length === 0 ? (
                <div className="p-8 text-center text-xs text-inkmute">
                  No live payments in feed yet. Click &quot;Simulate This&quot; on any scenario to start!
                </div>
              ) : (
                feed.map((c) => {
                  const isRecovered = c.status === "RECOVERED";
                  return (
                    <div key={c.case_id} className="p-4 hover:bg-raised/40 transition-colors">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm">{inr(c.amount_paise)}</span>
                            <span className="font-mono text-xs text-inkmute">
                              {c.razorpay_payment_id || c.case_id?.slice(0, 12)}
                            </span>
                            <span className="chip !text-[10px] !py-0 !px-1.5 uppercase font-semibold bg-red-500/10 text-red-500">
                              {c.error_reason || "declined"}
                            </span>
                          </div>

                          <div className="text-xs text-inkmid mt-1 flex items-center gap-3">
                            <span>{c.customer_id || "customer@demo.com"}</span>
                            <span>·</span>
                            <span>{ts(c.created_at)}</span>
                          </div>
                        </div>

                        <div className="flex flex-col items-end gap-1.5">
                          <Chip tone={STATUS_TONE[c.status] || "idle"}>{c.status}</Chip>

                          <div className="flex items-center gap-2 mt-1">
                            {!isRecovered && (
                              <button
                                disabled={loading}
                                onClick={() => handleSimulatePayment(c.case_id)}
                                className="text-[11px] font-semibold text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 hover:underline"
                              >
                                Pay Link ➔
                              </button>
                            )}
                            <a
                              href={`#/cases/${c.case_id}`}
                              className="text-[11px] font-semibold text-inkmid hover:text-ink hover:underline"
                            >
                              Timeline
                            </a>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
