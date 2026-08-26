from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, generate_otp, hash_otp
from app.schemas.auth import SignupIn, SigninIn, OTPIn, ResetPasswordIn

router = APIRouter()

def public_user(u):
    return {
        "_id": str(u["_id"]),
        "email": u["email"],
        "f_name": u.get("f_name"),
        "l_name": u.get("l_name"),
        "country": u.get("country"),
        "phone": u.get("phone"),
        "balance": u.get("balance", 0),
        "profit": u.get("profit", 0),
        "depositBalance": u.get("depositBalance", 0),
        "referralBalance": u.get("referralBalance", 0),
        "withdrawBalance": u.get("withdrawBalance", 0),
        "investBalance": u.get("investBalance", 0),
        "verified": u.get("verified", False),
        "role": u.get("role", "user"),
        "referralId": u.get("referralId"),
        "referrerId": u.get("referrerId"),
        "joinDate": u.get("joinDate"),
    }

@router.post("/signup")
async def signup(data: SignupIn, db=Depends(get_db)):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        return {"status": "err", "msg": "Email already registered"}

    referral_id = secrets_token = ObjectId().__str__()[:10]
    user = {
        "email": email,
        "password": hash_password(data.password),
        "f_name": data.f_name,
        "l_name": data.l_name,
        "phone": data.phone,
        "country": data.country,
        "balance": 0,
        "profit": 0,
        "depositBalance": 0,
        "referralBalance": 0,
        "withdrawBalance": 0,
        "investBalance": 0,
        "currency": "usd",
        "verified": False,
        "role": "user",
        "referralId": referral_id,
        "referrerId": data.refId,
    }
    result = await db.users.insert_one(user)
    user["_id"] = result.inserted_id
    return {"status": "success", "msg": "Account created. Verify your email.", "user": public_user(user)}

@router.post("/signin")
async def signin(data: SigninIn, db=Depends(get_db)):
    user = await db.users.find_one({"email": data.email.lower()})
    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(str(user["_id"]), user.get("role", "user"))
    return {"status": "success", "token": token, "user": public_user(user)}

@router.get("/me")
async def me(user=Depends(__import__("app.api.dependencies", fromlist=["current_user"]).current_user)):
    return {"status": "success", "user": public_user(user)}

@router.post("/verifyOtp")
async def verify_otp(data: OTPIn, db=Depends(get_db)):
    record = await db.otps.find_one({"email": data.email.lower(), "otp_hash": hash_otp(data.otp), "used": False})
    if not record:
        return {"status": "err", "msg": "Invalid or expired OTP"}
    await db.otps.update_one({"_id": record["_id"]}, {"$set": {"used": True}})
    await db.users.update_one({"email": data.email.lower()}, {"$set": {"verified": True}})
    return {"status": "success", "msg": "Email verified"}

@router.post("/generateVEOtp")
@router.post("/generateOtp")
async def generate_otp_route(data: dict, db=Depends(get_db)):
    email = str(data.get("email", "")).lower()
    if not email:
        raise HTTPException(status_code=422, detail="Email is required")
    otp = generate_otp()
    await db.otps.delete_many({"email": email})
    await db.otps.insert_one({"email": email, "otp_hash": hash_otp(otp), "used": False})
    # Email delivery is intentionally separated from OTP creation.
    return {"status": "success", "msg": "OTP generated. Configure email delivery to send it."}

@router.post("/resetPassword")
async def reset_password(data: ResetPasswordIn, db=Depends(get_db)):
    record = await db.otps.find_one({"email": data.email.lower(), "otp_hash": hash_otp(data.otp), "used": False})
    if not record:
        return {"status": "err", "msg": "Invalid or expired OTP"}
    result = await db.users.update_one({"email": data.email.lower()}, {"$set": {"password": hash_password(data.password)}})
    await db.otps.update_one({"_id": record["_id"]}, {"$set": {"used": True}})
    return {"status": "success" if result.modified_count else "err", "msg": "Password updated" if result.modified_count else "User not found"}
