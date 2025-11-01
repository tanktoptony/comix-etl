from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, render_template
from sqlalchemy.orm import Session
from sqlalchemy import select
from markupsafe import escape

from etl.models import get_engine, Series, Issue

app = Flask(__name__)

# --- MOCK DATA FOR MARKETPLACE DEMO (no DB dependency) -----------------

ISSUE_DEMO = {
    "issue_id": 1,
    "issue_number": "266",
    "series_title": "Uncanny X-Men",
    "title": "Uncanny X-Men #266 (First Appearance of Gambit)",
    "year": "1990",
    "blurb": (
        "First full appearance of Gambit. Storm is de-aged; "
        "Gambit rescues her from the Shadow King's thieves in New Orleans."
    ),
    "cover_url": "https://i.annihil.us/u/prod/marvel/i/mg/9/70/5c794f8f0f0a1.jpg",
    "tagline": "Multiple grades available. Starting under $100.",
}

LISTINGS_DEMO = [
    {
        "listing_id": 1,
        "seller": "MutantComics",
        "grade": "CGC 9.6 Slabbed",
        "notes": "Encased, white pages, razor corners. Investment copy.",
        "price_cents": 120000,
    },
    {
        "listing_id": 2,
        "seller": "MutantComics",
        "grade": "VF 8.0",
        "notes": "Light spine ticks, tight corners, glossy cover. Presents near VF.",
        "price_cents": 35000,
    },
    {
        "listing_id": 3,
        "seller": "Xavier Collectibles",
        "grade": "FN 6.5",
        "notes": "Edge wear and some color breaks along spine. Complete mid-grade.",
        "price_cents": 20000,
    },
    {
        "listing_id": 4,
        "seller": "Xavier Collectibles",
        "grade": "Reader Copy",
        "notes": "Heavy creasing, detached at staple. Story copy only.",
        "price_cents": 9000,
    },
]


def cents_to_price(cents):
    dollars = cents // 100
    remainder = cents % 100
    return f"${dollars}.{remainder:02d}"

# -------------------------------------------------
# /series  (list + search)
# -------------------------------------------------
@app.get("/series")
def series_search():
    """
    Show list of series. Optional ?q= query to filter by title.
    Renders templates/series.html using a normalized list of dicts,
    so the template doesn't need to know model internals.
    """
    q = request.args.get("q", "").strip()

    with Session(get_engine()) as s:
        stmt = select(Series).order_by(Series.title)
        if q:
            stmt = stmt.where(Series.title.ilike(f"%{q}%"))
        rows = s.scalars(stmt).all()

    # 🔴 IMPORTANT PART:
    # We normalize each SQLAlchemy model into a predictable dict:
    series_list_clean = []
    for row in rows:
        # Try common name guesses in priority order.
        # We'll take the first attribute that actually exists.
        # If one doesn't exist on the model, getattr will give None and we skip it.
        possible_id_fields = ["id", "series_id", "pk", "marvel_series_id"]
        actual_id_value = None
        for field in possible_id_fields:
            if hasattr(row, field):
                actual_id_value = getattr(row, field)
                if actual_id_value is not None:
                    break

        series_list_clean.append(
            {
                "id": actual_id_value,
                "title": getattr(row, "title", "(no title)"),
            }
        )

    return render_template(
        "series.html",
        series_list=series_list_clean,
        query=q,
    )



# -------------------------------------------------
# /series/<series_id>/issues  (table view)
# -------------------------------------------------
@app.get("/series/<int:series_id>/issues")
def series_issues(series_id: int):
    """
    Show all issues for a given series_id in a table layout.
    Renders templates/issues.html
    """
    with Session(get_engine()) as s:
        series_obj = s.get(Series, series_id)
        if not series_obj:
            return f"<h1>Series {escape(series_id)} not found</h1>", 404

        issue_rows = (
            s.execute(
                select(Issue)
                .where(Issue.series_id == series_id)
                .order_by(Issue.issue_number)
            )
            .scalars()
            .all()
        )

    # Build a simple list of dicts for the template
    issues_data = []
    for it in issue_rows:
        issues_data.append(
            {
                "issue_number": it.issue_number,
                "cover_date": it.cover_date.isoformat() if it.cover_date else "",
                "cover_image_url": it.cover_image_url or "",
            }
        )

    return render_template(
        "issues.html",
        series_title=series_obj.title,
        series_id=series_id,
        issues=issues_data,
    )


# -------------------------------------------------
# /series/<series_id>/gallery  (cover grid)
# -------------------------------------------------
@app.get("/series/<int:series_id>/gallery")
def series_gallery(series_id: int):
    """
    Show all issues for a given series_id in a visual grid of covers.
    Renders templates/gallery.html
    """
    with Session(get_engine()) as s:
        series_obj = s.get(Series, series_id)
        if not series_obj:
            return f"<h1>Series {escape(series_id)} not found</h1>", 404

        issue_rows = (
            s.execute(
                select(Issue)
                .where(Issue.series_id == series_id)
                .order_by(Issue.issue_number)
            )
            .scalars()
            .all()
        )

    # Same shape we used above, template will reuse it
    issues_data = []
    for it in issue_rows:
        issues_data.append(
            {
                "issue_number": it.issue_number,
                "cover_date": it.cover_date.isoformat() if it.cover_date else "",
                "cover_image_url": it.cover_image_url or "",
            }
        )

    return render_template(
        "gallery.html",
        series_title=series_obj.title,
        series_id=series_id,
        issues=issues_data,
    )

# -------------------------------------------------
# /marketplace  (landing / "search")
# -------------------------------------------------
@app.get("/marketplace")
def marketplace_home():
    """
    Landing/search-like page that teases a key issue (Gambit's first app).
    This is pure mock data for now so it's 100% reliable live.
    """
    return render_template(
        "marketplace_home.html",
        issue=ISSUE_DEMO,
    )


# -------------------------------------------------
# /marketplace/issue/<int:issue_id>
# -------------------------------------------------
@app.get("/marketplace/issue/<int:issue_id>")
def marketplace_issue(issue_id: int):
    """
    Show all graded copies for sale of a given issue.
    Also pure mock data for now.
    """
    if issue_id != ISSUE_DEMO["issue_id"]:
        return f"<h1>Issue {issue_id} not found in demo</h1>", 404

    # decorate listings with display price
    listings_display = []
    for row in LISTINGS_DEMO:
        listings_display.append(
            {
                **row,
                "price_display": cents_to_price(row["price_cents"]),
            }
        )

    return render_template(
        "marketplace_issue.html",
        issue=ISSUE_DEMO,
        listings=listings_display,
    )


# -------------------------------------------------
# /marketplace/cart   (stub for now)
# -------------------------------------------------
@app.get("/marketplace/cart")
def marketplace_cart():
    """
    Placeholder - later we can persist cart in session.
    For now, just show 'coming soon' but keep the comic-book theme.
    """
    subtotal_cents = LISTINGS_DEMO[1]["price_cents"]  # pretend they picked VF 8.0
    subtotal_display = cents_to_price(subtotal_cents)

    return render_template(
        "marketplace_cart.html",
        subtotal=subtotal_display,
        picked=LISTINGS_DEMO[1],  # VF 8.0 example
    )

# -------------------------------------------------
# Local dev entrypoint
# -------------------------------------------------
if __name__ == "__main__":
    # NOTE: You should run this file from project root using:
    #   python -m app.api
    #
    # But keeping this lets you ALSO do:
    #   python app/api.py
    # after adding sys.path, if you prefer.
    app.run(debug=True)
