from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_user, admin_user
from app.api.notifications import create_notification
from app.core.database import get_db
from app.core.email import render_admin_email, send_admin_email
from app.core.security import (
    create_withdrawal_token,
    hash_withdrawal_code,
)
from app.models.collections import (
    User,
    WithdrawalVerification,
)
from app.schemas.withdrawal import WithdrawalVerificationIn


WITHDRAWAL_CODE_EXPIRY_MINUTES = 15
WITHDRAWAL_TOKEN_EXPIRY_MINUTES = 15

CODE_ALPHABET = (
    "ABCDEFGHJKLMNPQRSTUVWXYZ"
    "23456789"
)


admin_router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["Admin Withdrawal Verification"],
)

router = APIRouter(
    prefix="/api/v1/withdrawal-verification",
    tags=["Withdrawal Verification"],
)


def generate_withdrawal_code() -> str:
    return "".join(
        secrets.choice(CODE_ALPHABET)
        for _ in range(7)
    )


def receiver_name(user: User) -> str:
    name = " ".join(
        part
        for part in [user.f_name, user.l_name]
        if part
    ).strip()

    return (
        name
        or user.email.split("@", 1)[0]
    )


@admin_router.post("/{user_id}/withdrawal-token")
async def issue_withdrawal_token(
    user_id: int,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if user.role == "admin":
        raise HTTPException(
            status_code=400,
            detail="Withdrawal authorization is only available for users",
        )

    if user.suspended:
        raise HTTPException(
            status_code=400,
            detail="User account is suspended",
        )

    if not user.verified:
        raise HTTPException(
            status_code=400,
            detail="User must be verified before withdrawal authorization can be issued",
        )

    now = datetime.now(timezone.utc)

    # Invalidate any older authorization that has not
    # already been consumed by a successful withdrawal.
    await db.execute(
        update(WithdrawalVerification)
        .where(
            WithdrawalVerification.user_id == user.id,
            WithdrawalVerification.token_used_at.is_(None),
            WithdrawalVerification.status.in_(
                ["pending", "used"]
            ),
        )
        .values(status="superseded")
    )

    code = generate_withdrawal_code()

    verification = WithdrawalVerification(
        user_id=user.id,
        issued_by=admin.id,
        code_hash=hash_withdrawal_code(code),
        status="pending",
        created_at=now,
        expires_at=(
            now
            + timedelta(
                minutes=WITHDRAWAL_CODE_EXPIRY_MINUTES
            )
        ),
    )

    db.add(verification)
    await db.flush()

    expires_text = (
        verification.expires_at
        .astimezone(timezone.utc)
        .strftime("%Y-%m-%d %H:%M UTC")
    )

    subject = "Your TriconTrade Withdrawal Authorization Code"

    body = (
        f"Hello {receiver_name(user)},\n\n"
        "A withdrawal authorization has been issued "
        "for your TriconTrade account.\n\n"
        f"Your withdrawal verification code is:\n\n"
        f"{code}\n\n"
        "This code is valid for 15 minutes and can only "
        "be used once.\n\n"
        f"Code expiry: {expires_text}\n\n"
        "After you verify this code, TriconTrade will "
        "issue a temporary withdrawal authorization for "
        "your withdrawal request.\n\n"
        "If you did not expect this authorization, "
        "please contact TriconTrade support."
    )

    html = render_admin_email(
        receiver_name=receiver_name(user),
        subject=subject,
        body=body,
        cta_label=None,
        cta_url=None,
    )

    try:
        await send_admin_email(
            user.email,
            subject,
            html,
        )

        await create_notification(
            db=db,
            user_id=user.id,
            title="Withdrawal Authorization Issued",
            message=(
                "A withdrawal verification code has "
                "been sent to your email. The code "
                "expires in 15 minutes."
            ),
            notification_type="withdrawal",
        )

        await db.commit()

    except Exception:
        await db.rollback()

        raise HTTPException(
            status_code=502,
            detail="Unable to send withdrawal authorization email",
        )

    return {
        "status": "success",
        "msg": "Withdrawal authorization code sent to user",
        "userId": str(user.id),
        "email": user.email,
        "expiresAt": verification.expires_at.isoformat(),
    }


@router.post("/verify")
async def verify_withdrawal_code(
    data: WithdrawalVerificationIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.suspended:
        raise HTTPException(
            status_code=403,
            detail="Account is suspended",
        )

    if not user.verified:
        raise HTTPException(
            status_code=403,
            detail="Account must be verified before withdrawing",
        )

    now = datetime.now(timezone.utc)
    code = data.code.strip().upper()

    result = await db.execute(
        select(WithdrawalVerification)
        .where(
            WithdrawalVerification.user_id == user.id,
            WithdrawalVerification.status == "pending",
        )
        .order_by(
            WithdrawalVerification.created_at.desc()
        )
        .limit(1)
        .with_for_update()
    )

    verification = result.scalars().first()

    if not verification:
        raise HTTPException(
            status_code=400,
            detail="No active withdrawal verification code",
        )

    if verification.expires_at <= now:
        verification.status = "expired"
        await db.commit()

        raise HTTPException(
            status_code=400,
            detail="Withdrawal verification code has expired",
        )

    if (
        hash_withdrawal_code(code)
        != verification.code_hash
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid withdrawal verification code",
        )

    verification.status = "used"
    verification.used_at = now

    withdrawal_token = create_withdrawal_token(
        user_id=str(user.id),
        verification_id=str(verification.id),
        expires_minutes=WITHDRAWAL_TOKEN_EXPIRY_MINUTES,
    )

    token_expires_at = (
        now
        + timedelta(
            minutes=WITHDRAWAL_TOKEN_EXPIRY_MINUTES
        )
    )

    await create_notification(
        db=db,
        user_id=user.id,
        title="Withdrawal Authorization Verified",
        message=(
            "Your withdrawal authorization has been "
            "verified and is valid for 15 minutes."
        ),
        notification_type="withdrawal",
    )

    await db.commit()

    return {
        "status": "success",
        "msg": "Withdrawal authorization verified",
        "token": withdrawal_token,
        "expiresAt": token_expires_at.isoformat(),
    }
