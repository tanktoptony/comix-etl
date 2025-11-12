"""
ComicVine cover fetcher (verbose)
- Reads seeds/static_issues.csv
- Resolves volume IDs by series title
- Fetches issue image by (volume_id, issue_number)
- Saves images under app/static/ (cover_path from CSV)
- Logs EVERYTHING so you can see what's happening
"""

import os
import csv
import time
import requests
from pathlib import Path
from urllib.parse import urlencode
from dotenv import load_dotenv

# ---------------- CONFIG ----------------
ROOT = Path(__file__).parent
CSV_IN = ROOT / "seeds" / "static_issues.csv"
CSV_MISSING = ROOT / "seeds" / "missing_covers.csv"
STATIC_ROOT = ROOT / "app" / "static"
COVERS_DIR = STATIC_ROOT / "img" / "covers"
CACHE_FILE = ROOT / "seeds" / ".cv_volume_cache.txt"

API_BASE = "https://comicvine.gamespot.com/api"
DEFAULT_DELAY = 1.0  # seconds

load_dotenv()
API_KEY = os.getenv("COMICVINE_API_KEY")

HEADERS = {
    "User-Agent": "ComixCatalog/cover-fetcher (+non-commercial demo)",
    "Accept": "application/json",
}

# --------------- UTIL -------------------
def say(msg): print(msg, flush=True)

def ensure_paths():
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    CSV_MISSING.parent.mkdir(parents=True, exist_ok=True)

def cv_get(endpoint, params):
    """
    GET wrapper with ComicVine API key + retries (verbose).
    """
    params["api_key"] = API_KEY
    params["format"] = "json"
    url = f"{API_BASE}/{endpoint}/?{urlencode(params)}"
    for attempt in range(3):
        try:
            say(f"→ GET {url}")
            res = requests.get(url, headers=HEADERS, timeout=25)
            say(f"  HTTP {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                # ComicVine embeds a status_code in the JSON body
                sc = data.get("status_code")
                if sc == 1:
                    return data
                else:
                    say(f"  ComicVine status_code={sc}, error={data.get('error')}")
            else:
                say(f"  ERROR HTTP {res.status_code}: {res.text[:200]}")
        except Exception as e:
            say(f"  EXCEPTION: {e}")
        time.sleep(DEFAULT_DELAY + attempt)
    return None

def load_cache():
    cache = {}
    if CACHE_FILE.exists():
        for line in CACHE_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                cache[k] = v
    return cache

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        for k, v in cache.items():
            f.write(f"{k}={v}\n")

def find_volume_id(series_title, cache):
    if series_title in cache:
        say(f"  ✓ cache volume for '{series_title}': {cache[series_title]}")
        return cache[series_title]
    say(f"  search volume for '{series_title}'")
    data = cv_get("search", {
        "query": series_title,
        "resources": "volume",
        "limit": 1,
    })
    if not data or not data.get("results"):
        say(f"  ✗ no volume for '{series_title}'")
        return None
    vol_id = str(data["results"][0]["id"])
    cache[series_title] = vol_id
    save_cache(cache)
    say(f"  ✓ found volume id={vol_id} for '{series_title}'")
    return vol_id

def get_issue_image(volume_id, issue_number):
    data = cv_get("issues", {
        "filter": f"volume:{volume_id},issue_number:{issue_number}",
        "field_list": "image,volume,issue_number",
        "limit": 1,
    })
    if not data or not data.get("results"):
        return None
    result = data["results"][0]
    image = result.get("image") or {}
    return image.get("medium_url") or image.get("thumb_url")

def download_image(url, dest_path):
    say(f"  downloading → {url}")
    r = requests.get(url, headers=HEADERS, stream=True, timeout=30)
    if r.status_code == 200:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    say(f"  ✗ download failed HTTP {r.status_code}")
    return False

# --------------- MAIN -------------------
def main():
    say("=== ComixCatalog • ComicVine cover fetch (verbose) ===")

    if not API_KEY:
        say("✗ Missing COMICVINE_API_KEY in .env")
        return

    if not CSV_IN.exists():
        say(f"✗ CSV not found: {CSV_IN}")
        return

    ensure_paths()

    # show small preview of CSV rows
    with open(CSV_IN, newline="", encoding="utf-8") as f:
        sniff = list(csv.reader(f))
    say(f"CSV path: {CSV_IN}")
    say(f"CSV rows (incl. header): {len(sniff)}")
    if len(sniff) <= 1:
        say("✗ CSV appears empty. Add rows and rerun.")
        return

    cache = load_cache()
    missing = []
    processed = 0
    saved = 0
    skipped = 0

    with open(CSV_IN, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            series = (row.get("series") or "").strip()
            issue_no = (row.get("issue_number") or "").strip()
            cover_rel = (row.get("cover_path") or "").strip()

            if not series or not issue_no:
                say(f"- skip malformed row: {row}")
                skipped += 1
                continue

            if not cover_rel:
                say(f"- no cover_path for {series} #{issue_no} (skipping)")
                skipped += 1
                continue

            dest = STATIC_ROOT / cover_rel
            say(f"\n[ {series} #{issue_no} ] → {dest.relative_to(ROOT)}")

            if dest.exists():
                say("  ✓ already exists, skipping")
                skipped += 1
                continue

            vol_id = find_volume_id(series, cache)
            if not vol_id:
                missing.append([series, issue_no, "no_volume"])
                continue

            img_url = get_issue_image(vol_id, issue_no)
            if not img_url:
                say("  ✗ no image found for that issue")
                missing.append([series, issue_no, "no_image"])
                continue

            ok = download_image(img_url, dest)
            if ok:
                say(f"  ✓ saved {dest.relative_to(ROOT)}")
                saved += 1
            else:
                missing.append([series, issue_no, "download_failed"])

            processed += 1
            time.sleep(DEFAULT_DELAY)

    # write missing report
    with open(CSV_MISSING, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["series", "issue_number", "reason"])
        w.writerows(missing)

    say("\n=== Summary ===")
    say(f"Saved: {saved}")
    say(f"Skipped(existing/malformed): {skipped}")
    say(f"Missing (report): {len(missing)} → {CSV_MISSING}")
    say("Done.")

if __name__ == "__main__":
    main()
