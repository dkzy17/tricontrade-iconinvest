from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import connect_db, close_db
from app.api import (
    auth,
    users,
    plans,
    finance,
    wallets,
    admin,
    admin_auth,
    admin_management,
    admin_users,
    admin_investments,
    notifications,
    withdrawal_verification,
)


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await connect_db()


@app.on_event("shutdown")
async def shutdown():
    await close_db()


app.include_router(
    auth.router,
    prefix="/api/v1/users",
    tags=["Authentication"],
)

app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["Users"],
)

app.include_router(
    plans.router,
    prefix="/api/v1/plans",
    tags=["Plans"],
)

app.include_router(
    finance.router,
    prefix="/api/v1/investments",
    tags=["Finance"],
)

app.include_router(
    wallets.router,
    prefix="/api/v1",
    tags=["Wallets"],
)

app.include_router(
    admin.router,
    prefix="/api/v1/admin",
    tags=["Admin"],
)

app.include_router(
    admin_auth.router,
    prefix="/api/v1/admin/auth",
    tags=["Admin Authentication"],
)


app.include_router(admin_management.router)

app.include_router(
    admin_users.router,
)

app.include_router(
    admin_investments.router,
)

app.include_router(
    withdrawal_verification.admin_router,
)

app.include_router(
    withdrawal_verification.router,
)

app.include_router(
    notifications.router,
    prefix="/api/v1",
    tags=["Notifications"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.service_name,
    }
