# Daily Financial Health Brief — PROVISIONAL DRAFT

> **PROVISIONAL — assumed for testing/review; not confirmed by Operations. Human approval required.**

- Reporting date: **2026-08-11**
- Reporting-date status: PROVISIONAL / UNCONFIRMED
- Prepared at: 2026-11-21T04:38:39.741145Z
- Review status: Awaiting Operations and Finance review; do not distribute as an approved report.
- Amount signs are preserved exactly as stored. Change = reporting-date signed total minus prior-day signed total.

## Source provenance

| Source | Tab | Drive version | Modified (UTC) | Rows | Row-level source version(s) |
|---|---|---:|---|---:|---|
| Project A — Transaction Ledger ([source](https://docs.google.com/spreadsheets/d/16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8)) | Transaction ledger | 174 | 2026-10-22T19:34:31.350Z | 70 | `ledger-2026-08-11-v2` |
| Project A — Budget Targets ([source](https://docs.google.com/spreadsheets/d/1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4)) | Budget targets | 152 | 2026-10-22T07:22:58.964Z | 10 | `budget-2026-08-v3` |
| Project A — Revenue Snapshot ([source](https://docs.google.com/spreadsheets/d/1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4)) | Revenue snapshot | 140 | 2026-10-22T07:23:09.755Z | 25 | `revenue-2026-08-03-v1`, `revenue-2026-08-05-v1`, `revenue-2026-08-07-v1`, `revenue-2026-08-10-v1`, `revenue-2026-08-11-v2` |

Drive versions are the values observed during the fresh, version-checked fetch. The interview says source owners identify accepted versions; no owner confirmation is recorded here, so Drive and row-level versions are listed separately and are not asserted equivalent.

## Five signed totals

| Measure | Signed total | Rows | Unknown amounts excluded |
|---|---:|---:|---:|
| 2026-08-11 posted | USD 2,750.35 | 6 | 0 |
| 2026-08-11 pending-confirmed | USD 2,650.00 | 4 | 1 |
| 2026-08-11 disputed-confirmed | USD 1,150.00 | 2 | 0 |
| 2026-08-10 prior-business-day posted | USD 7,894.50 | 8 | 0 |
| Change in posted total (2026-08-11 minus 2026-08-10) | USD -5,144.15 | — | — |

The pending-confirmed total includes 3 known-amount rows; 1 pending row(s) have unknown amounts and are excluded. The disputed-confirmed total includes 2 known-amount rows; 0 disputed row(s) have unknown amounts and are excluded. These totals do not combine statuses.

## Month-to-date posted activity vs. budget

Period: `2026-08` through `2026-08-11`. The earliest transaction date available is `2026-08-03`; source coverage before that date has not been confirmed. Amounts below are the signed posted amounts present in the ledger, compared arithmetically as available actual minus target.

| Category | Available posted MTD | Budget target | Signed variance (actual − target) | Materiality |
|---|---:|---:|---:|---|
| staffing | USD 23,070.00 | USD 21,000.00 | USD 2,070.00 | Unresolved — baseline undefined |
| supplies | USD 6,130.75 | USD 4,500.00 | USD 1,630.75 | Unresolved — baseline undefined |
| marketing | USD 6,600.00 | USD 6,000.00 | USD 600.00 | Unresolved — baseline undefined |
| refunds | USD 800.00 | USD 1,300.00 | USD -500.00 | Unresolved — baseline undefined |
| facilities | USD 5,085.00 | USD 4,200.00 | USD 885.00 | Unresolved — baseline undefined |
| software | USD 3,161.00 | USD 2,600.00 | USD 561.00 | Unresolved — baseline undefined |
| utilities | USD 2,020.55 | USD 1,800.00 | USD 220.55 | Unresolved — baseline undefined |
| training | USD 0.00 | USD 1,500.00 | USD -1,500.00 | Unresolved — baseline undefined |
| insurance | USD 3,500.00 | USD 3,000.00 | USD 500.00 | Unresolved — baseline undefined |
| professional-services | USD 3,330.00 | USD 2,500.00 | USD 830.00 | Unresolved — baseline undefined |

The stated rule is material only when absolute variance is strictly greater than both 10% of an agreed baseline and USD 500. The baseline definition is unresolved, so no category is labeled material or not material.

## Revenue and balance comparisons

Comparing the `2026-08-10` and `2026-08-11` snapshots. A missing or blank value is unavailable, not zero.

| Metric | Prior value | Reporting-date value | Signed change | Currency / unit | Row source version (prior → reporting date) |
|---|---:|---:|---:|---|---|
| collected_revenue | USD 24,600.00 | USD 25,100.00 | USD 500.00 | USD | `revenue-2026-08-10-v1 → revenue-2026-08-11-v2` |
| enrolled_students | 83 | 84 | 1 | count | `revenue-2026-08-10-v1 → revenue-2026-08-11-v2` |
| outstanding_balance | USD 4,700.00 | USD 4,300.00 | USD -400.00 | USD | `revenue-2026-08-10-v1 → revenue-2026-08-11-v2` |
| past_due_accounts | 8 | 7 | -1 | count | `revenue-2026-08-10-v1 → revenue-2026-08-11-v2` |
| payment_plan_balance | USD 2,100.00 | USD 1,950.00 | USD -150.00 | USD | `revenue-2026-08-10-v1 → revenue-2026-08-11-v2` |

These comparisons summarize the Revenue Snapshot only. No independent Finance reconciliation was supplied, so they are not represented as reconciled to the transaction ledger.

## Exceptions and unresolved items

- Pending amount unknown: `TX-1025` — emergency plumbing estimate; excluded from confirmed totals.
- Disputed transaction requires Operations review: `TX-1012` — duplicate charge dispute, USD 700.00.
- Disputed transaction requires Operations review: `TX-1070` — placement duplicate under review, USD 450.00.
- **Reporting date is unconfirmed.** `2026-08-11` is an explicit testing assumption based on the latest transaction and revenue date available; Operations approval is required.
- **Prior-business-day assumption.** `2026-08-10` is the prior weekday under a Monday–Friday calendar. The interview did not specify an official holiday/business-day calendar or row-selection rule; confirm this assumption with Operations.
- **Budget baseline unresolved.** The materiality test cannot be classified until Finance/Operations defines the baseline. The signed arithmetic variances above are informational only.
- **Month-to-date coverage unconfirmed.** Transaction rows begin on `2026-08-03`; completeness from August 1 through August 2 was not confirmed.
- **Accepted source versions unconfirmed.** Confirm the listed Drive versions and row-level source-version tags with each source owner before treating them as accepted business versions.
- **Revenue reconciliation unconfirmed.** Finance should confirm whether the snapshot metrics reconcile to its system of record and clarify any mismatches.
- Timezone and daily cutoff are unspecified; this draft uses exact date strings in the source rows and does not apply a time cutoff.

## Review decision

This is a provisional training/test draft, not an Operations-confirmed report. Operations must confirm or replace the reporting date, prior-business-day calendar, and unresolved transaction items. Finance must confirm source versions, budget baseline, and revenue reconciliation before conclusions are approved.
