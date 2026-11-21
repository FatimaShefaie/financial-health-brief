"""Create an explicitly provisional or Operations-confirmed draft report."""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from brief import InputError, decimal_value, materiality, validate_budget, validate_revenue, validate_transactions
from sync_sources import ROOT, sync


def previous_weekday(report_day: date) -> date:
    """Use Monday-Friday only; the interview did not supply a holiday calendar."""
    prior = report_day - timedelta(days=1)
    while prior.weekday() >= 5:
        prior -= timedelta(days=1)
    return prior


def _fmt_amount(value: Decimal | None, currency: str = "USD") -> str:
    if value is None:
        return "unavailable"
    text = format(value, ",f")
    if currency:
        if "." not in text:
            text += ".00"
        else:
            whole, fractional = text.split(".", 1)
            text = whole + "." + fractional.ljust(2, "0")
        return f"{currency} {text}"
    return text


def _read_csv(name: str) -> list[dict[str, str]]:
    path = ROOT / "deliverables" / "normalized" / f"{name}.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _status_total(rows: list[dict[str, str]], day: str, status: str) -> dict[str, Any]:
    selected = [r for r in rows if r["date"] == day and r["status"] == status]
    if not selected:
        return {"total": None, "unknown": 0, "rows": 0, "known_rows": 0, "currency": "USD"}
    currencies = sorted({r["currency"] for r in selected if r["currency"]})
    if len(currencies) > 1:
        raise InputError(f"{day} {status}: multiple currencies require separate totals")
    currency = currencies[0] if currencies else "USD"
    known = [decimal_value(r["amount"]) for r in selected if r["amount_status"] == "known"]
    unknown = sum(1 for r in selected if r["amount_status"] == "unknown")
    if any(r["amount_status"] not in ("known", "unknown") for r in selected):
        raise InputError(f"{day} {status}: unrecognized amount status")
    return {"total": sum(known, decimal_value("0")), "unknown": unknown,
            "rows": len(selected), "known_rows": len(known), "currency": currency}


def render_report(
    transactions: list[dict[str, str]],
    budgets: list[dict[str, str]],
    revenues: list[dict[str, str]],
    metadata: dict[str, dict[str, Any]],
    reporting_date: str,
    *,
    provisional: bool,
    prepared_at: str | None = None,
) -> str:
    try:
        report_day = date.fromisoformat(reporting_date)
    except ValueError as exc:
        raise InputError("reporting date must be YYYY-MM-DD") from exc
    if report_day.isoformat() != reporting_date:
        raise InputError("reporting date must be YYYY-MM-DD")

    validate_transactions(transactions)
    validate_budget(budgets)
    validate_revenue(revenues)
    day = report_day.isoformat()
    prior_day = previous_weekday(report_day).isoformat()
    prepared_at = prepared_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    day_status = {s: _status_total(transactions, day, s) for s in ("posted", "pending", "disputed")}
    prior_posted = _status_total(transactions, prior_day, "posted")
    posted_change = (
        day_status["posted"]["total"] - prior_posted["total"]
        if day_status["posted"]["total"] is not None and prior_posted["total"] is not None
        else None
    )

    start_month = day[:7]
    month_rows = [r for r in transactions if r["date"].startswith(start_month) and r["date"] <= day and r["status"] == "posted"]
    actual: dict[str, Decimal] = {}
    actual_unknown: dict[str, int] = {}
    for row in month_rows:
        category = row["category"]
        amount = decimal_value(row["amount"], allow_unknown=True)
        if amount is None:
            actual_unknown[category] = actual_unknown.get(category, 0) + 1
        else:
            actual[category] = actual.get(category, decimal_value("0")) + amount
    budget_periods = {r["period"] for r in budgets}
    period_budgets = [r for r in budgets if r["period"] == start_month]
    missing_budget = sorted(set(actual) - {r["category"] for r in period_budgets})

    revenue_by_metric: dict[str, dict[str, dict[str, str]]] = {}
    for row in revenues:
        if row["date"] in (prior_day, day):
            entries = revenue_by_metric.setdefault(row["metric"], {})
            if row["date"] in entries:
                raise InputError(f"duplicate revenue snapshot for {row['metric']} on {row['date']}")
            entries[row["date"]] = row

    latest_transaction_date = max((r["date"] for r in transactions), default="unavailable")
    first_transaction_date = min((r["date"] for r in transactions), default="unavailable")
    date_label = (
        "**PROVISIONAL — assumed for testing/review; not confirmed by Operations. Human approval required.**"
        if provisional else "Confirmed by Operations (operator attestation)."
    )
    lines = [
        "# Daily Financial Health Brief — PROVISIONAL DRAFT" if provisional else "# Daily Financial Health Brief — DRAFT",
        "",
        f"> {date_label}",
        "",
        f"- Reporting date: **{day}**",
        f"- Reporting-date status: {'PROVISIONAL / UNCONFIRMED' if provisional else 'operator marked confirmed'}",
        f"- Prepared at: {prepared_at}",
        "- Review status: Awaiting Operations and Finance review; do not distribute as an approved report.",
        "- Amount signs are preserved exactly as stored. Change = reporting-date signed total minus prior-day signed total.",
        "",
        "## Source provenance",
        "",
        "| Source | Tab | Drive version | Modified (UTC) | Rows | Row-level source version(s) |",
        "|---|---|---:|---|---:|---|",
    ]
    for key in ("transactions", "budget", "revenue"):
        meta = metadata[key]
        source_rows = {"transactions": transactions, "budget": budgets, "revenue": revenues}[key]
        row_versions = sorted({r["source_version"] for r in source_rows if r.get("source_version")})
        versions = ", ".join(f"`{v}`" for v in row_versions) or "not present"
        lines.append(
            f"| {meta['identity']} ([source]({meta['url']})) | {meta['tab']} | {meta['version']} | "
            f"{meta.get('modified_time', 'not returned')} | {meta['row_count']} | {versions} |"
        )
    lines.extend([
        "",
        "Drive versions are the values observed during the fresh, version-checked fetch. The interview says source owners identify accepted versions; no owner confirmation is recorded here, so Drive and row-level versions are listed separately and are not asserted equivalent.",
        "",
        "## Five signed totals",
        "",
        "| Measure | Signed total | Rows | Unknown amounts excluded |",
        "|---|---:|---:|---:|",
    ])
    totals_rows = [
        (f"{day} posted", day_status["posted"]),
        (f"{day} pending-confirmed", day_status["pending"]),
        (f"{day} disputed-confirmed", day_status["disputed"]),
        (f"{prior_day} prior-business-day posted", prior_posted),
    ]
    for label, item in totals_rows:
        lines.append(f"| {label} | {_fmt_amount(item['total'], item['currency'])} | {item['rows']} | {item['unknown']} |")
    lines.append(f"| Change in posted total ({day} minus {prior_day}) | {_fmt_amount(posted_change, day_status['posted']['currency'])} | — | — |")
    lines.extend([
        "",
        f"The pending-confirmed total includes {day_status['pending']['known_rows']} known-amount rows; {day_status['pending']['unknown']} pending row(s) have unknown amounts and are excluded. The disputed-confirmed total includes {day_status['disputed']['known_rows']} known-amount rows; {day_status['disputed']['unknown']} disputed row(s) have unknown amounts and are excluded. These totals do not combine statuses.",
        "",
        "## Month-to-date posted activity vs. budget",
        "",
        f"Period: `{start_month}` through `{day}`. The earliest transaction date available is `{first_transaction_date}`; source coverage before that date has not been confirmed. Amounts below are the signed posted amounts present in the ledger, compared arithmetically as available actual minus target.",
        "",
        "| Category | Available posted MTD | Budget target | Signed variance (actual − target) | Materiality |",
        "|---|---:|---:|---:|---|",
    ])
    for row in period_budgets:
        category = row["category"]
        actual_amount = actual.get(category, decimal_value("0"))
        budget_amount = decimal_value(row["budget_amount"])
        variance = actual_amount - budget_amount
        # The interview leaves baseline undefined, so intentionally do not classify.
        status = "Unresolved — baseline undefined"
        assert materiality(variance, None, row["currency"]) is None
        unknown_note = f"; {actual_unknown.get(category, 0)} unknown posted amount(s) excluded" if actual_unknown.get(category, 0) else ""
        lines.append(f"| {category} | {_fmt_amount(actual_amount, row['currency'])}{unknown_note} | {_fmt_amount(budget_amount, row['currency'])} | {_fmt_amount(variance, row['currency'])} | {status} |")
    if missing_budget:
        lines.append("")
        lines.append("Categories with posted activity but no matching target: " + ", ".join(f"`{c}`" for c in missing_budget) + ".")
    if start_month not in budget_periods:
        lines.append("")
        lines.append(f"No budget target exists for period `{start_month}`; budget comparison is unavailable.")
    lines.extend([
        "",
        "The stated rule is material only when absolute variance is strictly greater than both 10% of an agreed baseline and USD 500. The baseline definition is unresolved, so no category is labeled material or not material.",
        "",
        "## Revenue and balance comparisons",
        "",
        f"Comparing the `{prior_day}` and `{day}` snapshots. A missing or blank value is unavailable, not zero.",
        "",
        "| Metric | Prior value | Reporting-date value | Signed change | Currency / unit | Row source version (prior → reporting date) |",
        "|---|---:|---:|---:|---|---|",
    ])
    if not revenue_by_metric:
        lines.append("| No matching snapshots | unavailable | unavailable | unavailable | — | — |")
    for metric in sorted(revenue_by_metric):
        entries = revenue_by_metric[metric]
        prior = entries.get(prior_day)
        current = entries.get(day)
        prior_value = decimal_value(prior["value"], allow_unknown=True) if prior else None
        current_value = decimal_value(current["value"], allow_unknown=True) if current else None
        change = current_value - prior_value if prior_value is not None and current_value is not None else None
        currency = (current or prior or {}).get("currency", "")
        unit = currency or "count"
        version_pair = f"{prior['source_version'] if prior else 'missing'} → {current['source_version'] if current else 'missing'}"
        lines.append(f"| {metric} | {_fmt_amount(prior_value, currency)} | {_fmt_amount(current_value, currency)} | {_fmt_amount(change, currency)} | {unit} | `{version_pair}` |")
    lines.extend([
        "",
        "These comparisons summarize the Revenue Snapshot only. No independent Finance reconciliation was supplied, so they are not represented as reconciled to the transaction ledger.",
        "",
        "## Exceptions and unresolved items",
        "",
    ])
    pending_unknown = [r for r in transactions if r["date"] == day and r["status"] == "pending" and r["amount_status"] == "unknown"]
    disputes = [r for r in transactions if r["date"] == day and r["status"] == "disputed"]
    if pending_unknown:
        for row in pending_unknown:
            lines.append(f"- Pending amount unknown: `{row['transaction_id']}` — {row['description']}; excluded from confirmed totals.")
    if disputes:
        for row in disputes:
            amount = decimal_value(row["amount"], allow_unknown=True)
            amount_text = _fmt_amount(amount, row["currency"]) if amount is not None else "amount unknown"
            lines.append(f"- Disputed transaction requires Operations review: `{row['transaction_id']}` — {row['description']}, {amount_text}.")
    lines.extend([
        f"- **Reporting date is unconfirmed.** `{day}` is an explicit testing assumption based on the latest transaction and revenue date available; Operations approval is required.",
        f"- **Prior-business-day assumption.** `{prior_day}` is the prior weekday under a Monday–Friday calendar. The interview did not specify an official holiday/business-day calendar or row-selection rule; confirm this assumption with Operations.",
        f"- **Budget baseline unresolved.** The materiality test cannot be classified until Finance/Operations defines the baseline. The signed arithmetic variances above are informational only.",
        f"- **Month-to-date coverage unconfirmed.** Transaction rows begin on `{first_transaction_date}`; completeness from August 1 through August 2 was not confirmed.",
        "- **Accepted source versions unconfirmed.** Confirm the listed Drive versions and row-level source-version tags with each source owner before treating them as accepted business versions.",
        "- **Revenue reconciliation unconfirmed.** Finance should confirm whether the snapshot metrics reconcile to its system of record and clarify any mismatches.",
        "- Timezone and daily cutoff are unspecified; this draft uses exact date strings in the source rows and does not apply a time cutoff.",
        "",
        "## Review decision",
        "",
        "This is a provisional training/test draft, not an Operations-confirmed report. Operations must confirm or replace the reporting date, prior-business-day calendar, and unresolved transaction items. Finance must confirm source versions, budget baseline, and revenue reconciliation before conclusions are approved.",
        "",
    ])
    return "\n".join(lines)


def write_report(content: str) -> Path:
    path = ROOT / "deliverables" / "report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".report.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        Path(tmp_name).replace(path)
    finally:
        Path(tmp_name).unlink(missing_ok=True)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a source-backed daily financial health draft.")
    parser.add_argument("--reporting-date", required=True, help="YYYY-MM-DD date for the draft")
    status = parser.add_mutually_exclusive_group(required=True)
    status.add_argument("--provisional", action="store_true", help="explicitly label the assumed date provisional")
    status.add_argument("--confirmed-by-operations", action="store_true", help="operator attests Operations confirmed this date")
    args = parser.parse_args()
    try:
        metadata = sync()
        sources = {
            "transactions": _read_csv("transactions"),
            "budget": _read_csv("budget"),
            "revenue": _read_csv("revenue"),
        }
        content = render_report(
            sources["transactions"], sources["budget"], sources["revenue"], metadata,
            args.reporting_date, provisional=args.provisional,
        )
        path = write_report(content)
    except (InputError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Report generation stopped: {exc}")
        return 2
    except Exception as exc:
        # Do not print OAuth/API bodies or credential-bearing exception details.
        print(f"Report generation stopped: {type(exc).__name__}; review local setup and source availability.")
        return 2
    print(f"Draft written to {path}")
    print("Date status: " + ("PROVISIONAL / unconfirmed" if args.provisional else "operator marked confirmed"))
    print("The report remains for human review; no distribution or approvals were performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
