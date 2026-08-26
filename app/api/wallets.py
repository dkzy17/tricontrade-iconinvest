from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import admin_user
from app.core.database import get_db
from app.models.collections import Wallet
from app.schemas.finance import WalletIn


router = APIRouter()


def public_wallet(w: Wallet):
    return {
        "_id": str(w.id),
        "cryptocurrency": w.cryptocurrency,
        "network": w.network,
        "address": w.address,
        "isActive": w.is_active,
    }


@router.get("/wallet-addresses")
async def wallet_addresses(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Wallet).where(
            Wallet.is_active.is_(True)
        )
    )

    wallets = result.scalars().all()

    return {
        "status": "success",
        "addresses": [
            {
                "cryptocurrency": w.cryptocurrency,
                "network": w.network,
                "address": w.address,
            }
            for w in wallets
        ],
    }


@router.get("/wallets")
async def wallets(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Wallet).order_by(
            Wallet.cryptocurrency,
            Wallet.network,
            Wallet.id,
        )
    )

    return {
        "status": "success",
        "wallets": [
            public_wallet(w)
            for w in result.scalars().all()
        ],
    }


@router.get("/wallets/{crypto}")
async def wallet_by_crypto(
    crypto: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Wallet)
        .where(
            Wallet.cryptocurrency == crypto.upper()
        )
        .order_by(Wallet.network)
    )

    wallets_found = result.scalars().all()

    if not wallets_found:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found",
        )

    return {
        "status": "success",
        "wallets": [
            public_wallet(w)
            for w in wallets_found
        ],
    }


@router.post("/wallets")
async def create_wallet(
    data: WalletIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    cryptocurrency = data.cryptocurrency.upper().strip()
    network = data.network.strip()

    result = await db.execute(
        select(Wallet).where(
            and_(
                Wallet.cryptocurrency == cryptocurrency,
                Wallet.network == network,
            )
        )
    )

    wallet = result.scalar_one_or_none()

    if wallet:
        wallet.address = data.address
        wallet.is_active = data.isActive
    else:
        wallet = Wallet(
            cryptocurrency=cryptocurrency,
            network=network,
            address=data.address,
            is_active=data.isActive,
        )

        db.add(wallet)

    await db.commit()
    await db.refresh(wallet)

    return {
        "status": "success",
        "msg": "Wallet saved",
        "wallet": public_wallet(wallet),
    }


@router.put("/wallets/{wallet_id}")
async def update_wallet(
    wallet_id: str,
    data: WalletIn,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        wallet_id_int = int(wallet_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid wallet ID",
        )

    result = await db.execute(
        select(Wallet).where(
            Wallet.id == wallet_id_int
        )
    )

    wallet = result.scalar_one_or_none()

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found",
        )

    cryptocurrency = data.cryptocurrency.upper().strip()
    network = data.network.strip()

    duplicate_result = await db.execute(
        select(Wallet).where(
            and_(
                Wallet.cryptocurrency == cryptocurrency,
                Wallet.network == network,
                Wallet.id != wallet.id,
            )
        )
    )

    duplicate = duplicate_result.scalar_one_or_none()

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="A wallet already exists for this cryptocurrency and network",
        )

    wallet.cryptocurrency = cryptocurrency
    wallet.network = network
    wallet.address = data.address
    wallet.is_active = data.isActive

    await db.commit()
    await db.refresh(wallet)

    return {
        "status": "success",
        "msg": "Wallet updated",
        "wallet": public_wallet(wallet),
    }


@router.delete("/wallets/{wallet_id}")
async def delete_wallet(
    wallet_id: str,
    admin=Depends(admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        wallet_id_int = int(wallet_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid wallet ID",
        )

    result = await db.execute(
        select(Wallet).where(
            Wallet.id == wallet_id_int
        )
    )

    wallet = result.scalar_one_or_none()

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found",
        )

    await db.delete(wallet)
    await db.commit()

    return {
        "status": "success",
        "msg": "Wallet deleted",
    }