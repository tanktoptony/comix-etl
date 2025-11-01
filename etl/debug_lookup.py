from dotenv import load_dotenv
load_dotenv()

from etl.sources.marvel_extract import safe_get, marvel_auth_params, BASE

def find_series(keyword: str, limit=10):
    params = {
        **marvel_auth_params(),
        "titleStartsWith": keyword,
        "limit": limit
    }
    resp = safe_get(f"{BASE}/series", params=params)
    data = resp.json()["data"]["results"]

    print(f"--- Results for {keyword} ---")
    for s in data:
        sid = s["id"]
        title = s.get("title")
        start_year = s.get("startYear")
        end_year = s.get("endYear")
        print(f"{sid} :: {title} ({start_year} - {end_year})")

if __name__ == "__main__":
    find_series("Uncanny X-Men")
