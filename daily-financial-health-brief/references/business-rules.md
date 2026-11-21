# Interview-derived business rules and unresolved definitions

- The interview documents the process: Operations confirms the reporting date for the next meeting, and totals use rows dated exactly that day. It does not record a calendar date. Timezone and cutoff were not answered. Do not infer a reporting date from the latest source row.
- Posted, pending, and disputed transaction statuses remain separate. Posted alone is actual posted activity. Pending/disputed unknown amounts remain blank, are excluded from their totals, and are flagged.
- Compare reporting-date posted activity with the prior business day. The business-day calendar and exact row-selection semantics remain unresolved.
- Compare month-to-date posted spend by category against numeric budget targets. A variance is material only when its absolute value is strictly greater than both 10% of the baseline and USD 500. The baseline is undefined; do not calculate materiality until a human defines it. USD threshold treatment for non-USD categories is unresolved.
- Compare reporting-date and prior-business-day revenue and outstanding balances. Missing or unreconciled snapshots require Finance clarification; unavailable comparators stay unresolved.
- Flag missing mappings, material variances, and unresolved disputes in an unresolved-items section. Escalation belongs to the operations owner. The owner identity/contact is unknown.
- If a required source is unavailable, stop and notify its owner. Automation creates a draft only; it cannot distribute it or make spending/dispute decisions.
- Correct source versions must be confirmed with source owners. No version identification mechanism, tab names, schema, timezone, or calendar was provided.
