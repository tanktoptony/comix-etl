# etl/full_catalog_ingest.py

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime

from etl.db import get_session, get_engine
from etl.models import Base, Publisher, Series, Issue, EtlRun
from etl.sources.marvel_extract import (
    get_all_series,
    get_all_comics_for_series,
)
from etl.load import (
    upsert_series,
    upsert_issue_from_comic,    # creates/updates Issue row for one Marvel comic
)
from etl.utils import log


def get_or_create_marvel_publisher(db: Session) -> Publisher:
    """Make sure Publisher('Marvel') exists and return it."""
    stmt = select(Publisher).where(Publisher.name == "Marvel")
    pub = db.execute(stmt).scalar_one_or_none()
    if pub is None:
        pub = Publisher(name="Marvel")
        db.add(pub)
        db.commit()
        db.refresh(pub)
    return pub


def start_etl_run(db: Session) -> EtlRun:
    """Open a new EtlRun row for auditing."""
    run = EtlRun(
        source_system="marvel",
        status="running",
        notes="full catalog sync",
        started_at=datetime.utcnow(),
        records_read=0,
        records_loaded=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def finish_etl_run(db: Session, run: EtlRun, status: str, notes: str, read_ct: int, load_ct: int):
    """Mark EtlRun finished."""
    run.status = status
    run.notes = notes
    run.finished_at = datetime.utcnow()
    run.records_read = read_ct
    run.records_loaded = load_ct
    db.commit()


def ingest_entire_marvel_catalog():
    """
    High-level "do everything":
    - pull ALL series from Marvel
    - for each series, load series + issues
    """
    db = get_session()
    engine = get_engine()
    Base.metadata.create_all(engine)

    marvel_pub = get_or_create_marvel_publisher(db)
    etl_run = start_etl_run(db)

    total_series_seen = 0
    total_issues_seen = 0
    total_issues_upserted = 0

    log.info("[CATALOG] Fetching full Marvel series list...")
    all_series_payloads = list(get_all_series())  
    # NOTE: get_all_series() should already be a generator in your code that:
    #   - pages through /v1/public/series
    #   - yields each raw series dict

    for series_payload in all_series_payloads:
        total_series_seen += 1

        marvel_series_id = str(series_payload["id"])
        series_title = series_payload.get("title") or "UNKNOWN SERIES"

        log.info("[CATALOG] Upserting series %s (%s)", series_title, marvel_series_id)
        series_row = upsert_series(
            db,
            marvel_pub,
            series_title,
            marvel_series_id,
        )

        # Now pull ALL comics (issues) for this series
        log.info("[CATALOG]   Fetching issues for %s (%s)", series_title, marvel_series_id)
        comics_payloads = list(get_all_comics_for_series(marvel_series_id))
        # get_all_comics_for_series() in your code already pages /series/{id}/comics

        for comic_payload in comics_payloads:
            total_issues_seen += 1
            issue_row = upsert_issue_from_comic(db, series_row, comic_payload)
            if issue_row is not None:
                total_issues_upserted += 1

        # commit after each series so progress is durable
        db.commit()

    finish_etl_run(
        db,
        etl_run,
        status="success",
        notes="Completed full catalog ingest.",
        read_ct=total_issues_seen,
        load_ct=total_issues_upserted,
    )

    print("=== FULL CATALOG INGEST COMPLETE ===")
    print(f"Series seen:            {total_series_seen}")
    print(f"Issues (comics) seen:   {total_issues_seen}")
    print(f"Issues upserted:        {total_issues_upserted}")
    db.close()


if __name__ == "__main__":
    ingest_entire_marvel_catalog()
