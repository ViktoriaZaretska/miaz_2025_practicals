import os
from datetime import datetime, date
from typing import Optional, List, Dict, Tuple
from random import random

from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import (
    create_engine,
    Column,
    BigInteger,
    Text,
    Boolean,
    Numeric,
    DateTime,
    func,
    select,
    and_,
)
from sqlalchemy.orm import declarative_base, Session

# ----------------- ENV / DB -----------------
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing in .env")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
Base = declarative_base()

# ----------------- ORM Model -----------------
class ResourceAllocation(Base):
    __tablename__ = "resource_allocations"
    __table_args__ = {"schema": "public"}

    id = Column(BigInteger, primary_key=True, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)

    direction = Column(Text, nullable=False)
    resource_type = Column(Text, nullable=False)
    unit = Column(Text, nullable=False)
    allocation_reason = Column(Text, nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    duration_days = Column(Numeric(10, 2), nullable=False)

    source = Column(Text, nullable=False)
    confirmed = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)

# ----------------- Schemas -----------------
class AllocationOut(BaseModel):
    id: int
    occurred_at: datetime
    direction: str
    resource_type: str
    unit: str
    allocation_reason: str
    amount: float
    duration_days: float
    source: str
    confirmed: bool
    notes: Optional[str] = None

    class Config:
        from_attributes = True

class AllocationsPage(BaseModel):
    items: List[AllocationOut]
    total: int
    limit: int
    offset: int

class KPIOut(BaseModel):
    events_count: int
    amount_sum: float
    duration_avg: float
    top_resource_type: Optional[str] = None

class TrendPoint(BaseModel):
    bucket_start: date
    events_count: int
    amount_sum: float

class DistributionPoint(BaseModel):
    category: str
    events_count: int
    amount_sum: float

class HeatmapOut(BaseModel):
    resource_types: List[str]
    weeks: List[str]
    matrix: List[List[float]]  # metric per [resource_type][week]

class MapPoint(BaseModel):
    id: int
    occurred_at: datetime
    direction: str
    resource_type: str
    unit: str
    amount: float
    confirmed: bool
    lat: float
    lon: float

# ----------------- App -----------------
app = FastAPI(title="Resource Allocations API", version="1.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Helpers -----------------
def build_filters(
    start: Optional[datetime],
    end: Optional[datetime],
    direction: Optional[str],
    resource_type: Optional[str],
    unit: Optional[str],
    min_value: Optional[float],
    confirmed: Optional[bool],
):
    f = []
    if start:
        f.append(ResourceAllocation.occurred_at >= start)
    if end:
        f.append(ResourceAllocation.occurred_at <= end)
    if direction:
        f.append(ResourceAllocation.direction == direction)
    if resource_type:
        f.append(ResourceAllocation.resource_type == resource_type)
    if unit:
        f.append(ResourceAllocation.unit == unit)
    if min_value is not None:
        f.append(ResourceAllocation.duration_days >= min_value)
    if confirmed is not None:
        f.append(ResourceAllocation.confirmed == confirmed)
    return f

def metric_expr(metric: str):
    if metric == "events_count":
        return func.count(ResourceAllocation.id)
    # default: amount_sum
    return func.coalesce(func.sum(ResourceAllocation.amount), 0)

# “базові” координати по напрямках (для демо на OSM)
DIRECTION_COORDS = {
    "Північ": (51.50, 31.30),
    "Південь": (46.48, 30.73),
    "Схід": (48.45, 35.05),
    "Захід": (49.84, 24.03),
    "Центр": (48.51, 32.26),
}

# ----------------- Endpoints -----------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/allocations", response_model=AllocationsPage)
def list_allocations(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),

    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    direction: Optional[str] = None,
    resource_type: Optional[str] = None,
    unit: Optional[str] = None,
    min_value: Optional[float] = Query(None, description="Min duration_days"),
    confirmed: Optional[bool] = None,
):
    filters = build_filters(start, end, direction, resource_type, unit, min_value, confirmed)

    with Session(engine) as db:
        total_q = select(func.count(ResourceAllocation.id))
        if filters:
            total_q = total_q.where(and_(*filters))
        total = db.execute(total_q).scalar_one()

        q = select(ResourceAllocation).order_by(ResourceAllocation.occurred_at.desc())
        if filters:
            q = q.where(and_(*filters))
        q = q.limit(limit).offset(offset)

        items = db.execute(q).scalars().all()
        return {"items": items, "total": int(total), "limit": limit, "offset": offset}

@app.get("/allocations/{alloc_id}", response_model=AllocationOut)
def get_allocation(alloc_id: int):
    with Session(engine) as db:
        row = db.get(ResourceAllocation, alloc_id)
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return row

@app.get("/kpi", response_model=KPIOut)
def kpi(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    direction: Optional[str] = None,
    resource_type: Optional[str] = None,
    unit: Optional[str] = None,
    min_value: Optional[float] = None,
    confirmed: Optional[bool] = None,
):
    filters = build_filters(start, end, direction, resource_type, unit, min_value, confirmed)

    with Session(engine) as db:
        q = select(
            func.count(ResourceAllocation.id),
            func.coalesce(func.sum(ResourceAllocation.amount), 0),
            func.coalesce(func.avg(ResourceAllocation.duration_days), 0),
        )
        if filters:
            q = q.where(and_(*filters))
        events_count, amount_sum, duration_avg = db.execute(q).one()

        top_q = select(ResourceAllocation.resource_type, func.count().label("cnt"))
        if filters:
            top_q = top_q.where(and_(*filters))
        top_q = top_q.group_by(ResourceAllocation.resource_type).order_by(func.count().desc()).limit(1)
        top = db.execute(top_q).first()
        top_resource_type = top[0] if top else None

        return {
            "events_count": int(events_count),
            "amount_sum": float(amount_sum or 0),
            "duration_avg": float(duration_avg or 0),
            "top_resource_type": top_resource_type,
        }

@app.get("/trend", response_model=List[TrendPoint])
def trend(
    bucket: str = Query("day", pattern="^(day|week)$"),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    direction: Optional[str] = None,
    resource_type: Optional[str] = None,
    unit: Optional[str] = None,
    min_value: Optional[float] = None,
    confirmed: Optional[bool] = None,
):
    filters = build_filters(start, end, direction, resource_type, unit, min_value, confirmed)
    trunc = "day" if bucket == "day" else "week"

    with Session(engine) as db:
        q = select(
            func.date_trunc(trunc, ResourceAllocation.occurred_at).label("b"),
            func.count(ResourceAllocation.id),
            func.coalesce(func.sum(ResourceAllocation.amount), 0),
        )
        if filters:
            q = q.where(and_(*filters))
        q = q.group_by("b").order_by("b")

        rows = db.execute(q).all()
        return [
            {"bucket_start": b.date(), "events_count": int(c), "amount_sum": float(s or 0)}
            for b, c, s in rows
        ]

@app.get("/distribution/direction", response_model=List[DistributionPoint])
def distribution_direction(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    resource_type: Optional[str] = None,
    unit: Optional[str] = None,
    min_value: Optional[float] = None,
    confirmed: Optional[bool] = None,
):
    filters = build_filters(start, end, None, resource_type, unit, min_value, confirmed)

    with Session(engine) as db:
        q = select(
            ResourceAllocation.direction,
            func.count(ResourceAllocation.id),
            func.coalesce(func.sum(ResourceAllocation.amount), 0),
        )
        if filters:
            q = q.where(and_(*filters))
        q = q.group_by(ResourceAllocation.direction).order_by(func.count().desc())

        rows = db.execute(q).all()
        return [{"category": d, "events_count": int(c), "amount_sum": float(s or 0)} for d, c, s in rows]

@app.get("/distribution/unit", response_model=List[DistributionPoint])
def distribution_unit(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    direction: Optional[str] = None,
    resource_type: Optional[str] = None,
    min_value: Optional[float] = None,
    confirmed: Optional[bool] = None,
):
    filters = build_filters(start, end, direction, resource_type, None, min_value, confirmed)

    with Session(engine) as db:
        q = select(
            ResourceAllocation.unit,
            func.count(ResourceAllocation.id),
            func.coalesce(func.sum(ResourceAllocation.amount), 0),
        )
        if filters:
            q = q.where(and_(*filters))
        q = q.group_by(ResourceAllocation.unit).order_by(func.count().desc())

        rows = db.execute(q).all()
        return [{"category": u, "events_count": int(c), "amount_sum": float(s or 0)} for u, c, s in rows]

@app.get("/heatmap", response_model=HeatmapOut)
def heatmap(
    metric: str = Query("amount_sum", pattern="^(amount_sum|events_count)$"),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    direction: Optional[str] = None,
    unit: Optional[str] = None,
    min_value: Optional[float] = None,
    confirmed: Optional[bool] = None,
):
    filters = build_filters(start, end, direction, None, unit, min_value, confirmed)

    with Session(engine) as db:
        # axis 1: resource_types
        resource_types = db.execute(
            select(ResourceAllocation.resource_type)
            .distinct()
            .order_by(ResourceAllocation.resource_type)
        ).scalars().all()

        # axis 2: ISO weeks (sorted)
        weeks = db.execute(
            select(
                func.to_char(func.date_trunc("week", ResourceAllocation.occurred_at), "IYYY-IW").label("wk")
            )
            .group_by("wk")
            .order_by("wk")
        ).scalars().all()

        if not resource_types or not weeks:
            return {"resource_types": [], "weeks": [], "matrix": []}

        val = metric_expr(metric)

        q = select(
            ResourceAllocation.resource_type,
            func.to_char(func.date_trunc("week", ResourceAllocation.occurred_at), "IYYY-IW").label("wk"),
            val.label("v"),
        )
        if filters:
            q = q.where(and_(*filters))

        q = q.group_by(ResourceAllocation.resource_type, "wk")

        rows = db.execute(q).all()
        lookup: Dict[Tuple[str, str], float] = {(rt, wk): float(v or 0) for rt, wk, v in rows}

        matrix = []
        for rt in resource_types:
            matrix.append([float(lookup.get((rt, wk), 0.0)) for wk in weeks])

        return {"resource_types": resource_types, "weeks": weeks, "matrix": matrix}

@app.get("/map_points", response_model=List[MapPoint])
def map_points(
    limit: int = Query(200, ge=1, le=2000),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    direction: Optional[str] = None,
    resource_type: Optional[str] = None,
    unit: Optional[str] = None,
    min_value: Optional[float] = None,
    confirmed: Optional[bool] = None,
):
    filters = build_filters(start, end, direction, resource_type, unit, min_value, confirmed)

    with Session(engine) as db:
        q = select(ResourceAllocation).order_by(ResourceAllocation.occurred_at.desc())
        if filters:
            q = q.where(and_(*filters))
        q = q.limit(limit)

        rows = db.execute(q).scalars().all()
        out: List[Dict] = []

        for r in rows:
            base = DIRECTION_COORDS.get(r.direction, (48.38, 31.16))  # fallback
            # невеликий "джитер", щоб точки не накладались
            lat = base[0] + (random() - 0.5) * 0.25
            lon = base[1] + (random() - 0.5) * 0.35

            out.append({
                "id": int(r.id),
                "occurred_at": r.occurred_at,
                "direction": r.direction,
                "resource_type": r.resource_type,
                "unit": r.unit,
                "amount": float(r.amount),
                "confirmed": bool(r.confirmed),
                "lat": float(lat),
                "lon": float(lon),
            })

        return out
