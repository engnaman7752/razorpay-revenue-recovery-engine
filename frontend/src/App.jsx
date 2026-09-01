import { useEffect, useState } from "react";
import { api } from "./api.js";
import { useTheme } from "./theme.js";
import Dashboard from "./pages/Dashboard.jsx";
import CaseList from "./pages/CaseList.jsx";
import CaseDetail from "./pages/CaseDetail.jsx";
import Escalations from "./pages/Escalations.jsx";

// Tiny hash router: #/ , #/cases , #/cases/<id> , #/escalations
function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const onChange = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash.replace(/^#/, "");
}

const NAV = [
  ["#/", "Dashboard"],
  ["#/cases", "Cases"],
  ["#/escalations", "Approvals"],
];

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" aria-hidden>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}
function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  );
}

export default function App() {
  const route = useHashRoute();
  const [theme, toggleTheme] = useTheme();
  const [pendingCount, setPendingCount] = useState(0);

  // keep the approvals badge fresh — this is the queue a human is waiting on
  useEffect(() => {
    const load = () => api.escalations().then((r) => setPendingCount(r.length)).catch(() => {});
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [route]);

  let page;
  const caseMatch = route.match(/^\/cases\/(.+)$/);
  if (caseMatch) page = <CaseDetail id={caseMatch[1]} />;
  else if (route === "/cases") page = <CaseList />;
  else if (route === "/escalations") page = <Escalations onCountChange={setPendingCount} />;
  else page = <Dashboard />;

  const active = caseMatch ? "#/cases" : "#" + route;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 bg-surface backdrop-blur border-b border-line">
        <div className="max-w-[1180px] mx-auto px-6 h-14 flex items-center gap-6">
          <a href="#/" className="flex items-center gap-2.5 shrink-0">
            <span className="w-7 h-7 rounded-lg grid place-items-center text-surface text-sm font-bold"
                  style={{ background: "var(--series-1)" }}>₹</span>
            <span className="font-semibold tracking-tight">Revenue Recovery Engine</span>
          </a>

          <nav className="flex gap-1 ml-2">
            {NAV.map(([href, label]) => (
              <a key={href} href={href}
                 className={"px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 " +
                   (active === href ? "bg-raised text-ink" : "text-inkmid hover:text-ink hover:bg-raised")}>
                {label}
                {href === "#/escalations" && pendingCount > 0 && (
                  <span className="chip tabular-nums !px-1.5 !py-0"
                        style={{ color: "var(--status-warning)", background: "var(--status-warning-bg)" }}>
                    {pendingCount}
                  </span>
                )}
              </a>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <span className="hidden sm:inline text-xs text-inkmute">Razorpay · test mode</span>
            <button onClick={toggleTheme} aria-label="Toggle theme"
                    className="w-8 h-8 grid place-items-center rounded-lg border border-line text-inkmid hover:text-ink hover:bg-raised transition-colors">
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-[1180px] mx-auto px-6 py-6">{page}</main>

      <footer className="max-w-[1180px] mx-auto px-6 pb-8 pt-2 text-xs text-inkmute">
        Policy-as-code governance · every decision audited in <code>decision_log</code>
      </footer>
    </div>
  );
}
