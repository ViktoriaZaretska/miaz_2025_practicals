import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
import psycopg2

load_dotenv()

UNITS = [
    ("J1", "Особовий склад"),
    ("J2", "Розвідка"),
    ("J3", "Операції"),
    ("J4", "Логістика"),
    ("J5", "Планування"),
    ("J6", "Зв’язок / ІТ"),
    ("J7", "Підготовка"),
]

SECTORS = ["Сектор А", "Сектор Б", "Сектор В"]

DOC_TYPES = [
    ("ПБД", "Підсумкове бойове донесення"),
    ("БД", "Бойове донесення"),
    ("БЧС", "Бойове чергування"),
    ("ЗВІТ", "Звіт"),
    ("РОЗП", "Розпорядження"),
]

# Базові нормативи (хв) за пріоритетом: 1/2/3
NORM_BY_PRIORITY = {1: 60, 2: 180, 3: 360}

def env_dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL не знайдено. Перевір .env у корені проєкту.")
    return dsn

def dt_floor_day(d: datetime) -> datetime:
    return d.replace(hour=0, minute=0, second=0, microsecond=0)

def pick_weighted(items, weights):
    return random.choices(items, weights=weights, k=1)[0]

def ensure_reference_data(cur):
    cur.executemany(
        "INSERT INTO units (code, name) VALUES (%s,%s) ON CONFLICT (code) DO NOTHING;",
        UNITS
    )
    cur.executemany(
        "INSERT INTO sectors (name) VALUES (%s) ON CONFLICT (name) DO NOTHING;",
        [(s,) for s in SECTORS]
    )
    cur.executemany(
        "INSERT INTO doc_types (code, name) VALUES (%s,%s) ON CONFLICT (code) DO NOTHING;",
        DOC_TYPES
    )

    cur.execute("SELECT doc_type_id FROM doc_types;")
    type_ids = [r[0] for r in cur.fetchall()]
    for doc_type_id in type_ids:
        for prio, max_minutes in NORM_BY_PRIORITY.items():
            cur.execute(
                """
                INSERT INTO norms (doc_type_id, priority, max_minutes)
                VALUES (%s,%s,%s)
                ON CONFLICT (doc_type_id, priority) DO NOTHING;
                """,
                (doc_type_id, prio, max_minutes)
            )

def ids_map(cur):
    cur.execute("SELECT unit_id, code FROM units;")
    units = {r[1]: r[0] for r in cur.fetchall()}

    cur.execute("SELECT sector_id, name FROM sectors;")
    sectors = {r[1]: r[0] for r in cur.fetchall()}

    cur.execute("SELECT doc_type_id, code FROM doc_types;")
    types_ = {r[1]: r[0] for r in cur.fetchall()}

    return units, sectors, types_

def make_title(doc_type: str, unit: str, sector: str) -> str:
    templates = {
        "ПБД": "ПБД: узагальнення за добу",
        "БД": "БД: уточнення обстановки",
        "БЧС": "БЧС: поточний стан",
        "ЗВІТ": "ЗВІТ: аналіз ситуації",
        "РОЗП": "РОЗП: організаційні вказівки",
    }
    base = templates.get(doc_type, "Документ")
    return f"{base} ({unit}, {sector})"

def clear_documents(cur):
    cur.execute("TRUNCATE TABLE documents RESTART IDENTITY;")

def generate_week_documents(cur, *, days=7, total_docs=260, overload_unit="J3"):
    """
    Покращений генератор:
    - 7 днів
    - піки (середа/п’ятниця) + зростання T̄
    - перевантаження J3 (більше документів + довші цикли + більше прострочень)
    """
    units, sectors, types_ = ids_map(cur)

    now = datetime.now()
    end_day = dt_floor_day(now)
    start_day = end_day - timedelta(days=days - 1)

    # Пікові дні: середина тижня (index 2-3) + п’ятниця (index 4)
    # Це робить графіки “живими”
    day_weights = [0.9, 1.05, 1.55, 1.35, 1.45, 1.05, 0.85][:days]
    weight_sum = sum(day_weights)
    per_day = [max(16, int(total_docs * w / weight_sum)) for w in day_weights]

    unit_codes = [u[0] for u in UNITS]
    unit_weights = [1.0]*len(unit_codes)
    if overload_unit in unit_codes:
        unit_weights[unit_codes.index(overload_unit)] = 2.6  # сильніше

    type_codes = [t[0] for t in DOC_TYPES]
    type_weights = [1.1, 1.8, 1.2, 1.3, 1.0]  # БД частіше

    prios = [1, 2, 3]
    prio_weights = [0.22, 0.66, 0.12]

    inserted = 0

    for i in range(days):
        day = start_day + timedelta(days=i)

        # коефіцієнт “ускладнення” на піках (затримки ростуть)
        peak_factor = 1.0
        if i in (2, 4):      # умовно “середа” і “п’ятниця”
            peak_factor = 1.35
        elif i == 3:
            peak_factor = 1.20

        for _ in range(per_day[i]):
            unit = pick_weighted(unit_codes, unit_weights)
            sector = random.choice(SECTORS)
            doc_type = pick_weighted(type_codes, type_weights)
            prio = pick_weighted(prios, prio_weights)

            # час в межах дня
            hour = pick_weighted([7, 9, 11, 13, 15, 17, 19, 21], [0.6, 1.0, 1.1, 1.0, 1.05, 1.0, 0.9, 0.6])
            minute = random.choice([0, 5, 10, 15, 20, 30, 40, 50])
            doc_date = day.replace(hour=hour, minute=minute, second=0, microsecond=0)

            received_at = doc_date + timedelta(minutes=random.randint(0, 25))

            # База імовірностей статусів
            base = {"доведено": 0.60, "в_роботі": 0.22, "отримано": 0.10, "прострочено": 0.08}

            # На піках і при перевантаженні J3 збільшуємо “в роботі/прострочено”
            if peak_factor > 1.0:
                base["прострочено"] += 0.05
                base["в_роботі"] += 0.04
                base["доведено"] -= 0.07
                base["отримано"] -= 0.02

            if unit == overload_unit:
                base["прострочено"] += 0.06
                base["в_роботі"] += 0.05
                base["доведено"] -= 0.09
                base["отримано"] -= 0.02

            # нормалізація
            s = sum(base.values())
            weights = [base["доведено"]/s, base["в_роботі"]/s, base["отримано"]/s, base["прострочено"]/s]
            status = pick_weighted(["доведено", "в_роботі", "отримано", "прострочено"], weights)

            norm = NORM_BY_PRIORITY[prio]

            # Додатковий множник затримок для J3
            unit_delay = 1.0 if unit != overload_unit else 1.35

            processed_at = None
            delivered_at = None

            if status == "отримано":
                pass

            elif status == "в_роботі":
                proc_minutes = int(random.randint(10, int(norm*0.85) + 35) * peak_factor * unit_delay)
                processed_at = received_at + timedelta(minutes=proc_minutes)

            elif status == "доведено":
                proc_minutes = int(random.randint(8, int(norm*0.65) + 30) * peak_factor * unit_delay)
                del_minutes = int((proc_minutes + random.randint(6, int(norm*0.55) + 35)) * peak_factor * unit_delay)
                processed_at = received_at + timedelta(minutes=proc_minutes)
                delivered_at = received_at + timedelta(minutes=del_minutes)

            else:  # прострочено
                proc_minutes = int(random.randint(int(norm*0.8), int(norm*1.3) + 60) * peak_factor * unit_delay)
                del_minutes = int(random.randint(norm + 45, norm + 300) * peak_factor * unit_delay)
                processed_at = received_at + timedelta(minutes=proc_minutes)
                if random.random() < 0.65:
                    delivered_at = received_at + timedelta(minutes=del_minutes)
                else:
                    delivered_at = None

            # Не в майбутнє
            if received_at > now:
                received_at = now - timedelta(minutes=random.randint(1, 30))
            if processed_at and processed_at > now:
                processed_at = now - timedelta(minutes=random.randint(1, 20))
            if delivered_at and delivered_at > now:
                delivered_at = now - timedelta(minutes=random.randint(1, 10))

            title = make_title(doc_type, unit, sector)

            cur.execute(
                """
                INSERT INTO documents (
                    reg_number, title, doc_date,
                    unit_id, sector_id, doc_type_id,
                    status, priority,
                    received_at, processed_at, delivered_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
                """,
                (
                    None, title, doc_date,
                    units[unit], sectors[sector], types_[doc_type],
                    status, prio,
                    received_at, processed_at, delivered_at
                )
            )
            inserted += 1

    return inserted

def main():
    random.seed(13)

    dsn = env_dsn()
    conn = psycopg2.connect(dsn)
    conn.autocommit = True

    with conn.cursor() as cur:
        ensure_reference_data(cur)
        clear_documents(cur)
        inserted = generate_week_documents(cur, days=7, total_docs=260, overload_unit="J3")

    conn.close()
    print(f"✅ Seed виконано. Згенеровано документів за 7 днів: {inserted}")

if __name__ == "__main__":
    main()
