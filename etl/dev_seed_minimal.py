from dotenv import load_dotenv
load_dotenv()

from datetime import date, timedelta
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from etl.db import get_session, get_engine
from etl.models import Base, Publisher, Series, Issue

SEED_SOURCE_SYSTEM = "devseed"
SEED_SOURCE_KEY = "UXM-DEV-001"


def get_or_create_marvel_publisher(db: Session) -> Publisher:
    pub_stmt = select(Publisher).where(Publisher.name == "Marvel")
    pub = db.execute(pub_stmt).scalars().first()

    if not pub:
        pub = Publisher(name="Marvel")
        db.add(pub)
        db.commit()
        db.refresh(pub)

    return pub


def get_or_create_seed_series(db: Session, pub: Publisher) -> Series:
    """
    Stable dummy series row for dev/demo.
    We fingerprint it with source_system/source_key so we don't collide
    with real Marvel data later.
    """
    series_stmt = select(Series).where(
        and_(
            Series.source_system == SEED_SOURCE_SYSTEM,
            Series.source_key == SEED_SOURCE_KEY,
        )
    )
    series = db.execute(series_stmt).scalars().first()

    if series:
        return series

    series = Series(
        title="Uncanny X-Men",
        publisher_id=pub.publisher_id,
        start_year=1981,
        volume=1,
        source_system=SEED_SOURCE_SYSTEM,
        source_key=SEED_SOURCE_KEY,
    )
    db.add(series)
    db.commit()
    db.refresh(series)
    return series


def upsert_issue_by_series_and_number(
    db: Session,
    series: Series,
    issue_number: str,
    title: str,
    description: str,
    release_date: date | None,
    cover_url: str | None,
):
    """
    Create one Issue row for (series_id, issue_number) if it doesn't exist.
    Re-run safe.
    """
    existing_stmt = select(Issue).where(
        and_(
            Issue.series_id == series.series_id,
            Issue.issue_number == str(issue_number),
        )
    )
    existing = db.execute(existing_stmt).scalars().first()

    if existing:
        return existing

    new_issue = Issue(
        series_id=series.series_id,
        issue_number=str(issue_number),
        title=title,
        description=description,
        release_date=release_date,
        price_cents=None,
        isbn=None,
        upc=None,
        cover_url=cover_url,
    )
    db.add(new_issue)
    return new_issue


def bulk_seed_issues_for_series(
    db: Session,
    series: Series,
    start_issue: int,
    end_issue: int,
    start_year: int = 1981,
    start_month: int = 1,
):
    """
    Quickly generate a big run of sequential issues for this one series.

    - issue_number: "1", "2", ..., "300"
    - title: f"{series.title} #{issue_number}"
    - description: basic flavor + special text for milestones (1, 50, 100, etc.)
    - release_date: month-by-month starting from (start_year, start_month)
    - cover_url: placeholder that you can swap later

    We only insert if it doesn't already exist.
    """

    # We'll fake monthly releases. We'll just increment ~30 days per issue.
    # It's not historically accurate but looks good in UI and sorts well.
    current_date = date(start_year, start_month, 1)

    for n in range(start_issue, end_issue + 1):
        issue_no_str = str(n)

        # Special milestone flavor text for key issues:
        if n == 1:
            extra = " (Debut Issue)"
        elif n == 50:
            extra = " (Anniversary Special)"
        elif n == 100:
            extra = " (Giant-Size Milestone)"
        elif n == 141:
            extra = " (Days of Future Past Pt. 1)"
        elif n == 142:
            extra = " (Days of Future Past Pt. 2)"
        elif n == 266:
            extra = " (1st Gambit)"
        else:
            extra = ""

        title_text = f"{series.title} #{issue_no_str}{extra}"

        desc_text = (
            f"Issue #{issue_no_str} of {series.title}. "
            f"This is seeded demo data for development. "
            f"Story arc continues. {extra.strip()}"
        ).strip()

        # placeholder cover art – you can later swap this out per issue
        cover_url = f"https://example.com/{series.series_id}/{issue_no_str}.jpg"

        upsert_issue_by_series_and_number(
            db=db,
            series=series,
            issue_number=issue_no_str,
            title=title_text,
            description=desc_text,
            release_date=current_date,
            cover_url=cover_url,
        )

        # advance "publication" by ~30 days for next issue
        current_date = current_date + timedelta(days=30)


def run():
    # 1. make sure tables exist
    engine = get_engine()
    Base.metadata.create_all(engine)

    # 2. open session
    db = get_session()

    # 3. ensure publisher + series
    pub = get_or_create_marvel_publisher(db)
    series = get_or_create_seed_series(db, pub)

    # 4. seed a curated handful of famous keys (to show off "key issue" marketing copy)
    handpicked_issues = [
        {
            "issue_number": "266",
            "title": "Uncanny X-Men #266 (1st Gambit)",
            "description": "First full appearance of Gambit (popular key issue).",
            "release_date": date(1990, 8, 1),
            "cover_url": "https://example.com/xmen266.jpg",
        },
        {
            "issue_number": "141",
            "title": "Uncanny X-Men #141 (Days of Future Past Pt. 1)",
            "description": "Mutant dystopia future timeline begins.",
            "release_date": date(1981, 1, 1),
            "cover_url": "https://example.com/xmen141.jpg",
        },
        {
            "issue_number": "142",
            "title": "Uncanny X-Men #142 (Days of Future Past Pt. 2)",
            "description": "Conclusion of Days of Future Past.",
            "release_date": date(1981, 2, 1),
            "cover_url": "https://example.com/xmen142.jpg",
        },
    ]

    for item in handpicked_issues:
        upsert_issue_by_series_and_number(
            db=db,
            series=series,
            issue_number=item["issue_number"],
            title=item["title"],
            description=item["description"],
            release_date=item["release_date"],
            cover_url=item["cover_url"],
        )

    # 5. now blow it out: generate a believable full run of #1–300
    bulk_seed_issues_for_series(
        db=db,
        series=series,
        start_issue=1,
        end_issue=300,
        start_year=1981,
        start_month=1,
    )

    # commit and extract values before closing (avoid DetachedInstanceError)
    db.commit()

    series_title = series.title
    series_id_val = series.series_id

    db.close()

    print("✅ Bulk dev seed complete. You now have:")
    print(f"- Publisher: Marvel")
    print(f"- Series: {series_title} (series_id={series_id_val}) [{SEED_SOURCE_SYSTEM}/{SEED_SOURCE_KEY}]")
    print(f"- Issues: A run from #1 through #300 seeded (plus key-issue text for #141/#142/#266)")
    print("You can now build /series and /series/<series_id> routes and actually render catalog pages.")


if __name__ == "__main__":
    run()
