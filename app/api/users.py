from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_user
from app.core.database import get_db
from app.models.collections import User
from app.schemas.auth import UpdateUserIn


router = APIRouter()


def public_user(u: User):
    return {
        "_id": str(u.id),
        "email": u.email,
        "f_name": u.f_name,
        "l_name": u.l_name,
        "country": u.country,
        "phone": u.phone,
        "balance": float(u.balance),
        "profit": float(u.profit),
        "depositBalance": float(u.deposit_balance),
        "referralBalance": float(u.referral_balance),
        "withdrawBalance": float(u.withdraw_balance),
        "investBalance": float(u.invest_balance),
        "currency": u.currency,
        "verified": u.verified,
        "role": u.role,
        "referralId": u.referral_id,
        "referrerId": u.referrer_id,
        "joinDate": u.join_date.isoformat(),
    }


@router.post("/updateUser")
async def update_user(
    data: UpdateUserIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    updates = data.model_dump(exclude_none=True)

    if not updates:
        return {
            "status": "err",
            "msg": "No changes supplied",
        }

    field_mapping = {
        "f_name": "f_name",
        "l_name": "l_name",
        "phone": "phone",
        "country": "country",
        "currency": "currency",
    }

    for field, value in updates.items():
        model_field = field_mapping.get(field)

        if model_field:
            setattr(user, model_field, value)

    await db.commit()
    await db.refresh(user)

    return {
        "status": "success",
        "user": public_user(user),
    }


@router.post("/checkId")
async def check_id(
    user: User = Depends(current_user),
):
    return {
        "status": "success",
        "user": public_user(user),
    }