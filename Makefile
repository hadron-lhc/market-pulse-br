SHELL := /bin/bash

# Export .env (if present) so dbt and the Make targets share one configuration.
ifneq (,$(wildcard .env))
include .env
export
endif

export DBT_PROFILES_DIR := $(CURDIR)/dbt_project

.PHONY: setup db-up db-down ingest profile dbt-run dbt-test dbt-build \
        test lint format analyze dashboard all

## Install Python dependencies with uv
setup:
	uv sync

## Start local PostgreSQL via Docker Compose (requires docker group access)
db-up:
	docker compose up -d --wait

db-down:
	docker compose down

## Load raw CSVs into the raw schema (idempotent)
ingest:
	uv run python -m ecommerce_intel.ingest

## Generate the data quality report from the raw schema
profile:
	uv run python -m ecommerce_intel.quality_profile

## dbt
dbt-run:
	uv run dbt run --project-dir dbt_project

dbt-test:
	uv run dbt test --project-dir dbt_project

dbt-build:
	uv run dbt build --project-dir dbt_project

## Python checks
test:
	uv run pytest

lint:
	uv run ruff check src tests analysis dashboard
	uv run ruff format --check src tests analysis dashboard

format:
	uv run ruff format src tests analysis dashboard

## Analysis + dashboard
analyze:
	uv run python -m ecommerce_intel.analysis.run_all

dashboard:
	uv run streamlit run dashboard/app.py

## Full pipeline: deps -> ingest -> dbt build -> python tests -> analysis
all: setup ingest dbt-build test analyze
