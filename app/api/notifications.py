from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_user
from app.core.database import get_db
from app.models.collections import Notification


router = APIRouter()


def serialize_notification(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "_id": str(notification.id),
        "user_id": notification.user_id,
        "title": notification.title,
        "message": notification.message,
        "type": notification.type,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
        "read_at": (
            notification.read_at.isoformat()
            if notification.read_at
            else None
        ),
    }


async def create_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "general",
) -> Notification:
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notification_type,
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )

    db.add(notification)
    await db.flush()

    return notification


@router.get("/notifications")
async def get_notifications(
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    )

    notifications = result.scalars().all()

    unread_result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
    )

    unread_count = unread_result.scalar_one()

    return {
        "status": "success",
        "notifications": [
            serialize_notification(notification)
            for notification in notifications
        ],
        "unread_count": unread_count,
    }


@router.get("/notifications/unread")
async def get_unread_notifications(
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
        .order_by(Notification.created_at.desc())
    )

    notifications = result.scalars().all()

    return {
        "status": "success",
        "notifications": [
            serialize_notification(notification)
            for notification in notifications
        ],
        "unread_count": len(notifications),
    }


@router.get("/notifications/{notification_id}")
async def get_notification(
    notification_id: int,
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )

    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    return {
        "status": "success",
        "notification": serialize_notification(notification),
    }


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )

    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "status": "success",
        "msg": "Notification marked as read",
    }


@router.patch("/notifications/read-all")
async def mark_all_notifications_read(
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
        .values(
            is_read=True,
            read_at=datetime.now(timezone.utc),
        )
    )

    await db.commit()

    return {
        "status": "success",
        "msg": "All notifications marked as read",
    }


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: int,
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )

    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    await db.delete(notification)
    await db.commit()

    return {
        "status": "success",
        "msg": "Notification deleted",
    }