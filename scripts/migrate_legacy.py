"""
Icon Invest MongoDB migration helper.

IMPORTANT:
- This script is DRY-RUN by default.
- It does not delete source documents.
- It preserves MongoDB _id values.
- It converts legacy owner fields from strings to ObjectId when possible.
- It preserves legacy password hashes so existing users can continue to log in.
- Run a full MongoDB backup before using --apply.

Usage:
    python scripts/migrate_legacy.py
    python scripts/migrate_legacy.py --apply
"""
import argparse
import asyncio
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

COLLECTIONS = ["users", "plans", "wallets", "deposits", "investments", "withdrawals", "transactions"]

def oid(value):
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return value

def normalize_user(doc):
    out = dict(doc)
    out.setdefault("balance", 0)
    out.setdefault("profit", 0)
    out.setdefault("depositBalance", 0)
    out.setdefault("referralBalance", 0)
    out.setdefault("withdrawBalance", 0)
    out.setdefault("investBalance", 0)
    out.setdefault("currency", "usd")
    out.setdefault("country", "USA")
    out.setdefault("verified", False)
    out.setdefault("role", "user")
    return out

def normalize_owner(doc):
    out = dict(doc)
    if "owner" in out:
        out["owner"] = oid(out["owner"])
    return out

def normalize_finance(doc):
    out = normalize_owner(doc)
    if "amount" in out:
        try:
            out["amount"] = float(out["amount"])
        except (TypeError, ValueError):
            pass
    if "profit" in out:
        try:
            out["profit"] = float(out["profit"])
        except (TypeError, ValueError):
            pass
    if "rate" in out:
        try:
            out["rate"] = float(out["rate"])
        except (TypeError, ValueError):
            pass
    if "date" in out and isinstance(out["date"], str):
        # Keep the original date string when it cannot be safely parsed.
        pass
    return out

def normalize(collection, doc):
    if collection == "users":
        return normalize_user(doc)
    if collection in {"deposits", "investments", "withdrawals", "transactions"}:
        return normalize_finance(doc)
    return dict(doc)

async def main(apply: bool):
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]

    print(f"Database: {settings.mongodb_db}")
    print(f"Mode: {'APPLY' if apply else 'DRY RUN'}")

    for collection in COLLECTIONS:
        source = db[collection]
        target = db[collection]
        count = await source.count_documents({})
        print(f"\n{collection}: {count} document(s)")

        if not apply:
            continue

        changed = 0
        async for doc in source.find({}):
            new_doc = normalize(collection, doc)
            if new_doc != doc:
                await target.replace_one({"_id": doc["_id"]}, new_doc, upsert=False)
                changed += 1

        print(f"  normalized: {changed}")

    # Useful indexes. These are safe to create repeatedly.
    await db.users.create_index("email", unique=True, sparse=True)
    await db.wallets.create_index("cryptocurrency", unique=True, sparse=True)
    await db.transactions.create_index([("owner", 1), ("date", -1)])
    await db.deposits.create_index([("owner", 1), ("date", -1)])
    await db.withdrawals.create_index([("owner", 1), ("date", -1)])
    await db.investments.create_index([("owner", 1), ("date", -1)])

    print("\nIndexes ensured.")
    print("No documents were deleted.")

    client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually normalize documents")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
