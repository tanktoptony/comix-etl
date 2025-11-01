# Interview Talking Points (Cheat Sheet)

**ETL shape:** Extract (Marvel API) → Transform (normalize, dates, roles) → Load (Postgres upserts) → Quality (counts + nulls) → Audit (etl_run).

**Challenges you can discuss:**
- Pagination: iterate `offset` until fewer than `limit` returned.
- Data consistency: normalize creators by case-insensitive name; unique (series, issue_number).
- Nulls & schema drift: whitelist fields in transform; add defaults for missing prices/dates.
- Guardrails: abort load if the batch returns <80% of expected records for a known series.

**Monitoring:**
- `etl_run` row per job with records_read/loaded + status.
- Quality checks for null cover_date, orphan issues (no series), duplicate creators.

**Extensions:**
- Add GCD dump ingestion for breadth.
- Cache API responses locally to respect rate limits.
- Optional Flask read-only `/series?q=...` endpoint (see `app/api.py`).

**Why CPM/WBEZ:**
- This project shows you can turn messy, external data into trustworthy facts for storytelling & analytics (audience, membership, content KPIs).