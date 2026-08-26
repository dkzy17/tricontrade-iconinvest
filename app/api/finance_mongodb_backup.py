from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import current_user
from app.core.database import get_db
from app.schemas.finance import DepositIn, InvestmentIn, WithdrawalIn

router = APIRouter()

def money(v):
    return float(Decimal(str(v)))

@router.post("/deposit")
async def create_deposit(data: DepositIn, user=Depends(current_user), db=Depends(get_db)):
    amount = money(data.amount)
    doc = {
        "owner": user["_id"],
        "amount": amount,
        "date": datetime.now(timezone.utc),
        "verified": False,
        "status": "pending",
        "type": "deposit",
    }
    result = await db.deposits.insert_one(doc)
    await db.transactions.insert_one({
        "owner": user["_id"], "amount": amount, "type": "deposit",
        "status": "pending", "details": "Deposit awaiting payment verification",
        "date": datetime.now(timezone.utc), "reference": str(result.inserted_id)
    })
    return {"status": "success", "msg": "Deposit created and awaiting verification", "depositId": str(result.inserted_id)}

@router.post("/new")
async def new_investment(data: InvestmentIn, user=Depends(current_user), db=Depends(get_db)):
    amount = money(data.amount)
    if user.get("balance", 0) < amount:
        return {"status": "err", "msg": "Insufficient available balance"}

    plan = await db.plans.find_one({"name": data.name, "isActive": True})
    if not plan:
        return {"status": "err", "msg": "Investment plan not found"}
    if amount < plan["minimum"] or amount > plan["maximun"]:
        return {"status": "err", "msg": "Amount is outside this plan's limits"}

    # Atomic balance debit prevents two concurrent investments from overspending the same balance.
    result = await db.users.update_one(
        {"_id": user["_id"], "balance": {"$gte": amount}},
        {"$inc": {"balance": -amount, "investBalance": amount}}
    )
    if result.modified_count != 1:
        return {"status": "err", "msg": "Insufficient available balance"}

    investment = {
        "owner": user["_id"], "amount": amount, "profit": 0,
        "rate": float(plan["percentage"]), "name": plan["name"],
        "date": datetime.now(timezone.utc), "withdrawaled": False, "status": "Active"
    }
    inv = await db.investments.insert_one(investment)
    await db.transactions.insert_one({
        "owner": user["_id"], "amount": amount, "type": "investment",
        "status": "completed", "details": f"Investment in {plan['name']}",
        "date": datetime.now(timezone.utc), "reference": str(inv.inserted_id)
    })
    return {"status": "success", "msg": "Investment created", "investmentId": str(inv.inserted_id)}

@router.post("/myInvestments")
async def my_investments(user=Depends(current_user), db=Depends(get_db)):
    items = []
    async for x in db.investments.find({"owner": user["_id"]}).sort("date", -1):
        x["_id"] = str(x["_id"]); x["owner"] = str(x["owner"])
        items.append(x)
    return {"status": "success", "investments": items}

@router.post("/myDeposits")
async def my_deposits(user=Depends(current_user), db=Depends(get_db)):
    items = []
    async for x in db.deposits.find({"owner": user["_id"]}).sort("date", -1):
        x["_id"] = str(x["_id"]); x["owner"] = str(x["owner"])
        items.append(x)
    return {"status": "success", "deposits": items}

@router.post("/myWithdrawals")
async def my_withdrawals(user=Depends(current_user), db=Depends(get_db)):
    items = []
    async for x in db.withdrawals.find({"owner": user["_id"]}).sort("date", -1):
        x["_id"] = str(x["_id"]); x["owner"] = str(x["owner"])
        items.append(x)
    return {"status": "success", "withdrawals": items}

@router.post("/withdraw")
async def withdraw(data: WithdrawalIn, user=Depends(current_user), db=Depends(get_db)):
    amount = money(data.amount)
    if amount <= 0:
        raise HTTPException(422, "Amount must be positive")

    # Reserve funds atomically. The money is NOT treated as completed until processed.
    result = await db.users.update_one(
        {"_id": user["_id"], "balance": {"$gte": amount}},
        {"$inc": {"balance": -amount, "withdrawBalance": amount}}
    )
    if result.modified_count != 1:
        return {"status": "err", "msg": "Insufficient balance"}

    withdrawal = {
        "owner": user["_id"], "amount": amount, "date": datetime.now(timezone.utc),
        "wallet": data.address, "coin": data.coin, "status": "pending",
    }
    w = await db.withdrawals.insert_one(withdrawal)
    await db.transactions.insert_one({
        "owner": user["_id"], "amount": amount, "type": "withdrawal",
        "status": "pending", "details": f"{data.coin} withdrawal to {data.address}",
        "date": datetime.now(timezone.utc), "reference": str(w.inserted_id)
    })
    return {"status": "success", "msg": "Withdrawal submitted for processing", "withdrawalId": str(w.inserted_id)}
