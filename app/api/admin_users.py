from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import admin_user
from app.api.notifications import create_notification
from app.core.database import get_db
from app.models.collections import (
    Deposit,
    User,
    Withdrawal,
    Transaction,
    Plan,
    Investment,
)
from app.schemas.admin_finance import AdminMoneyAdjustmentIn
from app.schemas.admin_investment import AdminInvestmentIn
from app.schemas.admin_users import (
    # Admin finance schema is imported separately below
    BalanceIn,
    RoleIn,
    SuspendUserIn,
    VerifyUserIn,
)


router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["Admin Users"],
)


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "_id": str(user.id),
        "email": user.email,
        "f_name": user.f_name,
        "l_name": user.l_name,
        "country": user.country,
        "phone": user.phone,
        "balance": float(user.balance),
        "profit": float(user.profit),
        "depositBalance": float(user.deposit_balance),
        "referralBalance": float(user.referral_balance),
        "withdrawBalance": float(user.withdraw_balance),
        "investBalance": float(user.invest_balance),
        "currency": user.currency,
        "verified": user.verified,
        "suspended": user.suspended,
        "role": user.role,
        "referralId": user.referral_id,
        "referrerId": user.referrer_id,
        "created": user.join_date.isoformat(),
    }


async def get_user_or_404(
    user_id: int,
    db: AsyncSession,
) -> User:
    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return user


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_or_404(user_id, db)

    return {
        "user": user_to_dict(user),
    }


@router.get("/{user_id}/deposits")
async def get_user_deposits(
    user_id: int,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    await get_user_or_404(user_id, db)

    result = await db.execute(
        select(Deposit)
        .where(Deposit.owner == user_id)
        .order_by(Deposit.date.desc())
    )

    deposits = result.scalars().all()

    return {
        "deposits": [
            {
                "_id": str(deposit.id),
                "id": deposit.id,
                "amount": float(deposit.amount),
                "status": deposit.status,
                "date": deposit.date.isoformat(),
            }
            for deposit in deposits
        ]
    }


@router.get("/{user_id}/withdrawals")
async def get_user_withdrawals(
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    await get_user_or_404(user_id, db)

    result = await db.execute(
        select(Withdrawal)
        .where(Withdrawal.owner == user_id)
        .order_by(Withdrawal.date.desc())
    )

    withdrawals = result.scalars().all()

    return {
        "withdrawals": [
            {
                "_id": str(withdrawal.id),
                "id": withdrawal.id,
                "amount": float(withdrawal.amount),
                "status": withdrawal.status,
                "date": withdrawal.date.isoformat(),
            }
            for withdrawal in withdrawals
        ]
    }


@router.post("/{user_id}/verify")
async def verify_user(
    user_id: int,
    body: VerifyUserIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_or_404(user_id, db)

    user.verified = body.verified

    await db.commit()
    await db.refresh(user)

    return {
        "msg": "User verification updated",
        "verified": user.verified,
    }


@router.post("/{user_id}/suspend")
async def suspend_user(
    user_id: int,
    body: SuspendUserIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_or_404(user_id, db)

    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot suspend your own account",
        )

    user.suspended = body.suspended

    await db.commit()
    await db.refresh(user)

    return {
        "msg": "User account status updated",
        "suspended": user.suspended,
    }


@router.post("/{user_id}/role")
async def change_role(
    user_id: int,
    body: RoleIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_or_404(user_id, db)

    if user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot change your own role",
        )

    user.role = body.role

    await db.commit()
    await db.refresh(user)

    return {
        "msg": "User role updated",
        "role": user.role,
    }


@router.post("/{user_id}/balance")
async def adjust_balance(
    user_id: int,
    body: BalanceIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    allowed_fields = {
        "balance": "balance",
        "investBalance": "invest_balance",
        "profit": "profit",
    }

    if body.field not in allowed_fields:
        raise HTTPException(
            status_code=422,
            detail="Field must be 'balance', 'investBalance', or 'profit'",
        )

    # Lock the user row so concurrent admin adjustments/transfers
    # cannot overwrite each other's changes.
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    try:
        delta = Decimal(str(body.delta)).quantize(Decimal("0.01"))
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Adjustment amount must be a valid number",
        )

    if delta == 0:
        raise HTTPException(
            status_code=422,
            detail="Adjustment amount cannot be zero",
        )

    if body.field == "investBalance":
        current_main = Decimal(str(user.balance)).quantize(Decimal("0.01"))
        current_invest = Decimal(str(user.invest_balance)).quantize(Decimal("0.01"))

        if delta > 0:
            # Move money from main balance into invested balance.
            if current_main < delta:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient main balance",
                )

            user.balance = current_main - delta
            user.invest_balance = current_invest + delta

        else:
            # Move money from invested balance back into main balance.
            amount = abs(delta)

            if current_invest < amount:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient invested balance",
                )

            user.invest_balance = current_invest - amount
            user.balance = current_main + amount

        new_value = Decimal(str(user.invest_balance)).quantize(Decimal("0.01"))

    else:
        field_name = allowed_fields[body.field]
        current = Decimal(str(getattr(user, field_name))).quantize(Decimal("0.01"))
        new_value = (current + delta).quantize(Decimal("0.01"))

        if new_value < 0:
            raise HTTPException(
                status_code=400,
                detail="Insufficient balance",
            )

        setattr(user, field_name, new_value)

    await db.commit()
    await db.refresh(user)

    return {
        "msg": "Balance updated",
        # For investBalance this is the resulting invested balance.
        # For balance/profit it is the resulting selected field value.
        "balance": float(new_value),
        "field": body.field,
        "mainBalance": float(user.balance),
        "investBalance": float(user.invest_balance),
        "profit": float(user.profit),
    }


@router.post("/{user_id}/credit")
async def credit_user(
    user_id: int,
    body: AdminMoneyAdjustmentIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_or_404(user_id, db)

    field_map = {
        "balance": "balance",
        "depositBalance": "deposit_balance",
        "investBalance": "invest_balance",
        "referralBalance": "referral_balance",
        "withdrawBalance": "withdraw_balance",
    }

    field_name = field_map[body.field]
    current = getattr(user, field_name)
    new_balance = current + body.amount

    setattr(user, field_name, new_balance)

    transaction = Transaction(
        owner=user.id,
        amount=body.amount,
        type="admin_credit",
        status="completed",
        details=f"Admin credit: {body.reason}",
        date=datetime.now(timezone.utc),
        reference=f"admin_credit:{admin.id}",
    )

    db.add(transaction)

    await db.commit()
    await db.refresh(user)

    return {
        "msg": "User credited successfully",
        "userId": user.id,
        "field": body.field,
        "amount": float(body.amount),
        "balance": float(new_balance),
        "reason": body.reason,
    }


@router.post("/{user_id}/debit")
async def debit_user(
    user_id: int,
    body: AdminMoneyAdjustmentIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_or_404(user_id, db)

    field_map = {
        "balance": "balance",
        "depositBalance": "deposit_balance",
        "investBalance": "invest_balance",
        "referralBalance": "referral_balance",
        "withdrawBalance": "withdraw_balance",
    }

    field_name = field_map[body.field]
    current = getattr(user, field_name)

    if current < body.amount:
        raise HTTPException(
            status_code=400,
            detail="Insufficient balance",
        )

    new_balance = current - body.amount
    setattr(user, field_name, new_balance)

    transaction = Transaction(
        owner=user.id,
        amount=body.amount,
        type="admin_debit",
        status="completed",
        details=f"Admin debit: {body.reason}",
        date=datetime.now(timezone.utc),
        reference=f"admin_debit:{admin.id}",
    )

    db.add(transaction)

    await db.commit()
    await db.refresh(user)

    return {
        "msg": "User debited successfully",
        "userId": user.id,
        "field": body.field,
        "amount": float(body.amount),
        "balance": float(new_balance),
        "reason": body.reason,
    }




@router.post("/{user_id}/invest")
async def admin_create_investment(
    user_id: int,
    body: AdminInvestmentIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_or_404(user_id, db)
    amount = body.amount

    if user.balance < amount:
        raise HTTPException(
            status_code=400,
            detail="Insufficient available balance",
        )

    result = await db.execute(
        select(Plan).where(
            func.lower(func.trim(Plan.name)) == func.lower(func.trim(body.name)),
            Plan.is_active.is_(True),
        )
    )

    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Investment plan not found",
        )

    if amount < plan.minimum or amount > plan.maximun:
        raise HTTPException(
            status_code=400,
            detail="Amount is outside this plan's limits",
        )

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
        details=f"Admin-created investment in {plan.name}",
        date=investment_date,
        reference=f"admin_investment:{investment.id}:by:{admin.id}",
    )

    db.add(transaction)

    await create_notification(
        db=db,
        user_id=user.id,
        title="Investment Created",
        message=(
            f"An investment of ${float(amount):.2f} in {plan.name} "
            "has been created on your behalf by an administrator."
        ),
        notification_type="investment",
    )

    await db.commit()
    await db.refresh(investment)
    await db.refresh(user)

    return {
        "status": "success",
        "msg": "Investment created successfully",
        "investmentId": str(investment.id),
        "userId": user.id,
        "amount": float(amount),
        "plan": plan.name,
        "rate": float(plan.percentage),
        "maturityDate": maturity_date.isoformat(),
        "balance": float(user.balance),
        "investBalance": float(user.invest_balance),
    }
