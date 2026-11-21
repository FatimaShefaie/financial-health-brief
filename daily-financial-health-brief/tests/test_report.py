import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from brief import InputError
from generate_report import previous_weekday, render_report


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.transactions = [
            {"transaction_id": "a", "date": "2026-08-11", "account": "x", "category": "supplies", "description": "known posted", "amount": "100.00", "currency": "USD", "status": "posted", "source": "fixture", "source_version": "tx-v2", "amount_status": "known"},
            {"transaction_id": "b", "date": "2026-08-10", "account": "x", "category": "supplies", "description": "prior posted", "amount": "125.00", "currency": "USD", "status": "posted", "source": "fixture", "source_version": "tx-v2", "amount_status": "known"},
            {"transaction_id": "c", "date": "2026-08-11", "account": "x", "category": "supplies", "description": "pending known", "amount": "25.00", "currency": "USD", "status": "pending", "source": "fixture", "source_version": "tx-v2", "amount_status": "known"},
            {"transaction_id": "d", "date": "2026-08-11", "account": "x", "category": "supplies", "description": "unknown", "amount": "", "currency": "USD", "status": "pending", "source": "fixture", "source_version": "tx-v2", "amount_status": "unknown"},
            {"transaction_id": "e", "date": "2026-08-11", "account": "x", "category": "supplies", "description": "disputed known", "amount": "10.00", "currency": "USD", "status": "disputed", "source": "fixture", "source_version": "tx-v2", "amount_status": "known"},
        ]
        self.budgets = [{"period": "2026-08", "category": "supplies", "budget_amount": "100.00", "currency": "USD", "owner": "operations", "review_rule": "review", "source": "fixture", "source_version": "budget-v3"}]
        self.revenues = [
            {"date": day, "source": "fixture", "metric": "collected_revenue", "value": value, "currency": "USD", "source_version": "rev-v1" if day.endswith("10") else "rev-v2"}
            for day, value in (("2026-08-10", "200.00"), ("2026-08-11", "225.00"))
        ]
        self.metadata = {k: {"identity": k, "url": "https://example.test", "tab": k, "fetched_at": "2026-08-12T00:00:00Z", "version": "7", "modified_time": "2026-08-11T00:00:00Z", "row_count": n} for k, n in (("transactions", 5), ("budget", 1), ("revenue", 2))}

    def test_previous_weekday_uses_weekdays_and_flags_calendar_gap_in_report(self):
        self.assertEqual(previous_weekday(__import__("datetime").date(2026, 8, 11)).isoformat(), "2026-08-10")
        report = render_report(self.transactions, self.budgets, self.revenues, self.metadata, "2026-08-11", provisional=True, prepared_at="test")
        self.assertIn("PROVISIONAL — assumed for testing/review; not confirmed by Operations", report)
        self.assertIn("prior weekday under a Monday–Friday calendar", report)

    def test_five_totals_exclude_unknown_and_keep_statuses_separate(self):
        report = render_report(self.transactions, self.budgets, self.revenues, self.metadata, "2026-08-11", provisional=True, prepared_at="test")
        self.assertIn("USD 100.00", report)
        self.assertIn("USD 25.00", report)
        self.assertIn("USD 10.00", report)
        self.assertIn("USD 125.00", report)
        self.assertIn("USD -25.00", report)
        self.assertIn("Pending amount unknown", report)

    def test_materiality_and_version_semantics_remain_unresolved(self):
        report = render_report(self.transactions, self.budgets, self.revenues, self.metadata, "2026-08-11", provisional=True, prepared_at="test")
        self.assertIn("Unresolved — baseline undefined", report)
        self.assertIn("accepted versions", report)
        self.assertIn("USD 125.00", report)

    def test_invalid_reporting_date_fails(self):
        with self.assertRaises(InputError):
            render_report(self.transactions, self.budgets, self.revenues, self.metadata, "August 11", provisional=True)


if __name__ == "__main__":
    unittest.main()
