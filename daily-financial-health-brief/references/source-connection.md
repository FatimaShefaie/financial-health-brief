# Source connection options

## What this Codex session supports

- The Google Drive connector is `DISABLED_BY_ADMIN` / `NOT_AVAILABLE`; the user cannot connect it in this workspace.
- Codex document control reports no connected Google Sheets session.
- Open browser tabs do not expose their signed-in browser session to the Python process.
- The user configured a local Google Personal mode desktop OAuth client and enabled Drive, Sheets, and Picker APIs in `personal-mode-app`.
- The user created a Picker API key restricted to the Picker API and local Picker referrers. Its value is stored outside this repository.
- Google Sheets API can read selected spreadsheets with the Google Drive `drive.file` scope. The assignment does not require changing any sheet's sharing list or making it public.

## Recommended method: Desktop OAuth plus Google Picker, `drive.file`

Use a single-account Google OAuth desktop app with Google Picker's one-file-pick flow. Request **only** `https://www.googleapis.com/auth/drive.file`; do not request `spreadsheets.readonly`, `drive.metadata.readonly`, or full Drive scopes. Google Picker grants the app access to the files the user selects, and `drive.file` is the narrow per-file, non-sensitive scope. The selected three source IDs must match the assignment's fixed allowlist. This grants the app access to those files; it does not make them public or edit their sharing settings.

`drive.file` is technically read/write for selected files. The user's existing file role remains decisive. Before any read, call Drive `files.get` and require `capabilities.canEdit == false`; if it is true or unavailable, fail closed and do not read. The Python adapter must issue only GET requests (`files.get`, Sheets `spreadsheets.get` / `values.get`) and have no write endpoint. This preserves the assignment's view-only constraint.

Fresh provenance per run:

1. Get Drive file metadata for the three allowlisted IDs; verify name/ID and `canEdit == false`; record `version` and `modifiedTime`.
2. Read spreadsheet properties and tab names, then values from the approved tab/range every run. Do not read cached CSVs as runtime input.
3. Capture local UTC fetch timestamps and actual source row counts (excluding the header only after the source schema/header is confirmed).
4. Re-fetch Drive metadata after values. If version changed during the read, discard the batch and retry once; if it changes again, fail safely.
5. Record source identity, tab, fetch time, Drive version, modified time, and row count in the report. Ask the owner to confirm that Drive's file `version` is the accepted source-version identifier before claiming the business's version requirement is satisfied.

## Exact Google Cloud Console configuration

1. The user created `personal-mode-app` using Google's **Personal mode** flow and a **Desktop app** OAuth client. Personal mode limits authorization to the creating Google account.
2. The user enabled **Google Drive API**, **Google Sheets API**, and **Google Picker API** in that project.
3. OAuth client JSON is stored at `~/Library/Application Support/financial-health-brief/oauth-client.json`, outside the repository, with mode `0600`.
4. The Picker API key is restricted to the Picker API and website referrers `http://localhost:8765/*` and `https://docs.google.com/*`; it is stored at `~/Library/Application Support/financial-health-brief/picker-api-key.txt`, mode `0600`.
5. On first execution, `scripts/google_sources.py discover` opens Google's local desktop sign-in and Picker. Select exactly **Transaction Ledger**, **Budget Targets**, and **Revenue Snapshot**. The OAuth flow requests only `drive.file`; selection does not alter their sharing lists.
6. Before any values are read, the adapter requires Drive to report `capabilities.canEdit == false` and uses only HTTP GET requests for Drive and Sheets APIs. If edit capability is true or unavailable, the run stops.
7. OAuth refresh credentials and selected IDs are written outside the repository with mode `0600`. Do not paste credentials, codes, access tokens, refresh tokens, or API key values into chat. Revoke access under [Google Account → Third-party connections](https://myaccount.google.com/connections) when the training run is finished.

The source files' actual tab names/ranges and accepted version identifier must be confirmed from the selected Sheets and/or owners before mapping. Do not guess them. The source IDs are checked against the unchanged interview export before any source is read.

## Why current alternatives do not fit

- Browser-only reading is human-driven and cannot power the repeatable Python command.
- The Google Drive app connector would be simpler for agent-led inspection, but is unavailable by administrator policy and does not itself provide the Python command's runtime.
- Service accounts or a second account would require another identity to be granted access to the sheets; this task says not to change sharing.
