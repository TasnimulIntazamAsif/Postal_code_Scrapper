# Postal Codes → Google Sheets — Setup Guide

Fetch postal / ZIP codes for a set of countries from **GeoNames** and load them
into a **Google Sheet** (or a local CSV).

Countries included: United Arab Emirates, Australia, Bangladesh, Indonesia,
Sri Lanka, Maldives, Malaysia, Singapore, Thailand.

> ⚠️ Note: coverage varies by country in GeoNames. In testing, **Maldives (MV)**
> returned no data (HTTP 404), so it produces zero records. This is a
> data-source limitation, not a bug. Approximate record counts observed:
> UAE ~178k, Australia ~18k, Bangladesh ~1.3k, Indonesia ~81k, Sri Lanka ~1.8k,
> Malaysia ~2.8k, Singapore ~121k, Thailand ~900, Maldives 0.

---

## What's in this folder

| File | Purpose |
|------|---------|
| `postal_to_sheets.py` | Main script — writes data to a Google Sheet |
| `postal_to_csv.py` | Simple version — writes a local `postal_codes.csv` (no Google account needed) |
| `requirements.txt` | Python dependencies |
| `SETUP_GUIDE.md` | This file |

---

## Step 0 — Install Python & dependencies

You need **Python 3.9+**. Check with:

```bash
python --version
```

Then install the libraries:

```bash
pip install -r requirements.txt
```

---

## Quick test (no Google needed)

Run the CSV version first to confirm the data downloads correctly:

```bash
python postal_to_csv.py
```

This creates `postal_codes.csv` in the same folder. If that works, move on to
the Google Sheets setup.

---

## Step 1 — Create a Google Cloud project

1. Go to <https://console.cloud.google.com/>.
2. Click the project dropdown (top left) → **New Project** → give it a name →
   **Create**.
3. Make sure the new project is selected.

---

## Step 2 — Enable the APIs

In the same project:

1. Go to **APIs & Services → Library**.
2. Search for **Google Sheets API** → click it → **Enable**.
3. Go back to the Library, search for **Google Drive API** → **Enable**.

Both are required (Drive is used to create/open the spreadsheet file).

---

## Step 3 — Create a service account + key

1. Go to **APIs & Services → Credentials**.
2. Click **Create Credentials → Service account**.
3. Give it a name (e.g. `postal-bot`) → **Create and Continue** → skip the
   optional role steps → **Done**.
4. In the **Credentials** list, click your new service account.
5. Open the **Keys** tab → **Add Key → Create new key → JSON → Create**.
6. A `.json` file downloads. **Rename it to `service_account.json`** and place it
   in this project folder (next to `postal_to_sheets.py`).

> Keep this file private — it grants access to your Google resources.

---

## Step 4 — Share the sheet with the service account

Open `service_account.json` and find the `"client_email"` value. It looks like:

```
postal-bot@your-project-id.iam.gserviceaccount.com
```

You have two options:

**Option A — Let the script create the sheet for you**
Open `postal_to_sheets.py` and set your own email so the created sheet is shared
back to you:

```python
SHARE_WITH_EMAIL = "you@example.com"
```

**Option B — Use an existing Google Sheet**
1. Create a Google Sheet manually and note its exact name.
2. Set `SPREADSHEET_NAME` in the script to match that name.
3. In the Sheet, click **Share** and add the service account's
   `client_email` as an **Editor**.

If you skip sharing, you'll get a `PermissionError` / `403`.

---

## Step 5 — Configure the script

Open `postal_to_sheets.py` and review the CONFIG block near the top:

```python
SERVICE_ACCOUNT_FILE = "service_account.json"  # path to your JSON key
SPREADSHEET_NAME = "Postal Codes"              # sheet name
SHARE_WITH_EMAIL = ""                           # your email (Option A)
SEPARATE_TAB_PER_COUNTRY = False                # True = one tab per country
CHUNK_SIZE = 50000                              # rows per batch write
```

- Set `SEPARATE_TAB_PER_COUNTRY = True` if you want each country on its own
  worksheet tab instead of one combined tab.

---

## Step 6 — Run it

```bash
python postal_to_sheets.py
```

You'll see progress per country, then a final line with the spreadsheet URL.
Open that URL to view your data.

---

## Output columns

| Column | Meaning |
|--------|---------|
| country_name | Full country name |
| country_code | ISO-2 code |
| postal_code | Postal / ZIP code |
| place_name | City / locality |
| admin1 | State / region / province |
| admin2 | County / district |
| admin3 | Sub-district / community |
| lat | Latitude |
| lng | Longitude |

---

## Troubleshooting

**`SpreadsheetNotFound`** — The sheet name doesn't exist or isn't shared with the
service account. Use Option A, or share the existing sheet (Step 4).

**`403 / PermissionError`** — The service account email isn't an Editor on the
sheet, or an API isn't enabled (Step 2).

**`APIError: RESOURCE_EXHAUSTED` / quota** — Too many write calls. Increase
`CHUNK_SIZE` or wait a minute and re-run.

**A country returns 0 records** — GeoNames simply has no postal data for it
(e.g. Maldives returned HTTP 404 in testing). Nothing you can fix on your side.

**`ModuleNotFoundError`** — Run `pip install -r requirements.txt` again, making
sure you're using the same Python that runs the script.

---

## Changing the country list

Edit the `COUNTRIES` dictionary in either script. Keys are display names, values
are ISO-2 codes:

```python
COUNTRIES = {
    "Japan": "JP",
    "India": "IN",
}
```

Full list of available codes: <http://download.geonames.org/export/zip/>

---

## Data source & license

Data from **GeoNames** (<https://www.geonames.org/>), licensed under
**CC BY 4.0**. Attribute GeoNames if you publish or redistribute the data.
