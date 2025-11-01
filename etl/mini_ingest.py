# etl/mini_ingest.py
from dotenv import load_dotenv
load_dotenv()

from etl.db import get_session, get_engine
from etl.models import Base, Publisher
from etl.sources.marvel_extract import get_all_series, get_all_comics_for_series
from etl.load import upsert_series, upsert_issue_from_comic
from sqlalchemy import select

def get_or_create_marvel_publisher(db):
    pub = db.execute(select(Publisher).where(Publisher.name == "Marvel")).scalar_one_or_none()
    if not pub:
        pub = Publisher(name="Marvel")
        db.add(pub)
        db.commit()
        db.refresh(pub)
    return pub

def ingest_small_sample(limit_series=10):
    db = get_session()
    Base.metadata.create_all(get_engine())
    marvel_pub = get_or_create_marvel_publisher(db)

    print(f"=== Loading {limit_series} Marvel series ===")

    for i, series_payload in enumerate(get_all_series()):
        if i >= limit_series:
            break

        series_title = series_payload.get("title") or "Unknown Series"
        marvel_series_id = str(series_payload["id"])
        print(f"\n[{i+1}] Series: {series_title} ({marvel_series_id})")

        series_row = upsert_series(db, marvel_pub, series_title, marvel_series_id)
        db.commit()

        print("   Fetching up to 5 issues...")
        for j, comic_payload in enumerate(get_all_comics_for_series(marvel_series_id)):
            if j >= 5:  # only grab first 5 issues per series
                break
            issue_row = upsert_issue_from_comic(db, series_row, comic_payload)
            if issue_row:
                print(f"      → {issue_row.title}")
        db.commit()

    db.close()
    print("\n✅ Mini-ingest complete!")

if __name__ == "__main__":
    ingest_small_sample(limit_series=10)
