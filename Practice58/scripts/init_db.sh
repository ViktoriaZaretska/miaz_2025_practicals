#!/usr/bin/env bash
set -e
python scripts/run_sql.py db/schema.sql
python db/seed.py
