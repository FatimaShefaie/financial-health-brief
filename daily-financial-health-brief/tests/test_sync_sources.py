import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from brief import InputError
from sync_sources import records_from_values


class SourceNormalizationTests(unittest.TestCase):
    def test_transaction_header_and_amount_status_mapping(self):
        values = [
            ["transaction_id", "date", "account", "category", "description", "amount", "currency", "status", "source", "source_version", "amount_status"],
            ["tx-1", "2026-08-11", "checking", "supplies", "fixture", "1.20", "USD", "posted", "ledger", "v1", "confirmed"],
            ["tx-2", "2026-08-11", "checking", "refunds", "fixture", "", "USD", "disputed", "ledger", "v1", "unknown"],
        ]
        rows = records_from_values("transactions", values)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["amount"], "1.20")
        self.assertEqual(rows[0]["amount_status"], "known")
        self.assertEqual(rows[1]["amount_status"], "unknown")

    def test_schema_change_stops_normalization(self):
        with self.assertRaises(InputError):
            records_from_values("budget", [["period", "unexpected"]])


if __name__ == "__main__":
    unittest.main()
