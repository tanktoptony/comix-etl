# seed_from_csv.py
import csv
from pathlib import Path
from etl.db import get_session, get_engine
from etl.models import Base, Publisher, Series, Issue
from sqlalchemy import exists

CSV_PATH = Path("seeds/static_issues.csv")

def get_or_create_publisher(session, name: str):
    pub = session.query(Publisher).filter(Publisher.name == name).one_or_none()
    if pub:
        return pub
    pub = Publisher(name=name)
    session.add(pub)
    session.flush()
    return pub

def get_or_create_series(session, title: str, publisher_name: str):
    pub = get_or_create_publisher(session, publisher_name)
    s = session.query(Series).filter(
        Series.title == title,
        Series.publisher_id == pub.publisher_id
    ).one_or_none()
    if s:
        return s
    s = Series(title=title, publisher_id=pub.publisher_id)
    session.add(s)
    session.flush()
    return s

def upsert_issue(session, series, issue_number, title=None, notes=None, cover_path=None):
    already = session.query(
        exists().where((Issue.series_id == series.series_id) & (Issue.issue_number == str(issue_number)))
    ).scalar()
    if already:
        return
    # Store the relative static path; template will resolve via url_for('static', filename=cover_path)
    issue = Issue(
        series_id=series.series_id,
        issue_number=str(issue_number),
        title=title,
        description=notes,
        cover_url=cover_path  # relative path like "img/covers/asm-300.jpg"
    )
    session.add(issue)

def run():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    session = get_session()
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            series = get_or_create_series(session, row["series"].strip(), row["publisher"].strip())
            upsert_issue(
                session,
                series,
                row["issue_number"].strip(),
                title=(row.get("issue_title") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
                cover_path=(row.get("cover_path") or "").strip() or None,
            )
    session.commit()
    session.close()
    print("CSV seed complete.")

if __name__ == "__main__":
    run()
