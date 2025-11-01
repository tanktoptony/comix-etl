# ComixCatalog (MVP)

A tiny **Discogs-for-comics** ETL project - Python + APIs + SQL.

## What it does
- Postgres schema for publishers, series, issues, creators, credits.
- Python ETL for **Marvel API** (live) with pagination + auth.
- Upserts into Postgres via SQLAlchemy.
- Lightweight data-quality checks and an `etl_run` audit table.

> You can later add Grand Comics Database (GCD) dump ingestion as a second source.

## Quick start

### 1) Prereqs
- Python 3.10+
- Postgres (local or Docker)
- A Marvel developer account with **public** and **private** API keys

### 2) Create Postgres locally (Docker example)
```bash
docker run --name comix-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=comix -p 5432:5432 -d postgres:16
```

### 3) Setup Python env
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.sample .env
# then edit .env with your keys / DB URL
```

### 4) Initialize DB tables
```bash
python -m etl.etl initdb
```

### 5) Run a first extract+load from Marvel
```bash
# One or more titles (comma-separated). Keep small to start.
python -m etl.etl marvel --titles "Amazing Spider-Man" --max-items 100
```

### 6) Run quality checks
```bash
python -m etl.etl quality
```

### 7) Try a quick query (top series by issue count)
```bash
python -m etl.etl stats --top 10
```

## Notes
- The CLI logs each run to the `etl_run` table.
- You can extend `etl/sources/gcd_extract.py` later to process GCD dumps.
- For WBEZ interview talking points, see `README_TALKING_POINTS.md`.
