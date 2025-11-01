-- Base schema (also created by SQLAlchemy models)

CREATE TABLE IF NOT EXISTS publisher (
  publisher_id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS series (
  series_id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  publisher_id INT REFERENCES publisher(publisher_id),
  start_year INT,
  volume INT,
  source_key TEXT,
  source_system TEXT
);

CREATE TABLE IF NOT EXISTS creator (
  creator_id SERIAL PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issue (
  issue_id SERIAL PRIMARY KEY,
  series_id INT REFERENCES series(series_id),
  issue_number TEXT,
  cover_date DATE,
  price_cents INT,
  isbn TEXT,
  upc TEXT,
  description TEXT,
  UNIQUE(series_id, issue_number)
);

CREATE TABLE IF NOT EXISTS issue_creator (
  issue_id INT REFERENCES issue(issue_id),
  creator_id INT REFERENCES creator(creator_id),
  role TEXT,
  PRIMARY KEY (issue_id, creator_id, role)
);

CREATE TABLE IF NOT EXISTS etl_run (
  run_id BIGSERIAL PRIMARY KEY,
  source_system TEXT,
  started_at TIMESTAMP DEFAULT now(),
  finished_at TIMESTAMP,
  records_read INT,
  records_loaded INT,
  status TEXT,
  notes TEXT
);
