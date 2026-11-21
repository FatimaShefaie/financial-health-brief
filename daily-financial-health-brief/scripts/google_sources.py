"""Local, read-only Google Sheets discovery and fetch helpers.

OAuth credentials, Picker key, selected source IDs, and refreshed tokens live in
the user's Application Support directory, never in this repository.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

APP_SUPPORT = Path.home() / "Library" / "Application Support" / "financial-health-brief"
CLIENT_FILE = APP_SUPPORT / "oauth-client.json"
PICKER_KEY_FILE = APP_SUPPORT / "picker-api-key.txt"
TOKEN_FILE = APP_SUPPORT / "token.json"
SOURCES_FILE = APP_SUPPORT / "sources.json"
PICKER_HOST = "localhost"
PICKER_PORT = 8765
PICKER_ORIGIN = f"http://{PICKER_HOST}:{PICKER_PORT}"
SCOPE = "https://www.googleapis.com/auth/drive.file"
SOURCES = {
    "transactions": {
        "name": "Transaction Ledger",
        "id": "16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8",
        "url": "https://docs.google.com/spreadsheets/d/16HhjfR9uG1oUwSFNjQvAvU9Q9gVjzxL0ufBzTJe82v8",
    },
    "budget": {
        "name": "Budget Targets",
        "id": "1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4",
        "url": "https://docs.google.com/spreadsheets/d/1pnHBrxWvZBDIQItyxhmaSUZBxF8VMYqo_fyN7JtgyA4",
    },
    "revenue": {
        "name": "Revenue Snapshot",
        "id": "1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4",
        "url": "https://docs.google.com/spreadsheets/d/1DToTpZtuwtVIdCPethZRe4T-y6mxGpWuivWSmR2XZt4",
    },
}


class SourceError(RuntimeError):
    """A required source could not be safely and freshly read."""


def _private_file(path: Path) -> None:
    if not path.is_file():
        raise SourceError(f"Required local configuration file is missing: {path}")
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise SourceError(f"Restrict {path.name} to owner-only access (run chmod 600).")


def _atomic_private_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        tmp.unlink(missing_ok=True)


def load_picker_config() -> tuple[str, str, str]:
    _private_file(CLIENT_FILE)
    _private_file(PICKER_KEY_FILE)
    try:
        client = json.loads(CLIENT_FILE.read_text(encoding="utf-8"))
        client_data = client.get("installed") or client.get("web") or {}
        client_id = client_data["client_id"]
        api_key = PICKER_KEY_FILE.read_text(encoding="utf-8").strip()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SourceError("OAuth client JSON or Picker key file is invalid.") from exc
    match = re.match(r"^(\d+)-", client_id)
    if not match:
        raise SourceError("Could not derive the Google Cloud project number from the OAuth client ID.")
    if not api_key:
        raise SourceError("Picker API key file is empty.")
    return client_id, match.group(1), api_key


def get_credentials(*, force_login: bool = False):
    """Load or refresh the local OAuth grant, or run Google's desktop flow."""
    _private_file(CLIENT_FILE)
    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise SourceError(
            "Google OAuth support is not installed. Use the project's .venv and install requirements.txt."
        ) from exc

    if not force_login and TOKEN_FILE.exists():
        _private_file(TOKEN_FILE)
        try:
            credentials = Credentials.from_authorized_user_file(str(TOKEN_FILE), [SCOPE])
        except (OSError, ValueError) as exc:
            raise SourceError("Saved OAuth token is unreadable; remove it and authorize again.") from exc
        if credentials.valid:
            return credentials
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(GoogleRequest())
            _atomic_private_json(TOKEN_FILE, json.loads(credentials.to_json()))
            return credentials

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_FILE),
        scopes=[SCOPE],
        autogenerate_code_verifier=True,
    )
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )
    _atomic_private_json(TOKEN_FILE, json.loads(credentials.to_json()))
    return credentials


def _get_json(url: str, access_token: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Never echo response bodies; they may contain source or account details.
        raise SourceError(f"Google API GET failed with HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SourceError("Google API request failed or returned invalid JSON.") from exc


def drive_metadata(file_id: str, access_token: str) -> dict[str, Any]:
    fields = "id,name,mimeType,version,modifiedTime,capabilities(canEdit)"
    url = "https://www.googleapis.com/drive/v3/files/" + quote(file_id, safe="")
    url += "?" + urlencode({"fields": fields, "supportsAllDrives": "true"})
    return _get_json(url, access_token)


def spreadsheet_metadata(file_id: str, access_token: str) -> dict[str, Any]:
    fields = "spreadsheetId,properties(title),sheets(properties(sheetId,title,index,gridProperties(rowCount,columnCount)))"
    url = "https://sheets.googleapis.com/v4/spreadsheets/" + quote(file_id, safe="")
    url += "?" + urlencode({"includeGridData": "false", "fields": fields})
    return _get_json(url, access_token)


def values_get(file_id: str, tab: str, access_token: str, range_a1: str = "A:ZZ") -> list[list[str]]:
    # Quote the tab and range as one A1 sheet reference; apostrophes in names are doubled.
    sheet_range = "'" + tab.replace("'", "''") + "'!" + range_a1
    url = "https://sheets.googleapis.com/v4/spreadsheets/" + quote(file_id, safe="")
    url += "/values/" + quote(sheet_range, safe="")
    payload = _get_json(url, access_token)
    values = payload.get("values", [])
    if not isinstance(values, list) or any(not isinstance(row, list) for row in values):
        raise SourceError("Sheets API returned values in an unexpected format.")
    return values


def _validate_drive_file(record: dict[str, Any], source_id: str) -> None:
    if record.get("id") != source_id:
        raise SourceError("Drive metadata ID did not match the authorized source allowlist.")
    if record.get("mimeType") != "application/vnd.google-apps.spreadsheet":
        raise SourceError(f"Allowlisted source {source_id} is not a Google spreadsheet.")
    can_edit = (record.get("capabilities") or {}).get("canEdit")
    if can_edit is not False:
        raise SourceError("Source is editable or Drive did not confirm view-only access; stopping without reading values.")
    if not record.get("version") or not record.get("modifiedTime"):
        raise SourceError("Drive did not return source version and modified time.")


def picker_html(access_token: str, project_number: str, api_key: str) -> bytes:
    """Return the local file-picker page; credential strings stay in process memory."""
    template = r"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Choose Challenge A source sheets</title>
<main><h1>Choose the three Challenge A source sheets</h1>
<p>Select exactly Transaction Ledger, Budget Targets, and Revenue Snapshot. No edits will be made.</p>
<button id="open" disabled>Loading Google Picker…</button><p id="status" role="status"></p></main>
<script>
const API_KEY = __API_KEY__;
const ACCESS_TOKEN = __ACCESS_TOKEN__;
const PROJECT_NUMBER = __PROJECT_NUMBER__;
function onApiLoad() { gapi.load('picker', {callback: createPicker}); }
function createPicker() {
  const view = new google.picker.DocsView(google.picker.ViewId.SPREADSHEETS);
  const picker = new google.picker.PickerBuilder()
    .setAppId(PROJECT_NUMBER)
    .setDeveloperKey(API_KEY)
    .setOAuthToken(ACCESS_TOKEN)
    .setOrigin(window.location.origin)
    .enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
    .addView(view)
    .setCallback(handlePicker)
    .build();
  const button = document.getElementById('open');
  button.disabled = false;
  button.textContent = 'Choose source sheets';
  button.onclick = () => picker.setVisible(true);
}
async function handlePicker(data) {
  if (data.action === google.picker.Action.PICKED) {
    const docs = data.docs.map(d => ({id: d.id, name: d.name, mimeType: d.mimeType}));
    document.getElementById('status').textContent = 'Selection received. Return to Terminal.';
    await fetch('/selected', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(docs)});
  } else if (data.action === google.picker.Action.CANCEL) {
    document.getElementById('status').textContent = 'Picker cancelled. You can close this tab.';
    await fetch('/cancel', {method:'POST'});
  }
}
</script>
<script src="https://apis.google.com/js/api.js?onload=onApiLoad" async defer></script>"""
    html = (
        template.replace("__API_KEY__", json.dumps(api_key))
        .replace("__ACCESS_TOKEN__", json.dumps(access_token))
        .replace("__PROJECT_NUMBER__", json.dumps(project_number))
    )
    return html.encode("utf-8")


def pick_sources(access_token: str, project_number: str, api_key: str) -> dict[str, dict[str, str]]:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading
    import webbrowser

    selection: dict[str, Any] = {}
    ready = threading.Event()
    page = picker_html(access_token, project_number, api_key)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self):
            if self.path == "/cancel":
                selection["cancelled"] = True
                self.send_response(204)
                self.end_headers()
                ready.set()
                return
            if self.path != "/selected":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, list):
                    raise ValueError
                selection["docs"] = body
            except (ValueError, json.JSONDecodeError):
                self.send_error(400)
                return
            self.send_response(204)
            self.end_headers()
            ready.set()

        def log_message(self, format, *args):
            return

    try:
        server = HTTPServer((PICKER_HOST, PICKER_PORT), Handler)
    except OSError as exc:
        raise SourceError(f"Could not start local Picker at {PICKER_ORIGIN}; port {PICKER_PORT} may be in use.") from exc
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    webbrowser.open(PICKER_ORIGIN + "/")
    try:
        if not ready.wait(timeout=300):
            raise SourceError("Picker selection timed out; no sources were read.")
    finally:
        server.shutdown()
        server.server_close()
    docs = selection.get("docs", [])
    if selection.get("cancelled"):
        raise SourceError("Picker was cancelled; no sources were read.")
    by_id = {doc.get("id"): doc for doc in docs if isinstance(doc, dict)}
    if set(by_id) != {item["id"] for item in SOURCES.values()} or len(docs) != len(SOURCES):
        raise SourceError("Select exactly the three allowlisted Challenge A spreadsheets, then run discovery again.")
    result: dict[str, dict[str, str]] = {}
    for key, source in SOURCES.items():
        doc = by_id[source["id"]]
        result[key] = {"id": source["id"], "name": str(doc.get("name") or source["name"])}
    _atomic_private_json(SOURCES_FILE, result)
    return result


def load_selected_sources(access_token: str, project_number: str, api_key: str, repick: bool = False):
    if not repick and SOURCES_FILE.exists():
        _private_file(SOURCES_FILE)
        selected = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
        if {v.get("id") for v in selected.values()} == {v["id"] for v in SOURCES.values()}:
            return selected
    return pick_sources(access_token, project_number, api_key)


def discover(repick: bool = False) -> list[dict[str, Any]]:
    client_id, project_number, api_key = load_picker_config()
    credentials = get_credentials()
    selected = load_selected_sources(credentials.token, project_number, api_key, repick=repick)
    discovered = []
    for key, expected in SOURCES.items():
        source_id = selected[key]["id"]
        if source_id != expected["id"]:
            raise SourceError("Selected source does not match the assignment allowlist.")
        drive = drive_metadata(source_id, credentials.token)
        _validate_drive_file(drive, source_id)
        sheet = spreadsheet_metadata(source_id, credentials.token)
        if sheet.get("spreadsheetId") != source_id:
            raise SourceError("Sheets API returned a different source ID.")
        discovered.append({
            "key": key,
            "name": drive.get("name"),
            "id": source_id,
            "url": expected["url"],
            "version": str(drive["version"]),
            "modified_time": drive["modifiedTime"],
            "tabs": [s.get("properties", {}).get("title") for s in sheet.get("sheets", [])],
        })
    return discovered


def fetch_tab_values(source_key: str, tab: str, *, access_token: str) -> tuple[list[list[str]], dict[str, Any]]:
    """Freshly fetch one approved tab and reject mid-read Drive version changes."""
    if source_key not in SOURCES:
        raise SourceError("Unknown source key; only the three assignment sources are allowed.")
    source = SOURCES[source_key]
    for attempt in range(2):
        before = drive_metadata(source["id"], access_token)
        _validate_drive_file(before, source["id"])
        sheet = spreadsheet_metadata(source["id"], access_token)
        tabs = [s.get("properties", {}).get("title") for s in sheet.get("sheets", [])]
        if tab not in tabs:
            raise SourceError(f"Configured tab {tab!r} is not present in {source['name']}.")
        values = values_get(source["id"], tab, access_token)
        after = drive_metadata(source["id"], access_token)
        _validate_drive_file(after, source["id"])
        if before["version"] == after["version"]:
            row_count = sum(1 for row in values[1:] if any(str(cell).strip() for cell in row)) if values else 0
            meta = {
                "identity": after["name"],
                "url": source["url"],
                "tab": tab,
                "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "version": str(after["version"]),
                "modified_time": after["modifiedTime"],
                "row_count": row_count,
            }
            return values, meta
    raise SourceError(f"{source['name']} changed during both read attempts; discard this batch and retry later.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover authorized Challenge A Google Sheets source tabs.")
    parser.add_argument("command", choices=("discover",), help="discover source identities and tab names; does not read cell values")
    parser.add_argument("--pick-again", action="store_true", help="reopen Picker and reselect the three allowlisted sheets")
    args = parser.parse_args()
    try:
        rows = discover(repick=args.pick_again)
    except SourceError as exc:
        try:
            from brief import clear_canonical_outputs
            clear_canonical_outputs(Path(__file__).resolve().parents[2])
        except ImportError:
            pass
        print(f"Source discovery stopped: {exc}")
        return 2
    for item in rows:
        print(f"{item['name']} ({item['key']}): Drive version {item['version']}; modified {item['modified_time']}")
        print("Tabs: " + ", ".join(repr(tab) for tab in item["tabs"]))
    print("No cell values were read. Confirm each tab with the source owner before configuring a report run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
