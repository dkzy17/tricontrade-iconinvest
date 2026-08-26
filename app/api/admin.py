from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import admin_user
from app.api.notifications import create_notification
from app.core.database import get_db
from app.models.collections import (
    User,
    Deposit,
    Withdrawal,
    Investment,
    Transaction,
)


router = APIRouter()


# =========================================================
# ADMIN DASHBOARD STATS
# =========================================================

@router.get("/stats")
async def stats(
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    total_users_result = await db.execute(
        select(func.count(User.id))
    )
    total_users = total_users_result.scalar_one()

    verified_users_result = await db.execute(
        select(func.count(User.id)).where(
            User.verified.is_(True)
        )
    )
    verified_users = verified_users_result.scalar_one()

    pending_deposits_result = await db.execute(
        select(func.count(Deposit.id)).where(
            Deposit.status == "pending"
        )
    )
    pending_deposits = pending_deposits_result.scalar_one()

    pending_withdrawals_result = await db.execute(
        select(func.count(Withdrawal.id)).where(
            Withdrawal.status == "pending"
        )
    )
    pending_withdrawals = pending_withdrawals_result.scalar_one()

    investments_result = await db.execute(
        select(func.count(Investment.id))
    )
    investments = investments_result.scalar_one()

    return {
        "status": "success",
        "stats": {
            "users": total_users,
            "verified_users": verified_users,
            "pending_deposits": pending_deposits,
            "pending_withdrawals": pending_withdrawals,
            "investments": investments,
        },
    }


# =========================================================
# USERS
# =========================================================

@router.get("/users")
async def users(
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).order_by(User.join_date.desc())
    )

    user_records = result.scalars().all()

    items = []

    for user in user_records:
        full_name = " ".join(
            part for part in [user.f_name, user.l_name]
            if part
        ).strip()

        items.append({
            "_id": str(user.id),
            "email": user.email,
            "f_name": user.f_name,
            "l_name": user.l_name,
            "fullName": full_name,
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
            "isVerified": user.verified,
            "twoFactorEnabled": False,
            "role": user.role,
            "referralId": user.referral_id,
            "referrerId": user.referrer_id,
            "joinDate": user.join_date.isoformat(),
        })

    return {
        "status": "success",
        "users": items,
    }


# =========================================================
# TRANSACTIONS
# =========================================================

@router.get("/transactions")
async def transactions(
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .order_by(Transaction.date.desc())
    )

    records = result.scalars().all()

    items = []

    for transaction in records:
        items.append({
            "_id": str(transaction.id),
            "owner": str(transaction.owner),
            "amount": float(transaction.amount),
            "type": transaction.type,
            "status": transaction.status,
            "details": transaction.details,
            "date": transaction.date.isoformat(),
            "reference": transaction.reference,
        })

    return {
        "status": "success",
        "transactions": items,
    }


# =========================================================
# DEPOSITS
# =========================================================

@router.get("/deposits")
async def deposits(
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deposit)
        .order_by(Deposit.date.desc())
    )

    records = result.scalars().all()

    items = []

    for deposit in records:
        items.append({
            "_id": str(deposit.id),
            "owner": str(deposit.owner),
            "amount": float(deposit.amount),
            "date": deposit.date.isoformat(),
            "verified": deposit.verified,
            "status": deposit.status,
            "type": deposit.type,
        })

    return {
        "status": "success",
        "deposits": items,
    }


@router.post("/deposits/{deposit_id}/approve")
async def approve_deposit(
    deposit_id: int,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deposit).where(
            Deposit.id == deposit_id
        )
    )

    deposit = result.scalar_one_or_none()

    if not deposit:
        raise HTTPException(
            status_code=404,
            detail="Deposit not found",
        )

    if deposit.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Deposit is already {deposit.status}",
        )

    user_result = await db.execute(
        select(User).where(
            User.id == deposit.owner
        )
    )

    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Deposit owner not found",
        )

    # Credit the deposit.
    user.balance += deposit.amount
    user.deposit_balance += deposit.amount

    # Frontend contract expects "approved".
    deposit.status = "approved"
    deposit.verified = True

    transaction_result = await db.execute(
        select(Transaction).where(
            Transaction.reference == str(deposit.id),
            Transaction.type == "deposit",
        )
    )

    transaction = transaction_result.scalar_one_or_none()

    if transaction:
        transaction.status = "completed"
        transaction.details = "Deposit approved by admin"

    await create_notification(
        db=db,
        user_id=user.id,
        title="Deposit Approved",
        message=(
            f"Your deposit of ${float(deposit.amount):.2f} "
            "has been approved and credited to your account."
        ),
        notification_type="deposit",
    )

    await db.commit()
    await db.refresh(deposit)

    return {
        "status": "success",
        "msg": "Deposit approved",
        "depositId": str(deposit.id),
        "amount": float(deposit.amount),
        "userId": str(user.id),
    }


@router.post("/deposits/{deposit_id}/reject")
async def reject_deposit(
    deposit_id: int,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deposit).where(
            Deposit.id == deposit_id
        )
    )

    deposit = result.scalar_one_or_none()

    if not deposit:
        raise HTTPException(
            status_code=404,
            detail="Deposit not found",
        )

    if deposit.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Deposit is already {deposit.status}",
        )

    user_result = await db.execute(
        select(User).where(
            User.id == deposit.owner
        )
    )

    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Deposit owner not found",
        )

    # Rejected deposits do not affect the balance.
    deposit.status = "rejected"
    deposit.verified = False

    transaction_result = await db.execute(
        select(Transaction).where(
            Transaction.reference == str(deposit.id),
            Transaction.type == "deposit",
        )
    )

    transaction = transaction_result.scalar_one_or_none()

    if transaction:
        transaction.status = "rejected"
        transaction.details = "Deposit rejected by admin"

    await create_notification(
        db=db,
        user_id=user.id,
        title="Deposit Rejected",
        message=(
            f"Your deposit of ${float(deposit.amount):.2f} "
            "has been rejected. Please contact support if you "
            "believe this was a mistake."
        ),
        notification_type="deposit",
    )

    await db.commit()
    await db.refresh(deposit)

    return {
        "status": "success",
        "msg": "Deposit rejected",
        "depositId": str(deposit.id),
    }


# =========================================================
# WITHDRAWALS
# =========================================================

@router.get("/withdrawals")
async def withdrawals(
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Withdrawal)
        .order_by(Withdrawal.date.desc())
    )

    records = result.scalars().all()

    items = []

    for withdrawal in records:
        items.append({
            "_id": str(withdrawal.id),
            "owner": str(withdrawal.owner),
            "amount": float(withdrawal.amount),
            "date": withdrawal.date.isoformat(),
            "wallet": withdrawal.wallet,
            "coin": withdrawal.coin,
            "network": withdrawal.network,
            "status": withdrawal.status,
        })

    return {
        "status": "success",
        "withdrawals": items,
    }


@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(
    withdrawal_id: int,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Withdrawal).where(
            Withdrawal.id == withdrawal_id
        )
    )

    withdrawal = result.scalar_one_or_none()

    if not withdrawal:
        raise HTTPException(
            status_code=404,
            detail="Withdrawal not found",
        )

    if withdrawal.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Withdrawal is already {withdrawal.status}",
        )

    user_result = await db.execute(
        select(User).where(
            User.id == withdrawal.owner
        )
    )

    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Withdrawal owner not found",
        )

    # The amount was already reserved when the withdrawal
    # was submitted, so approval does NOT deduct it again.
    withdrawal.status = "approved"

    transaction_result = await db.execute(
        select(Transaction).where(
            Transaction.reference == str(withdrawal.id),
            Transaction.type == "withdrawal",
        )
    )

    transaction = transaction_result.scalar_one_or_none()

    if transaction:
        transaction.status = "completed"
        transaction.details = "Withdrawal approved by admin"

    await create_notification(
        db=db,
        user_id=user.id,
        title="Withdrawal Approved",
        message=(
            f"Your withdrawal of ${float(withdrawal.amount):.2f} "
            f"in {withdrawal.coin} ({withdrawal.network}) "
            "has been approved."
        ),
        notification_type="withdrawal",
    )

    await db.commit()
    await db.refresh(withdrawal)

    return {
        "status": "success",
        "msg": "Withdrawal approved",
        "withdrawalId": str(withdrawal.id),
        "amount": float(withdrawal.amount),
        "userId": str(user.id),
    }


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: int,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Withdrawal).where(
            Withdrawal.id == withdrawal_id
        )
    )

    withdrawal = result.scalar_one_or_none()

    if not withdrawal:
        raise HTTPException(
            status_code=404,
            detail="Withdrawal not found",
        )

    if withdrawal.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Withdrawal is already {withdrawal.status}",
        )

    user_result = await db.execute(
        select(User).where(
            User.id == withdrawal.owner
        )
    )

    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Withdrawal owner not found",
        )

    # Return the reserved withdrawal amount to the user.
    user.balance += withdrawal.amount
    user.withdraw_balance -= withdrawal.amount

    withdrawal.status = "rejected"

    transaction_result = await db.execute(
        select(Transaction).where(
            Transaction.reference == str(withdrawal.id),
            Transaction.type == "withdrawal",
        )
    )

    transaction = transaction_result.scalar_one_or_none()

    if transaction:
        transaction.status = "rejected"
        transaction.details = "Withdrawal rejected by admin"

    await create_notification(
        db=db,
        user_id=user.id,
        title="Withdrawal Rejected",
        message=(
            f"Your withdrawal of ${float(withdrawal.amount):.2f} "
            f"in {withdrawal.coin} ({withdrawal.network}) "
            "has been rejected. The reserved funds have been "
            "returned to your balance."
        ),
        notification_type="withdrawal",
    )

    await db.commit()
    await db.refresh(withdrawal)

    return {
        "status": "success",
        "msg": "Withdrawal rejected and funds returned",
        "withdrawalId": str(withdrawal.id),
        "amount": float(withdrawal.amount),
        "userId": str(user.id),
    }