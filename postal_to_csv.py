"""
Simple version: fetch postal / ZIP codes and save to a local CSV file.
No Google account or credentials needed. Good for testing.
"""

import io
import time
import zipfile
import csv

import requests

COUNTRIES = {
    # # "United Arab Emirates": "AE",
    # "Australia": "AU",
    "Bangladesh": "BD",
    # "Indonesia": "ID",
    # "Sri Lanka": "LK",
    # "Maldives": "MV",
    # "Malaysia": "MY",
    # "Singapore": "SG",
    # "Thailand": "TH",
    # "Brazil": "BR",
}

COLUMNS = ["country_name", "country_code", "postal_code", "place_name",
           "admin1", "admin2", "admin3", "lat", "lng"]


def fetch_country(name, code):
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
            rows.append([name, p[0], p[1], p[2], p[3], p[5], p[7], p[9], p[10]])
    print(f"  {name}: {len(rows)} records")
    return rows


def main():
    all_rows = []
    for name, code in COUNTRIES.items():
        print(f"Fetching {name} ({code})...")
        try:
            all_rows.extend(fetch_country(name, code))
        except Exception as e:  # noqa: BLE001
            print(f"  Error {name}: {e}")
        time.sleep(1)

    with open("postal_codes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(all_rows)

    print(f"\nDone. {len(all_rows)} records saved to postal_codes.csv")


if __name__ == "__main__":
    main()
