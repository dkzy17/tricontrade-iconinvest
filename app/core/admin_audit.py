from app.models.collections import AdminAuditLog, User


def record_admin_action(
    db,
    actor: User,
    action: str,
    target: User | None = None,
    details: dict | None = None,
) -> None:
    """Queue an audit event in the caller's current transaction."""

    db.add(
        AdminAuditLog(
            actor_id=actor.id,
            actor_email=actor.email,
            actor_role=actor.role,
            action=action,
            target_user_id=target.id if target else None,
            target_email=target.email if target else None,
            details=details or {},
        )
    )
