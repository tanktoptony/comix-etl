from flask import Flask, request, jsonify
from etl.db import get_session
from etl.models import Issue, Series, Listing, User

app = Flask(__name__)

##############
# /search
##############
# Usage:
#   /search?q=gambit
#   /search?q=uncanny
#
# Returns matching issues (based on issue title OR series title)
# plus some useful info so we can render a results grid in the UI.

@app.get("/search")
def search_issues():
    q = request.args.get("q", "").strip()

    # safety: empty query -> empty list
    if not q:
        return jsonify({"results": []})

    session = get_session()

    # We search by issue title and also the parent series title.
    # Note: Postgres ILIKE = case-insensitive LIKE.
    results = (
        session.query(
            Issue.issue_id,
            Issue.issue_number,
            Issue.title.label("issue_title"),
            Issue.cover_url,
            Series.title.label("series_title"),
        )
        .join(Series, Series.series_id == Issue.series_id)
        .filter(
            (Issue.title.ilike(f"%{q}%")) |
            (Series.title.ilike(f"%{q}%"))
        )
        .order_by(Series.title.asc(), Issue.issue_number.asc())
        .all()
    )

    # convert to dicts for JSON
    payload = []
    for row in results:
        payload.append({
            "issue_id": row.issue_id,
            "issue_number": row.issue_number,
            "issue_title": row.issue_title,
            "series_title": row.series_title,
            "cover_url": row.cover_url,
            "detail_url": f"/issue/{row.issue_id}/listings"
        })

    session.close()
    return jsonify({"results": payload})


##############
# /issue/<issue_id>/listings
##############
# Usage:
#   /issue/1/listings
#
# Returns all the copies of this book currently for sale,
# with grade, notes, price, and seller.

@app.get("/issue/<int:issue_id>/listings")
def issue_listings(issue_id):
    session = get_session()

    # First, pull the issue itself (title, number, cover, etc.)
    issue_row = (
        session.query(
            Issue.issue_id,
            Issue.issue_number,
            Issue.title.label("issue_title"),
            Issue.cover_url,
        )
        .filter(Issue.issue_id == issue_id)
        .one_or_none()
    )

    if not issue_row:
        session.close()
        return jsonify({"error": "issue not found"}), 404

    # Then pull all listings attached to that issue
    listing_rows = (
        session.query(
            Listing.listing_id,
            Listing.grade_label,
            Listing.condition_notes,
            Listing.asking_price_cents,
            User.display_name.label("seller_name"),
        )
        .join(User, User.user_id == Listing.seller_id)
        .filter(Listing.issue_id == issue_id)
        .order_by(Listing.asking_price_cents.asc())
        .all()
    )

    listings_payload = []
    for row in listing_rows:
        listings_payload.append({
            "listing_id": row.listing_id,
            "seller": row.seller_name,
            "grade": row.grade_label,
            "condition_notes": row.condition_notes,
            "price_cents": row.asking_price_cents,
            "price_display": cents_to_price(row.asking_price_cents),
        })

    session.close()

    response = {
        "issue": {
            "issue_id": issue_row.issue_id,
            "issue_number": issue_row.issue_number,
            "title": issue_row.issue_title,
            "cover_url": issue_row.cover_url,
        },
        "listings": listings_payload
    }

    return jsonify(response)


def cents_to_price(cents):
    # tiny helper so you don't have to do mental math in the browser
    if cents is None:
        return None
    dollars = cents // 100
    remainder = cents % 100
    return f"${dollars}.{remainder:02d}"


if __name__ == "__main__":
    # Dev mode server (Flask built-in). Fine for local testing.
    app.run(host="127.0.0.1", port=5000, debug=True)
