# Batch evaluation results

**Verified run** — produced by the real stack (Spring Boot backend + LangGraph
agent + PostgreSQL), 300 synthetic cases (seed 42), SimulatedGateway.
Run id `2026-08-31T15:47:36Z`. Reproduce with:

```
java -jar backend/target/recovery-backend-0.1.0.jar \
  --recovery.batch.enabled=true --recovery.batch.include-agent=true
```

Total at risk: **₹23,53,507**

| Strategy | Recovered ₹ | % of oracle | Cases recovered | Contacts | Contacts per ₹10k | Payment attempts | Stopping-rule activations | Escalations |
|---|---|---|---|---|---|---|---|---|
| DO_NOTHING | ₹0 | 0.0% | 0 | 0 | 0.00 | 0 | 0 | 0 |
| NAIVE | ₹4,65,450 | 30.2% | 65 | 0 | 0.00 | 770 | 0 | 0 |
| **AGENT** | **₹15,36,967** | **99.7%** | 173 | 254 | 1.65 | 316 | 180 | 26 |
| ORACLE | ₹15,41,589 | 100.0% | 177 | 52 | 0.34 | 125 | 0 | 0 |

The agent recovers **3.3× what naive retrying does using 454 fewer payment
attempts**, and reaches 99.7% of a player that reads the answer key.

## Learning curve (AGENT, Beta-Bernoulli)

| Cases | Recovered | Recovered ₹ | Contacts | Contacts per ₹10k |
|---|---|---|---|---|
| 1–100 | 59 | ₹4,45,574 | 86 | 1.93 |
| 101–200 | 59 | ₹5,18,731 | 85 | 1.64 |
| 201–300 | 55 | ₹5,72,662 | 83 | 1.45 |

Recovery holds steady while contact efficiency improves **25%** — the
posteriors prune actions whose true success rate is near zero.

## Per-cause breakdown (AGENT)

| Cause | Cases | Recovered | Rate | Recovered ₹ | Contacts |
|---|---|---|---|---|---|
| SOFT_DECLINE | 105 | 75 | 71.4% | ₹8,66,379 | 46 |
| TRANSIENT | 60 | 49 | 81.7% | ₹4,19,807 | 13 |
| CUSTOMER_ACTION | 60 | 29 | 48.3% | ₹1,36,023 | 89 |
| HARD_DECLINE | 45 | 19 | 42.2% | ₹1,01,735 | 67 |
| UNRECOVERABLE | 30 | 1 | 3.3% | ₹13,022 | 39 |

Reading this table: TRANSIENT is cheapest to recover (81.7% using only 13
contacts — retries cost nothing socially). UNRECOVERABLE is correctly almost
abandoned: 30 cases, 1 recovery. CUSTOMER_ACTION is the expensive segment —
89 contacts for 29 recoveries — and is exactly where the learning system has
the most room to improve.

## Governance during this run

- **26 escalations** — every case above ₹25,000 paused for human approval
- **180 stopping-rule activations** — guard vetoes plus EV-abandonment closes
- **6 opted-out customers** — zero actions taken against any of them
- Every action and every block written to `decision_log` with the inputs seen
