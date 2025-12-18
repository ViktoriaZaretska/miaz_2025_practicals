Орієнтир-А
Minimal Postgres + FastAPI (sync) + vanilla JS dashboard.

Quick start (Windows)
venv + deps: python -m venv .venv && .\.venv\Scripts\activate && pip install -r requirements.txt
create DB: psql -c "CREATE DATABASE orientyr_a;"
schema: .\scripts\init_db.ps1
seed: .\scripts\seed_db.ps1
API: uvicorn api.main:app --reload
web: cd web && python -m http.server 8000
Quick start (Linux/macOS)
venv + deps: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
create DB: psql -c "CREATE DATABASE orientyr_a;"
schema: bash scripts/init_db.sh
seed: bash scripts/seed_db.sh
API: uvicorn api.main:app --reload
web: cd web && python -m http.server 8000
Demo script
Executive view: open web/index.html?view=executive, apply filters, read KPI + trend insight.
Analyst view: switch to ?view=analyst, explore heatmap and incidents table/modal.
Demo view: switch to ?view=demo, show KPI + charts + heatmap (incidents hidden).