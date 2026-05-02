"""Gems & Luxury — internal staff platform backend."""
from __future__ import annotations

import asyncio
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Header, Query, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import storage
import ai_service
from db import db, init_pool, close_pool, check_db

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("gems")

# ---------- DB ----------
# Supabase Postgres connection string (from Supabase → Project Settings → Database).
# Use the "Connection Pooling" (pgbouncer) URI in production for best results.
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL (Supabase Postgres URI) must be set")
if DATABASE_URL.startswith("http://") or DATABASE_URL.startswith("https://"):
    raise RuntimeError(
        "DATABASE_URL must be a PostgreSQL connection string (postgresql://...), "
        "not an HTTP URL. Go to Supabase → Settings → Database → Connection string → URI."
    )

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
JWT_EXPIRES_MINUTES = int(os.environ.get("JWT_EXPIRES_MINUTES", "720"))

app = FastAPI(title="Gems & Luxury Internal")


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler — returns structured JSON 500. CORS headers are added
    by _CORSEverywhere (outermost wrapper), so do NOT set them here to avoid
    the duplicate-value '*, *' browser rejection."""
    logger.exception("Unhandled error %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


api = APIRouter(prefix="/api")
bearer_scheme = HTTPBearer(auto_error=False)

# ---------- Helpers ----------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def get_base_url() -> str:
    """Get the base URL for the API, from environment or request."""
    return os.environ.get("API_BASE_URL", "https://gems-luxury-backend.onrender.com/api").rstrip("/api")


def parse_utc_datetime(s: str) -> datetime:
    """Parse ISO datetime string to timezone-aware UTC datetime."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "exp": now_utc() + timedelta(minutes=JWT_EXPIRES_MINUTES),
        "iat": now_utc(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> dict:
    if not creds:
        raise HTTPException(401, "Missing token")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"], "is_deleted": {"$ne": True}}, {"_id": 0})
    if not user or not user.get("active", True):
        raise HTTPException(401, "User not found or inactive")
    user.pop("password_hash", None)
    return user


def require_role(*roles: str):
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "Forbidden")
        return user
    return dep


async def log_activity(user_id: str, event_type: str, detail: dict | None = None, item_type: str | None = None, item_id: str | None = None, ip_address: str | None = None, user_name: str | None = None):
    try:
        doc = {
            "id": new_id(),
            "user_id": user_id,
            "event_type": event_type,
            "item_type": item_type,
            "item_id": item_id,
            "detail": detail or {},
            "timestamp": iso(now_utc()),
        }
        if ip_address:
            doc["ip_address"] = ip_address
        if user_name:
            doc["user_name"] = user_name
        await db.activity_logs.insert_one(doc)
    except Exception as _log_err:
        logger.warning("log_activity failed (non-fatal): %s", _log_err)


async def get_settings() -> dict:
    s = await db.admin_settings.find_one({"id": "global"}, {"_id": 0})
    return s or {}


# ---------- Models ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: EmailStr
    name: str
    role: str
    active: bool = True
    created_at: str


class CreateUserIn(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = Field(pattern="^(admin|manager|worker)$")


class UpdateUserIn(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


class GenerateProductIn(BaseModel):
    category: Optional[str] = None
    image_asset_id: Optional[str] = None


class UpdateProductIn(BaseModel):
    name: Optional[str] = None
    short_title: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    sizes: Optional[list[str]] = None
    final_price: Optional[int] = None
    status: Optional[str] = None
    pricing_meta: Optional[dict] = None


class NamingFamilyIn(BaseModel):
    name: str
    words: list[str] = []
    enabled: bool = True


class PricingRulesIn(BaseModel):
    min_price: int
    max_price: int
    currency: str = "USD"
    category_multipliers: dict[str, float] = {}


class CategoryIn(BaseModel):
    name: str
    slug: str
    sizes: list[str] = ["S", "M", "L", "XL"]
    price_multiplier: float = 1.0
    active: bool = True


class SettingsIn(BaseModel):
    idle_timeout_minutes: Optional[int] = None
    warning_seconds: Optional[int] = None
    max_break_minutes: Optional[int] = None
    currency: Optional[str] = None
    features: Optional[dict[str, bool]] = None


class PromptTemplateIn(BaseModel):
    key: str
    name: str
    description: Optional[str] = ""
    model_provider: str = "anthropic"
    model_name: str = "claude-sonnet-4-5-20250929"
    system_prompt: str
    user_prompt_template: str
    enabled: bool = True


class PromptTemplatePatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    enabled: Optional[bool] = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AdminResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8)


# ---------- Auth ----------
@api.post("/auth/login")
async def login(body: LoginIn):
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not user.get("active", True) or not verify_pw(body.password, user.get("password_hash", "")):
        if user:
            await log_activity(user["id"], "login_failed", {"email": body.email})
        raise HTTPException(401, "Invalid credentials")
    token = create_token(user)
    await log_activity(user["id"], "login")
    return {
        "token": token,
        "user": {k: user[k] for k in ("id", "email", "name", "role", "active", "created_at")},
    }


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    await log_activity(user["id"], "logout")
    return {"ok": True}


# ---------- Admin: Users ----------
@api.get("/admin/users")
async def list_users(user: dict = Depends(require_role("admin", "manager"))):
    try:
        users = await db.users.find({"is_deleted": {"$ne": True}}, {"_id": 0, "password_hash": 0}).to_list(1000)
    except Exception as e:
        logger.exception("list_users DB error: %s", e)
        raise HTTPException(503, "Database unavailable, please retry")
    return users


@api.post("/admin/users")
async def create_user(body: CreateUserIn, user: dict = Depends(require_role("admin"))):
    try:
        if await db.users.find_one({"email": body.email.lower()}):
            raise HTTPException(400, "Email exists")
        doc = {
            "id": new_id(),
            "email": body.email.lower(),
            "name": body.name,
            "role": body.role,
            "active": True,
            "password_hash": hash_pw(body.password),
            "created_at": iso(now_utc()),
            "created_by": user["id"],
            "is_deleted": False,
        }
        await db.users.insert_one(doc)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_user DB error: %s", e)
        raise HTTPException(503, "Database unavailable, please retry")
    await log_activity(user["id"], "user_created", {"email": doc["email"], "role": doc["role"]}, "user", doc["id"])
    doc.pop("password_hash")
    doc.pop("_id", None)
    return doc


@api.patch("/admin/users/{user_id}")
async def update_user(user_id: str, body: UpdateUserIn, user: dict = Depends(require_role("admin"))):
    update: dict = {}
    if body.name is not None: update["name"] = body.name
    if body.role is not None: update["role"] = body.role
    if body.active is not None: update["active"] = body.active
    if body.password: update["password_hash"] = hash_pw(body.password)
    update["updated_at"] = iso(now_utc())
    update["updated_by"] = user["id"]
    try:
        res = await db.users.update_one({"id": user_id}, {"$set": update})
    except Exception as e:
        logger.exception("update_user DB error: %s", e)
        raise HTTPException(503, "Database unavailable, please retry")
    if not res.matched_count:
        raise HTTPException(404, "User not found")
    await log_activity(user["id"], "user_updated", {k: v for k, v in update.items() if k != "password_hash"}, "user", user_id)
    return {"ok": True}


@api.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_role("admin"))):
    if user_id == user["id"]:
        raise HTTPException(400, "Cannot delete your own account")
    try:
        target = await db.users.find_one({"id": user_id, "is_deleted": {"$ne": True}})
    except Exception as e:
        logger.exception("delete_user find failed: %s", e)
        raise HTTPException(503, "Database unavailable, please retry")
    if not target:
        raise HTTPException(404, "User not found")
    try:
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"is_deleted": True, "active": False, "deleted_at": iso(now_utc()), "deleted_by": user["id"]}},
        )
    except Exception as e:
        logger.exception("delete_user update failed: %s", e)
        raise HTTPException(503, f"DB write failed [{type(e).__name__}]: {e}")
    await log_activity(user["id"], "user_deleted", {"email": target.get("email")}, "user", user_id)
    return {"ok": True}


# ---------- Attendance ----------
async def _open_attendance(user_id: str) -> Optional[dict]:
    return await db.attendance_logs.find_one({"user_id": user_id, "punch_out": None}, {"_id": 0})


async def _open_break(att_id: str) -> Optional[dict]:
    return await db.break_logs.find_one({"attendance_id": att_id, "end": None}, {"_id": 0})


@api.post("/attendance/punch-in")
async def punch_in(request: Request, user: dict = Depends(get_current_user)):
    if await _open_attendance(user["id"]):
        raise HTTPException(400, "Already punched in")
    now = now_utc()
    doc = {
        "id": new_id(),
        "user_id": user["id"],
        "user_name": user["name"],
        "punch_in": iso(now),
        "last_activity": iso(now),
    }
    await db.attendance_logs.insert_one(doc)
    # Get client IP
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or request.client.host if request.client else None
    await log_activity(user["id"], "punch_in", {}, "attendance", doc["id"], ip_address=client_ip, user_name=user["name"])
    return doc


@api.post("/attendance/punch-out")
async def punch_out(user: dict = Depends(get_current_user)):
    att = await _open_attendance(user["id"])
    if not att:
        raise HTTPException(400, "Not punched in")
    # end any open break
    ob = await _open_break(att["id"])
    if ob:
        now = now_utc()
        mins = int((now - parse_utc_datetime(ob["start"])).total_seconds() // 60)
        await db.break_logs.update_one({"id": ob["id"]}, {"$set": {"end": iso(now), "minutes": mins}})
        await db.attendance_logs.update_one({"id": att["id"]}, {"$inc": {"break_minutes": mins}})
    now = now_utc()
    total = int((now - parse_utc_datetime(att["punch_in"])).total_seconds() // 60)
    await db.attendance_logs.update_one(
        {"id": att["id"]},
        {"$set": {"punch_out": iso(now), "total_minutes": total, "last_activity": iso(now)}},
    )
    await log_activity(user["id"], "punch_out", {"total_minutes": total}, "attendance", att["id"])
    return {"ok": True, "total_minutes": total}


@api.post("/attendance/break/start")
async def break_start(user: dict = Depends(get_current_user)):
    att = await _open_attendance(user["id"])
    if not att:
        raise HTTPException(400, "Not punched in")
    if await _open_break(att["id"]):
        raise HTTPException(400, "Already on break")
    doc = {"id": new_id(), "attendance_id": att["id"], "user_id": user["id"], "start": iso(now_utc()), "end": None}
    await db.break_logs.insert_one(doc)
    await log_activity(user["id"], "break_start", item_type="attendance", item_id=att["id"])
    doc.pop("_id", None)
    return doc


@api.post("/attendance/break/end")
async def break_end(user: dict = Depends(get_current_user)):
    att = await _open_attendance(user["id"])
    if not att:
        raise HTTPException(400, "Not punched in")
    ob = await _open_break(att["id"])
    if not ob:
        raise HTTPException(400, "Not on break")
    now = now_utc()
    mins = max(1, int((now - parse_utc_datetime(ob["start"])).total_seconds() // 60))
    await db.break_logs.update_one({"id": ob["id"]}, {"$set": {"end": iso(now), "minutes": mins}})
    await db.attendance_logs.update_one({"id": att["id"]}, {"$inc": {"break_minutes": mins}, "$set": {"last_activity": iso(now)}})
    await log_activity(user["id"], "break_end", {"minutes": mins}, "attendance", att["id"])
    return {"ok": True, "minutes": mins}


@api.post("/attendance/heartbeat")
async def heartbeat(user: dict = Depends(get_current_user)):
    att = await _open_attendance(user["id"])
    if not att:
        return {"ok": False}
    await db.attendance_logs.update_one({"id": att["id"]}, {"$set": {"last_activity": iso(now_utc())}})
    return {"ok": True}


@api.get("/attendance/me")
async def attendance_me(user: dict = Depends(get_current_user)):
    att = await _open_attendance(user["id"])
    open_break = await _open_break(att["id"]) if att else None
    # today
    today_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    today = await db.attendance_logs.find(
        {"user_id": user["id"], "punch_in": {"$gte": iso(today_start)}}, {"_id": 0}
    ).to_list(100)
    total_today = sum(a.get("total_minutes", 0) for a in today if a.get("punch_out"))
    if att:
        total_today += int((now_utc() - parse_utc_datetime(att["punch_in"])).total_seconds() // 60)
    # products today
    products_today = await db.generated_products.count_documents({
        "generated_by_user_id": user["id"],
        "generated_at": {"$gte": iso(today_start)},
    })
    # idle
    settings = await get_settings()
    idle_timeout = settings.get("idle_timeout_minutes", 60)
    warning_seconds = settings.get("warning_seconds", 300)
    idle_in_seconds = None
    if att and not open_break:
        last = parse_utc_datetime(att["last_activity"])
        elapsed = (now_utc() - last).total_seconds()
        idle_in_seconds = max(0, idle_timeout * 60 - elapsed)
    return {
        "attendance": att,
        "open_break": open_break,
        "total_today_minutes": total_today,
        "products_today": products_today,
        "idle_timeout_minutes": idle_timeout,
        "warning_seconds": warning_seconds,
        "idle_in_seconds": idle_in_seconds,
    }


async def auto_punch_out_sweep():
    """Check all open attendance entries and auto punch out if idle exceeds threshold."""
    settings = await get_settings()
    idle_timeout = settings.get("idle_timeout_minutes", 60)
    cutoff = now_utc() - timedelta(minutes=idle_timeout)
    opens = await db.attendance_logs.find({"punch_out": None}, {"_id": 0}).to_list(1000)
    for att in opens:
        last = parse_utc_datetime(att["last_activity"])
        if last < cutoff:
            # skip if on break
            if await _open_break(att["id"]):
                continue
            total = int((last - parse_utc_datetime(att["punch_in"])).total_seconds() // 60)
            await db.attendance_logs.update_one(
                {"id": att["id"]},
                {"$set": {"punch_out": iso(last), "total_minutes": total, "auto_punched_out": True}},
            )
            await log_activity(att["user_id"], "auto_punch_out", {"idle_minutes": idle_timeout}, "attendance", att["id"])


# ---------- Product Generation ----------
@api.post("/products/generate")
async def generate_product(body: GenerateProductIn, user: dict = Depends(get_current_user)):
    att = await _open_attendance(user["id"])
    if not att and user["role"] == "worker":
        raise HTTPException(400, "Punch in first")

    # category
    category = body.category
    if not category:
        cat_doc = await db.product_categories.find_one({"active": True}, {"_id": 0})
        category = cat_doc["name"] if cat_doc else "Women / Dresses / Occasion"
    cat_doc = await db.product_categories.find_one({"name": category}, {"_id": 0})
    sizes = (cat_doc or {}).get("sizes", ["S", "M", "L", "XL"])

    naming_families = await db.naming_families.find({}, {"_id": 0}).to_list(100)
    pricing = await db.pricing_rules.find_one({"id": "global"}, {"_id": 0}) or {"min_price": 40, "max_price": 150, "currency": "USD"}
    
    # Get CSV export settings
    settings = await db.admin_settings.find_one({"id": "global"}, {"_id": 0}) or {}
    csv_settings = settings.get("csv", {}) or {}
    default_brand = csv_settings.get("default_brand", "Gems & Luxury")

    # pick image if not provided
    image_asset_id = body.image_asset_id
    image_asset = None
    if image_asset_id:
        image_asset = await db.image_assets.find_one({"id": image_asset_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not image_asset:
        image_asset = await db.image_assets.find_one(
            {"status": "available", "is_deleted": {"$ne": True}}, {"_id": 0}
        )
    image_tags = (image_asset or {}).get("tags", [])

    existing = await db.generated_products.find({}, {"_id": 0, "name": 1}).sort("generated_at", -1).to_list(50)
    existing_names = [p["name"] for p in existing]

    try:
        draft = await ai_service.generate_product_draft(
            db=db,
            category=category,
            naming_families=naming_families,
            pricing_rules=pricing,
            size_template=sizes,
            image_tags=image_tags,
            image_description=(image_asset or {}).get("description"),
            existing_names=existing_names,
        )
    except Exception as e:
        logger.exception("AI generate failed: %s", e)
        raise HTTPException(500, f"AI generation failed: {e}")

    doc = {
        "id": new_id(),
        "name": draft["productName"],
        "short_title": draft["shortTitle"],
        "short_description": draft["shortDescription"],
        "full_description": draft["fullDescription"],
        "category": category,
        "tags": draft.get("tags", []),
        "sizes": draft.get("sizes", sizes),
        "final_price": draft["finalPrice"],
        "currency": pricing.get("currency", "USD"),
        # CSV export fields
        "active": True,
        "is_active": True,
        "brand": default_brand,
        "sku": f"{category[:3].upper()}-{new_id()[:8]}",
        "tax_class": csv_settings.get("default_tax_class", "Taxable Goods"),
        "special_price": None,
        "special_price_type": None,
        "special_price_start": None,
        "special_price_end": None,
        "manage_stock": csv_settings.get("default_manage_stock", True),
        "quantity": csv_settings.get("default_stock_quantity", 100),
        "in_stock": csv_settings.get("default_in_stock", True),
        "meta_title": draft["shortTitle"],
        "meta_description": draft["shortDescription"],
        "meta_keywords": draft.get("tags", []).join(", "),
        # Image structure for CSV export
        "base_image_id": (image_asset or {}).get("id"),  # Main image for CSV
        "additional_image_ids": [],  # Refined + variations for CSV
        # Internal tracking fields
        "source_image_id": (image_asset or {}).get("id"),
        "refined_image_id": None,
        "variation_image_1_id": None,
        "variation_image_2_id": None,
        "export_status": "pending",  # pending, approved, exported
        "reviewed_by_admin": False,
        "session_id": status.get("session_id") if status else None,
        "punch_status_at_generation": status.get("status") if status else None,
        # Legacy fields
        "image_asset_id": (image_asset or {}).get("id"),
        "image_variation_ids": [],
        "image_workflow_status": "assigned",  # assigned, refined, variation-created, skipped, completed
        "variation_image_ids": [],  # 2 AI-generated views
        "pricing_meta": draft.get("pricingMeta", {}),
        "status": "draft",
        "generated_by_user_id": user["id"],
        "generated_by_name": user["name"],
        "generated_at": iso(now_utc()),
    }
    try:
        await db.generated_products.insert_one(doc)
    except Exception as e:
        logger.exception("generate_product DB insert failed")
        raise HTTPException(503, f"DB insert failed: {e}")
    # Mark image assigned
    if image_asset:
        try:
            await db.image_assets.update_one(
                {"id": image_asset["id"]},
                {"$set": {"status": "assigned"}, "$inc": {"assigned_count": 1}},
            )
            await db.image_assignments.insert_one({
                "id": new_id(),
                "image_asset_id": image_asset["id"],
                "product_id": doc["id"],
                "user_id": user["id"],
                "assigned_at": iso(now_utc()),
            })
        except Exception as e:
            logger.exception("image assignment failed (non-fatal): %s", e)
    # update activity
    if att:
        try:
            await db.attendance_logs.update_one({"id": att["id"]}, {"$set": {"last_activity": iso(now_utc())}})
        except Exception as e:
            logger.exception("attendance update failed (non-fatal): %s", e)
    await log_activity(user["id"], "product_generated", {"name": doc["name"], "price": doc["final_price"]}, "product", doc["id"])
    doc.pop("_id", None)
    # strip pricing_meta for worker output
    if user["role"] == "worker":
        doc.pop("pricing_meta", None)
    return doc


@api.get("/products")
async def list_products(
    user: dict = Depends(get_current_user),
    mine: bool = Query(False),
    status: Optional[str] = Query(None),
    limit: int = Query(100),
):
    q: dict[str, Any] = {}
    if mine or user["role"] == "worker":
        q["generated_by_user_id"] = user["id"]
    if status:
        q["status"] = status
    projection = {"_id": 0}
    if user["role"] == "worker":
        projection["pricing_meta"] = 0
    items = await db.generated_products.find(q, projection).sort("generated_at", -1).to_list(limit)
    return items


@api.get("/products/{product_id}")
async def get_product(product_id: str, user: dict = Depends(get_current_user)):
    projection = {"_id": 0}
    if user["role"] == "worker":
        projection["pricing_meta"] = 0
    p = await db.generated_products.find_one({"id": product_id}, projection)
    if not p:
        raise HTTPException(404, "Not found")
    if user["role"] == "worker" and p["generated_by_user_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    return p


@api.patch("/products/{product_id}")
async def patch_product(product_id: str, body: UpdateProductIn, user: dict = Depends(get_current_user)):
    existing = await db.generated_products.find_one({"id": product_id}, {"_id": 0, "generated_by_user_id": 1})
    if not existing:
        raise HTTPException(404, "Not found")
    if user["role"] == "worker" and existing.get("generated_by_user_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    payload = body.model_dump()
    # Only admins/managers may edit pricing_meta
    if user["role"] == "worker":
        payload.pop("pricing_meta", None)
    update = {k: v for k, v in payload.items() if v is not None}
    if not update:
        return {"ok": True}
    update["updated_at"] = iso(now_utc())
    update["updated_by"] = user["id"]
    await db.generated_products.update_one({"id": product_id}, {"$set": update})
    await log_activity(user["id"], "product_edited", update, "product", product_id)
    return {"ok": True}


def _slugify(s: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:80]


@api.get("/products/{product_id}/cms-payload")
async def cms_payload(product_id: str, user: dict = Depends(require_role("admin", "manager"))):
    p = await db.generated_products.find_one({"id": product_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Not found")
    backend = os.environ.get("PUBLIC_BACKEND_URL", "")
    image_urls: list[str] = []
    if p.get("image_asset_id"):
        image_urls.append(f"{backend}/api/images/{p['image_asset_id']}/download")
    for vid in p.get("image_variation_ids", []) or []:
        image_urls.append(f"{backend}/api/images/{vid}/download")
    cat_path = (p.get("category") or "").split("/")
    product_type = cat_path[-1].strip() if cat_path else ""
    vendor = "Gems & Luxury"
    body_html = "".join(f"<p>{para.strip()}</p>" for para in (p.get("full_description") or "").split("\n") if para.strip())
    variants = [
        {
            "option1": s,
            "sku": f"GL-{_slugify(p['name'])}-{_slugify(s)}",
            "price": str(p.get("final_price", 0)),
            "currency": p.get("currency", "USD"),
            "inventory_management": None,
        }
        for s in (p.get("sizes") or [])
    ]
    return {
        "handle": _slugify(p["name"]),
        "title": p["name"],
        "short_title": p.get("short_title"),
        "body_html": body_html,
        "vendor": vendor,
        "product_type": product_type,
        "tags": p.get("tags", []),
        "options": ["Size"] if variants else [],
        "variants": variants,
        "images": image_urls,
        "metafields": {
            "ai.pricing_meta": p.get("pricing_meta", {}),
            "ai.generated_by": p.get("generated_by_name"),
            "ai.generated_at": p.get("generated_at"),
            "ai.short_description": p.get("short_description"),
        },
    }


@api.post("/products/{product_id}/export")
async def export_product(product_id: str, user: dict = Depends(get_current_user)):
    await db.generated_products.update_one({"id": product_id}, {"$set": {"status": "exported", "exported_at": iso(now_utc())}})
    await db.export_logs.insert_one({"id": new_id(), "product_id": product_id, "user_id": user["id"], "at": iso(now_utc())})
    await log_activity(user["id"], "product_exported", item_type="product", item_id=product_id)
    return {"ok": True}


# ---------- Naming Families ----------
@api.get("/admin/naming-families")
async def list_families(user: dict = Depends(require_role("admin", "manager"))):
    return await db.naming_families.find({}, {"_id": 0}).to_list(200)


@api.post("/admin/naming-families")
async def create_family(body: NamingFamilyIn, user: dict = Depends(require_role("admin"))):
    doc = {"id": new_id(), "name": body.name, "words": body.words, "enabled": body.enabled,
           "created_at": iso(now_utc()), "created_by": user["id"]}
    await db.naming_families.insert_one(doc)
    doc.pop("_id", None)
    await log_activity(user["id"], "naming_family_created", {"name": body.name}, "naming_family", doc["id"])
    return doc


@api.patch("/admin/naming-families/{fid}")
async def update_family(fid: str, body: NamingFamilyIn, user: dict = Depends(require_role("admin"))):
    await db.naming_families.update_one({"id": fid}, {"$set": {"name": body.name, "words": body.words, "enabled": body.enabled, "updated_at": iso(now_utc()), "updated_by": user["id"]}})
    await log_activity(user["id"], "naming_family_updated", {"name": body.name}, "naming_family", fid)
    return {"ok": True}


# ---------- Pricing ----------
@api.get("/admin/pricing-rules")
async def get_pricing(user: dict = Depends(require_role("admin", "manager"))):
    p = await db.pricing_rules.find_one({"id": "global"}, {"_id": 0})
    return p or {"min_price": 40, "max_price": 150, "currency": "USD", "category_multipliers": {}}


@api.put("/admin/pricing-rules")
async def put_pricing(body: PricingRulesIn, user: dict = Depends(require_role("admin"))):
    doc = {"id": "global", **body.model_dump(), "updated_at": iso(now_utc()), "updated_by": user["id"]}
    await db.pricing_rules.update_one({"id": "global"}, {"$set": doc}, upsert=True)
    await log_activity(user["id"], "pricing_updated", body.model_dump())
    return {"ok": True}


# ---------- Categories ----------
@api.get("/admin/categories")
async def list_categories(user: dict = Depends(get_current_user)):
    return await db.product_categories.find({"active": True}, {"_id": 0}).to_list(200)


@api.post("/admin/categories")
async def create_category(body: CategoryIn, user: dict = Depends(require_role("admin"))):
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc()), "created_by": user["id"]}
    await db.product_categories.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.patch("/admin/categories/{cid}")
async def update_category(cid: str, body: CategoryIn, user: dict = Depends(require_role("admin"))):
    await db.product_categories.update_one({"id": cid}, {"$set": {**body.model_dump(), "updated_at": iso(now_utc())}})
    return {"ok": True}


# ---------- Settings ----------
@api.get("/admin/settings")
async def get_admin_settings(user: dict = Depends(require_role("admin", "manager"))):
    return await get_settings()


@api.patch("/admin/settings")
async def patch_admin_settings(body: SettingsIn, user: dict = Depends(require_role("admin"))):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    update["updated_at"] = iso(now_utc())
    update["updated_by"] = user["id"]
    await db.admin_settings.update_one({"id": "global"}, {"$set": update}, upsert=True)
    await log_activity(user["id"], "settings_updated", update)
    return {"ok": True}


# ---------- Images ----------
@api.post("/admin/images/upload")
async def upload_image(
    file: UploadFile = File(...),
    category: str = Form(""),
    tags: str = Form(""),
    description: str = Form(""),
    user: dict = Depends(require_role("admin", "manager")),
):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    path = storage.build_path(user["id"], file.filename or "image.png")
    try:
        result = await asyncio.to_thread(storage.put_object, path, data, file.content_type or "image/png")
    except Exception as e:
        logger.exception("upload storage failed")
        raise HTTPException(500, f"Storage upload failed: {e}")
    doc = {
        "id": new_id(),
        "storage_path": result["path"],
        "filename": file.filename,
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "category": category or None,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "description": description or None,
        "status": "available",
        "assigned_count": 0,
        "is_deleted": False,
        "uploaded_by": user["id"],
        "uploaded_at": iso(now_utc()),
    }
    try:
        await db.image_assets.insert_one(doc)
    except Exception as e:
        logger.exception("upload DB insert failed")
        raise HTTPException(503, f"DB insert failed: {e}")
    doc.pop("_id", None)
    await log_activity(user["id"], "image_uploaded", {"filename": file.filename}, "image", doc["id"])
    return doc


@api.get("/admin/images")
async def list_images(user: dict = Depends(require_role("admin", "manager")), status: Optional[str] = None):
    q: dict = {"is_deleted": {"$ne": True}}
    if status:
        q["status"] = status
    return await db.image_assets.find(q, {"_id": 0}).sort("uploaded_at", -1).to_list(500)


@api.get("/images/{image_id}/download")
async def download_image(image_id: str, authorization: Optional[str] = Header(None), auth: Optional[str] = Query(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    elif auth:
        token = auth
    if not token:
        raise HTTPException(401, "Missing token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"], "is_deleted": {"$ne": True}, "active": True}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Inactive user")
    asset = await db.image_assets.find_one({"id": image_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not asset:
        # maybe a variation
        var = await db.image_variations.find_one({"id": image_id}, {"_id": 0})
        if not var:
            raise HTTPException(404, "Not found")
        data, ct = await asyncio.to_thread(storage.get_object, var["storage_path"])
        return Response(content=data, media_type=var.get("content_type", ct))
    data, ct = await asyncio.to_thread(storage.get_object, asset["storage_path"])
    return Response(content=data, media_type=asset.get("content_type") or ct)


@api.patch("/admin/images/{image_id}")
async def patch_image(image_id: str, body: dict, user: dict = Depends(require_role("admin", "manager"))):
    allowed = {k: body[k] for k in ("status", "tags", "category", "description") if k in body}
    allowed["updated_at"] = iso(now_utc())
    await db.image_assets.update_one({"id": image_id}, {"$set": allowed})
    return {"ok": True}


@api.post("/admin/images/{image_id}/reset")
async def reset_image(image_id: str, user: dict = Depends(require_role("admin"))):
    """Reset an assigned image back to available status."""
    asset = await db.image_assets.find_one({"id": image_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not asset:
        raise HTTPException(404, "Not found")
    await db.image_assets.update_one(
        {"id": image_id},
        {"$set": {"status": "available", "updated_at": iso(now_utc())}}
    )
    await log_activity(user["id"], "image_reset", {"image_id": image_id}, "image_assets", image_id)
    return {"ok": True}


@api.post("/products/{product_id}/skip-image")
async def skip_product_image(product_id: str, user: dict = Depends(get_current_user)):
    """Skip the assigned image for a product and mark workflow status."""
    product = await db.generated_products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Product not found")
    if product.get("generated_by_user_id") != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not authorized")
    # Reset image status to available
    if product.get("image_asset_id"):
        await db.image_assets.update_one(
            {"id": product["image_asset_id"]},
            {"$set": {"status": "available", "updated_at": iso(now_utc())}}
        )
    # Update product workflow status
    await db.generated_products.update_one(
        {"id": product_id},
        {"$set": {"image_workflow_status": "skipped", "image_asset_id": None, "updated_at": iso(now_utc())}}
    )
    await log_activity(user["id"], "product_image_skipped", {"product_id": product_id}, "generated_products", product_id)
    return {"ok": True}


@api.post("/products/{product_id}/refine-image")
async def refine_product_image(product_id: str, user: dict = Depends(get_current_user)):
    """Refine the assigned image for a product using AI enhancement."""
    product = await db.generated_products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Product not found")
    if product.get("generated_by_user_id") != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not authorized")
    if not product.get("image_asset_id"):
        raise HTTPException(400, "No image assigned to this product")
    
    # Get original image bytes
    asset = await db.image_assets.find_one({"id": product["image_asset_id"]}, {"_id": 0})
    if not asset:
        raise HTTPException(404, "Image asset not found")
    
    try:
        original_bytes_tuple = await asyncio.to_thread(storage.get_object, asset["storage_path"])
        original_bytes = original_bytes_tuple[0]  # Extract bytes from (bytes, mime_type) tuple
    except Exception as e:
        logger.exception("Failed to get original image: %s", e)
        raise HTTPException(500, "Failed to retrieve original image")
    
    # Enhance image
    enhanced_bytes = await ai_service.enhance_image(db, original_bytes)
    if not enhanced_bytes:
        raise HTTPException(500, "Image enhancement failed")
    
    # Store refined image
    storage_path = f"products/{product_id}/refined.png"
    await asyncio.to_thread(storage.put_object, storage_path, enhanced_bytes, "image/png")
    
    # Create image asset record
    refined_id = new_id()
    await db.image_assets.insert_one({
        "id": refined_id,
        "storage_path": storage_path,
        "filename": f"{product_id}_refined.png",
        "status": "assigned",
        "tags": asset.get("tags", []),
        "category": asset.get("category"),
        "description": f"Refined version of {asset.get('description', 'image')}",
        "assigned_count": 0,
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    })
    
    # Update product
    await db.generated_products.update_one(
        {"id": product_id},
        {"$set": {
            "refined_image_id": refined_id,
            "variation_image_1_id": refined_id,  # Also track as first variation for CSV export
            "additional_image_ids": [refined_id],  # Add to additional images for CSV
            "image_workflow_status": "refined",
            "updated_at": iso(now_utc())
        }}
    )
    
    await log_activity(user["id"], "product_image_refined", {"product_id": product_id, "refined_image_id": refined_id}, "generated_products", product_id)
    return {"ok": True, "refined_image_id": refined_id}


@api.post("/products/{product_id}/generate-views")
async def generate_product_views(product_id: str, user: dict = Depends(get_current_user)):
    """Generate 2 AI-derived views from the original image for a product."""
    product = await db.generated_products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Product not found")
    if product.get("generated_by_user_id") != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not authorized")
    
    # Use original or refined image
    source_image_id = product.get("refined_image_id") or product.get("image_asset_id")
    if not source_image_id:
        raise HTTPException(400, "No image available for view generation")
    
    asset = await db.image_assets.find_one({"id": source_image_id}, {"_id": 0})
    if not asset:
        raise HTTPException(404, "Image asset not found")
    
    try:
        original_bytes_tuple = await asyncio.to_thread(storage.get_object, asset["storage_path"])
        original_bytes = original_bytes_tuple[0]  # Extract bytes from (bytes, mime_type) tuple
    except Exception as e:
        logger.exception("Failed to get source image: %s", e)
        raise HTTPException(500, "Failed to retrieve source image")
    
    # Generate 2 alternate views
    views = []
    for i, view in enumerate(["front", "side"], 1):
        view_bytes = await ai_service.generate_alternate_view(db, original_bytes, view)
        if not view_bytes:
            raise HTTPException(500, f"Failed to generate view {i}")
        
        storage_path = f"products/{product_id}/view_{i}_{view}.png"
        await asyncio.to_thread(storage.put_object, storage_path, view_bytes, "image/png")
        
        view_id = new_id()
        await db.image_assets.insert_one({
            "id": view_id,
            "storage_path": storage_path,
            "filename": f"{product_id}_view_{i}_{view}.png",
            "status": "assigned",
            "tags": asset.get("tags", []),
            "category": asset.get("category"),
            "description": f"AI-generated {view} view of {asset.get('description', 'product')}",
            "assigned_count": 0,
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        })
        views.append(view_id)
    
    # Update product
    # Build additional_image_ids: include refined image + variations
    additional_images = []
    if product.get("refined_image_id"):
        additional_images.append(product["refined_image_id"])
    additional_images.extend(views)
    
    await db.generated_products.update_one(
        {"id": product_id},
        {"$set": {
            "variation_image_ids": views,
            "variation_image_1_id": views[0] if len(views) > 0 else None,
            "variation_image_2_id": views[1] if len(views) > 1 else None,
            "additional_image_ids": additional_images,
            "image_workflow_status": "variation-created",
            "updated_at": iso(now_utc())
        }}
    )
    
    await log_activity(user["id"], "product_views_generated", {"product_id": product_id, "view_ids": views}, "generated_products", product_id)
    return {"ok": True, "variation_image_ids": views}


@api.post("/products/{product_id}/complete")
async def complete_product(product_id: str, user: dict = Depends(get_current_user)):
    """Mark a product as completed in the workflow."""
    product = await db.generated_products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Product not found")
    if product.get("generated_by_user_id") != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not authorized")
    
    await db.generated_products.update_one(
        {"id": product_id},
        {"$set": {
            "image_workflow_status": "completed",
            "status": "completed",
            "updated_at": iso(now_utc())
        }}
    )
    
    await log_activity(user["id"], "product_completed", {"product_id": product_id}, "generated_products", product_id)
    return {"ok": True}


@api.get("/products/export/csv")
async def export_products_csv(user: dict = Depends(get_current_user)):
    """Export products as CSV in Gems & Luxury import format."""
    # Get products to export - filter by export_status and user role
    if user["role"] == "admin":
        # Admin can export all approved products
        products = await db.generated_products.find(
            {"export_status": "approved"},
            {"_id": 0}
        ).to_list(length=None)
    else:
        # Workers can only export their own approved products
        products = await db.generated_products.find(
            {"export_status": "approved", "generated_by_user_id": user["id"]},
            {"_id": 0}
        ).to_list(length=None)
    
    if not products:
        raise HTTPException(404, "No approved products to export")
    
    # Build CSV headers
    headers = [
        "Name",
        "SKU",
        "description",
        "short_description",
        "Active",
        "is_active",
        "Brand",
        "categories",
        "Tax Class",
        "Tags",
        "Price",
        "Special Price",
        "Special Price Type",
        "Special Price Start",
        "Special Price End",
        "Manage Stock",
        "Quantity",
        "In Stock",
        "Base Image",
        "Additional Images",
        "meta_title",
        "meta_description",
        "meta_keywords"
    ]
    
    # Build CSV rows
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    
    for p in products:
        # Get image URLs
        base_image_url = ""
        if p.get("base_image_id"):
            base_image_url = f"{get_base_url()}/images/{p['base_image_id']}"
        
        additional_image_urls = []
        for img_id in p.get("additional_image_ids", []):
            additional_image_urls.append(f"{get_base_url()}/images/{img_id}")
        additional_images = ",".join(additional_image_urls)
        
        row = [
            p.get("name", ""),
            p.get("sku", ""),
            p.get("full_description", ""),
            p.get("short_description", ""),
            "yes" if p.get("active", True) else "no",
            "yes" if p.get("is_active", True) else "no",
            p.get("brand", "Gems & Luxury"),
            p.get("category", ""),
            p.get("tax_class", "Taxable Goods"),
            ",".join(p.get("tags", [])),
            p.get("final_price", ""),
            p.get("special_price", ""),
            p.get("special_price_type", ""),
            p.get("special_price_start", ""),
            p.get("special_price_end", ""),
            "yes" if p.get("manage_stock", True) else "no",
            p.get("quantity", 100),
            "yes" if p.get("in_stock", True) else "no",
            base_image_url,
            additional_images,
            p.get("meta_title", ""),
            p.get("meta_description", ""),
            p.get("meta_keywords", "")
        ]
        writer.writerow(row)
    
    # Mark products as exported
    product_ids = [p["id"] for p in products]
    await db.generated_products.update_many(
        {"id": {"$in": product_ids}},
        {"$set": {"export_status": "exported", "exported_at": iso(now_utc())}}
    )
    
    await log_activity(user["id"], "products_exported_csv", {"count": len(products)}, "generated_products")
    
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products_export.csv"}
    )


@api.post("/products/{product_id}/approve")
async def approve_product(product_id: str, user: dict = Depends(require_role("admin"))):
    """Admin approves a product for export."""
    product = await db.generated_products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Product not found")
    
    await db.generated_products.update_one(
        {"id": product_id},
        {"$set": {
            "export_status": "approved",
            "reviewed_by_admin": True,
            "updated_at": iso(now_utc())
        }}
    )
    
    await log_activity(user["id"], "product_approved", {"product_id": product_id}, "generated_products", product_id)
    return {"ok": True}


@api.post("/products/approve-batch")
async def approve_products_batch(body: dict, user: dict = Depends(require_role("admin"))):
    """Admin approves multiple products for export."""
    product_ids = body.get("product_ids", [])
    if not product_ids:
        raise HTTPException(400, "No product IDs provided")
    
    await db.generated_products.update_many(
        {"id": {"$in": product_ids}},
        {"$set": {
            "export_status": "approved",
            "reviewed_by_admin": True,
            "updated_at": iso(now_utc())
        }}
    )
    
    await log_activity(user["id"], "products_approved_batch", {"count": len(product_ids)}, "generated_products")
    return {"ok": True, "count": len(product_ids)}


@api.post("/products/reject-batch")
async def reject_products_batch(body: dict, user: dict = Depends(require_role("admin"))):
    """Admin rejects multiple products from export."""
    product_ids = body.get("product_ids", [])
    if not product_ids:
        raise HTTPException(400, "No product IDs provided")
    
    await db.generated_products.update_many(
        {"id": {"$in": product_ids}},
        {"$set": {
            "export_status": "rejected",
            "reviewed_by_admin": True,
            "updated_at": iso(now_utc())
        }}
    )
    
    await log_activity(user["id"], "products_rejected_batch", {"count": len(product_ids)}, "generated_products")
    return {"ok": True, "count": len(product_ids)}


@api.delete("/admin/images/{image_id}")
async def delete_image(image_id: str, user: dict = Depends(require_role("admin", "manager"))):
    asset = await db.image_assets.find_one({"id": image_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not asset:
        raise HTTPException(404, "Not found")
    # Delete from storage
    try:
        await asyncio.to_thread(storage.delete_object, asset["storage_path"])
    except Exception as e:
        logger.exception("storage delete failed (non-fatal): %s", e)
    # Mark as deleted in DB
    await db.image_assets.update_one({"id": image_id}, {"$set": {"is_deleted": True, "deleted_at": iso(now_utc()), "deleted_by": user["id"]}})
    await log_activity(user["id"], "image_deleted", {"filename": asset.get("filename")}, "image", image_id)
    return {"ok": True}


@api.post("/admin/images/upload-bulk")
async def upload_images_bulk(
    files: list[UploadFile] = File(...),
    category: str = Form(""),
    tags: str = Form(""),
    user: dict = Depends(require_role("admin", "manager")),
):
    out: list[dict] = []
    errors: list[dict] = []
    for f in files:
        try:
            data = await f.read()
            if not data:
                errors.append({"filename": f.filename, "error": "empty"})
                continue
            path = storage.build_path(user["id"], f.filename or "image.png")
            result = await asyncio.to_thread(storage.put_object, path, data, f.content_type or "image/png")
            doc = {
                "id": new_id(),
                "storage_path": result["path"],
                "filename": f.filename,
                "content_type": f.content_type,
                "size": result.get("size", len(data)),
                "category": category or None,
                "tags": [t.strip() for t in tags.split(",") if t.strip()],
                "status": "available",
                "assigned_count": 0,
                "is_deleted": False,
                "uploaded_by": user["id"],
                "uploaded_at": iso(now_utc()),
            }
            try:
                await db.image_assets.insert_one(doc)
            except Exception as e:
                logger.exception("bulk upload DB insert failed for file %s: %s", f.filename, e)
                errors.append({"filename": f.filename, "error": f"DB insert failed: {e}"})
                continue
            doc.pop("_id", None)
            out.append(doc)
            await log_activity(user["id"], "image_uploaded", {"filename": f.filename, "bulk": True}, "image", doc["id"])
        except Exception as e:
            logger.exception("bulk upload entry failed")
            errors.append({"filename": f.filename, "error": str(e)})
    return {"uploaded": out, "errors": errors, "count": len(out)}


@api.get("/admin/images/{image_id}/variations")
async def list_variations(image_id: str, user: dict = Depends(require_role("admin", "manager"))):
    asset = await db.image_assets.find_one({"id": image_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not asset:
        raise HTTPException(404, "Not found")
    variations = await db.image_variations.find({"source_image_id": image_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"source": asset, "variations": variations}


@api.post("/admin/images/{image_id}/enhance")
async def enhance_image_ep(image_id: str, user: dict = Depends(require_role("admin", "manager"))):
    asset = await db.image_assets.find_one({"id": image_id}, {"_id": 0})
    if not asset:
        raise HTTPException(404, "Not found")
    try:
        data, _ = await asyncio.to_thread(storage.get_object, asset["storage_path"])
    except Exception as e:
        raise HTTPException(500, f"Could not load image: {e}")
    result = await ai_service.enhance_image(db, data)
    if not result:
        raise HTTPException(500, "Enhance failed — check GEMINI_API_KEY")
    path = storage.build_path(user["id"], f"enhanced-{asset.get('filename') or 'x.png'}", kind="variations")
    try:
        await asyncio.to_thread(storage.put_object, path, result, "image/png")
    except Exception as e:
        raise HTTPException(500, f"Storage error: {e}")
    doc = {"id": new_id(), "source_image_id": image_id, "storage_path": path,
           "content_type": "image/png", "kind": "enhanced",
           "created_by": user["id"], "created_at": iso(now_utc())}
    try:
        await db.image_variations.insert_one(doc)
    except Exception as e:
        raise HTTPException(503, f"DB insert failed: {e}")
    doc.pop("_id", None)
    await log_activity(user["id"], "image_enhanced", {"source": image_id}, "image_variation", doc["id"])
    return doc


@api.post("/admin/images/{image_id}/alternates")
async def generate_alternates(image_id: str, user: dict = Depends(require_role("admin", "manager"))):
    asset = await db.image_assets.find_one({"id": image_id}, {"_id": 0})
    if not asset:
        raise HTTPException(404, "Not found")
    try:
        data, _ = await asyncio.to_thread(storage.get_object, asset["storage_path"])
    except Exception as e:
        raise HTTPException(500, f"Could not load image: {e}")
    results = []
    for view in ["three-quarter angle", "back view"]:
        out = await ai_service.generate_alternate_view(db, data, view)
        if not out:
            continue
        path = storage.build_path(user["id"], f"alt-{view.replace(' ', '-')}.png", kind="variations")
        try:
            await asyncio.to_thread(storage.put_object, path, out, "image/png")
        except Exception as e:
            logger.exception("alternates storage failed for view %s: %s", view, e)
            continue
        doc = {"id": new_id(), "source_image_id": image_id, "storage_path": path,
               "content_type": "image/png", "kind": "alternate", "view": view,
               "created_by": user["id"], "created_at": iso(now_utc())}
        try:
            await db.image_variations.insert_one(doc)
        except Exception as e:
            logger.exception("alternates DB insert failed: %s", e)
            continue
        doc.pop("_id", None)
        results.append(doc)
    await log_activity(user["id"], "image_alternates", {"count": len(results)}, "image", image_id)
    return {"variations": results}


class GenerateImageIn(BaseModel):
    prompt: str
    category: Optional[str] = None


class RegenerateImageIn(BaseModel):
    instruction: Optional[str] = None


@api.post("/admin/images/generate")
async def generate_image_ep(body: GenerateImageIn, user: dict = Depends(require_role("admin", "manager"))):
    """Generate a new product image from a text prompt using HuggingFace FLUX (free)."""
    result = await ai_service.generate_image_from_prompt(db, body.prompt)
    if not result:
        raise HTTPException(500, "Image generation failed — check HUGGINGFACE_API_KEY or model availability")
    path = storage.build_path(user["id"], "generated.png", kind="generated")
    try:
        await asyncio.to_thread(storage.put_object, path, result, "image/png")
    except Exception as e:
        logger.exception("generate_image storage failed")
        raise HTTPException(500, f"Storage error: {e}")
    doc = {
        "id": new_id(),
        "storage_path": path,
        "filename": "generated.png",
        "content_type": "image/png",
        "size": len(result),
        "category": body.category,
        "tags": ["generated", "ai", "huggingface"],
        "description": body.prompt[:200],
        "status": "available",
        "assigned_count": 0,
        "is_deleted": False,
        "uploaded_by": user["id"],
        "uploaded_at": iso(now_utc()),
        "source": "ai_generated",
    }
    try:
        await db.image_assets.insert_one(doc)
    except Exception as e:
        logger.exception("generate_image DB insert failed")
        raise HTTPException(503, f"DB insert failed: {e}")
    doc.pop("_id", None)
    await log_activity(user["id"], "image_generated", {"prompt": body.prompt[:100]}, "image", doc["id"])
    return doc


@api.post("/admin/images/{image_id}/regenerate")
async def regenerate_image_ep(image_id: str, body: RegenerateImageIn, user: dict = Depends(require_role("admin", "manager"))):
    """Regenerate a variation of an existing image using HuggingFace instruct-pix2pix (free)."""
    asset = await db.image_assets.find_one({"id": image_id, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not asset:
        raise HTTPException(404, "Not found")
    try:
        data, _ = await asyncio.to_thread(storage.get_object, asset["storage_path"])
    except Exception as e:
        raise HTTPException(500, f"Could not load source image: {e}")
    result = await ai_service.regenerate_image_variation(db, data, body.instruction or "")
    if not result:
        raise HTTPException(500, "Regeneration failed — check HUGGINGFACE_API_KEY or model availability")
    path = storage.build_path(user["id"], f"regen-{asset.get('filename', 'image.png')}", kind="variations")
    try:
        await asyncio.to_thread(storage.put_object, path, result, "image/png")
    except Exception as e:
        logger.exception("regenerate_image storage failed")
        raise HTTPException(500, f"Storage error: {e}")
    doc = {
        "id": new_id(),
        "source_image_id": image_id,
        "storage_path": path,
        "content_type": "image/png",
        "kind": "regenerated",
        "instruction": body.instruction,
        "created_by": user["id"],
        "created_at": iso(now_utc()),
    }
    try:
        await db.image_variations.insert_one(doc)
    except Exception as e:
        logger.exception("regenerate_image DB insert failed")
        raise HTTPException(503, f"DB insert failed: {e}")
    doc.pop("_id", None)
    await log_activity(user["id"], "image_regenerated", {"source": image_id, "instruction": body.instruction}, "image_variation", doc["id"])
    return doc


# ---------- Admin dashboard ----------
@api.get("/admin/dashboard/stats")
async def dashboard_stats(user: dict = Depends(require_role("admin", "manager"))):
    today = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    week = today - timedelta(days=7)
    all_users = await db.users.count_documents({"is_deleted": {"$ne": True}, "active": True})
    open_atts = await db.attendance_logs.find({"punch_out": None}, {"_id": 0}).to_list(500)
    active_users = len(open_atts)
    on_break = 0
    idle = 0
    settings = await get_settings()
    idle_cutoff = now_utc() - timedelta(minutes=settings.get("idle_timeout_minutes", 60))
    if open_atts:
        att_ids = [a["id"] for a in open_atts]
        breaks = await db.break_logs.find({"attendance_id": {"$in": att_ids}, "end": None}, {"_id": 0}).to_list(1000)
        on_break_set = {b["attendance_id"] for b in breaks}
        on_break = len(on_break_set)
        for a in open_atts:
            if a["id"] in on_break_set:
                continue
            if parse_utc_datetime(a["last_activity"]) < idle_cutoff:
                idle += 1
    products_today = await db.generated_products.count_documents({"generated_at": {"$gte": iso(today)}})
    products_week = await db.generated_products.count_documents({"generated_at": {"$gte": iso(week)}})
    available_images = await db.image_assets.count_documents({"status": "available", "is_deleted": {"$ne": True}})
    total_products = await db.generated_products.count_documents({})
    return {
        "users_active": all_users,
        "punched_in": active_users,
        "on_break": on_break,
        "idle": idle,
        "products_today": products_today,
        "products_week": products_week,
        "available_images": available_images,
        "total_products": total_products,
    }


@api.get("/admin/dashboard/live-users")
async def live_users(user: dict = Depends(require_role("admin", "manager"))):
    open_atts = await db.attendance_logs.find({"punch_out": None}, {"_id": 0}).to_list(500)
    settings = await get_settings()
    idle_cutoff = now_utc() - timedelta(minutes=settings.get("idle_timeout_minutes", 60))
    on_break_set: set[str] = set()
    if open_atts:
        att_ids = [a["id"] for a in open_atts]
        breaks = await db.break_logs.find({"attendance_id": {"$in": att_ids}, "end": None}, {"_id": 0}).to_list(1000)
        on_break_set = {b["attendance_id"] for b in breaks}
    out = []
    for a in open_atts:
        state = "on_break" if a["id"] in on_break_set else ("idle" if parse_utc_datetime(a["last_activity"]) < idle_cutoff else "active")
        out.append({"user_id": a["user_id"], "user_name": a["user_name"], "state": state,
                    "punch_in": a["punch_in"], "last_activity": a["last_activity"], "attendance_id": a["id"]})
    return out


@api.get("/admin/attendance")
async def admin_attendance(user: dict = Depends(require_role("admin", "manager"))):
    return await db.attendance_logs.find({}, {"_id": 0}).sort("punch_in", -1).to_list(300)


@api.post("/admin/attendance/{att_id}/force-punch-out")
async def force_punch_out(att_id: str, user: dict = Depends(require_role("admin"))):
    att = await db.attendance_logs.find_one({"id": att_id}, {"_id": 0})
    if not att or att.get("punch_out"):
        raise HTTPException(400, "Not an open session")
    now = now_utc()
    total = int((now - parse_utc_datetime(att["punch_in"])).total_seconds() // 60)
    await db.attendance_logs.update_one({"id": att_id}, {"$set": {"punch_out": iso(now), "total_minutes": total, "force_out_by": user["id"]}})
    await log_activity(user["id"], "force_punch_out", {"target_user": att["user_id"]}, "attendance", att_id)
    return {"ok": True}


@api.get("/admin/settings/ai")
async def get_ai_settings(user: dict = Depends(require_role("admin"))):
    settings = await db.admin_settings.find_one({"id": "global"}, {"_id": 0})
    ai_settings = settings.get("ai", {}) if settings else {}
    return ai_settings


@api.patch("/admin/settings/ai")
async def update_ai_settings(body: dict, user: dict = Depends(require_role("admin"))):
    allowed = {
        "text_provider": body.get("text_provider"),
        "image_provider": body.get("image_provider"),
        "openrouter_model": body.get("openrouter_model"),
        "groq_model": body.get("groq_model"),
        "anthropic_api_key": body.get("anthropic_api_key", ""),
        "gemini_api_key": body.get("gemini_api_key", ""),
        "huggingface_api_key": body.get("huggingface_api_key", ""),
        "openrouter_api_key": body.get("openrouter_api_key", ""),
        "groq_api_key": body.get("groq_api_key", ""),
    }
    update = {k: v for k, v in allowed.items() if v is not None}
    if not update:
        return {"ok": True}
    await db.admin_settings.update_one(
        {"id": "global"},
        {"$set": {"ai": update, "updated_at": iso(now_utc())}},
        upsert=True
    )
    await log_activity(user["id"], "ai_settings_updated", {"fields": list(update.keys())}, "settings", "global")
    return {"ok": True}


@api.get("/admin/activity-logs")
async def activity_logs(
    user: dict = Depends(require_role("admin", "manager")),
    limit: int = Query(200, ge=1, le=1000),
    event_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None),
):
    """Get activity logs with filtering options. Returns user-friendly data."""
    query: dict = {}
    if event_type:
        query["event_type"] = event_type
    if user_id:
        query["user_id"] = user_id
    if item_type:
        query["item_type"] = item_type
    logs = await db.activity_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    # Enrich with user names if missing
    user_ids_to_fetch = [log["user_id"] for log in logs if log.get("user_id") and not log.get("user_name")]
    if user_ids_to_fetch:
        users = await db.users.find({"id": {"$in": user_ids_to_fetch}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(user_ids_to_fetch))
        user_map = {u["id"]: u.get("name") for u in users}
        for log in logs:
            if log.get("user_id") and not log.get("user_name"):
                log["user_name"] = user_map.get(log["user_id"], log["user_id"])
    return logs


# ---------- Prompt templates ----------
@api.get("/admin/prompts")
async def list_prompts(user: dict = Depends(require_role("admin", "manager"))):
    return await db.prompt_templates.find({}, {"_id": 0}).sort("key", 1).to_list(100)


@api.post("/admin/prompts")
async def create_prompt(body: PromptTemplateIn, user: dict = Depends(require_role("admin"))):
    if await db.prompt_templates.find_one({"key": body.key}):
        raise HTTPException(400, "Prompt key already exists")
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc()), "created_by": user["id"]}
    await db.prompt_templates.insert_one(doc)
    doc.pop("_id", None)
    await log_activity(user["id"], "prompt_created", {"key": body.key}, "prompt", doc["id"])
    return doc


@api.patch("/admin/prompts/{prompt_id}")
async def patch_prompt(prompt_id: str, body: PromptTemplatePatch, user: dict = Depends(require_role("admin"))):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update:
        return {"ok": True}
    update["updated_at"] = iso(now_utc())
    update["updated_by"] = user["id"]
    res = await db.prompt_templates.update_one({"id": prompt_id}, {"$set": update})
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    await log_activity(user["id"], "prompt_updated", update, "prompt", prompt_id)
    return {"ok": True}


# ---------- Password management ----------
@api.post("/auth/change-password")
async def change_password(body: ChangePasswordIn, user: dict = Depends(get_current_user)):
    full = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not full or not verify_pw(body.current_password, full.get("password_hash", "")):
        raise HTTPException(400, "Current password is incorrect")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_pw(body.new_password), "password_changed_at": iso(now_utc())}},
    )
    await log_activity(user["id"], "password_changed")
    return {"ok": True}


@api.post("/admin/users/{user_id}/reset-password")
async def admin_reset_password(user_id: str, body: AdminResetPasswordIn, user: dict = Depends(require_role("admin"))):
    try:
        target = await db.users.find_one({"id": user_id, "is_deleted": {"$ne": True}})
    except Exception as e:
        logger.exception("reset-password find failed: %s", e)
        raise HTTPException(500, "Database error")
    if not target:
        raise HTTPException(404, "User not found")
    try:
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"password_hash": hash_pw(body.new_password), "password_reset_at": iso(now_utc()), "password_reset_by": user["id"]}},
        )
        await log_activity(user["id"], "admin_password_reset", {"target_user_id": user_id, "target_email": target.get("email")}, "user", user_id)
    except Exception as e:
        logger.exception("reset-password update failed: %s", e)
        raise HTTPException(500, "Database error")
    return {"ok": True}


# ---------- Reports / Timesheet Data ----------
@api.get("/admin/reports/timesheet")
async def timesheet_data(
    user: dict = Depends(require_role("admin", "manager")),
    days: int = Query(7, ge=1, le=90),
    user_id: Optional[str] = Query(None),
):
    """Get timesheet data for the last N days, optionally for a single user.
    
    PDF generation is now handled client-side. This endpoint returns JSON data
    that the frontend can use to generate PDFs using jspdf or similar.
    """
    from collections import defaultdict

    end = now_utc()
    start = end - timedelta(days=days)
    q: dict = {"punch_in": {"$gte": iso(start)}}
    if user_id:
        q["user_id"] = user_id
    rows = await db.attendance_logs.find(q, {"_id": 0}).sort("punch_in", 1).to_list(2000)

    # product counts per (user, day)
    products = await db.generated_products.find(
        {"generated_at": {"$gte": iso(start)}}, {"_id": 0, "generated_by_user_id": 1, "generated_at": 1}
    ).to_list(5000)
    pcount: dict[tuple[str, str], int] = defaultdict(int)
    for p in products:
        d = p["generated_at"][:10]
        pcount[(p["generated_by_user_id"], d)] += 1

    # aggregated totals
    agg: dict[str, dict] = defaultdict(lambda: {"name": "", "minutes": 0, "breaks": 0, "products": 0, "days": set()})
    for r in rows:
        a = agg[r["user_id"]]
        a["name"] = r["user_name"]
        mins = r.get("total_minutes") or (
            int((now_utc() - parse_utc_datetime(r["punch_in"])).total_seconds() // 60) if not r.get("punch_out") else 0
        )
        a["minutes"] += mins
        a["breaks"] += r.get("break_minutes", 0)
        a["days"].add(r["punch_in"][:10])
    for uid, a in agg.items():
        total_p = await db.generated_products.count_documents({"generated_by_user_id": uid, "generated_at": {"$gte": iso(start)}})
        a["products"] = total_p

    # Convert sets to lists for JSON serialization
    agg_serializable = {}
    for uid, a in agg.items():
        agg_serializable[uid] = {
            "name": a["name"],
            "minutes": a["minutes"],
            "breaks": a["breaks"],
            "products": a["products"],
            "days": list(a["days"]),
        }

    # Build per-day detail with product counts
    detail = []
    for r in rows:
        pin = parse_utc_datetime(r["punch_in"])
        pout = parse_utc_datetime(r["punch_out"]) if r.get("punch_out") else None
        mins = r.get("total_minutes") or (int((now_utc() - pin).total_seconds() // 60) if not pout else 0)
        hours = f"{mins // 60}h {mins % 60:02d}m"
        detail.append({
            "user_name": r["user_name"],
            "date": pin.strftime("%Y-%m-%d"),
            "punch_in": pin.strftime("%H:%M"),
            "punch_out": pout.strftime("%H:%M") if pout else "open",
            "hours": hours,
            "break_minutes": r.get("break_minutes", 0),
            "products": pcount.get((r["user_id"], r["punch_in"][:10]), 0),
            "status": "auto" if r.get("auto_punched_out") else ("open" if not pout else "closed"),
        })

    await log_activity(user["id"], "timesheet_data_exported", {"days": days, "user_id": user_id, "rows": len(rows)})
    
    return {
        "title": "Gems & Luxury — Timesheet",
        "date_range": {
            "start": iso(start),
            "end": iso(end),
            "days": days,
        },
        "generated_at": iso(end),
        "summary_by_worker": agg_serializable,
        "daily_detail": detail,
    }


# ---------- Seed ----------
async def seed():
    # admin
    try:
        if not await db.users.find_one({"email": "admin@gemsandluxury.com"}):
            await db.users.insert_one({
                "id": new_id(), "email": "admin@gemsandluxury.com", "name": "Gems Admin",
                "role": "admin", "active": True, "password_hash": hash_pw("Admin@123"),
                "created_at": iso(now_utc()), "is_deleted": False,
            })
            logger.info("seeded admin")
    except Exception as e:
        logger.exception("seed admin failed: %s", e)
    try:
        if not await db.users.find_one({"email": "worker@gemsandluxury.com"}):
            await db.users.insert_one({
                "id": new_id(), "email": "worker@gemsandluxury.com", "name": "Amara Worker",
                "role": "worker", "active": True, "password_hash": hash_pw("Worker@123"),
                "created_at": iso(now_utc()), "is_deleted": False,
            })
            logger.info("seeded worker")
    except Exception as e:
        logger.exception("seed worker failed: %s", e)
    # settings
    try:
        if not await db.admin_settings.find_one({"id": "global"}):
            await db.admin_settings.insert_one({
                "id": "global",
                "idle_timeout_minutes": 60,
                "warning_seconds": 300,
                "max_break_minutes": 30,
                "currency": "USD",
                "features": {"ai_images": True, "alternates": True, "admin_pricing_reveal": True},
                "ai": {
                    "text_provider": "groq",  # anthropic, huggingface, openrouter, groq
                    "image_provider": "huggingface",  # huggingface, gemini
                    "openrouter_model": "meta-llama/llama-3-8b-instruct:free",
                    "groq_model": "llama3-8b-8192",
                    "anthropic_api_key": "",
                    "gemini_api_key": "",
                    "huggingface_api_key": "",
                    "openrouter_api_key": "",
                    "groq_api_key": "",
                },
                "created_at": iso(now_utc()),
            })
    except Exception as e:
        logger.exception("seed settings failed: %s", e)
    # pricing
    try:
        if not await db.pricing_rules.find_one({"id": "global"}):
            await db.pricing_rules.insert_one({
                "id": "global", "min_price": 40, "max_price": 150, "currency": "USD",
                "category_multipliers": {
                    "Women / Dresses / Occasion": 1.1,
                    "Women / Gowns / Ceremony": 1.25,
                    "Men / Agbada": 1.2,
                    "Accessories / Headwrap": 0.6,
                },
                "created_at": iso(now_utc()),
            })
    except Exception as e:
        logger.exception("seed pricing failed: %s", e)
    # categories
    try:
        if await db.product_categories.count_documents({}) == 0:
            cats = [
                ("Women / Dresses / Occasion", "women-dresses-occasion", ["XS","S","M","L","XL"], 1.10),
                ("Women / Gowns / Ceremony", "women-gowns-ceremony", ["S","M","L","XL","XXL"], 1.25),
                ("Women / Kaftan", "women-kaftan", ["S","M","L","XL"], 1.00),
                ("Men / Agbada", "men-agbada", ["M","L","XL","XXL"], 1.20),
                ("Men / Dashiki", "men-dashiki", ["S","M","L","XL","XXL"], 0.9),
                ("Accessories / Headwrap", "accessories-headwrap", ["One Size"], 0.6),
            ]
            for n, s, sz, m in cats:
                await db.product_categories.insert_one({
                    "id": new_id(), "name": n, "slug": s, "sizes": sz, "price_multiplier": m,
                    "active": True, "created_at": iso(now_utc()),
                })
    except Exception as e:
        logger.exception("seed categories failed: %s", e)
    # naming families
    try:
        if await db.naming_families.count_documents({}) == 0:
            fams = [
                ("Ankara", ["Ankara", "Print", "Heritage", "Motif", "Weave"]),
                ("Royal", ["Royal", "Regal", "Noble", "Crown", "Sovereign"]),
                ("Luxury", ["Luxury", "Premium", "Opulent", "Prestige", "Elite"]),
                ("Heritage", ["Heritage", "Legacy", "Origin", "Ancestral", "Tribal"]),
                ("Silk & Velvet", ["Silk", "Silky", "Velvet", "Satin", "Cashmere"]),
                ("Couture", ["Couture", "Atelier", "Tailored", "Bespoke", "Haute"]),
                ("Grace", ["Grace", "Aura", "Poise", "Radiance", "Bloom"]),
                ("Gold & Afro-luxury", ["Gold", "Gilded", "Afro", "Sunburst", "Amber"]),
                ("Ceremony & Statement", ["Ceremony", "Gala", "Statement", "Ovation", "Moment"]),
            ]
            for n, w in fams:
                await db.naming_families.insert_one({
                    "id": new_id(), "name": n, "words": w, "enabled": True,
                    "created_at": iso(now_utc()),
                })
    except Exception as e:
        logger.exception("seed naming families failed: %s", e)
    # prompt templates
    try:
        if await db.prompt_templates.count_documents({}) == 0:
            for tpl in ai_service.DEFAULT_PROMPTS:
                await db.prompt_templates.insert_one({
                    "id": new_id(), **tpl,
                    "created_at": iso(now_utc()),
                })
            logger.info("seeded prompt templates")
    except Exception as e:
        logger.exception("seed prompt templates failed: %s", e)
    logger.info("seed complete")


# ---------- Raw ASGI CORS middleware ----------
class _CORSEverywhere:
    """Inject CORS headers on every HTTP response at the raw ASGI level.

    This runs below FastAPI's exception handler so it adds headers even when
    uvicorn catches an unhandled exception and sends a bare 500 response.
    """
    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if scope.get("method") == "OPTIONS":
            headers = [
                (b"access-control-allow-origin", b"*"),
                (b"access-control-allow-methods", b"GET, POST, PUT, PATCH, DELETE, OPTIONS"),
                (b"access-control-allow-headers", b"authorization, content-type, accept"),
                (b"access-control-max-age", b"86400"),
            ]
            await send({"type": "http.response.start", "status": 200, "headers": headers})
            await send({"type": "http.response.body", "body": b""})
            return

        async def _send_cors(message):
            if message["type"] == "http.response.start":
                hdrs = list(message.get("headers", []))
                existing = {k.lower() for k, _ in hdrs}
                if b"access-control-allow-origin" not in existing:
                    hdrs.append((b"access-control-allow-origin", b"*"))
                if b"access-control-allow-headers" not in existing:
                    hdrs.append((b"access-control-allow-headers", b"authorization, content-type, accept"))
                message = {**message, "headers": hdrs}
            await send(message)

        await self._app(scope, receive, _send_cors)


# ---------- App ----------
app.include_router(api)


_scheduler: AsyncIOScheduler | None = None


@app.on_event("startup")
async def on_start():
    global _scheduler
    await init_pool(DATABASE_URL)
    await seed()
    try:
        _scheduler = AsyncIOScheduler(timezone="UTC")
        _scheduler.add_job(auto_punch_out_sweep, "interval", minutes=2, id="auto_punch_out", coalesce=True, max_instances=1)
        _scheduler.start()
        logger.info("scheduler started — auto punch-out every 2m")
    except Exception as e:
        logger.warning("scheduler init failed: %s", e)


@app.on_event("shutdown")
async def on_stop():
    global _scheduler
    if _scheduler:
        try: _scheduler.shutdown(wait=False)
        except Exception: pass
    await close_pool()


@app.get("/health")
async def health() -> dict:
    db_status = await check_db()
    return {"status": "ok", "deploy_version": "v7-critical-fixes", **db_status}


# Wrap the ENTIRE FastAPI stack (including Starlette's ServerErrorMiddleware)
# so CORS headers appear on every response — including raw 500s.
app = _CORSEverywhere(app)
