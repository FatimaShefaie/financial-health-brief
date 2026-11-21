import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import google_sources as gs


class GoogleSourceTests(unittest.TestCase):
    def test_source_allowlist_matches_interview_ids(self):
        self.assertEqual(set(v["id"] for v in gs.SOURCES.values()), {
            "16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8",
            "1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4",
            "1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4",
        })

    def test_source_metadata_must_confirm_uneditable_spreadsheet(self):
        valid = {"id": "x", "mimeType": "application/vnd.google-apps.spreadsheet",
                 "capabilities": {"canEdit": False}, "version": "4", "modifiedTime": "2026-11-20T12:00:00Z"}
        gs._validate_drive_file(valid, "x")
        for capability in (True, None):
            invalid = {**valid, "capabilities": {"canEdit": capability}}
            with self.assertRaises(gs.SourceError):
                gs._validate_drive_file(invalid, "x")

    def test_picker_page_uses_ephemeral_values_and_selected_files_view(self):
        html = gs.picker_html("test-access", "12345", "test-key").decode()
        self.assertIn("google.picker.ViewId.SPREADSHEETS", html)
        self.assertIn("drive.file", gs.SCOPE)
        self.assertIn("test-access", html)
        self.assertIn("test-key", html)
        self.assertIn("MULTISELECT_ENABLED", html)

    def test_values_get_escapes_tab_name_and_uses_get_json(self):
        with patch.object(gs, "_get_json", return_value={"values": [["h"]]}) as get_json:
            rows = gs.values_get("sheet-id", "Owner's Tab", "token")
        self.assertEqual(rows, [["h"]])
        self.assertIn("Owner%27%27s%20Tab", get_json.call_args.args[0])

    def test_fresh_fetch_retries_once_if_drive_version_changes(self):
        base = {"id": "16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8",
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "capabilities": {"canEdit": False}, "modifiedTime": "2026-11-20T12:00:00Z"}
        versions = iter([
            {**base, "name": "Transaction Ledger", "version": "1"},
            {**base, "name": "Transaction Ledger", "version": "2"},
            {**base, "name": "Transaction Ledger", "version": "2"},
            {**base, "name": "Transaction Ledger", "version": "2"},
        ])
        with patch.object(gs, "drive_metadata", side_effect=lambda *_: next(versions)), \
             patch.object(gs, "spreadsheet_metadata", return_value={
                 "spreadsheetId": base["id"], "sheets": [{"properties": {"title": "Ledger"}}]
             }), \
             patch.object(gs, "values_get", return_value=[["header"], ["value"], [""]]):
            values, meta = gs.fetch_tab_values("transactions", "Ledger", access_token="token")
        self.assertEqual(len(values), 3)
        self.assertEqual(meta["row_count"], 1)
        self.assertEqual(meta["version"], "2")
        self.assertTrue(meta["fetched_at"].endswith("Z"))

    def test_two_version_changes_fail_safely(self):
        base = {"id": "16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8",
                "name": "Transaction Ledger", "mimeType": "application/vnd.google-apps.spreadsheet",
                "capabilities": {"canEdit": False}, "modifiedTime": "2026-11-20T12:00:00Z"}
        versions = iter([{**base, "version": str(i)} for i in (1, 2, 2, 3)])
        with patch.object(gs, "drive_metadata", side_effect=lambda *_: next(versions)), \
             patch.object(gs, "spreadsheet_metadata", return_value={"sheets": [{"properties": {"title": "Ledger"}}]}), \
             patch.object(gs, "values_get", return_value=[["header"], ["value"]]):
            with self.assertRaises(gs.SourceError):
                gs.fetch_tab_values("transactions", "Ledger", access_token="token")


if __name__ == "__main__":
    unittest.main()
