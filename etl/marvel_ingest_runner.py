from dotenv import load_dotenv
load_dotenv()

import argparse, sys, time
from sqlalchemy.orm import Session
from sqlalchemy import text, func, select
from etl.models import Base, get_engine, EtlRun, Series
from etl.sources.marvel_extract import get_series_by_title, get_comics_for_series
from etl.transform import map_marvel_comic_to_rows
from etl.load import load_series_husk, upsert_issue_with_creators

def initdb():
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("✅ Database initialized.")

def marvel(titles: list[str], max_items: int):
    engine = get_engine()
    with Session(engine) as s:
        run = EtlRun(source_system="MARVEL", records_read=0, records_loaded=0, status="STARTED")
        s.add(run); s.flush()
        total_loaded = 0; total_read = 0
        try:
            for t in titles:
                series_results = get_series_by_title(t, limit=5)  # keep it tight
                for sr in series_results:
                    title = sr.get("title") or t
                    series = load_series_husk(s, title=title, source_key=str(sr.get("id")), source_system="MARVEL", publisher_name=None)
                    comics = get_comics_for_series(sr["id"], max_items=max_items)
                    total_read += len(comics)
                    for c in comics:
                        issue_row, creators = map_marvel_comic_to_rows({"series_id": series.series_id}, c)
                        upsert_issue_with_creators(s, series.series_id, issue_row, creators)
                        total_loaded += 1
            run.records_read = total_read
            run.records_loaded = total_loaded
            run.status = "SUCCESS"
            s.commit()
            print(f"✅ Marvel load complete. read={total_read} loaded={total_loaded}")
        except Exception as e:
            s.rollback()          # <-- add this
            run.status = "FAILED"
            run.notes = str(e)
            s.add(run)
            s.commit()
            print(f"❌ Marvel load failed: {e}")
            sys.exit(1)
            
def migrate():
    engine = get_engine()
    with engine.connect() as c:
        c.execute(text("ALTER TABLE issue ADD COLUMN IF NOT EXISTS thumbnail_url TEXT"))
        print("✅ Migration complete: added column issue.thumbnail_url (if missing).")

def quality():
    engine = get_engine()
    with engine.connect() as c:
        total = c.execute(text("SELECT COUNT(*) FROM issue")).scalar() or 0
        null_dates = c.execute(text("SELECT COUNT(*) FROM issue WHERE cover_date IS NULL")).scalar() or 0
        print(f"Quality report: total issues={total}, NULL cover_date={null_dates} ({(null_dates/total*100 if total else 0):.1f}%), orphans=0")

        print("\nTop series with missing dates:")
        rows = c.execute(text("""
            SELECT s.title, COUNT(*) AS null_cnt
            FROM issue i JOIN series s ON i.series_id = s.series_id
            WHERE i.cover_date IS NULL
            GROUP BY s.title
            ORDER BY null_cnt DESC
            LIMIT 10
        """)).fetchall()
        for title, cnt in rows:
            print(f"{cnt:>4}  {title}")

def stats(top_n: int):
    engine = get_engine()
    with engine.connect() as c:
        q = text("""
            SELECT s.title, COUNT(*) AS issue_count
            FROM issue i JOIN series s ON i.series_id = s.series_id
            GROUP BY s.title
            ORDER BY issue_count DESC
            LIMIT :n
        """)
        rows = c.execute(q, {"n": top_n}).fetchall()
        for title, cnt in rows:
            print(f"{cnt:>4}  {title}")

def main(argv=None):
    p = argparse.ArgumentParser(prog="comixcatalog-etl")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("initdb")

    p_marvel = sub.add_parser("marvel")
    p_marvel.add_argument("--titles", required=True, help="Comma-separated list of series titles to load")
    p_marvel.add_argument("--max-items", type=int, default=200)

    p_quality = sub.add_parser("quality")
    p_stats = sub.add_parser("stats")
    p_stats.add_argument("--top", type=int, default=10)

    p_migrate = sub.add_parser("migrate")

    args = p.parse_args(argv)
    if args.cmd == "initdb":
        initdb()
    elif args.cmd == "marvel":
        titles = [t.strip() for t in args.titles.split(",") if t.strip()]
        marvel(titles, args.max_items)
    elif args.cmd == "quality":
        quality()
    elif args.cmd == "stats":
        stats(args.top)
    elif args.cmd == "migrate":
        migrate()

if __name__ == "__main__":
    main()
