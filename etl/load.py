from dotenv import load_dotenv
load_dotenv()  # so we can read .env before anything else

from sqlalchemy.orm import Session
from etl.db import get_engine, get_session
from etl.models import Publisher, Series, Issue
from etl.sources.marvel_extract import get_specific_comic, get_all_series, get_all_comics_for_series
from etl.utils import log

from dotenv import load_dotenv
load_dotenv()

from etl.db import get_session
from etl.models import Publisher, Series, Issue
from etl.sources.marvel_extract import get_specific_comic
from etl.utils import log

def get_or_create_publisher(session, name: str) -> Publisher:
    pub = session.query(Publisher).filter_by(name=name).one_or_none()
    if not pub:
        pub = Publisher(name=name)
        session.add(pub)
        session.commit()
    return pub

def upsert_series(session, marvel_pub: Publisher, series_name: str, marvel_series_id: str | None):
    """
    Unlike the earlier upsert_series(), which took a Marvel /series object,
    here we might not have full /series data because /series is unreliable.
    So we build/find a Series using just a name and an optional marvel_series_id.
    """
    q = session.query(Series)

    if marvel_series_id:
        existing = q.filter_by(source_system="marvel", source_key=str(marvel_series_id)).one_or_none()
    else:
        # fallback: title match if we don't know marvel_series_id
        existing = q.filter_by(title=series_name).one_or_none()

    if existing:
        # Make sure publisher is set
        if existing.publisher_id is None:
            existing.publisher = marvel_pub
        session.commit()
        return existing

    s = Series(
        title=series_name,
        publisher=marvel_pub,
        start_year=None,
        volume=None,
        source_key=str(marvel_series_id) if marvel_series_id else None,
        source_system="marvel",
    )
    session.add(s)
    session.commit()
    return s

def upsert_issue_from_comic(session, series_obj: Series, comic: dict) -> Issue:
    # Pull metadata from the Marvel comic payload
    issue_number = comic.get("issueNumber")
    title = comic.get("title")

    # release_date: look in "dates" array for onsaleDate
    release_date = None
    for d in comic.get("dates", []):
        if d.get("type") == "onsaleDate":
            release_date = d.get("date")
            break

    # thumbnail => cover_url
    thumb = comic.get("thumbnail") or {}
    cover_url = None
    if thumb.get("path") and thumb.get("extension"):
        cover_url = f"{thumb['path']}.{thumb['extension']}"

    # description / upc / isbn
    description = comic.get("description")
    upc = comic.get("upc")
    isbn = comic.get("isbn")

    # Try to find an existing issue for this series + issue_number
    existing = (
        session.query(Issue)
        .filter_by(series_id=series_obj.series_id, issue_number=str(issue_number))
        .one_or_none()
    )

    if existing:
        existing.title = title
        existing.release_date = release_date
        existing.cover_url = cover_url
        existing.upc = upc
        existing.isbn = isbn
        existing.description = description
        session.commit()
        return existing

    i = Issue(
        series_id=series_obj.series_id,
        issue_number=str(issue_number),
        title=title,
        release_date=release_date,
        cover_url=cover_url,
        upc=upc,
        isbn=isbn,
        description=description,
        price_cents=None  # we don't get actual sale price from Marvel
    )
    session.add(i)
    session.commit()
    return i

def ingest_single_issue(series_title: str, issue_no: str):
    """
    Pull one known key issue (e.g. Uncanny X-Men #266),
    insert Publisher -> Series -> Issue in DB.
    """
    from etl.sources.marvel_extract import get_specific_comic

    with get_session() as session:
        marvel_pub = get_or_create_publisher(session, "Marvel")

        comic = get_specific_comic(series_title, issue_no)
        if not comic:
            log.warning("Could not fetch %s #%s from Marvel", series_title, issue_no)
            return

        # Marvel gives us comic["series"] metadata:
        marvel_series_id = None
        series_name = series_title  # fallback, like "Uncanny X-Men"
        series_block = comic.get("series")
        # comic["series"] is usually like: {"resourceURI": ".../series/2258", "name": "Uncanny X-Men"}
        if isinstance(series_block, dict):
            if series_block.get("name"):
                series_name = series_block["name"]
            resource_uri = series_block.get("resourceURI")
            if resource_uri:
                # try to extract numeric id from ".../series/2258"
                maybe_id = resource_uri.rstrip("/").split("/")[-1]
                if maybe_id.isdigit():
                    marvel_series_id = maybe_id

        our_series = upsert_series(session, marvel_pub, series_name, marvel_series_id)

        issue_row = upsert_issue_from_comic(session, our_series, comic)

        log.info("[SINGLE ISSUE LOAD] Ingested %s #%s as issue_id=%s",
                 series_title, issue_no, issue_row.issue_id)
        print(f"[SINGLE ISSUE LOAD] Ingested {series_title} #{issue_no} as issue_id={issue_row.issue_id}")

if __name__ == "__main__":
    ingest_single_issue("Uncanny X-Men", "266")