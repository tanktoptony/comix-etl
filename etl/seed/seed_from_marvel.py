"""
Seed ComixCatalog with curated Marvel runs for demo use.

Usage (from project root):
    python -m etl.seed.seed_from_marvel
"""

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import requests
from sqlalchemy.orm import Session

from etl.db import get_engine
from etl.models import Publisher, Series, Issue

# --- Config ---

PUBLIC = os.getenv("MARVEL_PUBLIC_KEY")
PRIVATE = os.getenv("MARVEL_PRIVATE_KEY")

if not PUBLIC or not PRIVATE:
    raise SystemExit(
        "MARVEL_PUBLIC_KEY and MARVEL_PRIVATE_KEY must be set in your environment."
    )

PAGE_SIZE = int(os.getenv("MARVEL_PAGE_SIZE", "100"))
MAX_PER_SERIES = int(os.getenv("MARVEL_MAX_PER_SERIES", "120"))

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Core demo series you care about
SERIES_TARGETS = [
    {"title": "Uncanny X-Men"},
    {"title": "Daredevil"},
    {"title": "The Amazing Spider-Man"},
    {"title": "Iron Man"},
    {"title": "Avengers"},
    {"title": "The Incredible Hulk"},
]


# --- Helpers ---

def _auth_params() -> Dict[str, str]:
    ts = str(time.time())
    raw = (ts + PRIVATE + PUBLIC).encode("utf-8")
    digest = hashlib.md5(raw).hexdigest()
    return {"ts": ts, "apikey": PUBLIC, "hash": digest}


def _get(url: str, params: Dict[str, Any], retries: int = 5, backoff: float = 1.5) -> Dict[str, Any]:
    last_status = None
    last_body = None

    for attempt in range(retries):
        resp = requests.get(url, params={**params, **_auth_params()}, timeout=20)
        last_status = resp.status_code
        try:
            last_body = resp.text
        except Exception:
            last_body = "<unable to read body>"

        if resp.status_code == 200:
            data = resp.json().get("data", {})
            return data

        # brief log so you can see what's up
        print(
            f"[Marvel API] Attempt {attempt+1}/{retries} "
            f"{resp.status_code} for {url}\n"
            f"Params: {params}\n"
            f"Body: {last_body[:400]}\n"
        )

        time.sleep(backoff ** (attempt + 1))

    # helpful final error
    raise RuntimeError(
        f"Marvel API failed for {url} with params={params} "
        f"after {retries} attempts. Last status={last_status}, body={last_body[:400]}"
    )


def _series_cache_path(title: str) -> Path:
    return CACHE_DIR / f"series_{title.replace(' ', '_')}.json"


def _comics_cache_path(series_id: int) -> Path:
    return CACHE_DIR / f"comics_{series_id}.json"


def find_series_by_title(title: str) -> Dict[str, Any]:
    """Pick the best Marvel series match for a given title."""
    cpath = _series_cache_path(title)
    if cpath.exists():
        return json.loads(cpath.read_text())

    # try exact title first
    data = _get(
        "https://gateway.marvel.com/v1/public/series",
        {"limit": 20, "title": title},
    )
    results = data.get("results", [])

    # fallback: titleStartsWith if exact fails
    if not results:
        data = _get(
            "https://gateway.marvel.com/v1/public/series",
            {"limit": 40, "titleStartsWith": title.split()[0]},
        )
        results = data.get("results", [])

    if not results:
        raise RuntimeError(f"No Marvel series found for title='{title}'")

    # choose best by overlap + comics count
    best = None
    best_score = -1
    wanted_tokens = set(title.lower().split())
    for s in results:
        st = s.get("title", "")
        tokens = set(st.lower().split())
        overlap = len(tokens & wanted_tokens)
        comics_count = s.get("comics", {}).get("available", 0)
        score = overlap * 10 + comics_count
        if score > best_score:
            best_score = score
            best = s

    if not best:
        raise RuntimeError(f"Could not score Marvel series for title='{title}'")

    cpath.write_text(json.dumps(best, indent=2))
    return best


def list_comics_for_series(series_id: int, max_comics: int) -> List[Dict[str, Any]]:
    """Fetch comics for a Marvel series id, with caching."""
    cpath = _comics_cache_path(series_id)
    if cpath.exists():
        return json.loads(cpath.read_text())[:max_comics]

    out: List[Dict[str, Any]] = []
    offset = 0

    while True:
        data = _get(
            "https://gateway.marvel.com/v1/public/comics",
            {
                "series": series_id,
                "formatType": "comic",
                "noVariants": False,
                "orderBy": "onsaleDate",
                "limit": PAGE_SIZE,
                "offset": offset,
            },
        )
        results = data.get("results", [])
        if not results:
            break

        out.extend(results)
        offset += PAGE_SIZE

        if len(out) >= max_comics or offset >= data.get("total", 0):
            break

        time.sleep(0.2)  # be nice

    cpath.write_text(json.dumps(out, indent=2))
    return out[:max_comics]


def normalize_thumb(comic: Dict[str, Any]) -> str | None:
    thumb = comic.get("thumbnail") or {}
    path = thumb.get("path")
    ext = thumb.get("extension")
    if not path or not ext:
        return None
    if "image_not_available" in path:
        return None
    # portrait_uncanny is a good vertical cover size
    return f"{path}/portrait_uncanny.{ext}"


def parse_marvel_date(comic: Dict[str, Any], date_type: str) -> str | None:
    for d in comic.get("dates", []):
        if d.get("type") == date_type and d.get("date"):
            raw = d["date"]
            try:
                # marvel: "2010-01-06T00:00:00-0500"
                return datetime.fromisoformat(
                    raw.replace("Z", "+00:00")
                ).date().isoformat()
            except Exception:
                return raw[:10]
    return None


def hydrate_series_and_issues(db: Session, series_meta: Dict[str, Any], comics: List[Dict[str, Any]]):
    """Upsert Publisher, Series, Issues based on Marvel data."""

    # ensure Marvel publisher row exists
    publisher = db.query(Publisher).filter(Publisher.name == "Marvel").one_or_none()
    if not publisher:
        publisher = Publisher(name="Marvel")
        db.add(publisher)
        db.flush()

    # upsert Series
    marvel_series_id = series_meta["id"]
    title = series_meta.get("title") or "Unknown Series"
    start_year = series_meta.get("startYear")

    series = (
        db.query(Series)
        .filter(
            Series.source_system == "marvel",
            Series.source_key == str(marvel_series_id),
        )
        .one_or_none()
    )

    if not series:
        series = Series(
            title=title,
            publisher_id=publisher.publisher_id,
            start_year=start_year,
            volume=None,
            source_key=str(marvel_series_id),
            source_system="marvel",
        )
        db.add(series)
        db.flush()

    issue_order = 0
    for c in comics:
        issue_order += 1

        marvel_comic_id = c["id"]
        existing = (
            db.query(Issue)
            .filter(Issue.marvel_comic_id == marvel_comic_id)
            .one_or_none()
        )
        if existing:
            continue

        number = c.get("issueNumber")
        title = c.get("title")
        desc = c.get("description")

        onsale = parse_marvel_date(c, "onsaleDate")
        digital = parse_marvel_date(c, "digitalPurchaseDate")
        release_date = onsale or digital

        thumb = normalize_thumb(c)

        # variant heuristic
        full_text = (title or "") + " " + (c.get("variantDescription") or "")
        is_variant = "variant" in full_text.lower()
        variant_name = c.get("variantDescription") or (None)

        issue = Issue(
            series_id=series.series_id,
            issue_number=str(number) if number is not None else None,
            title=title,
            description=desc,
            release_date=(
                datetime.fromisoformat(release_date).date()
                if release_date and len(release_date) == 10
                else None
            ),
            cover_url=thumb,
            isbn=c.get("isbn"),
            upc=c.get("upc"),
            marvel_series_id=marvel_series_id,
            marvel_comic_id=marvel_comic_id,
            onsale_date=(
                datetime.fromisoformat(onsale).date()
                if onsale and len(onsale) == 10
                else None
            ),
            is_variant=is_variant,
            variant_name=variant_name,
            issue_order=issue_order,
        )
        db.add(issue)

    db.commit()


def run():
    engine = get_engine()
    with Session(engine) as db:
        for target in SERIES_TARGETS:
            title = target["title"]
            print(f"==> Fetching series: {title}")
            meta = find_series_by_title(title)
            comics = list_comics_for_series(meta["id"], max_comics=MAX_PER_SERIES)
            print(f"    Found {len(comics)} comics for '{meta.get('title')}'")
            hydrate_series_and_issues(db, meta, comics)
    print("Done. Seed complete.")


if __name__ == "__main__":
    run()
