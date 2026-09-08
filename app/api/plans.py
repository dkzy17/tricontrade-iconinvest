from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import admin_user
from app.core.database import get_db
from app.models.collections import Plan
from app.schemas.finance import PlanIn


router = APIRouter()


def public_plan(plan: Plan):
    return {
        "_id": str(plan.id),
        "name": plan.name,
        "minimum": float(plan.minimum),
        "maximun": float(plan.maximun),
        "percentage": float(plan.percentage),
        "wDate": plan.w_date,
        "isActive": plan.is_active,
        "createdAt": plan.created_at,
        "updatedAt": plan.updated_at,
    }


@router.get("/")
async def get_plans(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Plan)
        .where(Plan.is_active == True)
        .order_by(Plan.created_at.asc())
    )

    plans = result.scalars().all()

    return {
        "status": "success",
        "plans": [public_plan(plan) for plan in plans],
    }


@router.post("/admin/all")
async def all_plans(
    _: dict | None = None,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Plan).order_by(Plan.created_at.asc())
    )

    plans = result.scalars().all()

    return {
        "status": "success",
        "plans": [public_plan(plan) for plan in plans],
    }


@router.post("/admin/create")
async def create_plan(
    data: PlanIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    existing_result = await db.execute(
        select(Plan).where(Plan.name == data.name)
    )

    existing = existing_result.scalar_one_or_none()

    if existing:
        return {
            "status": "err",
            "msg": "Plan already exists",
        }

    now = datetime.now(timezone.utc)

    plan = Plan(
        name=data.name,
        minimum=Decimal(str(data.minimum)),
        maximun=Decimal(str(data.maximun)),
        percentage=Decimal(str(data.percentage)),
        w_date=data.duration,
        is_active=data.active,
        created_at=now,
        updated_at=now,
    )

    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    return {
        "status": "success",
        "id": str(plan.id),
        "plan": public_plan(plan),
    }


@router.post("/admin/update/{plan_id}")
async def update_plan(
    plan_id: int,
    data: PlanIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )

    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Plan not found",
        )

    plan.name = data.name
    plan.minimum = Decimal(str(data.minimum))
    plan.maximun = Decimal(str(data.maximun))
    plan.percentage = Decimal(str(data.percentage))
    plan.w_date = data.duration
    plan.is_active = data.active
    plan.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(plan)

    return {
        "status": "success",
        "msg": "Plan updated",
        "plan": public_plan(plan),
    }


@router.post("/admin/delete/{plan_id}")
async def delete_plan(
    plan_id: int,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )

    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Plan not found",
        )

    await db.delete(plan)
    await db.commit()

    return {
        "status": "success",
        "msg": "Plan deleted",
    }