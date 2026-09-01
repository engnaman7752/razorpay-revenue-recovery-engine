# Batch evaluation results

Run: `2026-08-31T15:47:36.749150900Z` — 300 synthetic cases (seed 42), SimulatedGateway.

Total at risk: **₹2,353,507**

| Strategy | Recovered ₹ | % of oracle | Cases recovered | Contacts | Contacts per ₹10k | Payment attempts | Stopping-rule activations | Escalations |
|---|---|---|---|---|---|---|---|---|
| DO_NOTHING | ₹0 | 0.0% | 0 | 0 | 0.00 | 0 | 0 | 0 |
| NAIVE | ₹465,450 | 30.2% | 65 | 0 | 0.00 | 770 | 0 | 0 |
| AGENT | ₹1,536,967 | 99.7% | 173 | 254 | 1.65 | 316 | 180 | 26 |
| ORACLE | ₹1,541,589 | 100.0% | 177 | 52 | 0.34 | 125 | 0 | 0 |

## Learning curve (AGENT, Beta-Bernoulli)

| Cases | Recovered | Recovered ₹ | Contacts | Contacts per ₹10k |
|---|---|---|---|---|
| 1-100 | 59 | ₹445,574 | 86 | 1.93 |
| 101-200 | 59 | ₹518,731 | 85 | 1.64 |
| 201-300 | 55 | ₹572,662 | 83 | 1.45 |

## Per-cause breakdown (AGENT)

| Cause | Cases | Recovered | Rate | Recovered ₹ | Contacts |
|---|---|---|---|---|---|
| TRANSIENT | 60 | 49 | 81.7% | ₹419,807 | 13 |
| CUSTOMER_ACTION | 60 | 29 | 48.3% | ₹136,023 | 89 |
| SOFT_DECLINE | 105 | 75 | 71.4% | ₹866,379 | 46 |
| HARD_DECLINE | 45 | 19 | 42.2% | ₹101,735 | 67 |
| UNRECOVERABLE | 30 | 1 | 3.3% | ₹13,022 | 39 |
