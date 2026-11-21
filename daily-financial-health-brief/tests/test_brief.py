import sys
import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from brief import (BUDGET_COLUMNS, REVENUE_COLUMNS, TRANSACTION_COLUMNS, InputError, clear_canonical_outputs, decimal_value, materiality, sum_status, validate_budget, validate_fresh_source_metadata, validate_revenue, validate_transactions, write_csv, write_normalized_outputs)

class BriefTests(unittest.TestCase):
    def setUp(self):
        fixture = Path(__file__).parent / "fixtures/synthetic_sources.json"
        self.sources = json.loads(fixture.read_text())
        self.rows = self.sources["transactions"]
    def test_decimal_is_exact(self):
        self.assertEqual(decimal_value("0.10") + decimal_value("0.20"), Decimal("0.30"))
        self.assertEqual(decimal_value("8,000.00"), Decimal("8000.00"))
        with self.assertRaises(InputError):
            decimal_value("8,00.00")
    def test_unknown_is_counted_not_zero_filled_or_summed(self):
        validate_transactions(self.rows)
        self.assertEqual(sum_status(self.rows, "2026-11-20", "pending", "USD"), (Decimal("0"), 1))
    def test_statuses_are_separate(self):
        self.assertEqual(sum_status(self.rows, "2026-11-20", "posted", "USD"), (Decimal("0.30"), 0))
        self.assertEqual(sum_status(self.rows, "2026-11-20", "disputed", "USD"), (Decimal("700.00"), 0))
    def test_materiality_is_strict_and_baseline_unknown(self):
        self.assertTrue(materiality(Decimal("501"), Decimal("1000"), "USD"))
        self.assertFalse(materiality(Decimal("500"), Decimal("1000"), "USD"))
        self.assertFalse(materiality(Decimal("100"), Decimal("1000"), "USD"))
        self.assertIsNone(materiality(Decimal("900"), None, "USD"))
    def test_all_source_fixtures_validate_and_keep_row_counts(self):
        validate_transactions(self.sources["transactions"])
        validate_budget(self.sources["budget"])
        validate_revenue(self.sources["revenue"])
        self.assertEqual(len(self.sources["transactions"]), 3)
        self.assertEqual(len(self.sources["budget"]), 1)
        self.assertEqual(len(self.sources["revenue"]), 2)
        self.assertEqual(self.sources["revenue"][1]["value"], "")
    def test_synthetic_pipeline_writes_all_three_contracts_with_all_rows(self):
        names = ("transactions", "budget", "revenue")
        metadata = {
            name: dict(identity=f"synthetic-{name}", url="fixture://synthetic", tab="fixture", fetched_at="2026-11-20T12:00:00Z", version="fixture-v1", row_count=len(self.sources[name]))
            for name in names
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_normalized_outputs(root, self.sources, metadata)
            for name in names:
                path = root / "deliverables/normalized" / f"{name}.csv"
                with path.open(newline="", encoding="utf-8") as f:
                    records = list(csv.DictReader(f))
                self.assertEqual(len(records), len(self.sources[name]))
            self.assertFalse((root / "deliverables/report.md").exists())
    def test_incomplete_synthetic_batch_removes_old_csvs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            normalized = root / "deliverables/normalized"
            normalized.mkdir(parents=True)
            (normalized / "transactions.csv").write_text("stale")
            with self.assertRaises(InputError):
                write_normalized_outputs(root, {"transactions": self.rows}, {})
            self.assertFalse((normalized / "transactions.csv").exists())
    def test_fresh_metadata_requires_tab_version_and_timestamp(self):
        valid = dict(identity="Revenue Snapshot", url="synthetic", tab="test", fetched_at="2026-11-20T12:00:00Z", version="fixture-v1", row_count=2)
        validate_fresh_source_metadata(valid)
        with self.assertRaises(InputError):
            validate_fresh_source_metadata({**valid, "version": ""})
    def test_csv_contract_columns_and_deterministic_rewrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "transactions.csv"
            write_csv(path, TRANSACTION_COLUMNS, self.rows)
            first = path.read_bytes()
            write_csv(path, TRANSACTION_COLUMNS, self.rows)
            self.assertEqual(path.read_bytes(), first)
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, TRANSACTION_COLUMNS)
                self.assertEqual(len(list(reader)), len(self.rows))
            self.assertEqual(BUDGET_COLUMNS, ["period", "category", "budget_amount", "currency", "owner", "review_rule", "source", "source_version"])
            self.assertEqual(REVENUE_COLUMNS, ["date", "source", "metric", "value", "currency", "source_version"])
    def test_invalid_status_fails(self):
        with self.assertRaises(InputError):
            validate_transactions([{**self.rows[0], "status": "maybe"}])
    def test_count_metrics_keep_currency_blank(self):
        validate_revenue([{"date": "2026-11-20", "source": "fixture", "metric": "enrolled_students", "value": "42", "currency": "", "source_version": "v1"}])
        with self.assertRaises(InputError):
            validate_revenue([{"date": "2026-11-20", "source": "fixture", "metric": "enrolled_students", "value": "42", "currency": "USD", "source_version": "v1"}])
    def test_failed_run_clears_stale_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "deliverables/report.md"
            target.parent.mkdir(parents=True)
            target.write_text("stale")
            clear_canonical_outputs(root)
            self.assertFalse(target.exists())

if __name__ == "__main__":
    unittest.main()
