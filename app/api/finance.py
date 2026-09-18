from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_user
from app.api.notifications import create_notification
from app.core.database import get_db
from app.core.investment_accrual import (
    preview_accrual,
    settle_accrual,
)

from app.models.collections import (
    User,
    Plan,
    Deposit,
    Investment,
    Withdrawal,
    Transaction,
)
from app.schemas.finance import (
    DepositIn,
    InvestmentIn,
    WithdrawalIn,
)


router = APIRouter()


def money(v):
    return Decimal(str(v))


def serialize_deposit(d: Deposit):
    return {
        "_id": str(d.id),
        "owner": str(d.owner),
        "amount": float(d.amount),
        "date": d.date.isoformat(),
        "verified": d.verified,
        "status": d.status,
        "type": d.type,
    }




def serialize_investment(i: Investment):
    state = preview_accrual(i)

    amount = money(i.amount)
    rate = money(i.rate)

    effective_roi = Decimal("0.00")

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

    return {
        "_id": str(i.id),
        "owner": str(i.owner),
        "amount": float(amount),
        "profit": float(
            money(i.profit)
        ),
        "rate": float(rate),
        "name": i.name,

        "date": (
            i.date.isoformat()
            if i.date
            else None
        ),

        "maturity_date": (
            i.maturity_date.isoformat()
            if i.maturity_date
            else None
        ),

        # Existing profit fields
        "additionalProfit": float(
            money(i.additional_profit)
        ),
        "baseProfit": float(
            state.base_profit
        ),
        "totalProfit": float(
            state.expected_profit
        ),
        "effectiveRoi": float(
            effective_roi
        ),

        # 6-hour accrual
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

        # Existing investment state
        "pausedAt": (
            i.paused_at.isoformat()
            if i.paused_at
            else None
        ),
        "totalPausedSeconds": (
            i.total_paused_seconds
        ),
        "withdrawaled": i.withdrawaled,
        "status": i.status,
    }



def serialize_withdrawal(w: Withdrawal):
    return {
        "_id": str(w.id),
        "owner": str(w.owner),
        "amount": float(w.amount),
        "date": w.date.isoformat(),
        "wallet": w.wallet,
        "coin": w.coin,
        "network": w.network,
        "status": w.status,
    }


def serialize_transaction(t: Transaction):
    return {
        "_id": str(t.id),
        "owner": str(t.owner),
        "amount": float(t.amount),
        "type": t.type,
        "status": t.status,
        "details": t.details,
        "date": t.date.isoformat(),
        "reference": t.reference,
    }


@router.post("/deposit")
async def create_deposit(
    data: DepositIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    amount = money(data.amount)

    deposit = Deposit(
        owner=user.id,
        amount=amount,
        date=datetime.now(timezone.utc),
        verified=False,
        status="pending",
        type="deposit",
    )

    db.add(deposit)
    await db.flush()

    transaction = Transaction(
        owner=user.id,
        amount=amount,
        type="deposit",
        status="pending",
        details="Deposit awaiting payment verification",
        date=datetime.now(timezone.utc),
        reference=f"deposit:{deposit.id}",
    )

    db.add(transaction)

    await create_notification(
        db=db,
        user_id=user.id,
        title="Deposit Submitted",
        message=(
            f"Your deposit of ${amount:.2f} has been submitted "
            "and is awaiting verification."
        ),
        notification_type="deposit",
    )

    await db.commit()
    await db.refresh(deposit)

    return {
        "status": "success",
        "msg": "Deposit created and awaiting verification",
        "depositId": str(deposit.id),
    }


@router.post("/new")
async def new_investment(
    data: InvestmentIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    amount = money(data.amount)

    if user.balance < amount:
        return {
            "status": "err",
            "msg": "Insufficient available balance",
        }

    result = await db.execute(
        select(Plan).where(
            func.lower(func.trim(Plan.name)) == func.lower(func.trim(data.name)),
            Plan.is_active.is_(True),
        )
    )

    plan = result.scalar_one_or_none()

    if not plan:
        return {
            "status": "err",
            "msg": "Investment plan not found",
        }

    if amount < plan.minimum or amount > plan.maximun:
        return {
            "status": "err",
            "msg": "Amount is outside this plan's limits",
        }

    investment_date = datetime.now(timezone.utc)

    duration_text = plan.w_date.lower().strip()

    try:
        value = int(duration_text.split()[0])
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=400,
            detail="Invalid investment plan duration",
        )

    if "day" in duration_text:
        days = value
    elif "month" in duration_text:
        days = value * 30
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid investment plan duration",
        )

    maturity_date = investment_date + timedelta(days=days)

    user.balance -= amount
    user.invest_balance += amount

    investment = Investment(
        owner=user.id,
        amount=amount,
        profit=Decimal("0"),
        rate=plan.percentage,
        name=plan.name,
        date=investment_date,
        maturity_date=maturity_date,
        withdrawaled=False,
        status="Active",
    )

    db.add(investment)
    await db.flush()

    transaction = Transaction(
        owner=user.id,
        amount=amount,
        type="investment",
        status="completed",
        details=f"Investment in {plan.name}",
        date=investment_date,
        reference=f"investment:{investment.id}",
    )

    db.add(transaction)

    await create_notification(
        db=db,
        user_id=user.id,
        title="Investment Created",
        message=(
            f"Your investment of ${amount:.2f} in {plan.name} "
            "has been created successfully."
        ),
        notification_type="investment",
    )

    await db.commit()
    await db.refresh(investment)

    return {
        "status": "success",
        "msg": "Investment created successfully",
        "investmentId": str(investment.id),
    }


@router.post("/myInvestments")
async def my_investments(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Investment)
        .where(Investment.owner == user.id)
        .order_by(Investment.date.desc())
    )

    items = [
        serialize_investment(item)
        for item in result.scalars().all()
    ]

    return {
        "status": "success",
        "investments": items,
    }



@router.post("/claimInvestment/{investment_id}")
async def claim_investment(
    investment_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        investment_id_int = int(investment_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid investment ID",
        )

    result = await db.execute(
        select(Investment).where(
            Investment.id == investment_id_int,
            Investment.owner == user.id,
        )
    )

    investment = result.scalar_one_or_none()

    if not investment:
        raise HTTPException(
            status_code=404,
            detail="Investment not found",
        )

    if investment.withdrawaled:
        return {
            "status": "err",
            "msg": "Investment has already been claimed",
        }

    if investment.status.lower() == "paused":
        return {
            "status": "err",
            "msg": "Investment is currently paused",
        }

    if investment.maturity_date is None:
        return {
            "status": "err",
            "msg": "Investment maturity date is not set",
        }

    now = datetime.now(timezone.utc)

    if now < investment.maturity_date:
        return {
            "status": "err",
            "msg": "Investment has not matured yet",
            "maturityDate": investment.maturity_date.isoformat(),
        }

    # Finalize the accrual at maturity.
    state = settle_accrual(
        investment,
        now,
    )

    principal = money(
        investment.amount
    )

    profit = money(
        state.expected_profit
    )

    total = (
        principal + profit
    ).quantize(
        Decimal("0.01")
    )

    investment.profit = profit
    investment.withdrawaled = True
    investment.status = "Completed"

    user.balance += total
    user.invest_balance -= principal
    user.profit += profit

    transaction = Transaction(
        owner=user.id,
        amount=total,
        type="investment_profit",
        status="completed",
        details=(
            f"Investment #{investment.id} matured"
        ),
        date=now,
        reference=(
            f"investment_profit:{investment.id}"
        ),
    )

    db.add(transaction)

    await create_notification(
        db=db,
        user_id=user.id,
        title="Investment Completed",
        message=(
            f"Your investment in {investment.name} "
            f"has matured. You received "
            f"${total:.2f}, including "
            f"${profit:.2f} profit."
        ),
        notification_type="investment",
    )

    await db.commit()
    await db.refresh(investment)
    await db.refresh(user)

    return {
        "status": "success",
        "msg": "Investment claimed successfully",
        "investmentId": str(investment.id),
        "principal": float(principal),
        "profit": float(profit),
        "total": float(total),
    }






@router.post("/myDeposits")
async def my_deposits(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deposit)
        .where(Deposit.owner == user.id)
        .order_by(Deposit.date.desc())
    )

    items = [
        serialize_deposit(item)
        for item in result.scalars().all()
    ]

    return {
        "status": "success",
        "deposits": items,
    }


@router.post("/myWithdrawals")
async def my_withdrawals(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Withdrawal)
        .where(Withdrawal.owner == user.id)
        .order_by(Withdrawal.date.desc())
    )

    items = [
        serialize_withdrawal(item)
        for item in result.scalars().all()
    ]

    return {
        "status": "success",
        "withdrawals": items,
    }


@router.post("/withdraw")
async def withdraw(
    data: WithdrawalIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    amount = money(data.amount)

    if amount <= 0:
        raise HTTPException(
            status_code=422,
            detail="Amount must be positive",
        )

    if user.balance < amount:
        return {
            "status": "err",
            "msg": "Insufficient balance",
        }

    user.balance -= amount
    user.withdraw_balance += amount

    withdrawal = Withdrawal(
        owner=user.id,
        amount=amount,
        date=datetime.now(timezone.utc),
        wallet=data.address,
        coin=data.coin.upper().strip(),
        network=data.network.strip(),
        status="pending",
    )

    db.add(withdrawal)
    await db.flush()

    transaction = Transaction(
        owner=user.id,
        amount=amount,
        type="withdrawal",
        status="pending",
        details=(
            f"{data.coin.upper().strip()} "
            f"({data.network.strip()}) withdrawal "
            f"to {data.address}"
        ),
        date=datetime.now(timezone.utc),
        reference=f"withdrawal:{withdrawal.id}",
    )

    db.add(transaction)

    await create_notification(
        db=db,
        user_id=user.id,
        title="Withdrawal Submitted",
        message=(
            f"Your withdrawal request of ${amount:.2f} "
            f"in {data.coin.upper().strip()} "
            f"({data.network.strip()}) has been submitted "
            "for processing."
        ),
        notification_type="withdrawal",
    )

    await db.commit()
    await db.refresh(withdrawal)

    return {
        "status": "success",
        "msg": "Withdrawal submitted for processing",
        "withdrawalId": str(withdrawal.id),
    }
