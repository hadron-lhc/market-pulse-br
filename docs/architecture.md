# Architecture

```
Olist CSVs (data/, git-ignored)
        │  python -m ecommerce_intel.ingest
        ▼
PostgreSQL  ── raw schema          (typed landing tables, PKs + FKs, truncate+copy per run)
        │     dbt run
        ▼
analytics.staging                   (typed/cleaned views, 1:1 with sources)
analytics.intermediate              (order-grain aggregations; the anti-fan-out layer)
analytics.marts                     (business-facing tables, one grain each)
        │     dbt test              (83 tests: keys, FKs, values, fan-out invariants)
        ▼
python -m ecommerce_intel.analysis.run_all   →  Plotly charts + computed_findings.md
analysis/insights.md                          →  hand-written professional report
streamlit run dashboard/app.py                →  dashboard over the marts
```

## Key decisions

- **Local PostgreSQL first, Docker Compose optional.** The pipeline only needs
  a Postgres 14+ reachable through libpq env vars. `docker-compose.yml`
  provides an isolated instance on port 5433; a system-installed Postgres works
  identically (this repository was developed against PG 16 via unix socket).
- **One transaction per ingestion run.** All raw tables are truncated and
  reloaded inside a single transaction with row-count assertions — repeated
  runs cannot duplicate or partially load data.
- **Explicit types at load time.** CSV values are cast in Python with row-level
  error messages, then `COPY`'d; the DDL in `sql/raw_ddl.sql` is the schema of
  record. Original CSVs are never modified.
- **Order-grain backbone.** Olist's orders fan out to items (9,803 multi-item
  orders), payments (2,961) and reviews (547). Every join that could fan out is
  resolved inside `int_order_facts` (one row per order); marts only read that
  backbone or item-grain rows with explicit aggregation. This is enforced by
  dbt tests, not convention.
- **dbt materializations:** staging = views, intermediate/marts = tables
  (fast dashboard reads; full build ≈ 10 s on this dataset).
- **Schemas without prefixes.** A `generate_schema_name` macro maps model
  folders to plain schemas `staging` / `intermediate` / `marts` / `fixtures`.
- **No warehouse, no orchestrator.** The dataset is 1.5M rows and a laptop
  pipeline; Airflow/cloud warehouses would add ceremony without value.
- **dbt profiles via env vars.** `dbt_project/profiles.yml` contains only
  `env_var()` references; the Makefile exports `.env` before running dbt.
- **Analysis in Python, logic in SQL.** Business logic lives in dbt models;
  Python scripts fetch finished marts for statistics (scipy) and Plotly charts.
- **Fixtures are labeled.** Synthetic seed data (multi-item, multi-payment,
  canceled, missing timestamps) exists only to pin test expectations and is
  clearly separated from Olist data.

## Repository layout

| Path | Purpose |
|---|---|
| `src/ecommerce_intel/` | ingestion, profiling, analysis package |
| `sql/raw_ddl.sql` | raw schema (source of truth for landing tables) |
| `dbt_project/` | dbt project: staging/intermediate/marts, tests, fixture seeds |
| `analysis/` | insights report (committed) + generated charts (git-ignored) |
| `dashboard/` | Streamlit app over the marts |
| `docs/` | data dictionary, metrics, limitations, quality report |
| `tests/` | pytest unit + database integration tests |
