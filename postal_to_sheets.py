"""
Fetch postal / ZIP codes for a list of countries from GeoNames
and write them into a Google Sheet.

See SETUP_GUIDE.md for full instructions before running.
"""

import io
import time
import zipfile

import requests
import gspread
from google.oauth2.service_account import Credentials

# ============================================================
# CONFIG  -- edit these
# ============================================================
SERVICE_ACCOUNT_FILE = "service_account.json"   # path to your JSON key
SPREADSHEET_NAME = "Postal Codes"               # Google Sheet name
SHARE_WITH_EMAIL = ""                            # optional: your email to auto-share a newly created sheet
SEPARATE_TAB_PER_COUNTRY = False                 # True = one worksheet tab per country
CHUNK_SIZE = 50000                               # rows per batch write (avoids API limits)

# ISO-2 country codes to fetch
COUNTRIES = {
    "United Arab Emirates": "AE",
    "Australia": "AU",
    "Bangladesh": "BD",
    "Indonesia": "ID",
    "Sri Lanka": "LK",
    "Maldives": "MV",
    "Malaysia": "MY",
    "Singapore": "SG",
    "Thailand": "TH",
}

COLUMNS = ["country_name", "country_code", "postal_code", "place_name",
           "admin1", "admin2", "admin3", "lat", "lng"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ============================================================
# FETCH
# ============================================================
def fetch_country(name, code):
    """Download one country's postal codes from the GeoNames bulk export."""
    rows = []
    url = f"http://download.geonames.org/export/zip/{code}.zip"
    r = requests.get(url, timeout=60)
    if r.status_code != 200:
        print(f"  {name}: no data (HTTP {r.status_code})")
        return rows

    z = zipfile.ZipFile(io.BytesIO(r.content))
    with z.open(f"{code}.txt") as f:
        for line in io.TextIOWrapper(f, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) < 11:
                continue
            # GeoNames columns:
            # 0 country, 1 postal, 2 place, 3 admin1, 4 admin1code,
            # 5 admin2, 6 admin2code, 7 admin3, 8 admin3code,
            # 9 lat, 10 lng, 11 accuracy
            rows.append([
                name, p[0], p[1], p[2],
                p[3], p[5], p[7], p[9], p[10],
            ])
    print(f"  {name}: {len(rows)} records")
    return rows


def fetch_all():
    data = {}
    for name, code in COUNTRIES.items():
        print(f"Fetching {name} ({code})...")
        try:
            data[name] = fetch_country(name, code)
        except Exception as e:  # noqa: BLE001
            print(f"  Error {name}: {e}")
            data[name] = []
        time.sleep(1)
    return data


# ============================================================
# GOOGLE SHEETS
# ============================================================
def get_spreadsheet():
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    client = gspread.authorize(creds)
    try:
        ss = client.open(SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        ss = client.create(SPREADSHEET_NAME)
        if SHARE_WITH_EMAIL:
            ss.share(SHARE_WITH_EMAIL, perm_type="user", role="writer")
    return ss


def write_rows(ws, rows):
    """Clear a worksheet and write header + rows in chunks."""
    ws.clear()
    ws.update(range_name="A1", values=[COLUMNS], value_input_option="RAW")

    start_row = 2
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i:i + CHUNK_SIZE]
        ws.update(
            range_name=f"A{start_row}",
            values=chunk,
            value_input_option="RAW",
        )
        start_row += len(chunk)
        print(f"    wrote rows {i + 1}-{i + len(chunk)}")
        time.sleep(1)


def write_single_tab(ss, data):
    all_rows = [row for rows in data.values() for row in rows]
    ws = ss.sheet1
    ws.update_title("All Postal Codes")
    # make sure the sheet is big enough
    needed = len(all_rows) + 10
    if ws.row_count < needed:
        ws.add_rows(needed - ws.row_count)
    write_rows(ws, all_rows)
    print(f"\nDone. {len(all_rows)} total records written.")


def write_tab_per_country(ss, data):
    total = 0
    for name, rows in data.items():
        title = name[:99]  # sheet title length limit
        try:
            ws = ss.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(
                title=title, rows=max(len(rows) + 10, 100), cols=len(COLUMNS)
            )
        if ws.row_count < len(rows) + 10:
            ws.add_rows(len(rows) + 10 - ws.row_count)
        print(f"  Writing tab: {name}")
        write_rows(ws, rows)
        total += len(rows)

    # remove the default empty first sheet if it isn't one of ours
    try:
        default = ss.sheet1
        if default.title not in data and default.title == "Sheet1":
            ss.del_worksheet(default)
    except Exception:  # noqa: BLE001
        pass
    print(f"\nDone. {total} total records written across {len(data)} tabs.")


# ============================================================
# MAIN
# ============================================================
def main():
    data = fetch_all()
    ss = get_spreadsheet()
    if SEPARATE_TAB_PER_COUNTRY:
        write_tab_per_country(ss, data)
    else:
        write_single_tab(ss, data)
    print("URL:", ss.url)


if __name__ == "__main__":
    main()
