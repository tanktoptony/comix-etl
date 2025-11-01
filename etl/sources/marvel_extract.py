import string
import requests
import time
from etl.utils import log, marvel_auth_params

BASE = "https://gateway.marvel.com/v1/public"

def safe_get(url, params, max_retries=5, sleep_seconds=1.5):
    """
    GET with retry/backoff for Marvel API instability.
    Retries on 5xx responses.
    """
    for attempt in range(1, max_retries + 1):
        resp = requests.get(url, params=params, timeout=30)

        # Retry if Marvel pukes 500/502/503/504
        if resp.status_code >= 500:
            print(f"Marvel 5xx on {url} (attempt {attempt}/{max_retries}) params={params}")
            time.sleep(sleep_seconds * attempt)
            continue

        resp.raise_for_status()
        return resp

    # if we somehow get here, last resp.raise_for_status() will throw anyway
    resp.raise_for_status()
    return resp

def get_specific_comic(series_title: str, issue_number: str | int):
    """
    Fetch ONE comic by exact series title + issue number.
    Example: ("Uncanny X-Men", "266")
    Returns a dict like Marvel's /comics object or None.
    """
    params = {
        **marvel_auth_params(),
        "title": series_title,
        "issueNumber": issue_number,
        "limit": 1
    }

    resp = safe_get(f"{BASE}/comics", params=params)
    data = resp.json().get("data", {}).get("results", [])
    if not data:
        print(f"Marvel returned 0 results for {series_title} #{issue_number}")
        return None

    return data[0]



def get_series_by_id(series_id: int):
    params = {
        **marvel_auth_params(),
        "limit": 1
    }
    resp = safe_get(f"{BASE}/series/{series_id}", params=params)
    data = resp.json()["data"]["results"]
    return data[0] if data else None

def get_all_comics_for_series(series_id: int, limit_per_page=50, max_pages=40):
    all_items = []
    offset = 0

    for _ in range(max_pages):
        params = {
            **marvel_auth_params(),
            "limit": limit_per_page,
            "offset": offset,
            "orderBy": "issueNumber",
            "series": series_id
        }

        resp = safe_get(f"{BASE}/comics", params=params)
        data = resp.json()["data"]

        batch = data["results"]
        if not batch:
            break

        all_items.extend(batch)
        offset += len(batch)

        if offset >= data["total"]:
            break

    return all_items

def get_all_series(max_series: int | None = None):
    """
    Yield series by crawling A-Z and 0-9 using titleStartsWith.
    This avoids Marvel's giant unfiltered /series call that keeps 500'ing.
    """
    prefixes = list(string.digits) + list(string.ascii_uppercase)
    seen_ids = set()
    yielded = 0

    for prefix in prefixes:
        offset = 0
        while True:
            params = {
                **marvel_auth_params(),
                "limit": 20,
                "offset": offset,
                "titleStartsWith": prefix
            }

            resp = safe_get(f"{BASE}/series", params=params)
            data = resp.json()["data"]

            results = data["results"]
            if not results:
                break

            for s in results:
                sid = s["id"]
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)

                yield s
                yielded += 1

                if max_series is not None and yielded >= max_series:
                    return

            offset += len(results)
            total = data["total"]
            if offset >= total:
                break
            
            def get_series_by_id(series_id: int):
                params = {
                    **marvel_auth_params(),
                    "limit": 1
                }
    resp = safe_get(f"{BASE}/series/{series_id}", params=params)
    data = resp.json()["data"]["results"]
    return data[0] if data else None

def get_comics_for_series(series_id: int, limit_per_page=50, max_pages=40):
    """
    Pull comics for a known series id.
    """
    all_items = []
    offset = 0
    for _ in range(max_pages):
        params = {
            **marvel_auth_params(),
            "limit": limit_per_page,
            "offset": offset,
            "orderBy": "issueNumber"
        }
        resp = safe_get(f"{BASE}/series/{series_id}/comics", params=params)
        data = resp.json()["data"]
        results = data["results"]
        if not results:
            break
        all_items.extend(results)
        offset += len(results)
        if offset >= data["total"]:
            break
    return all_items