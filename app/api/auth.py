from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_user
from app.core.database import get_db
from app.core.email import send_otp_email
from app.core.security import (
    create_access_token,
    generate_otp,
    hash_otp,
    hash_password,
    verify_password,
)
from app.models.collections import OTP, User
from app.schemas.auth import OTPIn, ResetPasswordIn, SigninIn, SignupIn


router = APIRouter()


OTP_EXPIRY_MINUTES = 10


def public_user(user: User) -> dict:
    return {
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
        "joinDate": user.join_date.isoformat(),
    }


async def create_and_send_otp(
    db: AsyncSession,
    email: str,
) -> None:
    email = email.lower().strip()

    otp = generate_otp()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)

    # Only one active OTP per email.
    await db.execute(
        delete(OTP).where(OTP.email == email)
    )

    record = OTP(
        email=email,
        otp_hash=hash_otp(otp),
        used=False,
        created_at=now,
        expires_at=expires_at,
    )

    db.add(record)

    # Commit OTP before sending so the record exists if Resend succeeds.
    await db.commit()

    try:
        await send_otp_email(email, otp)
    except Exception:
        # Do not leave a usable OTP behind if email delivery fails.
        await db.delete(record)
        await db.commit()
        raise


@router.post("/signup")
async def signup(
    data: SignupIn,
    db: AsyncSession = Depends(get_db),
):
    email = data.email.lower().strip()

    result = await db.execute(
        select(User).where(User.email == email)
    )
    existing = result.scalar_one_or_none()

    if existing:
        return {
            "status": "err",
            "msg": "Email already registered",
        }

    referral_id = None

    # Generate a unique referral ID.
    while True:
        candidate = generate_otp() + generate_otp()[:4]

        result = await db.execute(
            select(User).where(
                User.referral_id == candidate
            )
        )

        if result.scalar_one_or_none() is None:
            referral_id = candidate
            break

    user = User(
        email=email,
        password=hash_password(data.password),
        f_name=data.f_name,
        l_name=data.l_name,
        phone=data.phone,
        country=data.country,
        balance=0,
        profit=0,
        deposit_balance=0,
        referral_balance=0,
        withdraw_balance=0,
        invest_balance=0,
        currency="usd",
        verified=False,
        role="user",
        referral_id=referral_id,
        referrer_id=data.refId,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Automatically send verification OTP after registration.
    try:
        await create_and_send_otp(
            db=db,
            email=email,
        )
    except Exception:
        return {
            "status": "success",
            "msg": (
                "Account created, but we could not send the "
                "verification email. Please request a new OTP."
            ),
            "user": public_user(user),
            "verificationRequired": True,
        }

    return {
        "status": "success",
        "msg": "Account created. Verification OTP sent to your email.",
        "user": public_user(user),
        "verificationRequired": True,
    }


@router.post("/signin")
async def signin(
    data: SigninIn,
    db: AsyncSession = Depends(get_db),
):
    email = data.email.lower().strip()

    result = await db.execute(
        select(User).where(User.email == email)
    )

    user = result.scalar_one_or_none()

    if not user or not verify_password(
        data.password,
        user.password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    if user.suspended:
        raise HTTPException(
            status_code=403,
            detail="Your account has been suspended",
        )

    # Do not allow unverified users into the application.
    if not user.verified:
        return {
            "status": "pending",
            "msg": "Please verify your email before signing in.",
            "verificationRequired": True,
            "email": user.email,
        }

    token = create_access_token(
        str(user.id),
        user.role,
    )

    return {
        "status": "success",
        "token": token,
        "user": public_user(user),
    }


@router.get("/me")
async def me(
    user: User = Depends(current_user),
):
    return {
        "status": "success",
        "user": public_user(user),
    }


@router.post("/verifyOtp")
async def verify_otp(
    data: OTPIn,
    db: AsyncSession = Depends(get_db),
):
    email = data.email.lower().strip()
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(OTP).where(
            OTP.email == email,
            OTP.otp_hash == hash_otp(data.otp),
            OTP.used.is_(False),
        )
    )

    record = result.scalar_one_or_none()

    if not record:
        return {
            "status": "err",
            "msg": "Invalid or expired OTP",
        }

    # Expired OTPs become unusable immediately.
    if record.expires_at and record.expires_at <= now:
        record.used = True
        await db.commit()

        return {
            "status": "err",
            "msg": "Invalid or expired OTP",
        }

    result = await db.execute(
        select(User).where(User.email == email)
    )

    user = result.scalar_one_or_none()

    if not user:
        record.used = True
        await db.commit()

        return {
            "status": "err",
            "msg": "User not found",
        }

    user.verified = True
    record.used = True

    await db.commit()
    await db.refresh(user)

    return {
        "status": "success",
        "msg": "Email verified successfully",
        "user": public_user(user),
    }


@router.post("/generateVEOtp")
@router.post("/generateOtp")
async def generate_otp_route(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    email = str(data.get("email", "")).lower().strip()

    if not email:
        raise HTTPException(
            status_code=422,
            detail="Email is required",
        )

    result = await db.execute(
        select(User).where(User.email == email)
    )

    user = result.scalar_one_or_none()

    if not user:
        return {
            "status": "err",
            "msg": "User not found",
        }

    if user.verified:
        return {
            "status": "err",
            "msg": "Email is already verified",
        }

    try:
        await create_and_send_otp(
            db=db,
            email=email,
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to send OTP email",
        )

    return {
        "status": "success",
        "msg": "OTP sent to your email",
    }


@router.post("/resetPassword")
async def reset_password(
    data: ResetPasswordIn,
    db: AsyncSession = Depends(get_db),
):
    email = data.email.lower().strip()
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(OTP).where(
            OTP.email == email,
            OTP.otp_hash == hash_otp(data.otp),
            OTP.used.is_(False),
        )
    )

    record = result.scalar_one_or_none()

    if not record:
        return {
            "status": "err",
            "msg": "Invalid or expired OTP",
        }

    if record.expires_at and record.expires_at <= now:
        record.used = True
        await db.commit()

        return {
            "status": "err",
            "msg": "Invalid or expired OTP",
        }

    result = await db.execute(
        select(User).where(User.email == email)
    )

    user = result.scalar_one_or_none()

    if not user:
        record.used = True
        await db.commit()

        return {
            "status": "err",
            "msg": "User not found",
        }

    user.password = hash_password(data.password)
    record.used = True

    await db.commit()

    return {
        "status": "success",
        "msg": "Password updated",
    }