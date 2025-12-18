import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Підтягує .env з кореня проєкту
load_dotenv()

def get_conn():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL не знайдено. Перевір файл .env у корені проєкту.")
    return psycopg2.connect(dsn, cursor_factory=RealDictCursor)
