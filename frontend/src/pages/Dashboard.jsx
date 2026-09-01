import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api.js";
import { inr, inrCompact, CAUSE_LABEL } from "../format.js";
import { Card, SectionCard, StatTile, Meter, PageSkeleton, ErrorState, EmptyState } from "../components/ui.jsx";

const S1 = "var(--series-1)";
const S3 = "var(--series-3)";
const NEUTRAL = "var(--neutral-mark)";
const AXIS = { fontSize: 12, fill: "var(--text-secondary)" };
const GRID = "var(--border)";

const STRATEGY_LABEL = {
  DO_NOTHING: "Do nothing",
  NAIVE: "Naive retry ×3",
  AGENT: "Agent",
  ORACLE: "Oracle",
};

function StrategyChart({ strategies }) {
  const data = ["DO_NOTHING", "NAIVE", "AGENT", "ORACLE"]
    .filter((s) => strategies[s])
    .map((s) => ({
      key: s,
      name: STRATEGY_LABEL[s],
      recovered: strategies[s].recovered_paise,
      isAgent: s === "AGENT",
    }));

  return (
    <ResponsiveContainer width="100%" height={230}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 64, left: 0, bottom: 0 }}>
        <CartesianGrid horizontal={false} stroke={GRID} />
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="name" width={104} tickLine={false}
               axisLine={false} tick={AXIS} />
        <Tooltip cursor={{ fill: "var(--surface-2)" }}
                 formatter={(v) => [inr(v), "Recovered"]}
                 labelStyle={{ color: "var(--text-primary)", fontWeight: 600 }} />
        <Bar dataKey="recovered" radius={[0, 4, 4, 0]} barSize={22}
             label={{ position: "right", formatter: inrCompact, fontSize: 11,
                      fill: "var(--text-secondary)" }}>
          {data.map((d) => (
            <Cell key={d.key} fill={d.isAgent ? S1 : NEUTRAL} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function LearningChart({ curve }) {
  const data = curve.map((row) => ({
    cases: row.cases,
    contacts: row.contacts_per_10k,
    recovered: row.recovered_paise,
  }));
  return (
    <ResponsiveContainer width="100%" height={230}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="cases" tickLine={false} axisLine={false} tick={AXIS} />
        <YAxis tickLine={false} axisLine={false} width={34} tick={AXIS}
               domain={[0, (max) => Math.ceil(max * 1.25)]} />
        <Tooltip cursor={{ stroke: GRID }}
                 formatter={(v, n) => n === "recovered" ? [inr(v), "Recovered"]
                                                        : [v, "Contacts / ₹10k"]}
                 labelStyle={{ color: "var(--text-primary)", fontWeight: 600 }} />
        <Line type="monotone" dataKey="contacts" name="contacts" stroke={S1} strokeWidth={2}
              dot={{ r: 4, fill: S1, strokeWidth: 2, stroke: "var(--surface-1)" }}
              activeDot={{ r: 6 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function CauseBreakdown({ perCause }) {
  const rows = Object.entries(perCause).map(([cause, m]) => ({
    cause, ...m,
  })).sort((a, b) => b.recovered_paise - a.recovered_paise);
  const max = Math.max(...rows.map((r) => r.recovered_paise), 1);

  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.cause}>
          <div className="flex items-baseline gap-2 text-sm mb-1">
            <span className="font-medium">{CAUSE_LABEL[r.cause] || r.cause}</span>
            <span className="text-xs text-inkmid">
              {r.recovered_cases}/{r.cases} cases · {r.recovery_rate_pct}%
            </span>
            <span className="ml-auto tabular-nums text-sm">{inrCompact(r.recovered_paise)}</span>
          </div>
          <Meter value={r.recovered_paise} max={max} color={S3} />
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);

  const load = () => {
    setError(null);
    api.metrics().then(setMetrics).catch((e) => setError(e.message));
  };
  useEffect(load, []);

  if (error) return <ErrorState error={error} onRetry={load} />;
  if (!metrics) return <PageSkeleton />;

  const strategies = metrics.strategies || {};
  const agent = strategies.AGENT;
  if (!agent) {
    return (
      <Card>
        <EmptyState icon="◷" title="No batch results yet">
          Run the evaluation to populate the dashboard:
          <code className="block mt-2 text-xs bg-raised rounded-lg px-3 py-2 text-left">
            java -jar backend.jar --recovery.batch.enabled=true --recovery.batch.include-agent=true
          </code>
        </EmptyState>
      </Card>
    );
  }

  const oracle = strategies.ORACLE?.recovered_paise ?? 0;
  const naive = strategies.NAIVE?.recovered_paise ?? 0;
  const lift = naive > 0 ? (agent.recovered_paise / naive).toFixed(1) : null;
  const curve = agent.learning_curve || [];
  const first = curve[0]?.contacts_per_10k;
  const last = curve[curve.length - 1]?.contacts_per_10k;
  const efficiencyGain = first && last ? Math.round((1 - last / first) * 100) : null;

  return (
    <div className="space-y-4">
      {/* headline: how much of the money at risk came back */}
      <Card className="p-5 animate-risein">
        <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
          <div>
            <div className="text-[11px] font-semibold text-inkmid uppercase tracking-wider">
              Recovered by the agent
            </div>
            <div className="text-[40px] leading-none font-semibold tabular-nums mt-1.5">
              {inr(agent.recovered_paise)}
            </div>
          </div>
          <div className="text-sm text-inkmid pb-1">
            of <span className="font-medium text-ink">{inr(agent.total_at_risk_paise)}</span> at risk
            {lift && <> · <span className="font-medium text-ink">{lift}×</span> naive retrying</>}
          </div>
        </div>
        <div className="mt-4">
          <Meter value={agent.recovered_paise} max={agent.total_at_risk_paise} height={10} />
          <div className="flex justify-between text-xs text-inkmid mt-1.5">
            <span>{agent.cases_recovered} cases recovered</span>
            <span>Oracle ceiling {inrCompact(oracle)} · agent at {agent.pct_of_oracle}%</span>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Customer contacts" value={agent.contacts_made}
                  accent="var(--series-2)"
                  sub={`${agent.contacts_per_10k_recovered} per ₹10k recovered`} />
        <StatTile label="Payment attempts" value={agent.payment_attempts}
                  accent="var(--series-1)"
                  sub={`vs ${strategies.NAIVE ? 770 : "–"} for naive retry ×3`} />
        <StatTile label="Stopping rules fired" value={agent.stopping_rule_activations}
                  accent="var(--series-4)"
                  sub="guard vetoes + EV abandonments, all logged" />
        <StatTile label="Human escalations" value={agent.escalations}
                  accent="var(--series-3)"
                  sub="every case above ₹25,000" />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <SectionCard title="Recovered by strategy"
                     subtitle="Agent highlighted; oracle plays with perfect knowledge">
          <StrategyChart strategies={strategies} />
        </SectionCard>

        <SectionCard title="Learning curve"
                     subtitle="Contacts spent per ₹10k recovered, across the batch"
                     right={efficiencyGain > 0 && (
                       <span className="chip" style={{ color: "var(--status-good)",
                                                       background: "var(--status-good-bg)" }}>
                         ↓ {efficiencyGain}% waste
                       </span>
                     )}>
          <LearningChart curve={curve} />
          <p className="text-xs text-inkmid mt-2">
            Falling = Beta-Bernoulli posteriors pruning outreach that never works.
          </p>
        </SectionCard>
      </div>

      {agent.per_cause && (
        <SectionCard title="Recovery by root cause"
                     subtitle="Diagnosis is deterministic — mapped from the Razorpay error reason, not guessed by the LLM">
          <CauseBreakdown perCause={agent.per_cause} />
        </SectionCard>
      )}
    </div>
  );
}
