from datetime import datetime
from typing import Dict, Any, Optional

DATE_CANDIDATES = ["coverDate", "onsaleDate", "focDate", "unlimitedDate", "digitalPurchaseDate"]

def parse_any_date(s: Optional[str]):
    if not s:
        return None
    # Try common Marvel formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    # Last-ditch: fromisoformat without tz
    try:
        return datetime.fromisoformat(s.replace("Z", "")).date()
    except Exception:
        return None

def pick_best_date(comic: Dict[str, Any]):
    # Prefer coverDate; otherwise fall back through known types
    dates = comic.get("dates", []) or []
    by_type = {d.get("type"): d.get("date") for d in dates if d.get("type")}
    for t in DATE_CANDIDATES:
        d = parse_any_date(by_type.get(t))
        if d:
            return d
    return None

def normalize_issue_number(num) -> str | None:
    if num is None:
        return None
    try:
        return str(num).strip()
    except Exception:
        return None

def cents_from_price(price) -> int | None:
    if price is None:
        return None
    try:
        return int(round(float(price) * 100))
    except Exception:
        return None

def map_marvel_comic_to_rows(series_row: Dict[str, Any], comic: Dict[str, Any]):
    issue = {
        "series_id": series_row["series_id"],
        "issue_number": normalize_issue_number(comic.get("issueNumber")),
        "cover_date": pick_best_date(comic),  # <-- use fallback
        "price_cents": cents_from_price(next((p.get("price") for p in comic.get("prices", []) if p.get("type") == "printPrice"), None)),
        "isbn": comic.get("isbn"),
        "upc": comic.get("upc"),
        "description": comic.get("description"),
        "cover_image_url": build_thumbnail_url(comic),
    }
    creators = []
    for c in comic.get("creators", {}).get("items", []):
        name = (c.get("name") or "").strip()
        role = (c.get("role") or "").strip()
        if name:
            creators.append({"name": name, "role": role})
    return issue, creators

# ADD THIS helper
def build_thumbnail_url(comic):
    # Marvel returns {"thumbnail": {"path": "...", "extension": "jpg"}}
    thumb = (comic.get("thumbnail") or {})
    path = thumb.get("path")
    ext = thumb.get("extension")
    if not path or not ext:
        return None
    # Force https, and pick a nice size variant
    if path.startswith("http://"):
        path = "https://" + path[len("http://"):]
    # Other variants you can try: portrait_fantastic, portrait_incredible
    return f"{path}/portrait_xlarge.{ext}"
