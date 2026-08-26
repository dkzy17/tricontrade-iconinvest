from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from app.core.database import get_db
from app.api.dependencies import admin_user
from app.schemas.finance import PlanIn

router = APIRouter()

@router.get("/")
async def get_plans(db=Depends(get_db)):
    plans = []
    async for p in db.plans.find({"isActive": True}).sort("createdAt", 1):
        p["_id"] = str(p["_id"])
        plans.append(p)
    return {"status": "success", "plans": plans}

@router.post("/admin/all")
async def all_plans(_: dict | None = None, admin=Depends(admin_user), db=Depends(get_db)):
    plans = []
    async for p in db.plans.find({}).sort("createdAt", 1):
        p["_id"] = str(p["_id"])
        plans.append(p)
    return {"status": "success", "plans": plans}

@router.post("/admin/create")
async def create_plan(data: PlanIn, admin=Depends(admin_user), db=Depends(get_db)):
    doc = data.model_dump()
    doc["createdAt"] = doc["updatedAt"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    result = await db.plans.insert_one(doc)
    return {"status": "success", "id": str(result.inserted_id)}

@router.post("/admin/update/{plan_id}")
async def update_plan(plan_id: str, data: PlanIn, admin=Depends(admin_user), db=Depends(get_db)):
    if not ObjectId.is_valid(plan_id):
        raise HTTPException(400, "Invalid plan ID")
    doc = data.model_dump()
    doc["updatedAt"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    result = await db.plans.update_one({"_id": ObjectId(plan_id)}, {"$set": doc})
    return {"status": "success" if result.matched_count else "err", "msg": "Plan updated" if result.matched_count else "Plan not found"}

@router.post("/admin/delete/{plan_id}")
async def delete_plan(plan_id: str, admin=Depends(admin_user), db=Depends(get_db)):
    if not ObjectId.is_valid(plan_id):
        raise HTTPException(400, "Invalid plan ID")
    result = await db.plans.delete_one({"_id": ObjectId(plan_id)})
    return {"status": "success" if result.deleted_count else "err", "msg": "Plan deleted" if result.deleted_count else "Plan not found"}
