from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.investment_accrual import (
    preview_accrual,
    settle_accrual,
)

from app.api.dependencies import admin_user
from app.core.admin_audit import record_admin_action
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
    state = preview_accrual(investment)

    amount = money(investment.amount)
    rate = money(investment.rate)

    effective_roi = Decimal("0")

    if amount > 0:
        effective_roi = (
            state.expected_profit
            / amount
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    remaining_periods = max(
        0,
        state.total_periods - state.completed_periods,
    )

    remaining_profit = max(
        Decimal("0.00"),
        state.expected_profit - state.accrued_profit,
    )

    accrual_per_period = Decimal("0.00")

    if remaining_periods > 0:
        accrual_per_period = (
            remaining_profit
            / Decimal(remaining_periods)
        ).quantize(Decimal("0.01"))

    result = {
        "_id": str(investment.id),
        "owner": str(investment.owner),
        "amount": float(amount),
        "rate": float(rate),

        "baseProfit": float(state.base_profit),
        "additionalProfit": float(
            money(investment.additional_profit)
        ),
        "totalProfit": float(
            state.expected_profit
        ),
        "effectiveRoi": float(effective_roi),

        # 6-hour accumulation
        "accruedProfit": float(
            state.accrued_profit
        ),
        "withdrawableProfit": float(
            state.withdrawable_profit
        ),
        "withdrawableAmount": float(
            state.withdrawable_amount
        ),
        "completedAccrualPeriods": (
            state.completed_periods
        ),
        "totalAccrualPeriods": (
            state.total_periods
        ),
        "accrualIntervalHours": 6,
        "accrualPerPeriod": float(
            accrual_per_period
        ),
        "nextAccrualAt": (
            state.next_accrual_at.isoformat()
            if state.next_accrual_at
            else None
        ),

        "name": (
            investment.name.strip()
            if investment.name
            else investment.name
        ),
        "date": (
            investment.date.isoformat()
            if investment.date
            else None
        ),
        "maturityDate": (
            investment.maturity_date.isoformat()
            if investment.maturity_date
            else None
        ),
        "pausedAt": (
            investment.paused_at.isoformat()
            if investment.paused_at
            else None
        ),
        "totalPausedSeconds": (
            investment.total_paused_seconds
        ),
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

    now = datetime.now(timezone.utc)

    # Lock in everything that has already accumulated
    # before changing the expected final profit.
    accrual_state = settle_accrual(
        investment,
        now,
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

    new_expected_profit = (
        base_profit + new_additional
    ).quantize(Decimal("0.01"))

    # Never allow the expected final profit to be reduced
    # below the profit that has already accumulated.
    if new_expected_profit < accrual_state.accrued_profit:
        await db.rollback()

        raise HTTPException(
            status_code=400,
            detail=(
                "Adjustment would reduce expected profit "
                "below already accumulated profit"
            ),
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
        created_at=now,
    )

    db.add(audit)

    record_admin_action(db, admin, "investment.roi_adjusted", details={"investment_id": investment.id, "adjustment": str(adjustment), "previous_additional_profit": str(current_additional), "new_additional_profit": str(new_additional), "reason": body.reason})
    await db.commit()
    await db.refresh(investment)

    updated = serialize_admin_investment(
        investment
    )

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

    # Settle all completed 6-hour accrual periods
    # before starting the pause.
    settle_accrual(
        investment,
        now,
    )

    # Pause begins after the accrual checkpoint.
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

    record_admin_action(db, admin, "investment.paused", details={"investment_id": investment.id, "reason": body.reason})
    await db.commit()
    await db.refresh(investment)

    return {
        "status": "success",
        "msg": "Investment paused successfully",
        "investment": serialize_admin_investment(
            investment
        ),
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

    # Persist any completed 6-hour accrual periods
    # reached before the investment is resumed.
    settle_accrual(
        investment,
        now,
    )

    paused_seconds = max(
        0,
        int(
            (
                now - investment.paused_at
            ).total_seconds()
        ),
    )

    # Add the paused time to the investment's
    # total paused duration.
    investment.total_paused_seconds += paused_seconds

    # Extend maturity by exactly the time the
    # investment was paused.
    if investment.maturity_date is not None:
        investment.maturity_date += timedelta(
            seconds=paused_seconds
        )

    # Resume the investment.
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

    record_admin_action(db, admin, "investment.resumed", details={"investment_id": investment.id, "paused_seconds": paused_seconds, "reason": body.reason})
    await db.commit()
    await db.refresh(investment)

    return {
        "status": "success",
        "msg": "Investment resumed",
        "investment": serialize_admin_investment(
            investment
        ),
        "pausedSeconds": paused_seconds,
        "reason": body.reason,
    }
