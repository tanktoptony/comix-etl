from dotenv import load_dotenv
load_dotenv()

from datetime import date, timedelta
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from etl.db import get_session, get_engine
from etl.models import Base, Publisher, Series, Issue


def get_or_create_publisher(db: Session, name: str) -> Publisher:
    row = db.execute(
        select(Publisher).where(Publisher.name == name)
    ).scalars().first()

    if row:
        return row

    row = Publisher(name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_or_create_series(
    db: Session,
    publisher: Publisher,
    title: str,
    start_year: int,
    volume: int,
    source_system: str,
    source_key: str,
) -> Series:
    """
    We DO NOT rely on title being unique.
    We fingerprint by (source_system, source_key).
    """
    row = db.execute(
        select(Series).where(
            and_(
                Series.source_system == source_system,
                Series.source_key == source_key,
            )
        )
    ).scalars().first()

    if row:
        return row

    row = Series(
        title=title,
        publisher_id=publisher.publisher_id,
        start_year=start_year,
        volume=volume,
        source_system=source_system,
        source_key=source_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def upsert_issue(
    db: Session,
    series: Series,
    issue_number: int,
    title: str,
    description: str,
    release_date: date,
    cover_url: str,
):
    """
    Idempotent insert:
    - Check if we already have (series_id, issue_number)
    - If not, create a new Issue row.
    """
    issue_row = db.execute(
        select(Issue).where(
            and_(
                Issue.series_id == series.series_id,
                Issue.issue_number == str(issue_number),
            )
        )
    ).scalars().first()

    if issue_row:
        # already exists, leave it alone
        return issue_row

    new_issue = Issue(
        series_id=series.series_id,
        issue_number=str(issue_number),
        title=title,
        description=description,
        release_date=release_date,
        cover_url=cover_url,
        price_cents=None,
        isbn=None,
        upc=None,
    )

    db.add(new_issue)
    return new_issue


def seed_issues_run(
    db: Session,
    series: Series,
    base_year: int,
    base_month: int,
    run_length: int,
    slug: str,
):
    """
    Create a ~monthly run of issues #1..run_length for a given series.

    slug is used to build cover_url like:
        /static/covers/{slug}_{issue_no}.jpg

    We'll:
    - increment 28 days per issue for a believable timeline
    - mark certain key issues with spicy descriptions
    """

    current_date = date(base_year, base_month, 1)

    key_notes = {
        1:  "Debut Issue",
        50: "Anniversary Special",
        100: "Milestone Giant-Size",
        141: "Classic storyline",
        142: "Classic storyline (Part 2)",
        266: "First appearance of Gambit",
    }

    for num in range(1, run_length + 1):
        extra = ""
        if num in key_notes:
            extra = f" ({key_notes[num]})"

        issue_title = f"{series.title} #{num}{extra}"

        issue_desc = (
            f"Issue #{num} of {series.title}. "
            f"This seeded data simulates a real release so you can browse, "
            f"list for sale, and show key-issue callouts in the UI."
        )

        cover_url = f"/static/covers/{slug}_{num}.jpg"
        # You will actually add files like:
        #   static/covers/avengers_1.jpg
        #   static/covers/ironman_1.jpg
        # etc. For now it's just a path in the DB.

        upsert_issue(
            db=db,
            series=series,
            issue_number=num,
            title=issue_title,
            description=issue_desc,
            release_date=current_date,
            cover_url=cover_url,
        )

        # move ~monthly
        current_date = current_date + timedelta(days=28)


def run():
    # 1. ensure tables are there
    engine = get_engine()
    Base.metadata.create_all(engine)

    # 2. session
    db = get_session()

    marvel_pub = get_or_create_publisher(db, "Marvel")

    # 3. define the core "franchises" you want in your catalog
    # We'll pick 10 classic, high-visibility titles.
    # We attach historically reasonable start_year/volume for flavor.
    # (These are well-known: Avengers launched in 1963 vol 1; Iron Man vol 1 in 1968, etc.) :contentReference[oaicite:3]{index=3}
    core_series_specs = [
        {
            "title": "Uncanny X-Men",
            "start_year": 1981,   # seeded era we care about (Days of Future Past 1981, Gambit 1990). :contentReference[oaicite:4]{index=4}
            "volume": 1,
            "slug": "xmen",
            "source_key": "UXM-DEV-001",
        },
        {
            "title": "The Avengers",
            "start_year": 1963,
            "volume": 1,
            "slug": "avengers",
            "source_key": "AVENGERS-DEV-001",
        },
        {
            "title": "The Invincible Iron Man",
            "start_year": 1968,
            "volume": 1,
            "slug": "ironman",
            "source_key": "IRONMAN-DEV-001",
        },
        {
            "title": "Captain America",
            "start_year": 1968,   # Cap's solo Silver Age relaunch era is late '60s
            "volume": 1,
            "slug": "captainamerica",
            "source_key": "CAP-DEV-001",
        },
        {
            "title": "The Mighty Thor",
            "start_year": 1966,   # classic Journey Into Mystery -> Thor era
            "volume": 1,
            "slug": "thor",
            "source_key": "THOR-DEV-001",
        },
        {
            "title": "The Incredible Hulk",
            "start_year": 1968,   # ongoing Hulk revival era
            "volume": 1,
            "slug": "hulk",
            "source_key": "HULK-DEV-001",
        },
        {
            "title": "The Amazing Spider-Man",
            "start_year": 1963,
            "volume": 1,
            "slug": "spiderman",
            "source_key": "ASM-DEV-001",
        },
        {
            "title": "Fantastic Four",
            "start_year": 1961,
            "volume": 1,
            "slug": "fantasticfour",
            "source_key": "FF-DEV-001",
        },
        {
            "title": "Daredevil",
            "start_year": 1964,
            "volume": 1,
            "slug": "daredevil",
            "source_key": "DD-DEV-001",
        },
        {
            "title": "Black Panther",
            "start_year": 1977,   # Black Panther headlined his own book in the '70s
            "volume": 1,
            "slug": "blackpanther",
            "source_key": "BP-DEV-001",
        },
    ]

    created_series = []

    for spec in core_series_specs:
        series_row = get_or_create_series(
            db=db,
            publisher=marvel_pub,
            title=spec["title"],
            start_year=spec["start_year"],
            volume=spec["volume"],
            source_system="devseed",
            source_key=spec["source_key"],
        )

        # create 20 issues for each series
        seed_issues_run(
            db=db,
            series=series_row,
            base_year=spec["start_year"],
            base_month=1,
            run_length=20,
            slug=spec["slug"],
        )

        created_series.append(
            (series_row.series_id, spec["title"], spec["slug"])
        )

    # write to DB
    db.commit()

    # snapshot values before closing session (avoid DetachedInstanceError)
    summary_lines = [
        f"{title} (series_id={sid}) → cover path like /static/covers/{slug}_1.jpg"
        for (sid, title, slug) in created_series
    ]

    db.close()

    print("✅ multi_seed complete.")
    print("You now have these series in DB:")
    for line in summary_lines:
        print("  - " + line)
    print("Each with issues #1-20, each issue has:")
    print("  - release_date (month-stepped)")
    print("  - title including milestone notes for key numbers")
    print("  - cover_url pointing at /static/covers/<slug>_<issue>.jpg")
    print("")
    print("Next step: put actual JPEGs into your Flask static folder, e.g.:")
    print("  static/covers/avengers_1.jpg")
    print("  static/covers/ironman_1.jpg")
    print("  static/covers/captainamerica_1.jpg")
    print("...and they'll render in templates.")
    

if __name__ == "__main__":
    run()
