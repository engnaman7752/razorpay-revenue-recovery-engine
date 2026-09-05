/** Small shared primitives. Kept in one file — the whole UI is Tailwind classes
 *  over the CSS custom properties in index.css, no component library (spec §13). */

const TONE_STYLE = {
  good:    { color: "var(--status-good)",     background: "var(--status-good-bg)" },
  warning: { color: "var(--status-warning)",  background: "var(--status-warning-bg)" },
  critical:{ color: "var(--status-critical)", background: "var(--status-critical-bg)" },
  info:    { color: "var(--status-info)",     background: "var(--status-info-bg)" },
  idle:    { color: "var(--text-secondary)",  background: "var(--status-idle-bg)" },
};

export function Chip({ tone = "idle", children, className = "" }) {
  return (
    <span className={"chip " + className} style={TONE_STYLE[tone] || TONE_STYLE.idle}>
      {children}
    </span>
  );
}

export function Card({ children, className = "", ...rest }) {
  return <div className={"card " + className} {...rest}>{children}</div>;
}

export function SectionCard({ title, subtitle, right, children, className = "" }) {
  return (
    <Card className={"p-5 " + className}>
      {(title || right) && (
        <div className="flex items-start gap-3 mb-4">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold tracking-tight">{title}</h2>}
            {subtitle && <p className="text-xs text-inkmid mt-0.5">{subtitle}</p>}
          </div>
          {right && <div className="ml-auto shrink-0">{right}</div>}
        </div>
      )}
      {children}
    </Card>
  );
}

/** Big number tile. `accent` draws a left rule in a series colour. */
export function StatTile({ label, value, sub, accent, children }) {
  return (
    <Card className="p-4 relative overflow-hidden animate-risein">
      {accent && (
        <span className="absolute left-0 top-0 bottom-0 w-1" style={{ background: accent }} />
      )}
      <div className="text-[11px] font-semibold text-inkmid uppercase tracking-wider">{label}</div>
      <div className="text-[26px] leading-tight font-semibold mt-1 tabular-nums">{value}</div>
      {sub && <div className="text-xs text-inkmid mt-1 leading-snug">{sub}</div>}
      {children}
    </Card>
  );
}

/** Thin proportional bar — used for "recovered of at-risk" and EV ranking rows. */
export function Meter({ value, max, color = "var(--series-1)", track = "var(--surface-2)", height = 6 }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div className="rounded-full overflow-hidden w-full" style={{ background: track, height }}>
      <div className="h-full rounded-full transition-[width] duration-500"
           style={{ width: pct + "%", background: color }} />
    </div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={"skeleton " + className} />;
}

export function PageSkeleton({ tiles = 4, panels = 2 }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Array.from({ length: tiles }).map((_, i) => <Skeleton key={i} className="h-[92px]" />)}
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        {Array.from({ length: panels }).map((_, i) => <Skeleton key={i} className="h-[300px]" />)}
      </div>
    </div>
  );
}

export function EmptyState({ icon = "○", title, children }) {
  return (
    <div className="text-center py-10 px-6">
      <div className="text-2xl text-inkmute mb-2" aria-hidden>{icon}</div>
      <div className="font-medium">{title}</div>
      {children && <div className="text-sm text-inkmid mt-1 max-w-md mx-auto">{children}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <Card className="p-5">
      <div className="font-medium" style={{ color: "var(--status-critical)" }}>
        Couldn’t load data
      </div>
      <p className="text-sm text-inkmid mt-1">
        {String(error)} — is the backend running? Vite prints the port it proxies to when you start it.
      </p>
      {onRetry && <button className="btn-ghost mt-3" onClick={onRetry}>Retry</button>}
    </Card>
  );
}
