"""Gems & Luxury — internal staff platform backend."""
from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, Query, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import storage
import ai_service

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("gems")

# ---------- DB ----------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
JWT_EXPIRES_MINUTES = int(os.environ.get("JWT_EXPIRES_MINUTES", "720"))

app = FastAPI(title="Gems & Luxury Internal")
api = APIRouter(prefix="/api")
bearer_scheme = HTTPBearer(auto_error=False)

# ---------- Helpers ----------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


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


async def log_activity(user_id: str, event_type: str, detail: dict | None = None, item_type: str | None = None, item_id: str | None = None):
    await db.activity_logs.insert_one({
        "id": new_id(),
        "user_id": user_id,
        "event_type": event_type,
        "item_type": item_type,
        "item_id": item_id,
        "detail": detail or {},
        "timestamp": iso(now_utc()),
    })


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
    users = await db.users.find({"is_deleted": {"$ne": True}}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return users


@api.post("/admin/users")
async def create_user(body: CreateUserIn, user: dict = Depends(require_role("admin"))):
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
    res = await db.users.update_one({"id": user_id}, {"$set": update})
    if not res.matched_count:
        raise HTTPException(404, "User not found")
    await log_activity(user["id"], "user_updated", {k: v for k, v in update.items() if k != "password_hash"}, "user", user_id)
    return {"ok": True}


# ---------- Attendance ----------
async def _open_attendance(user_id: str) -> Optional[dict]:
    return await db.attendance_logs.find_one({"user_id": user_id, "punch_out": None}, {"_id": 0})


async def _open_break(att_id: str) -> Optional[dict]:
    return await db.break_logs.find_one({"attendance_id": att_id, "end": None}, {"_id": 0})


@api.post("/attendance/punch-in")
async def punch_in(user: dict = Depends(get_current_user)):
    existing = await _open_attendance(user["id"])
    if existing:
        return existing
    doc = {
        "id": new_id(),
        "user_id": user["id"],
        "user_name": user["name"],
        "punch_in": iso(now_utc()),
        "punch_out": None,
        "last_activity": iso(now_utc()),
        "auto_punched_out": False,
        "total_minutes": 0,
        "break_minutes": 0,
    }
    await db.attendance_logs.insert_one(doc)
    await log_activity(user["id"], "punch_in", item_type="attendance", item_id=doc["id"])
    doc.pop("_id", None)
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
        mins = int((now - datetime.fromisoformat(ob["start"])).total_seconds() // 60)
        await db.break_logs.update_one({"id": ob["id"]}, {"$set": {"end": iso(now), "minutes": mins}})
        await db.attendance_logs.update_one({"id": att["id"]}, {"$inc": {"break_minutes": mins}})
    now = now_utc()
    total = int((now - datetime.fromisoformat(att["punch_in"])).total_seconds() // 60)
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
    mins = max(1, int((now - datetime.fromisoformat(ob["start"])).total_seconds() // 60))
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
        total_today += int((now_utc() - datetime.fromisoformat(att["punch_in"])).total_seconds() // 60)
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
        last = datetime.fromisoformat(att["last_activity"])
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
        last = datetime.fromisoformat(att["last_activity"])
        if last < cutoff:
            # skip if on break
            if await _open_break(att["id"]):
                continue
            total = int((last - datetime.fromisoformat(att["punch_in"])).total_seconds() // 60)
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
        "image_asset_id": (image_asset or {}).get("id"),
        "image_variation_ids": [],
        "pricing_meta": draft.get("pricingMeta", {}),
        "status": "draft",
        "generated_by_user_id": user["id"],
        "generated_by_name": user["name"],
        "generated_at": iso(now_utc()),
    }
    await db.generated_products.insert_one(doc)
    # Mark image assigned
    if image_asset:
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
    # update activity
    if att:
        await db.attendance_logs.update_one({"id": att["id"]}, {"$set": {"last_activity": iso(now_utc())}})
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
        result = storage.put_object(path, data, file.content_type or "image/png")
    except Exception as e:
        logger.exception("upload failed")
        raise HTTPException(500, f"Upload failed: {e}")
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
    await db.image_assets.insert_one(doc)
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
        data, ct = storage.get_object(var["storage_path"])
        return Response(content=data, media_type=var.get("content_type", ct))
    data, ct = storage.get_object(asset["storage_path"])
    return Response(content=data, media_type=asset.get("content_type") or ct)


@api.patch("/admin/images/{image_id}")
async def patch_image(image_id: str, body: dict, user: dict = Depends(require_role("admin", "manager"))):
    allowed = {k: body[k] for k in ("status", "tags", "category", "description") if k in body}
    allowed["updated_at"] = iso(now_utc())
    await db.image_assets.update_one({"id": image_id}, {"$set": allowed})
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
            result = storage.put_object(path, data, f.content_type or "image/png")
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
            await db.image_assets.insert_one(doc)
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
    data, _ = storage.get_object(asset["storage_path"])
    result = await ai_service.enhance_image(data)
    if not result:
        raise HTTPException(500, "Enhance failed")
    path = storage.build_path(user["id"], f"enhanced-{asset['filename'] or 'x.png'}", kind="variations")
    storage.put_object(path, result, "image/png")
    doc = {"id": new_id(), "source_image_id": image_id, "storage_path": path,
           "content_type": "image/png", "kind": "enhanced",
           "created_by": user["id"], "created_at": iso(now_utc())}
    await db.image_variations.insert_one(doc)
    doc.pop("_id", None)
    await log_activity(user["id"], "image_enhanced", {"source": image_id}, "image_variation", doc["id"])
    return doc


@api.post("/admin/images/{image_id}/alternates")
async def generate_alternates(image_id: str, user: dict = Depends(require_role("admin", "manager"))):
    asset = await db.image_assets.find_one({"id": image_id}, {"_id": 0})
    if not asset:
        raise HTTPException(404, "Not found")
    data, _ = storage.get_object(asset["storage_path"])
    results = []
    for view in ["three-quarter angle", "back view"]:
        out = await ai_service.generate_alternate_view(data, view)
        if not out:
            continue
        path = storage.build_path(user["id"], f"alt-{view.replace(' ', '-')}.png", kind="variations")
        storage.put_object(path, out, "image/png")
        doc = {"id": new_id(), "source_image_id": image_id, "storage_path": path,
               "content_type": "image/png", "kind": "alternate", "view": view,
               "created_by": user["id"], "created_at": iso(now_utc())}
        await db.image_variations.insert_one(doc)
        doc.pop("_id", None)
        results.append(doc)
    await log_activity(user["id"], "image_alternates", {"count": len(results)}, "image", image_id)
    return {"variations": results}


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
            if datetime.fromisoformat(a["last_activity"]) < idle_cutoff:
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
        state = "on_break" if a["id"] in on_break_set else ("idle" if datetime.fromisoformat(a["last_activity"]) < idle_cutoff else "active")
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
    total = int((now - datetime.fromisoformat(att["punch_in"])).total_seconds() // 60)
    await db.attendance_logs.update_one({"id": att_id}, {"$set": {"punch_out": iso(now), "total_minutes": total, "force_out_by": user["id"]}})
    await log_activity(user["id"], "force_punch_out", {"target_user": att["user_id"]}, "attendance", att_id)
    return {"ok": True}


@api.get("/admin/activity-logs")
async def activity_logs(user: dict = Depends(require_role("admin", "manager")), limit: int = 200):
    return await db.activity_logs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)


# ---------- Seed ----------
async def seed():
    # admin
    if not await db.users.find_one({"email": "admin@gemsandluxury.com"}):
        await db.users.insert_one({
            "id": new_id(), "email": "admin@gemsandluxury.com", "name": "Gems Admin",
            "role": "admin", "active": True, "password_hash": hash_pw("Admin@123"),
            "created_at": iso(now_utc()), "is_deleted": False,
        })
        logger.info("seeded admin")
    if not await db.users.find_one({"email": "worker@gemsandluxury.com"}):
        await db.users.insert_one({
            "id": new_id(), "email": "worker@gemsandluxury.com", "name": "Amara Worker",
            "role": "worker", "active": True, "password_hash": hash_pw("Worker@123"),
            "created_at": iso(now_utc()), "is_deleted": False,
        })
        logger.info("seeded worker")
    # settings
    if not await db.admin_settings.find_one({"id": "global"}):
        await db.admin_settings.insert_one({
            "id": "global",
            "idle_timeout_minutes": 60,
            "warning_seconds": 300,
            "max_break_minutes": 30,
            "currency": "USD",
            "features": {"ai_images": True, "alternates": True, "admin_pricing_reveal": True},
            "created_at": iso(now_utc()),
        })
    # pricing
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
    # categories
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
    # naming families
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
    logger.info("seed complete")


# ---------- App ----------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


_scheduler: AsyncIOScheduler | None = None


@app.on_event("startup")
async def on_start():
    global _scheduler
    try:
        storage.init_storage()
        logger.info("storage ready")
    except Exception as e:
        logger.warning("storage init failed: %s", e)
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
    client.close()
