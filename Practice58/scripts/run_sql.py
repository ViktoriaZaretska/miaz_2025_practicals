import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Використання: python scripts/run_sql.py db/schema.sql")

    sql_path = Path(sys.argv[1])
    if not sql_path.exists():
        raise SystemExit(f"Файл не знайдено: {sql_path}")

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL не знайдено. Перевір .env у корені проєкту.")

    sql = sql_path.read_text(encoding="utf-8")

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.close()

    print(f"✅ Виконано: {sql_path}")

if __name__ == "__main__":
    main()
