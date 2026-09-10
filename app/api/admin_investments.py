from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import admin_user
from app.core.database import get_db
from app.models.collections import (
    Investment,
    User,
    InvestmentAdminAction,
)
from app.schemas.admin_investment_controls import (
    InvestmentROIAdjustmentIn,
    InvestmentPauseIn,
    InvestmentResumeIn,
)


router = APIRouter(
    prefix="/api/v1/admin/investments",
    tags=["Admin Investments"],
)


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def serialize_admin_investment(
    investment: Investment,
    user: User | None = None,
) -> dict:
    amount = money(investment.amount)
    rate = money(investment.rate)

    base_profit = (
        amount * rate / Decimal("100")
    ).quantize(Decimal("0.01"))

    additional_profit = money(
        investment.additional_profit
    )

    total_profit = (
        base_profit + additional_profit
    ).quantize(Decimal("0.01"))

    effective_roi = Decimal("0")

    if amount > 0:
        effective_roi = (
            total_profit / amount * Decimal("100")
        ).quantize(Decimal("0.01"))

    result = {
        "_id": str(investment.id),
        "owner": str(investment.owner),
        "amount": float(amount),
        "rate": float(rate),
        "baseProfit": float(base_profit),
        "additionalProfit": float(additional_profit),
        "totalProfit": float(total_profit),
        "effectiveRoi": float(effective_roi),
        "name": investment.name.strip() if investment.name else investment.name,
        "date": (
            investment.date.isoformat()
            if investment.date else None
        ),
        "maturityDate": (
            investment.maturity_date.isoformat()
            if investment.maturity_date else None
        ),
        "pausedAt": (
            investment.paused_at.isoformat()
            if investment.paused_at else None
        ),
        "totalPausedSeconds": investment.total_paused_seconds,
        "withdrawaled": investment.withdrawaled,
        "status": investment.status,
    }

    if user:
        result["user"] = {
            "_id": str(user.id),
            "email": user.email,
            "f_name": user.f_name,
            "l_name": user.l_name,
        }

    return result


async def get_investment_or_404(
    investment_id: int,
    db: AsyncSession,
) -> Investment:
    result = await db.execute(
        select(Investment).where(
            Investment.id == investment_id
        )
    )

    investment = result.scalar_one_or_none()

    if not investment:
        raise HTTPException(
            status_code=404,
            detail="Investment not found",
        )

    return investment


@router.get("")
async def admin_investments(
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Investment)
        .order_by(Investment.date.desc())
    )

    investments = []

    for investment in result.scalars().all():
        user_result = await db.execute(
            select(User).where(User.id == investment.owner)
        )

        user = user_result.scalar_one_or_none()

        investments.append(
            serialize_admin_investment(
                investment,
                user,
            )
        )

    return {
        "status": "success",
        "investments": investments,
    }


@router.get("/{investment_id}")
async def admin_investment_detail(
    investment_id: int,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    investment = await get_investment_or_404(
        investment_id,
        db,
    )

    user_result = await db.execute(
        select(User).where(User.id == investment.owner)
    )

    user = user_result.scalar_one_or_none()

    return {
        "status": "success",
        "investment": serialize_admin_investment(
            investment,
            user,
        ),
    }


@router.post("/{investment_id}/roi-adjustment")
async def adjust_investment_roi(
    investment_id: int,
    body: InvestmentROIAdjustmentIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    investment = await get_investment_or_404(
        investment_id,
        db,
    )

    if investment.withdrawaled:
        raise HTTPException(
            status_code=400,
            detail="Investment has already been claimed",
        )

    adjustment = money(body.amount)

    if adjustment == 0:
        raise HTTPException(
            status_code=422,
            detail="Adjustment amount cannot be zero",
        )

    current_additional = money(
        investment.additional_profit
    )

    new_additional = (
        current_additional + adjustment
    ).quantize(Decimal("0.01"))

    base_profit = (
        money(investment.amount)
        * money(investment.rate)
        / Decimal("100")
    ).quantize(Decimal("0.01"))

    if base_profit + new_additional < 0:
        raise HTTPException(
            status_code=400,
            detail="Adjustment would make total profit negative",
        )

    investment.additional_profit = new_additional

    audit = InvestmentAdminAction(
        investment_id=investment.id,
        admin_id=admin.id,
        action="roi_adjustment",
        amount=adjustment,
        previous_value=current_additional,
        new_value=new_additional,
        reason=body.reason,
        created_at=datetime.now(timezone.utc),
    )

    db.add(audit)

    await db.commit()
    await db.refresh(investment)

    updated = serialize_admin_investment(investment)

    return {
        "status": "success",
        "msg": "Investment ROI adjustment applied",
        "investment": updated,
        "reason": body.reason,
    }


@router.post("/{investment_id}/pause")
async def pause_investment(
    investment_id: int,
    body: InvestmentPauseIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    investment = await get_investment_or_404(
        investment_id,
        db,
    )

    if investment.withdrawaled:
        raise HTTPException(
            status_code=400,
            detail="Investment has already been claimed",
        )

    if investment.status.lower() != "active":
        raise HTTPException(
            status_code=400,
            detail="Only active investments can be paused",
        )

    now = datetime.now(timezone.utc)

    investment.status = "Paused"
    investment.paused_at = now

    audit = InvestmentAdminAction(
        investment_id=investment.id,
        admin_id=admin.id,
        action="pause",
        previous_value=None,
        new_value=None,
        reason=body.reason,
        created_at=now,
    )

    db.add(audit)

    await db.commit()
    await db.refresh(investment)

    return {
        "status": "success",
        "msg": "Investment paused successfully",
        "investment": serialize_admin_investment(investment),
        "reason": body.reason,
    }


@router.post("/{investment_id}/resume")
async def resume_investment(
    investment_id: int,
    body: InvestmentResumeIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    investment = await get_investment_or_404(
        investment_id,
        db,
    )

    if investment.withdrawaled:
        raise HTTPException(
            status_code=400,
            detail="Investment has already been claimed",
        )

    if investment.status.lower() != "paused":
        raise HTTPException(
            status_code=400,
            detail="Only paused investments can be resumed",
        )

    if investment.paused_at is None:
        raise HTTPException(
            status_code=400,
            detail="Investment pause timestamp is missing",
        )

    now = datetime.now(timezone.utc)

    paused_seconds = max(
        0,
        int(
            (
                now - investment.paused_at
            ).total_seconds()
        ),
    )

    investment.total_paused_seconds += paused_seconds

    if investment.maturity_date is not None:
        investment.maturity_date += timedelta(
            seconds=paused_seconds
        )

    investment.paused_at = None
    investment.status = "Active"

    audit = InvestmentAdminAction(
        investment_id=investment.id,
        admin_id=admin.id,
        action="resume",
        amount=Decimal(paused_seconds),
        previous_value=None,
        new_value=None,
        reason=body.reason,
        created_at=now,
    )

    db.add(audit)

    await db.commit()
    await db.refresh(investment)

    return {
        "status": "success",
        "msg": "Investment resumed",
        "investment": serialize_admin_investment(investment),
        "pausedSeconds": paused_seconds,
        "reason": body.reason,
    }
