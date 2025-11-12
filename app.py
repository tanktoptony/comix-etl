from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, render_template, redirect, url_for
from sqlalchemy.orm import Session
from sqlalchemy import select

# Your models are optional at runtime; app still boots without DB
try:
    from etl.models import get_engine, Series, Issue
except Exception:
    get_engine = None
    Series = None
    Issue = None

# IMPORTANT: point Flask at the real folders
app = Flask(
    __name__,
    template_folder="app/templates",
    static_folder="app/static",
)

# put this near the top of app.py, after app = Flask(...)
@app.context_processor
def inject_defaults():
    # Provide safe defaults for commonly-referenced vars
    return {
        "issue": {},     # so {{ issue.* }} won’t explode if not provided
        "series": None,
        "issues": [],
        "q": "",
        "results": [],
    }

# ---------- Demo data for marketplace ----------
def cents_to_price(n: int) -> str:
    return f"${n/100:.2f}"

ISSUES_DEMO = [
    {"issue_id": 1, "series_title": "Uncanny X-Men", "issue_number": 266, "title": "Gambit!", "cover_url": None},
    {"issue_id": 2, "series_title": "Amazing Spider-Man", "issue_number": 300, "title": "Venom!", "cover_url": None},
    {"issue_id": 3, "series_title": "Daredevil", "issue_number": 168, "title": "Elektra!", "cover_url": None},
]

LISTINGS_DEMO = [
    {
        "listing_id": 101,
        "issue_id": 1,
        "grade": "CGC 9.6",
        "price_cents": 32500,
        "price_display": cents_to_price(32500),
        "seller": "mutant-keys",
        "notes": "White pages, case is clean.",
    },
    {
        "listing_id": 102,
        "issue_id": 1,
        "grade": "VF 8.0 (raw)",
        "price_cents": 14500,
        "price_display": cents_to_price(14500),
        "seller": "westchester-stash",
        "notes": "Light spine ticks, presents great.",
    },
]

# ===================== Root / Nav =====================

@app.get("/")
def home():
    return redirect(url_for("marketplace_home"))

# Some older links might hit this; keep as redirect to the real endpoint.
@app.get("/ui/search")
def legacy_ui_search():
    return redirect(url_for("ui_search"))

# ===================== Series / Issues / Gallery =====================

@app.get("/series")
def series_index():
    series_list = []
    if get_engine and Series:
        try:
            engine = get_engine()
            with Session(engine) as s:
                series_list = list(s.execute(select(Series).order_by(Series.title)).scalars())
        except Exception:
            series_list = []
    return render_template("series.html", series=series_list)

@app.get("/series/<int:series_id>/issues")
def series_issues(series_id: int):
    items, series = [], None
    if get_engine and Series and Issue:
        try:
            engine = get_engine()
            with Session(engine) as s:
                series = s.get(Series, series_id)
                if series:
                    items = list(
                        s.execute(
                            select(Issue)
                            .where(Issue.series_id == series_id)
                            .order_by(Issue.issue_number)
                        ).scalars()
                    )
        except Exception:
            pass
    return render_template("issue.html", series=series, issues=items)

@app.get("/series/<int:series_id>/gallery")
def series_gallery(series_id: int):
    items, series = [], None
    if get_engine and Series and Issue:
        try:
            engine = get_engine()
            with Session(engine) as s:
                series = s.get(Series, series_id)
                if series:
                    items = list(
                        s.execute(
                            select(Issue)
                            .where(Issue.series_id == series_id)
                            .order_by(Issue.issue_number)
                        ).scalars()
                    )
        except Exception:
            pass
    return render_template("gallery.html", series=series, issues=items)

# Top-level convenience routes used by header
@app.get("/issues")
def issues_root():
    items, series = [], None
    if get_engine and Series and Issue:
        try:
            engine = get_engine()
            with Session(engine) as s:
                series = s.execute(select(Series).order_by(Series.id)).scalars().first()
                if series:
                    items = list(
                        s.execute(
                            select(Issue)
                            .where(Issue.series_id == series.id)
                            .order_by(Issue.issue_number)
                        ).scalars()
                    )
        except Exception:
            pass
    return render_template("issue.html", series=series, issues=items)

@app.get("/gallery")
def gallery_root():
    items, series = [], None
    if get_engine and Series and Issue:
        try:
            engine = get_engine()
            with Session(engine) as s:
                series = s.execute(select(Series).order_by(Series.id)).scalars().first()
                if series:
                    items = list(
                        s.execute(
                            select(Issue)
                            .where(Issue.series_id == series.id)
                            .order_by(Issue.issue_number)
                        ).scalars()
                    )
        except Exception:
            pass
    return render_template("gallery.html", series=series, issues=items)

# ===================== Search (templates call url_for('ui_search')) =====================

@app.get("/search")
def ui_search():
    q = (request.args.get("q") or "").strip()
    results = []
    if q and get_engine and Series:
        try:
            engine = get_engine()
            with Session(engine) as s:
                stmt = select(Series).where(Series.title.ilike(f"%{q}%")).order_by(Series.title).limit(50)
                results = list(s.execute(stmt).scalars())
        except Exception:
            results = []
    return render_template("search.html", q=q, results=results)

# Back-compat UI issue page
@app.get("/ui/issue/<int:issue_id>")
def ui_issue(issue_id: int):
    payload = {
        "issue_id": issue_id,
        "series_title": "Unknown Series",
        "issue_number": issue_id,
        "issue_title": None,
    }
    if get_engine and Issue and Series:
        try:
            engine = get_engine()
            with Session(engine) as s:
                row = s.get(Issue, issue_id)
                if row:
                    payload["issue_number"] = getattr(row, "issue_number", payload["issue_number"])
                    payload["issue_title"] = getattr(row, "title", None)
                    if row.series_id:
                        series = s.get(Series, row.series_id)
                        if series:
                            payload["series_title"] = series.title
        except Exception:
            pass
    return render_template("issue.html", issue=payload)

# ===================== Marketplace demo (static-friendly) =====================

@app.get("/marketplace")
def marketplace_home():
    return render_template("marketplace_home.html", issues=ISSUES_DEMO)

@app.get("/marketplace/issue/<int:issue_id>")
def marketplace_issue(issue_id: int):
    issue = next((i for i in ISSUES_DEMO if i["issue_id"] == issue_id), None) or ISSUES_DEMO[0]
    return render_template(
        "marketplace_issue.html",
        issue=issue,
        listings=LISTINGS_DEMO,
        picked=LISTINGS_DEMO[0],
    )

@app.get("/marketplace/cart")
def marketplace_cart():
    subtotal_cents = LISTINGS_DEMO[1]["price_cents"]
    return render_template(
        "marketplace_cart.html",
        subtotal=cents_to_price(subtotal_cents),
        picked=LISTINGS_DEMO[1],
    )

# ===================== Dev entry =====================

if __name__ == "__main__":
    # Run from project root:  python app.py
    app.run(debug=True)
