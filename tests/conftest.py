import os
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

if os.getenv("ENV_FILE") != ".env.test":
    raise RuntimeError(
        "Tests refused: set ENV_FILE=.env.test before importing the application."
    )

from app.main import app
from app.core.database import SessionLocal, connect_db, engine
from app.core.security import hash_password
from app.models.collections import User


@pytest_asyncio.fixture
async def api_client():
    await connect_db()

    # Hard safety check: never run integration tests against production.
    async with engine.connect() as connection:
        database, db_user = (
            await connection.execute(
                text("SELECT current_database(), current_user")
            )
        ).one()

    if database != "triconcapital_test":
        await engine.dispose()
        raise RuntimeError(
            f"Tests refused: connected to {database!r}, not triconcapital_test."
        )

    if db_user != "triconcapital_test_app":
        await engine.dispose()
        raise RuntimeError(
            f"Tests refused: unexpected database role {db_user!r}."
        )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def user_factory(api_client):
    async def create_user(
        role="user",
        suspended=False,
        email=None,
        password="TestPassword!234",
    ):
        if email is None:
            email = f"{role}-{uuid4().hex}@example.com"

        async with SessionLocal() as session:
            user = User(
                email=email,
                password=hash_password(password),
                f_name="Test",
                l_name=role.capitalize(),
                country="Nigeria",
                role=role,
                verified=True,
                suspended=suspended,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            return {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "password": password,
            }

    return create_user
