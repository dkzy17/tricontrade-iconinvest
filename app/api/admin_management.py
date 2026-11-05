from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import super_admin_user
from app.core.admin_audit import record_admin_action
from app.core.database import get_db
from app.core.security import hash_password
from app.models.collections import User, AdminAuditLog
from app.schemas.admin_management import (
    AdminStaffCreateIn,
    AdminStaffRoleUpdateIn,
    AdminStaffSuspensionIn,
)


router = APIRouter(
    prefix="/api/v1/admin/staff",
    tags=["Super Admin - Staff Management"],
)


def staff_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "f_name": user.f_name,
        "l_name": user.l_name,
        "role": user.role,
        "verified": user.verified,
        "suspended": user.suspended,
        "created": user.join_date.isoformat(),
    }


async def get_staff_for_update(
    user_id: int,
    db: AsyncSession,
    *,
    allow_user: bool = False,
) -> User:
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrator not found",
        )

    if user.role == "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admin accounts cannot be modified through staff controls",
        )

    allowed_roles = {"admin"}
    if allow_user:
        allowed_roles.add("user")

    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrator not found",
        )

    return user


@router.get("")
async def list_staff(
    superadmin: User = Depends(super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .where(User.role == "admin")
        .order_by(User.join_date.desc())
    )

    return {
        "status": "success",
        "admins": [
            staff_to_dict(user)
            for user in result.scalars().all()
        ],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_staff_admin(
    body: AdminStaffCreateIn,
    superadmin: User = Depends(super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    email = str(body.email).strip().lower()

    result = await db.execute(
        select(User).where(User.email == email)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    moderator = User(
        email=email,
        password=hash_password(body.password),
        f_name=body.f_name,
        l_name=body.l_name,
        phone="",
        country="Nigeria",
        balance=0,
        profit=0,
        deposit_balance=0,
        referral_balance=0,
        withdraw_balance=0,
        invest_balance=0,
        currency="usd",
        verified=True,
        suspended=False,
        role="admin",
        referral_id=None,
        referrer_id=None,
    )

    db.add(moderator)
    await db.flush()

    record_admin_action(
        db,
        superadmin,
        "admin.created",
        target=moderator,
        details={"role": "admin"},
    )

    await db.commit()
    await db.refresh(moderator)

    return {
        "status": "success",
        "message": "Administrator created successfully",
        "admin": staff_to_dict(moderator),
    }


@router.patch("/{admin_id}/role")
async def update_staff_role(
    admin_id: int,
    body: AdminStaffRoleUpdateIn,
    superadmin: User = Depends(super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if admin_id == superadmin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )

    target = await get_staff_for_update(admin_id, db, allow_user=True)
    previous_role = target.role

    if previous_role == body.role:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already has this role",
        )

    target.role = body.role

    record_admin_action(
        db,
        superadmin,
        "admin.role_changed",
        target=target,
        details={
            "previous_role": previous_role,
            "new_role": body.role,
        },
    )

    await db.commit()
    await db.refresh(target)

    return {
        "status": "success",
        "message": "Administrator role updated",
        "admin": staff_to_dict(target),
    }


@router.patch("/{admin_id}/suspension")
async def update_staff_suspension(
    admin_id: int,
    body: AdminStaffSuspensionIn,
    superadmin: User = Depends(super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if admin_id == superadmin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot suspend or reactivate your own account",
        )

    target = await get_staff_for_update(admin_id, db)
    previous_status = target.suspended
    target.suspended = body.suspended

    record_admin_action(
        db,
        superadmin,
        "admin.suspended" if body.suspended else "admin.reactivated",
        target=target,
        details={
            "previous_suspended": previous_status,
            "suspended": body.suspended,
        },
    )

    await db.commit()
    await db.refresh(target)

    return {
        "status": "success",
        "message": (
            "Administrator suspended"
            if body.suspended
            else "Administrator reactivated"
        ),
        "admin": staff_to_dict(target),
    }


@router.get("/audit-logs")
async def list_admin_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    superadmin: User = Depends(super_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
    )

    return {
        "status": "success",
        "auditLogs": [
            {
                "id": entry.id,
                "actorId": entry.actor_id,
                "actorEmail": entry.actor_email,
                "actorRole": entry.actor_role,
                "action": entry.action,
                "targetUserId": entry.target_user_id,
                "targetEmail": entry.target_email,
                "details": entry.details,
                "createdAt": entry.created_at.isoformat(),
            }
            for entry in result.scalars().all()
        ],
    }
