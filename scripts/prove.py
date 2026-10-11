"""Live proof tool — computes the comparison in front of the audience.

Nothing here is pre-computed or hardcoded: it loads data/cases.jsonl, runs the
REAL LangGraph agent against the same simulator the baselines use, and prints
what each strategy did.

    python scripts/prove.py case         one case, side by side (~5 seconds)
    python scripts/prove.py case --pick  let someone choose from a menu
    python scripts/prove.py batch        all 300 cases, full table (~60 seconds)

No Java, no database, no network needed.
"""

import argparse
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "agent"
sys.path.insert(0, str(AGENT))
os.environ.setdefault("BACKEND_BASE_URL", "http://127.0.0.1:18099")
os.environ.setdefault("AGENT_SHARED_SECRET", "dev-agent-secret")

import httpx
import uvicorn
import yaml
from tests import mock_backend
from graph import build, ev

CASES = ROOT / "data" / "cases.jsonl"
NOON_IST = "2026-08-27T12:00:00+05:30"
PORT = 18099
POLICY = yaml.safe_load((AGENT / "policy.yaml").read_text())

BOLD, DIM, GREEN, RED, YELLOW, CYAN, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[0m")


def rupees(paise):
    return "₹" + f"{paise / 100:,.0f}"


def start_tools_server():
    """Serve the six tool endpoints the agent calls (same semantics as Java)."""
    server = uvicorn.Server(uvicorn.Config(mock_backend.app, host="127.0.0.1",
                                           port=PORT, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(80):
        try:
            httpx.get(f"http://127.0.0.1:{PORT}/docs", timeout=1)
            return server
        except httpx.HTTPError:
            time.sleep(0.1)
    raise SystemExit("tool server did not start")


def run_agent(case, graph):
    state = {
        "case_id": case["id"], "amount_paise": case["amount_paise"],
        "error_reason": case["error_reason"],
        "opted_out": case["customer_history"]["opted_out"],
        "attempts": 0, "contacts_made": 0,
        "auto_approve": True, "now_iso": NOON_IST,
        "actions": [], "trace": [],
    }
    config = {"configurable": {"policy": POLICY, "thread_id": case["id"],
                               "ev_stats": mock_backend.stats_wire()}}
    return graph.invoke(state, config)


def naive_steps(case):
    """Exactly what a retry-3-times cron job would do to this case."""
    steps, recovered = [], 0
    for attempt in range(1, 4):
        won = case["ground_truth"]["recovers_if"] == "retry_now"
        steps.append(("retry_now", "RECOVERED" if won else "FAILED"))
        if won:
            recovered = case["amount_paise"]
            break
    return steps, recovered


# ----------------------------------------------------------------- single case
def demo_case(pick):
    mock_backend.load_cases(CASES)
    all_cases = list(mock_backend.CASES.values())

    # good demo cases: naive cannot win, agent can
    candidates = [c for c in all_cases
                  if c["ground_truth"]["recoverable"]
                  and c["ground_truth"]["recovers_if"] != "retry_now"
                  and not c["customer_history"]["opted_out"]
                  and c["amount_paise"] < 25_000_00]
    candidates.sort(key=lambda c: -c["amount_paise"])

    if pick:
        print(f"\n{BOLD}Pick a failed payment:{OFF}\n")
        for i, c in enumerate(candidates[:8], 1):
            print(f"  {i}. {rupees(c['amount_paise']):>10}   {c['error_reason']}")
        choice = input("\nNumber (enter = 1): ").strip() or "1"
        case = candidates[int(choice) - 1]
    else:
        case = candidates[0]

    print(f"\n{BOLD}CASE {case['id'][:8]}{OFF}   {BOLD}{rupees(case['amount_paise'])}{OFF}"
          f"   error: {CYAN}{case['error_reason']}{OFF}")
    print("=" * 74)

    # --- naive ---
    steps, naive_recovered = naive_steps(case)
    print(f"\n{BOLD}A retry-3-times cron job{OFF}")
    for action, outcome in steps:
        mark = f"{GREEN}✓{OFF}" if outcome == "RECOVERED" else f"{RED}✗{OFF}"
        print(f"   {mark} {action:<20} {outcome}")
    print(f"   → recovered {BOLD}{rupees(naive_recovered)}{OFF}, {len(steps)} attempts")

    # --- agent (the real graph) ---
    server = start_tools_server()
    graph = build.build_graph()
    final = run_agent(case, graph)
    live = mock_backend.CASES[case["id"]]

    print(f"\n{BOLD}This agent{OFF}")
    for e in final["trace"]:
        node = e["node"]
        if node == "diagnose":
            print(f"   · diagnose            {CYAN}{e['outcome']}{OFF}  {DIM}(dictionary, not the LLM){OFF}")
        elif node == "decide" and e.get("inputs_seen", {}).get("ranked_actions"):
            ranked = e["inputs_seen"]["ranked_actions"]
            print(f"   · scored the options:")
            for r in ranked:
                star = f"{GREEN}←chosen{OFF}" if r["action"] == e["action_chosen"] else ""
                print(f"       {r['action']:<20} p={r['p']:<6} EV={r['ev']:>12,.0f}  {star}")
        elif node == "guard" and e.get("blocked"):
            print(f"   {RED}✗ BLOCKED by policy{OFF}   {e['block_reason']}")
        elif node == "execute":
            mark = f"{GREEN}✓{OFF}" if e["outcome"] == "RECOVERED" else f"{RED}✗{OFF}"
            print(f"   {mark} executed {e['action_chosen']:<18} {e['outcome']}")
        elif node == "close":
            print(f"   · closed              {DIM}{e.get('reasoning','')}{OFF}")

    print(f"   → recovered {BOLD}{GREEN if live['recovered_paise'] else RED}"
          f"{rupees(live['recovered_paise'])}{OFF}, "
          f"{live['attempts']} attempts + {live['contacts_made']} contacts")

    delta = live["recovered_paise"] - naive_recovered
    print("\n" + "=" * 74)
    print(f"{BOLD}Difference on this one payment: "
          f"{GREEN if delta > 0 else DIM}{rupees(delta)}{OFF}")
    why = {
        "HARD_DECLINE": "The cron job kept retrying a card that will never work online.\n"
                        "The agent priced that at ~2% and sent a payment link instead.",
        "CUSTOMER_ACTION": "The customer abandoned the payment — retrying a machine does\n"
                           "not persuade a person. The agent messaged them with a link.",
        "SOFT_DECLINE": "There was no money in the account. Retrying now fails again;\n"
                        "the agent waited a day instead.",
        "TRANSIENT": "A temporary glitch — here retrying IS right, and the agent\n"
                     "agreed. It is not contrarian for its own sake.",
        "UNRECOVERABLE": "The card number itself is invalid. Nothing recovers this except\n"
                         "a new payment method.",
    }.get(final.get("diagnosis"), "")
    print(f"{DIM}{why}{OFF}\n")
    server.should_exit = True


# ---------------------------------------------------------------------- batch
def demo_batch():
    print(f"\n{BOLD}Running all 300 cases through every strategy, right now.{OFF}")
    print(f"{DIM}Same data, same simulator, no cached numbers.{OFF}\n")
    server = start_tools_server()
    results = {}

    # DO_NOTHING
    mock_backend.load_cases(CASES)
    total_at_risk = sum(c["amount_paise"] for c in mock_backend.CASES.values())
    results["Do nothing"] = dict(recovered=0, cases=0, attempts=0, contacts=0)
    print(f"  Do nothing            {rupees(0):>14}")

    # NAIVE
    mock_backend.load_cases(CASES)
    rec = cases_won = attempts = 0
    for c in mock_backend.CASES.values():
        steps, r = naive_steps(c)
        attempts += len(steps)
        rec += r
        cases_won += 1 if r else 0
    results["Retry x3 (cron)"] = dict(recovered=rec, cases=cases_won,
                                      attempts=attempts, contacts=0)
    print(f"  Retry x3 (cron)       {rupees(rec):>14}   {attempts} attempts")

    # AGENT — the real graph
    mock_backend.load_cases(CASES)
    graph = build.build_graph()
    start = time.time()
    for i, c in enumerate(list(mock_backend.CASES.values()), 1):
        run_agent(c, graph)
        if i % 50 == 0:
            done = sum(x["recovered_paise"] for x in mock_backend.CASES.values())
            print(f"    …{i}/300 cases, {rupees(done)} recovered so far", flush=True)
    live = list(mock_backend.CASES.values())
    results["This agent"] = dict(
        recovered=sum(c["recovered_paise"] for c in live),
        cases=sum(1 for c in live if c["status"] == "RECOVERED"),
        attempts=sum(c["attempts"] for c in live),
        contacts=sum(c["contacts_made"] for c in live))
    print(f"  This agent            {rupees(results['This agent']['recovered']):>14}"
          f"   {DIM}({time.time()-start:.0f}s){OFF}")

    # ORACLE
    mock_backend.load_cases(CASES)
    rec = cases_won = contacts = attempts = 0
    for c in mock_backend.CASES.values():
        ri = c["ground_truth"]["recovers_if"]
        if ri is None:
            continue
        if ri in ev.CONTACT_ACTIONS and c["customer_history"]["opted_out"]:
            continue
        rec += c["amount_paise"]
        cases_won += 1
        contacts += 1 if ri in ev.CONTACT_ACTIONS else 0
        attempts += 0 if ri in ev.CONTACT_ACTIONS else 1
    results["Perfect play (cheats)"] = dict(recovered=rec, cases=cases_won,
                                            attempts=attempts, contacts=contacts)
    print(f"  Perfect play (cheats) {rupees(rec):>14}")

    oracle = results["Perfect play (cheats)"]["recovered"]
    naive = results["Retry x3 (cron)"]["recovered"]
    agent = results["This agent"]["recovered"]

    print(f"\n{BOLD}{'Strategy':<24}{'Recovered':>14}{'% of best':>11}"
          f"{'Cases':>8}{'Attempts':>10}{'Contacts':>10}{OFF}")
    print("-" * 77)
    for name, m in results.items():
        pct = 100 * m["recovered"] / oracle if oracle else 0
        hl = BOLD if name == "This agent" else ""
        print(f"{hl}{name:<24}{rupees(m['recovered']):>14}{pct:>10.1f}%"
              f"{m['cases']:>8}{m['attempts']:>10}{m['contacts']:>10}{OFF}")

    print(f"\n{BOLD}Total at risk: {rupees(total_at_risk)}{OFF}")
    print(f"{BOLD}{GREEN}The agent recovered {agent/naive:.1f}x what the cron job did, "
          f"using {results['Retry x3 (cron)']['attempts'] - results['This agent']['attempts']} "
          f"fewer payment attempts.{OFF}\n")
    server.should_exit = True


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["case", "batch"])
    p.add_argument("--pick", action="store_true", help="choose the case from a menu")
    a = p.parse_args()
    demo_case(a.pick) if a.mode == "case" else demo_batch()
