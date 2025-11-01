PY=python

initdb:
	$(PY) -m etl.etl initdb

marvel:
	$(PY) -m etl.etl marvel --titles "Amazing Spider-Man" --max-items 100

quality:
	$(PY) -m etl.etl quality

stats:
	$(PY) -m etl.etl stats --top 10

db-up:
\tdocker compose up -d

db-down:
\tdocker compose down

db-psql:
\tdocker exec -it comixcatalog_db psql -U postgres -d comixcatalog

