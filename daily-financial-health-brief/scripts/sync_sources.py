"""Fetch and validate all three authorized Sheets into normalized CSV extracts.

This sync deliberately does not produce a financial brief. A reporting date,
business calendar, and accepted source-version semantics still require human
confirmation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from brief import InputError, clear_canonical_outputs, write_normalized_outputs
import google_sources as google

ROOT = Path(__file__).resolve().parents[2]
TABS = {
    "transactions": "Transaction ledger",
    "budget": "Budget targets",
    "revenue": "Revenue snapshot",
}
HEADERS = {
    "transactions": ["transaction_id", "date", "account", "category", "description", "amount", "currency", "status", "source", "source_version", "amount_status"],
    "budget": ["period", "category", "budget_amount", "currency", "owner", "review_rule", "source", "source_version"],
    "revenue": ["date", "source", "metric", "value", "currency", "source_version"],
}


def records_from_values(key: str, values: list[list[Any]]) -> list[dict[str, str]]:
    """Require the confirmed source schema and preserve every nonblank data row."""
    expected = HEADERS[key]
    if not values or [str(cell).strip() for cell in values[0]] != expected:
        raise InputError(f"{key}: source header no longer matches the confirmed schema")
    records = []
    for row_number, row in enumerate(values[1:], 2):
        cells = list(row) + [""] * max(0, len(expected) - len(row))
        record = {name: str(cells[i]).strip() for i, name in enumerate(expected)}
        if not any(record.values()):
            continue
        if key == "transactions":
            # The source's `confirmed` label means the amount is known; the
            # normalized contract uses the explicit `known` / `unknown` pair.
            if record["amount_status"] == "confirmed":
                record["amount_status"] = "known"
            elif record["amount_status"] != "unknown":
                raise InputError(f"transactions row {row_number}: unrecognized amount_status")
        records.append(record)
    return records


def fetch_batch(access_token: str) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    batch: dict[str, list[dict]] = {}
    metadata: dict[str, dict] = {}
    for key in ("transactions", "budget", "revenue"):
        values, source_meta = google.fetch_tab_values(key, TABS[key], access_token=access_token)
        records = records_from_values(key, values)
        if len(records) != source_meta["row_count"]:
            raise InputError(f"{key}: fetched rows differ from the source row count")
        batch[key] = records
        metadata[key] = source_meta
    return batch, metadata


def write_manifest(metadata: dict[str, dict]) -> None:
    path = ROOT / "deliverables" / "normalized" / "source-metadata.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".source-metadata.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(metadata, stream, indent=2, sort_keys=True)
            stream.write("\n")
        Path(tmp_name).replace(path)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def sync() -> dict[str, dict]:
    credentials = google.get_credentials()
    batch, metadata = fetch_batch(credentials.token)
    write_normalized_outputs(ROOT, batch, metadata)
    try:
        write_manifest(metadata)
    except Exception:
        clear_canonical_outputs(ROOT)
        raise
    return metadata


def main() -> int:
    try:
        metadata = sync()
    except (google.SourceError, InputError) as exc:
        clear_canonical_outputs(ROOT)
        print(f"Source sync stopped: {exc}")
        return 2
    for key in ("transactions", "budget", "revenue"):
        item = metadata[key]
        print(f"{key}: normalized {item['row_count']} rows from {item['identity']} / {item['tab']}; Drive version {item['version']}")
    print("Normalized extracts are current. No daily brief was generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
