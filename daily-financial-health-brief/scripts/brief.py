"""Deterministic, source-neutral helpers for the Daily Financial Health Brief."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import csv
import os
import re
import tempfile

TRANSACTION_COLUMNS = ["transaction_id", "date", "account", "category", "description", "amount", "currency", "status", "source", "source_version", "amount_status"]
BUDGET_COLUMNS = ["period", "category", "budget_amount", "currency", "owner", "review_rule", "source", "source_version"]
REVENUE_COLUMNS = ["date", "source", "metric", "value", "currency", "source_version"]
STATUSES = {"posted", "pending", "disputed"}
COUNT_METRICS = {"enrolled_students", "past_due_accounts"}

class InputError(ValueError):
    """Input is incomplete, ambiguous or invalid; no report should be emitted."""

def decimal_value(value: object, *, allow_unknown: bool = False) -> Decimal | None:
    if value is None or str(value).strip() == "":
        if allow_unknown:
            return None
        raise InputError("required numeric amount is blank")
    text = str(value).strip()
    if "," in text:
        if not re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
            raise InputError(f"invalid decimal amount: {value!r}")
        text = text.replace(",", "")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise InputError(f"invalid decimal amount: {value!r}") from exc
    if not result.is_finite():
        raise InputError("amount must be finite")
    return result

def validate_transactions(rows: list[dict]) -> None:
    ids = set()
    for n, row in enumerate(rows, 1):
        missing = [k for k in ("transaction_id", "date", "status", "currency") if not str(row.get(k, "")).strip()]
        if missing:
            raise InputError(f"transaction row {n}: missing {', '.join(missing)}")
        if row["transaction_id"] in ids:
            raise InputError(f"duplicate transaction_id: {row['transaction_id']}")
        ids.add(row["transaction_id"])
        status = str(row["status"]).strip().lower()
        if status not in STATUSES:
            raise InputError(f"transaction row {n}: unknown status {row['status']!r}")
        unknown = row.get("amount") is None or str(row.get("amount", "")).strip() == ""
        decimal_value(row.get("amount"), allow_unknown=True)
        if unknown and str(row.get("amount_status", "")).lower() != "unknown":
            raise InputError(f"transaction row {n}: blank amount must be marked unknown")
        if not unknown and str(row.get("amount_status", "")).lower() != "known":
            raise InputError(f"transaction row {n}: numeric amount must be marked known")

def sum_status(rows: list[dict], report_date: str, status: str, currency: str) -> tuple[Decimal, int]:
    """Return known amount subtotal and count of unknown amounts; never zero-fill unknowns."""
    total, unknowns = Decimal("0"), 0
    for row in rows:
        if row["date"] != report_date or row["status"].lower() != status or row["currency"] != currency:
            continue
        amount = decimal_value(row.get("amount"), allow_unknown=True)
        if amount is None:
            unknowns += 1
        else:
            total += amount
    return total, unknowns

def materiality(variance: Decimal, baseline: Decimal | None, currency: str, threshold: Decimal = Decimal("500")) -> bool | None:
    """Strictly above both 10% of an agreed baseline and USD 500; None if undefined."""
    if baseline is None:
        return None
    if currency != "USD":
        return None
    return abs(variance) > abs(baseline) * Decimal("0.10") and abs(variance) > threshold

def strict_previous_business_day(rows: list[str], report_date: str) -> str:
    """Require source/interview-owned business calendar when weekends/holidays make it ambiguous."""
    earlier = sorted({d for d in rows if d < report_date})
    if not earlier:
        raise InputError("no prior dated records available")
    return earlier[-1]

def validate_budget(rows: list[dict]) -> None:
    for n, row in enumerate(rows, 1):
        missing = [k for k in ("period", "category", "currency") if not str(row.get(k, "")).strip()]
        if missing:
            raise InputError(f"budget row {n}: missing {', '.join(missing)}")
        decimal_value(row.get("budget_amount"))
        if not row.get("source") or not row.get("source_version"):
            raise InputError(f"budget row {n}: source provenance is required")

def validate_revenue(rows: list[dict]) -> None:
    for n, row in enumerate(rows, 1):
        missing = [k for k in ("date", "source", "metric", "source_version") if not str(row.get(k, "")).strip()]
        metric = str(row.get("metric", "")).strip()
        currency = str(row.get("currency", "")).strip()
        if metric in COUNT_METRICS:
            if currency:
                raise InputError(f"revenue row {n}: count metric {metric!r} must not have a currency")
        elif not currency:
            missing.append("currency")
        if missing:
            raise InputError(f"revenue row {n}: missing {', '.join(missing)}")
        # A blank value means unavailable, never numeric zero. It remains in the output for review.
        decimal_value(row.get("value"), allow_unknown=True)

def validate_fresh_source_metadata(source: dict) -> None:
    required = ("identity", "url", "tab", "fetched_at", "version", "row_count")
    missing = [k for k in required if source.get(k) in (None, "")]
    if missing:
        raise InputError(f"source metadata missing {', '.join(missing)}")
    if not isinstance(source["row_count"], int) or source["row_count"] < 0:
        raise InputError("source row_count must be a non-negative integer")

def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if row.get(k) is None else row.get(k, "") for k in columns})
    os.replace(tmp, path)

def clear_canonical_outputs(root: Path) -> None:
    """Remove prior canonical outputs before a run so a failed fetch cannot look current."""
    for rel in ("deliverables/normalized/transactions.csv", "deliverables/normalized/budget.csv", "deliverables/normalized/revenue.csv", "deliverables/normalized/source-metadata.json", "deliverables/report.md"):
        (root / rel).unlink(missing_ok=True)


def write_normalized_outputs(root: Path, sources: dict[str, dict], metadata: dict[str, dict]) -> None:
    """Validate a complete in-memory source batch, then atomically publish its three CSVs.

    The caller must freshly fetch sources before calling this function. This helper does not
    fetch Google Sheets and must not be fed cached source data in an operational run.
    """
    clear_canonical_outputs(root)
    try:
        for key in ("transactions", "budget", "revenue"):
            if key not in sources or key not in metadata:
                raise InputError(f"required source {key!r} was not fetched")
            validate_fresh_source_metadata(metadata[key])
            if metadata[key]["row_count"] != len(sources[key]):
                raise InputError(f"{key}: fetched row count does not match supplied rows")
        validate_transactions(sources["transactions"])
        validate_budget(sources["budget"])
        validate_revenue(sources["revenue"])
        contracts = {
            "transactions": (TRANSACTION_COLUMNS, sources["transactions"]),
            "budget": (BUDGET_COLUMNS, sources["budget"]),
            "revenue": (REVENUE_COLUMNS, sources["revenue"]),
        }
        final_dir = root / "deliverables" / "normalized"
        final_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=final_dir, prefix=".build-") as temp_name:
            stage = Path(temp_name)
            for name, (columns, rows) in contracts.items():
                write_csv(stage / f"{name}.csv", columns, rows)
            for name in contracts:
                os.replace(stage / f"{name}.csv", final_dir / f"{name}.csv")
    except Exception:
        clear_canonical_outputs(root)
        raise
