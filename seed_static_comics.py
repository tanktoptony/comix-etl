# seed_static_comics.py
"""
Static seed for a minimal, demo-ready catalog (no Marvel API).
Place this file next to app.py and run:  python seed_static_comics.py
"""

from etl.db import get_session, get_engine
from etl.models import Base, Publisher, Series, Issue
from sqlalchemy import exists

def get_or_create_publisher(session, name: str) -> Publisher:
    pub = session.query(Publisher).filter(Publisher.name == name).one_or_none()
    if pub:
        return pub
    pub = Publisher(name=name)
    session.add(pub)
    session.flush()  # ensures pub.publisher_id
    return pub

def get_or_create_series(session, title: str, publisher_name: str = "Marvel") -> Series:
    pub = get_or_create_publisher(session, publisher_name)
    s = (
        session.query(Series)
        .filter(Series.title == title, Series.publisher_id == pub.publisher_id)
        .one_or_none()
    )
    if s:
        return s
    s = Series(title=title, publisher_id=pub.publisher_id, start_year=None, volume=None)
    session.add(s)
    session.flush()  # ensures s.series_id
    return s

def add_issue(
    session,
    series: Series,
    issue_number,
    title: str | None = None,
    key_notes: str | None = None,      # goes into Issue.description for now
    release_date=None,
    cover_url: str | None = None,
):
    already = session.query(
        exists().where((Issue.series_id == series.series_id) & (Issue.issue_number == str(issue_number)))
    ).scalar()
    if already:
        return

    issue = Issue(
        series_id=series.series_id,
        issue_number=str(issue_number),
        title=title,
        description=key_notes,
        release_date=release_date,
        cover_url=cover_url,
    )
    session.add(issue)

def run():
    # Create tables if they don't exist yet
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    session = get_session()

    # --- UNCANNY X-MEN ---
    ux = get_or_create_series(session, "Uncanny X-Men")
    add_issue(session, ux, 266, "Gambit’s First Appearance", "First full appearance of Gambit (Remy LeBeau).")
    add_issue(session, ux, 141, "Days of Future Past, Part 1", "Classic storyline; Kate Pryde time travel.")
    add_issue(session, ux, 142, "Days of Future Past, Part 2", "Conclusion to Days of Future Past.")

    # --- AMAZING SPIDER-MAN ---
    asm = get_or_create_series(session, "Amazing Spider-Man")
    add_issue(session, asm, 129, "The Punisher Strikes Twice!", "First appearance of the Punisher and the Jackal.")
    add_issue(session, asm, 300, "Venom", "First full appearance of Venom (Eddie Brock).")
    add_issue(session, asm, 361, "Carnage, Part One", "First full appearance of Carnage.")

    # --- DAREDEVIL ---
    dd = get_or_create_series(session, "Daredevil")
    add_issue(session, dd, 1, "The Origin of Daredevil", "First appearance & origin of Matt Murdock.")
    add_issue(session, dd, 168, "A Daredevil is Born", "First appearance of Elektra.")

    # --- IRON MAN ---
    im = get_or_create_series(session, "Iron Man")
    add_issue(session, im, 55, "Beware the Blood Brothers!", "First appearance of Thanos and Drax.")

    # --- AVENGERS ---
    av = get_or_create_series(session, "Avengers")
    add_issue(session, av, 1, "The Coming of the Avengers!", "First appearance of the Avengers team.")
    add_issue(session, av, 4, "Captain America Joins... The Avengers!", "Silver Age revival of Captain America.")

    # --- INCREDIBLE HULK ---
    hulk = get_or_create_series(session, "Incredible Hulk")
    add_issue(session, hulk, 181, "And Now... The Wolverine!", "First full appearance of Wolverine.")

    session.commit()
    session.close()
    print("Static seed complete.")

if __name__ == "__main__":
    run()
