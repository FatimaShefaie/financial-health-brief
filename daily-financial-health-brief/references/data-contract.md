# Data contract

Transactions columns: `transaction_id,date,account,category,description,amount,currency,status,source,source_version,amount_status`.

Budget columns: `period,category,budget_amount,currency,owner,review_rule,source,source_version`.

Revenue columns: `date,source,metric,value,currency,source_version`. Currency is required for monetary metrics and blank for the count metrics `enrolled_students` and `past_due_accounts`; do not assign a currency to counts.

Amounts are decimal strings, never binary floats. Blank transaction amounts are allowed only when `amount_status=unknown`; known amounts use `amount_status=known`. Unknowns are excluded from totals and surfaced for review. Preserve every recognized source row and source provenance. Do not invent row IDs; if the source has no stable ID, resolve a deterministic ID scheme with the source owner before production.

## Confirmed live source mapping

- Transaction Ledger headers match the contract. Source `amount_status=confirmed` normalizes to `known`; `unknown` remains `unknown`.
- Budget Targets headers match the contract without field renaming.
- Revenue Snapshot headers match the contract without field renaming. `enrolled_students` and `past_due_accounts` are counts and have blank currency; the other observed metrics carry a currency.
- The adapter stores current Drive `version` and `modifiedTime` in `source-metadata.json`; it preserves each row's own `source_version`. The interview says source owners confirm the accepted version, so the two version systems must not be treated as equivalent without confirmation.
