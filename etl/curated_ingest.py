from dotenv import load_dotenv
load_dotenv()

import time
from sqlalchemy import select
from sqlalchemy.orm import Session

from etl.db import get_session, get_engine
from etl.models import Base, Publisher
from etl.sources.marvel_extract import (
    get_all_series,
    get_series_by_id,
    get_all_comics_for_series,
)

from etl.load import (
    upsert_series,
    upsert_issue_from_comic,
)
from etl.utils import log


# These are the “franchises” we want in the app right now.
# We'll try to resolve each by title using get_series_by_title()
CURATED_SERIES_TITLES = [
    "Uncanny X-Men",
    "The Avengers",
    "The Invincible Iron Man",
    "Captain America",
    "The Mighty Thor",
    "The Incredible Hulk",
    "The Amazing Spider-Man",
    "Fantastic Four",
    "Daredevil",
    "Black Panther",
]


def get_or_create_marvel_publisher(db: Session) -> Publisher:
    """Ensure Publisher('Marvel') exists, return it."""
    stmt = select(Publisher).where(Publisher.name == "Marvel")
    pub = db.execute(stmt).scalars().first()
    if pub:
        return pub

    pub = Publisher(name="Marvel")
    db.add(pub)
    db.commit()
    db.refresh(pub)
    return pub


def ingest_single_series(db: Session, marvel_pub: Publisher, series_title: str, sleep_between_calls: float = 1.5):
    """
    1. Use Marvel API to look up the given series by title.
    2. Upsert that series into our DB.
    3. Fetch all comics/issues for that series from Marvel.
    4. Upsert each issue.
    """

    log.info(f"[INGEST] Resolving series '{series_title}' from Marvel API ...")
    series_payload = None
    for s in get_all_series():
        if s.get("title", "").lower().startswith(series_title.lower()):
            series_payload = s
            break

    if not series_payload:
        log.warning(f"[INGEST] Could not find series '{series_title}' via Marvel API.")
        return {
            "series_title": series_title,
            "status": "not_found",
            "issues_loaded": 0,
        }

    marvel_series_id = str(series_payload["id"])
    series_row = upsert_series(
        db,
        marvel_pub,
        series_title,
        marvel_series_id,
    )
    db.commit()

    log.info(f"[INGEST] Series '{series_title}' mapped to marvel_series_id={marvel_series_id}, local series_id={series_row.series_id}")

    # polite pause before pulling issues
    time.sleep(sleep_between_calls)

    log.info(f"[INGEST] Fetching comics for marvel_series_id={marvel_series_id} ...")
    issues_loaded = 0

    # get_all_comics_for_series() in your code already:
    #   - pages through /series/<id>/comics
    #   - yields full comic payloads including thumbnail, dates, etc.
    for comic_payload in get_all_comics_for_series(marvel_series_id):
        # upsert_issue_from_comic() should:
        #   - transform Marvel comic json into your Issue row format
        #   - fill cover_url/thumbnail_url using the Marvel thumbnail
        #   - attach series_id FK
        issue_row = upsert_issue_from_comic(db, series_row, comic_payload)

        if issue_row:
            issues_loaded += 1

        # light pause between individual comic inserts to avoid rapid-fire calls from any nested lookups
        time.sleep(0.25)

    db.commit()

    log.info(f"[INGEST] Done with '{series_title}'. Inserted/updated ~{issues_loaded} issues.")
    # pause before the next series so Marvel doesn't slap us with a 500/429
    time.sleep(sleep_between_calls)

    return {
        "series_title": series_title,
        "status": "ok",
        "issues_loaded": issues_loaded,
        "series_id_local": series_row.series_id,
        "marvel_series_id": marvel_series_id,
    }


def run():
    # Make sure DB schema exists
    engine = get_engine()
    Base.metadata.create_all(engine)

    db = get_session()
    marvel_pub = get_or_create_marvel_publisher(db)

    summary = []

    for title in CURATED_SERIES_TITLES:
        try:
            result = ingest_single_series(db, marvel_pub, title)
        except Exception as e:
            # if Marvel gave us a 500 or we hit a weird field, we record the failure and keep going
            log.exception(f"[INGEST] Error while ingesting '{title}': {e}")
            result = {
                "series_title": title,
                "status": "error",
                "issues_loaded": 0,
            }
        summary.append(result)

    # capture summary info before closing session
    printable = []
    for row in summary:
        printable.append(
            f"{row['series_title']}: {row['status']} "
            + (f"(local series_id={row.get('series_id_local')}, marvel_id={row.get('marvel_series_id')}, issues={row.get('issues_loaded')})"
               if row["status"] == "ok" else "")
        )

    db.close()

    print("=== CURATED INGEST COMPLETE ===")
    for line in printable:
        print(" - " + line)
    print("")
    print("If 'status' == ok, that series and its real Marvel issues (with real cover thumbnails) are now in your DB.")


if __name__ == "__main__":
    run()
