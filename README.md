# Market Pulse — E-commerce Intelligence Platform

A production-minded analytics project built on the
[Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
It takes raw marketplace CSVs all the way to tested analytical marts, a
statistically-grounded insights report and an executive dashboard — with the
correctness traps of this dataset (join fan-out, payment vs item totals,
review duplicates, promise-relative lateness) handled explicitly and enforced
by data tests.

## Business problem

Olist-style marketplaces need answers that survive scrutiny: *How much did we
really sell? Which categories and sellers drive value? Where does delivery
break its promise, and what does that do to reviews? Is there any repeat
purchasing?* This project answers those questions with a reproducible
pipeline, documented metric definitions and evidence-based (never causal)
findings.

## What's inside

| Layer | Implementation |
|---|---|
| Ingestion | `src/ecommerce_intel/ingest.py` — typed, transactional, idempotent CSV → PostgreSQL `COPY` |
| Data quality | `src/ecommerce_intel/quality_profile.py` → [docs/data_quality_report.md](docs/data_quality_report.md) |
| Transformations | dbt: 8 staging views, 5 intermediate tables, 14 marts ([dbt_project](dbt_project/)) |
| Data tests | 83 dbt tests incl. fan-out/double-counting invariants + 21 pytest tests (unit + DB integration on synthetic fixtures) |
| Metrics layer | [docs/metric_definitions.md](docs/metric_definitions.md) |
| Analysis | `python -m ecommerce_intel.analysis.run_all` → 22 Plotly charts + computed findings |
| Insights | [analysis/insights.md](analysis/insights.md) — 9 findings with metrics, limitations, recommendations |
| Dashboard | [dashboard/app.py](dashboard/app.py) — Streamlit over the marts only |

## Architecture

```
CSVs (data/, git-ignored) ──ingest──▶ raw schema ──dbt──▶ staging ──▶ intermediate ──▶ marts
                                        │                                               │
                                   83 data tests ◀─────────────────────────────────────┤
                                                                                       ▼
                                             analysis scripts (scipy + Plotly) · Streamlit dashboard
```

Design decisions and rationale: [docs/architecture.md](docs/architecture.md).
Table grains: [docs/data_dictionary.md](docs/data_dictionary.md).
Known limitations: [docs/limitations.md](docs/limitations.md).

**The anti-double-counting backbone:** 9,803 orders have multiple items,
2,961 have multiple payment records and 547 have multiple reviews. All
order-level joins are resolved once in `int_order_facts` (exactly one row per
order, tested), so revenue and order metrics can never fan out.

## Tech stack

Python 3.12 · uv · PostgreSQL 14+ · dbt Core (postgres adapter) · pandas ·
scipy · Plotly · Streamlit · pytest · ruff · Docker Compose (optional).

## Setup

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), PostgreSQL
(local install or Docker).

```bash
git clone git@github.com:hadron-lhc/market-pulse-br.git && cd market-pulse-br
cp .env.example .env         # then edit PG* settings (see below)
uv sync                      # install Python deps (incl. dbt)
```

Place the nine Olist CSVs from Kaggle in `data/` (kept out of git).
They must be present before ingestion.

### Database configuration

`docker-compose.yml` runs an isolated PostgreSQL 16 on port **5433**:

```bash
make db-up                   # docker compose up -d --wait
# in .env set: PGHOST=localhost PGPORT=5433 PGUSER=postgres PGPASSWORD=changeit
```

A system-installed PostgreSQL works identically (this project was developed
against PG 16 via unix socket):

```bash
# in .env: PGHOST=/var/run/postgresql PGUSER=<your role> PGDATABASE=olist_analytics
```

`.env` is git-ignored; `.env.example` documents every variable.

## Run the pipeline

```bash
make ingest      # CSVs → raw schema (truncate+COPY, one transaction, ~35s)
make profile     # regenerate docs/data_quality_report.md from the raw schema
make dbt-build   # dbt seed + run + test (27 models, 83 tests, ~15s)
make test        # pytest: unit + DB integration + dashboard smoke test
make analyze     # analysis scripts → analysis/output/ (charts + computed findings)
make dashboard   # streamlit run dashboard/app.py
```

`make all` chains setup → ingest → dbt-build → pytest → analyze.
Every target also works standalone; the dbt CLI needs `DBT_PROFILES_DIR`,
which the Makefile exports (profiles.yml contains only `env_var()` refs).

## Deploy

**Live demo:** [market-pulse-br.streamlit.app](https://market-pulse-br.streamlit.app)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://market-pulse-br.streamlit.app)

```
push ─▶ GitHub Actions ── ruff · pytest · dbt build ──(SSL)──▶ Neon PostgreSQL
Streamlit Community Cloud ── reads marts ────────────────────────┘
```

- **Streamlit Cloud** runs `dashboard/app.py` on Python 3.12, installing
  `requirements.txt` (generated with `uv export --frozen --no-dev --no-hashes`).
  Connection params live in the app's `secrets` (`PGHOST`, `PGPORT`, `PGUSER`,
  `PGPASSWORD`, `PGDATABASE`, `PGSSLMODE`) and are exported to the environment at
  startup by `export_secrets_to_env()` in `dashboard/app.py`.
- **Neon** (free tier) hosts the analytics database. It is loaded once with
  `make ingest && make dbt-build` from a workstation (raw CSVs stay out of git).
- **CI** (`.github/workflows/ci.yml`) re-runs lint, pytest and the full dbt
  build — including all 83 data tests — on every push and pull request.
- Cold starts: free-tier Neon compute and the Streamlit app scale to zero when
  idle, so the first load after a pause can take 10–30 s.
- Local alternative: `docker-compose.yml` + `make db-up` (see Setup).

## Verified headline results

Computed from the full dataset (2016-09 → 2018-08 effective window; all
definitions in [docs/metric_definitions.md](docs/metric_definitions.md)):

- **R$ 15.74M** revenue (item price + freight) over **98,199** revenue orders;
  AOV R$ 160.24 vs median R$ 105.28 — growth is volume-driven (+21.2% 2018 vs 2017).
- `health_beauty` leads with 9.1% of revenue; top-10 categories hold 62.3%.
- **135 sellers (4.4%) produce half** of seller revenue (HHI ≈ 35).
- Median delivery **10.2 days**, p90 23.1; late rate **6.78%** overall but
  **12–19% in peak months** (Nov-17, Feb/Mar-18) — lateness is episodic.
- Lateness ≠ slowness: AL is late 21.4% of the time (median 22.3 d) while AM
  is late 2.8% despite a 25.9-day median — promises are region-padded.
- Late orders gather **≤2-star reviews 62.4% of the time vs 9.3%** on time
  (6.7× risk ratio; Mann-Whitney rank-biserial −0.64; associational).
- Installments and order value: Spearman ρ = 0.46 (n = 75,614) — association, not causation.
- **Repeat customers: 3.04%** of customers (5.66% of revenue); median 28 days to second order.

Full narrative with recommendations: [analysis/insights.md](analysis/insights.md).

## Data quality at a glance

- 1,550,922 rows loaded; zero PK duplicates, zero orphans (enforced by FKs at load).
- Item revenue + freight (R$ 15.84M) vs payment totals (R$ 16.01M): the R$ 165k
  gap is explained by payments on orders with **no items** (R$ 162.6k, mostly
  canceled/unavailable) plus 303 orders differing by >0.01 BRL (max R$ 182.81) —
  reconciled by a dedicated dbt test with documented thresholds.
- 8 delivered orders lack delivery timestamps; 547 orders carry multiple
  reviews (dedup rule documented in `int_reviews_agg`).

Details: [docs/data_quality_report.md](docs/data_quality_report.md).

## Tests

```bash
uv run pytest          # 21 tests: casting, config, PK/FK, idempotent reload,
                       # fan-out guards, review dedup, quality report, dashboard
cd dbt_project && dbt test   # 83 tests: keys, FKs, accepted values,
                             # revenue reconciliation, additivity, fixtures
```

Synthetic fixtures (`dbt_project/seeds/fixture_*.csv`) pin the aggregation
math on invented rows (multi-item, multi-payment, canceled, missing
timestamps); they are never presented as Olist results.

## Repository layout

```
├── src/ecommerce_intel/      # ingestion, profiling, analysis package
├── sql/raw_ddl.sql           # raw schema (PKs, FKs, explicit types)
├── dbt_project/              # staging / intermediate / marts + tests + fixtures
├── analysis/                 # insights.md (committed) + output/ (generated charts)
├── dashboard/app.py          # Streamlit over the marts
├── docs/                     # architecture, dictionary, metrics, limitations, quality
├── tests/                    # pytest suite
├── docker-compose.yml        # optional local PostgreSQL 16
└── Makefile                  # one command per workflow step
```

## Dataset attribution

Olist Brazilian E-Commerce Public Dataset, published on Kaggle under the
[ODbL 1.0 license](https://opendatacommons.org/licenses/odbl/1-0/).
Original CSVs are used unmodified; all cleaning happens in code.

## Limitations (summary)

No cost/margin data (revenue ≠ profit) · pseudonymous customer ids (repeat
rates are bounds, not truth) · ~20-month window with heavy cohort censoring ·
all statistical relationships are observational (no causal claims) · category
and payment dimensions are non-additive for order counts.
Full list: [docs/limitations.md](docs/limitations.md).
