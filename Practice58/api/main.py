from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, date, time
import os

from api.db import get_conn

app = FastAPI(title="IAZ Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_dt(x: str | None):
    return datetime.fromisoformat(x) if x else None

def parse_date(x: str | None):
    return date.fromisoformat(x) if x else None

def parse_time(x: str | None):
    return time.fromisoformat(x) if x else None

# -------------------------
# Time model
# -------------------------
class TimeControlUpdate(BaseModel):
    mode: str | None = None         # 'auto' або 'manual'
    op_date: str | None = None      # 'YYYY-MM-DD' (для manual)
    op_day_start: str | None = None # 'HH:MM'
    astro_time: str | None = None   # 'YYYY-MM-DDTHH:MM:SS' (опційно, для тестів)

class EventCreate(BaseModel):
    event_time: str | None = None   # якщо None — now()
    event_type: str = "RIZKA_ZMINA"
    sector_id: int | None = None
    severity: int | None = None
    note: str | None = None

def get_time_control():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM time_control WHERE id=1;")
        row = cur.fetchone()
        if not row:
            # fallback: створимо
            cur.execute("""
                INSERT INTO time_control (id, astro_time, op_date, op_day_start, mode)
                VALUES (1, now(), CURRENT_DATE, '06:00', 'manual')
                RETURNING *;
            """)
            row = cur.fetchone()
    return row

def compute_op_date(astro: datetime, op_day_start: time) -> date:
    # auto режим: оп-доба починається з op_day_start
    if astro.time() < op_day_start:
        return (astro.date() - timedelta(days=1))
    return astro.date()

def compute_op_now(astro: datetime, op_date_val: date) -> datetime:
    # оперативний час = час доби з astro, але дата = op_date
    return datetime.combine(op_date_val, astro.time())

@app.get("/api/time_status")
def time_status():
    tc = get_time_control()

    astro = tc["astro_time"]
    op_day_start = tc["op_day_start"]
    mode = tc["mode"]

    if mode == "auto":
        op_date_val = compute_op_date(astro, op_day_start)
    else:
        op_date_val = tc["op_date"]

    op_now = compute_op_now(astro, op_date_val)

    return {
        "mode": mode,
        "astro_time": astro.isoformat(sep=" ", timespec="seconds"),
        "op_date": op_date_val.isoformat(),
        "op_time": op_now.strftime("%H:%M:%S"),
        "op_day_start": op_day_start.strftime("%H:%M"),
    }

@app.post("/api/time_control")
def update_time_control(body: TimeControlUpdate):
    tc = get_time_control()

    mode = body.mode or tc["mode"]
    op_day_start = parse_time(body.op_day_start) if body.op_day_start else tc["op_day_start"]
    astro_time = parse_dt(body.astro_time) if body.astro_time else datetime.now()

    op_date_val = tc["op_date"]
    if mode == "auto":
        op_date_val = compute_op_date(astro_time, op_day_start)
    else:
        if body.op_date:
            op_date_val = parse_date(body.op_date)
        # якщо не передали op_date — залишимо як є

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE time_control
            SET astro_time=%s, op_date=%s, op_day_start=%s, mode=%s, updated_at=now()
            WHERE id=1
            RETURNING *;
            """,
            (astro_time, op_date_val, op_day_start, mode)
        )
        row = cur.fetchone()

    return {
        "mode": row["mode"],
        "astro_time": row["astro_time"].isoformat(sep=" ", timespec="seconds"),
        "op_date": row["op_date"].isoformat(),
        "op_day_start": row["op_day_start"].strftime("%H:%M"),
    }

@app.post("/api/event")
def create_event(body: EventCreate):
    tc = get_time_control()
    astro = datetime.now()
    # op_date визначимо як у time_control (manual/auto)
    mode = tc["mode"]
    op_day_start = tc["op_day_start"]
    op_date_val = compute_op_date(astro, op_day_start) if mode == "auto" else tc["op_date"]

    ev_time = parse_dt(body.event_time) if body.event_time else astro

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO events (event_time, op_date, event_type, sector_id, severity, note)
            VALUES (%s,%s,%s,%s,%s,%s)
            RETURNING event_id;
            """,
            (ev_time, op_date_val, body.event_type, body.sector_id, body.severity, body.note)
        )
        eid = cur.fetchone()["event_id"]

    return {"event_id": eid, "op_date": op_date_val.isoformat(), "event_time": ev_time.isoformat(sep=" ", timespec="seconds")}

# -------------------------
# Existing endpoints (filters, kpi, charts, docs)
# -------------------------
@app.get("/api/filters")
def filters():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT unit_id, code FROM units ORDER BY code;")
        units = cur.fetchall()
        cur.execute("SELECT sector_id, name FROM sectors ORDER BY name;")
        sectors = cur.fetchall()
        cur.execute("SELECT doc_type_id, code FROM doc_types ORDER BY code;")
        types_ = cur.fetchall()
    return {"units": units, "sectors": sectors, "types": types_}

@app.get("/api/kpi")
def kpi(
    date_from: str | None = None,
    date_to: str | None = None,
    unit_id: int | None = None,
    sector_id: int | None = None,
    doc_type_id: int | None = None,
    status: str | None = None,
    priority: int | None = None,
):
    df = parse_dt(date_from)
    dt = parse_dt(date_to)

    where = ["1=1"]
    params = {}
    if df:
        where.append("doc_date >= %(df)s"); params["df"] = df
    if dt:
        where.append("doc_date <= %(dt)s"); params["dt"] = dt
    if unit_id:
        where.append("unit_id = %(unit_id)s"); params["unit_id"] = unit_id
    if sector_id:
        where.append("sector_id = %(sector_id)s"); params["sector_id"] = sector_id
    if doc_type_id:
        where.append("doc_type_id = %(doc_type_id)s"); params["doc_type_id"] = doc_type_id
    if status:
        where.append("status = %(status)s"); params["status"] = status
    if priority:
        where.append("priority = %(priority)s"); params["priority"] = priority

    sql = f"""
      SELECT
        COUNT(*) AS total_docs,
        COUNT(*) FILTER (WHERE status='доведено') AS delivered_docs,
        COUNT(*) FILTER (WHERE status='прострочено') AS overdue_docs,
        ROUND(AVG(cycle_minutes)::numeric, 1) AS avg_cycle_minutes
      FROM documents
      WHERE {" AND ".join(where)};
    """

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()

    total = row["total_docs"] or 0
    delivered = row["delivered_docs"] or 0
    operativity = round((delivered / total) * 100, 1) if total else 0.0

    return {
        "operativity_percent": operativity,
        "avg_cycle_minutes": row["avg_cycle_minutes"],
        "total_docs": total,
        "overdue_docs": row["overdue_docs"] or 0,
    }

@app.get("/api/worked_docs")
def worked_docs(
    date_from: str | None = None,
    date_to: str | None = None,
    unit_id: int | None = None,
    sector_id: int | None = None,
    priority: int | None = None,
):
    df = parse_dt(date_from)
    dt = parse_dt(date_to)

    where = ["1=1"]
    params = {}
    if df: where.append("d.doc_date >= %(df)s"); params["df"] = df
    if dt: where.append("d.doc_date <= %(dt)s"); params["dt"] = dt
    if unit_id: where.append("d.unit_id = %(unit_id)s"); params["unit_id"] = unit_id
    if sector_id: where.append("d.sector_id = %(sector_id)s"); params["sector_id"] = sector_id
    if priority: where.append("d.priority = %(priority)s"); params["priority"] = priority

    sql = f"""
      SELECT dt.code AS doc_type,
             COUNT(*) FILTER (WHERE d.status IN ('в_роботі','доведено','прострочено')) AS processed,
             COUNT(*) FILTER (WHERE d.status='доведено') AS delivered,
             COUNT(*) FILTER (WHERE d.status='отримано') AS received
      FROM documents d
      JOIN doc_types dt ON dt.doc_type_id = d.doc_type_id
      WHERE {" AND ".join(where)}
      GROUP BY dt.code
      ORDER BY dt.code;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"rows": rows}

@app.get("/api/docs_by_unit")
def docs_by_unit(
    date_from: str | None = None,
    date_to: str | None = None,
    sector_id: int | None = None,
    doc_type_id: int | None = None,
    priority: int | None = None,
):
    df = parse_dt(date_from)
    dt = parse_dt(date_to)

    where = ["1=1"]
    params = {}
    if df: where.append("d.doc_date >= %(df)s"); params["df"] = df
    if dt: where.append("d.doc_date <= %(dt)s"); params["dt"] = dt
    if sector_id: where.append("d.sector_id = %(sector_id)s"); params["sector_id"] = sector_id
    if doc_type_id: where.append("d.doc_type_id = %(doc_type_id)s"); params["doc_type_id"] = doc_type_id
    if priority: where.append("d.priority = %(priority)s"); params["priority"] = priority

    sql = f"""
      SELECT u.code AS unit, COUNT(*) AS cnt
      FROM documents d
      JOIN units u ON u.unit_id = d.unit_id
      WHERE {" AND ".join(where)}
      GROUP BY u.code
      ORDER BY u.code;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"rows": rows}

@app.get("/api/documents")
def documents(
    date_from: str | None = None,
    date_to: str | None = None,
    unit_id: int | None = None,
    sector_id: int | None = None,
    doc_type_id: int | None = None,
    status: str | None = None,
    priority: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
):
    df = parse_dt(date_from)
    dt = parse_dt(date_to)

    where = ["1=1"]
    params = {"limit": limit}
    if df: where.append("d.doc_date >= %(df)s"); params["df"] = df
    if dt: where.append("d.doc_date <= %(dt)s"); params["dt"] = dt
    if unit_id: where.append("d.unit_id = %(unit_id)s"); params["unit_id"] = unit_id
    if sector_id: where.append("d.sector_id = %(sector_id)s"); params["sector_id"] = sector_id
    if doc_type_id: where.append("d.doc_type_id = %(doc_type_id)s"); params["doc_type_id"] = doc_type_id
    if status: where.append("d.status = %(status)s"); params["status"] = status
    if priority: where.append("d.priority = %(priority)s"); params["priority"] = priority

    sql = f"""
      SELECT
        d.doc_id, d.reg_number, d.title, d.doc_date,
        u.code AS unit, s.name AS sector, dt.code AS doc_type,
        d.status, d.priority, d.cycle_minutes
      FROM documents d
      JOIN units u ON u.unit_id = d.unit_id
      LEFT JOIN sectors s ON s.sector_id = d.sector_id
      JOIN doc_types dt ON dt.doc_type_id = d.doc_type_id
      WHERE {" AND ".join(where)}
      ORDER BY d.doc_date DESC
      LIMIT %(limit)s;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"rows": rows}

@app.get("/api/week_dynamics")
def week_dynamics(
    date_to: str | None = None,
    unit_id: int | None = None,
    sector_id: int | None = None,
    doc_type_id: int | None = None,
    status: str | None = None,
    priority: int | None = None,
):
    dt = parse_dt(date_to)
    end_day = (dt.date() if dt else datetime.now().date())
    start_day = end_day - timedelta(days=6)

    params = {"start_day": start_day, "end_day": end_day}

    filters = []
    if unit_id:
        filters.append("d.unit_id = %(unit_id)s"); params["unit_id"] = unit_id
    if sector_id:
        filters.append("d.sector_id = %(sector_id)s"); params["sector_id"] = sector_id
    if doc_type_id:
        filters.append("d.doc_type_id = %(doc_type_id)s"); params["doc_type_id"] = doc_type_id
    if status:
        filters.append("d.status = %(status)s"); params["status"] = status
    if priority:
        filters.append("d.priority = %(priority)s"); params["priority"] = priority

    where_extra = (" AND " + " AND ".join(filters)) if filters else ""

    sql_cycle = f"""
    WITH days AS (
      SELECT generate_series(%(start_day)s::date, %(end_day)s::date, interval '1 day')::date AS day
    ),
    agg AS (
      SELECT
        d.doc_date::date AS day,
        COUNT(*) AS total_docs,
        ROUND(AVG(d.cycle_minutes)::numeric, 1) AS avg_cycle_minutes
      FROM documents d
      WHERE d.doc_date::date BETWEEN %(start_day)s AND %(end_day)s
      {where_extra}
      GROUP BY d.doc_date::date
    )
    SELECT
      days.day,
      COALESCE(agg.total_docs, 0) AS total_docs,
      agg.avg_cycle_minutes
    FROM days
    LEFT JOIN agg USING (day)
    ORDER BY days.day;
    """

    sql_flow = f"""
    WITH days AS (
      SELECT generate_series(%(start_day)s::date, %(end_day)s::date, interval '1 day')::date AS day
    ),
    rec AS (
      SELECT d.received_at::date AS day, COUNT(*) AS received_cnt
      FROM documents d
      WHERE d.received_at::date BETWEEN %(start_day)s AND %(end_day)s
      {where_extra}
      GROUP BY d.received_at::date
    ),
    proc AS (
      SELECT d.processed_at::date AS day, COUNT(*) AS processed_cnt
      FROM documents d
      WHERE d.processed_at IS NOT NULL
        AND d.processed_at::date BETWEEN %(start_day)s AND %(end_day)s
      {where_extra}
      GROUP BY d.processed_at::date
    ),
    delv AS (
      SELECT d.delivered_at::date AS day, COUNT(*) AS delivered_cnt
      FROM documents d
      WHERE d.delivered_at IS NOT NULL
        AND d.delivered_at::date BETWEEN %(start_day)s AND %(end_day)s
      {where_extra}
      GROUP BY d.delivered_at::date
    )
    SELECT
      days.day,
      COALESCE(rec.received_cnt, 0)  AS received,
      COALESCE(proc.processed_cnt, 0) AS processed,
      COALESCE(delv.delivered_cnt, 0) AS delivered
    FROM days
    LEFT JOIN rec  USING (day)
    LEFT JOIN proc USING (day)
    LEFT JOIN delv USING (day)
    ORDER BY days.day;
    """

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql_cycle, params)
        cycle_rows = cur.fetchall()
        cur.execute(sql_flow, params)
        flow_rows = cur.fetchall()

    return {
        "range": {"start": str(start_day), "end": str(end_day)},
        "cycle": cycle_rows,
        "flow": flow_rows,
    }

# -------------------------
# CONTROL BOARD (регламент)
# -------------------------
@app.get("/api/control_board")
def control_board():
    tc = get_time_control()
    astro = tc["astro_time"]
    op_day_start = tc["op_day_start"]
    mode = tc["mode"]
    op_date_val = compute_op_date(astro, op_day_start) if mode == "auto" else tc["op_date"]

    # оперативний "зараз"
    op_now = compute_op_now(astro, op_date_val)

    with get_conn() as conn, conn.cursor() as cur:
        # schedule
        cur.execute("""
            SELECT schedule_id, doc_type_code, due_time, tolerance_min, is_event_driven, event_type, sla_minutes, note
            FROM doc_schedule
            WHERE is_active=TRUE
            ORDER BY is_event_driven ASC, doc_type_code ASC, due_time ASC NULLS LAST;
        """)
        sched = cur.fetchall()

        results = []
        counters = {"done": 0, "in_work": 0, "overdue": 0, "waiting": 0, "no_trigger": 0}

        # мапа code -> doc_type_id
        cur.execute("SELECT doc_type_id, code FROM doc_types;")
        type_map = {r["code"]: r["doc_type_id"] for r in cur.fetchall()}

        for s in sched:
            code = s["doc_type_code"]

            if s["is_event_driven"]:
                # ПзБД: тригер події
                et = s["event_type"]
                sla = s["sla_minutes"] or 60

                cur.execute("""
                    SELECT event_time
                    FROM events
                    WHERE op_date=%s AND event_type=%s
                    ORDER BY event_time DESC
                    LIMIT 1;
                """, (op_date_val, et))
                ev = cur.fetchone()

                if not ev:
                    counters["no_trigger"] += 1
                    results.append({
                        "doc": code,
                        "due": "подієво",
                        "status": "немає тригера",
                        "fact": None,
                        "deviation_min": None,
                        "detail": f"Очікується подія типу {et}"
                    })
                    continue

                ev_time = ev["event_time"]
                deadline = ev_time + timedelta(minutes=sla)

                # шукаємо доведений ПзБД після події в SLA
                dtid = type_map.get(code)
                if not dtid:
                    results.append({
                        "doc": code, "due": "подієво", "status": "помилка довідника", "fact": None,
                        "deviation_min": None, "detail": "doc_types не містить цей code"
                    })
                    continue

                cur.execute("""
                    SELECT delivered_at
                    FROM documents
                    WHERE doc_type_id=%s
                      AND delivered_at IS NOT NULL
                      AND delivered_at >= %s
                      AND delivered_at <= %s
                    ORDER BY delivered_at ASC
                    LIMIT 1;
                """, (dtid, ev_time, deadline))
                ok = cur.fetchone()

                if ok:
                    counters["done"] += 1
                    results.append({
                        "doc": code,
                        "due": f"SLA {sla} хв",
                        "status": "виконано",
                        "fact": ok["delivered_at"].strftime("%H:%M"),
                        "deviation_min": int((ok["delivered_at"] - deadline).total_seconds() // 60),
                        "detail": f"Тригер {et}: {ev_time.strftime('%H:%M')}, дедлайн: {deadline.strftime('%H:%M')}"
                    })
                else:
                    if astro >= deadline:
                        counters["overdue"] += 1
                        results.append({
                            "doc": code,
                            "due": f"SLA {sla} хв",
                            "status": "прострочено",
                            "fact": None,
                            "deviation_min": int((astro - deadline).total_seconds() // 60),
                            "detail": f"Тригер {et}: {ev_time.strftime('%H:%M')}, дедлайн: {deadline.strftime('%H:%M')}"
                        })
                    else:
                        counters["in_work"] += 1
                        results.append({
                            "doc": code,
                            "due": f"SLA {sla} хв",
                            "status": "очікується",
                            "fact": None,
                            "deviation_min": -int((deadline - astro).total_seconds() // 60),
                            "detail": f"Тригер {et}: {ev_time.strftime('%H:%M')}, дедлайн: {deadline.strftime('%H:%M')}"
                        })
                continue

            # Фіксовані контрольні точки
            due_t: time = s["due_time"]
            tol = int(s["tolerance_min"] or 10)
            due_dt = datetime.combine(op_date_val, due_t)
            due_dt_tol = due_dt + timedelta(minutes=tol)

            dtid = type_map.get(code)
            if not dtid:
                results.append({
                    "doc": code,
                    "due": due_t.strftime("%H:%M"),
                    "status": "помилка довідника",
                    "fact": None,
                    "deviation_min": None,
                    "detail": "doc_types не містить цей code"
                })
                continue

            # 1) виконано: є доведений до due+tol у межах оперативної доби
            cur.execute("""
                SELECT delivered_at
                FROM documents
                WHERE doc_type_id=%s
                  AND delivered_at IS NOT NULL
                  AND delivered_at::date=%s
                  AND delivered_at <= %s
                ORDER BY delivered_at DESC
                LIMIT 1;
            """, (dtid, op_date_val, due_dt_tol))
            done = cur.fetchone()

            if done:
                counters["done"] += 1
                dev = int((done["delivered_at"] - due_dt).total_seconds() // 60)
                results.append({
                    "doc": code,
                    "due": due_t.strftime("%H:%M"),
                    "status": "виконано",
                    "fact": done["delivered_at"].strftime("%H:%M"),
                    "deviation_min": dev,
                    "detail": f"Допуск: {tol} хв"
                })
                continue

            # 2) в роботі: є документ (отримано/в_роботі) у межах оп-доби
            cur.execute("""
                SELECT status, doc_date
                FROM documents
                WHERE doc_type_id=%s
                  AND doc_date::date=%s
                  AND status IN ('отримано','в_роботі')
                ORDER BY doc_date DESC
                LIMIT 1;
            """, (dtid, op_date_val))
            inw = cur.fetchone()

            if op_now <= due_dt_tol:
                if inw:
                    counters["in_work"] += 1
                    results.append({
                        "doc": code,
                        "due": due_t.strftime("%H:%M"),
                        "status": "в роботі",
                        "fact": None,
                        "deviation_min": -int((due_dt - op_now).total_seconds() // 60),
                        "detail": f"Залишилось до контрольної точки (оперативний час)"
                    })
                else:
                    counters["waiting"] += 1
                    results.append({
                        "doc": code,
                        "due": due_t.strftime("%H:%M"),
                        "status": "очікується",
                        "fact": None,
                        "deviation_min": -int((due_dt - op_now).total_seconds() // 60),
                        "detail": "Документ ще не зафіксовано"
                    })
            else:
                counters["overdue"] += 1
                results.append({
                    "doc": code,
                    "due": due_t.strftime("%H:%M"),
                    "status": "прострочено",
                    "fact": None,
                    "deviation_min": int((op_now - due_dt).total_seconds() // 60),
                    "detail": f"Перевищено контрольну точку (оперативний час), допуск {tol} хв"
                })

    return {
        "mode": mode,
        "astro_time": astro.isoformat(sep=" ", timespec="seconds"),
        "op_date": op_date_val.isoformat(),
        "op_time": op_now.strftime("%H:%M:%S"),
        "counters": counters,
        "items": results
    }
