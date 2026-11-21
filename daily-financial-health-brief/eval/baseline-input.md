# Baseline input — synthetic only

A synthetic dataset contains a reporting-date posted USD amount of 12.10, a reporting-date pending row with unavailable amount, and a reporting-date disputed USD amount of 700.00. The budget variance is 700 USD, but the business has not defined “baseline.” Prepare the calculation behavior, not a source-derived financial report.

## Acceptance criteria

- Use exact Decimal values, not float arithmetic.
- Keep posted, pending, and disputed separate.
- Keep pending amount blank/unknown, exclude it from numeric subtotal, and surface the unknown.
- Do not declare the budget variance material because its baseline is undefined.
- Label the data synthetic and do not imply source provenance or business approval.
