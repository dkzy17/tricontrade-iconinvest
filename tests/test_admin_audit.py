import ast
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DBAPIError

from app.core.database import SessionLocal, engine
from app.models.collections import AdminAuditLog
from test_admin_roles import auth


AUDITED_FUNCTIONS = {
    "app/api/admin.py": [
        "approve_deposit",
        "reject_deposit",
        "approve_withdrawal",
        "reject_withdrawal",
    ],
    "app/api/admin_users.py": [
        "verify_user",
        "suspend_user",
        "adjust_balance",
        "credit_user",
        "debit_user",
        "admin_create_investment",
    ],
    "app/api/admin_investments.py": [
        "adjust_investment_roi",
        "pause_investment",
        "resume_investment",
    ],
    "app/api/wallets.py": [
        "create_wallet",
        "update_wallet",
        "delete_wallet",
    ],
}


def test_audit_model_uses_postgresql_jsonb():
    assert isinstance(AdminAuditLog.__table__.c.details.type, JSONB)


def test_all_operational_mutations_record_audit_events():
    for filename, function_names in AUDITED_FUNCTIONS.items():
        tree = ast.parse(Path(filename).read_text())
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        for function_name in function_names:
            assert function_name in functions, (
                f"{filename}: missing function {function_name}"
            )
            count = sum(
                1
                for node in ast.walk(functions[function_name])
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "record_admin_action"
            )
            assert count == 1, (
                f"{filename}:{function_name} must contain exactly "
                "one record_admin_action call"
            )


@pytest.mark.asyncio
async def test_database_rejects_audit_update_delete_and_truncate(
    api_client, user_factory
):
    actor = await user_factory(role="superadmin")

    async with SessionLocal() as session:
        entry = AdminAuditLog(
            actor_id=actor["id"],
            actor_email=actor["email"],
            actor_role="superadmin",
            action="test.append_only_probe",
            details={"test": True},
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        audit_id = entry.id

    async with engine.connect() as connection:
        trigger_count = await connection.scalar(text("""
            SELECT COUNT(*)
            FROM pg_trigger
            WHERE tgrelid = 'public.admin_audit_logs'::regclass
              AND NOT tgisinternal
              AND tgname IN (
                  'trg_admin_audit_logs_no_update_delete',
                  'trg_admin_audit_logs_no_truncate'
              )
        """))

    assert trigger_count == 2, (
        "Both append-only triggers must be installed in the test database."
    )

    attempts = [
        (
            "UPDATE admin_audit_logs SET action = 'tampered' WHERE id = :id",
            {"id": audit_id},
        ),
        (
            "DELETE FROM admin_audit_logs WHERE id = :id",
            {"id": audit_id},
        ),
        ("TRUNCATE TABLE admin_audit_logs", {}),
    ]

    for statement, parameters in attempts:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                with pytest.raises(DBAPIError):
                    await connection.execute(text(statement), parameters)
            finally:
                await transaction.rollback()


@pytest.mark.asyncio
async def test_operational_user_verification_writes_audit_record(
    api_client, user_factory
):
    for role in ("admin", "superadmin"):
        actor = await user_factory(role=role)
        target = await user_factory(role="user")

        response = await api_client.post(
            f"/api/v1/admin/users/{target['id']}/verify",
            json={"verified": False},
            headers=auth(actor),
        )

        assert response.status_code == 200, response.text
        assert response.json()["verified"] is False

        async with SessionLocal() as session:
            result = await session.execute(
                select(AdminAuditLog).where(
                    AdminAuditLog.actor_id == actor["id"],
                    AdminAuditLog.target_user_id == target["id"],
                    AdminAuditLog.action == "user.verification_changed",
                )
            )
            entry = result.scalar_one_or_none()

        assert entry is not None
        assert entry.actor_role == role
        assert entry.details["verified"] is False
