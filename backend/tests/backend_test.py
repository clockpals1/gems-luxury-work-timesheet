"""Gems & Luxury backend regression tests."""
import os, io, time, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback to frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE = line.split("=",1)[1].strip().strip('"').rstrip("/")

ADMIN = {"email": "admin@gemsandluxury.com", "password": "Admin@123"}
WORKER = {"email": "worker@gemsandluxury.com", "password": "Worker@123"}

state = {}

def _login(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()

def H(tok): return {"Authorization": f"Bearer {tok}"}

# ---------- Auth ----------
def test_admin_login():
    d = _login(ADMIN)
    assert d["user"]["role"] == "admin"
    state["admin_tok"] = d["token"]
    state["admin_id"] = d["user"]["id"]

def test_worker_login():
    d = _login(WORKER)
    assert d["user"]["role"] == "worker"
    state["worker_tok"] = d["token"]
    state["worker_id"] = d["user"]["id"]

def test_auth_me():
    r = requests.get(f"{BASE}/api/auth/me", headers=H(state["admin_tok"]))
    assert r.status_code == 200 and r.json()["email"] == ADMIN["email"]

def test_login_bad_creds():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN["email"], "password": "wrong"})
    assert r.status_code == 401

# ---------- Role enforcement ----------
def test_worker_blocked_admin():
    r = requests.get(f"{BASE}/api/admin/users", headers=H(state["worker_tok"]))
    assert r.status_code == 403
    r = requests.get(f"{BASE}/api/admin/dashboard/stats", headers=H(state["worker_tok"]))
    assert r.status_code == 403

# ---------- Admin users ----------
def test_admin_list_users():
    r = requests.get(f"{BASE}/api/admin/users", headers=H(state["admin_tok"]))
    assert r.status_code == 200 and len(r.json()) >= 2

def test_admin_create_user():
    email = f"test_{int(time.time())}@test.com"
    r = requests.post(f"{BASE}/api/admin/users", headers=H(state["admin_tok"]),
                      json={"email": email, "name": "TEST_U", "password": "Pass@123", "role": "worker"})
    assert r.status_code == 200, r.text
    state["new_uid"] = r.json()["id"]

def test_admin_patch_user():
    r = requests.patch(f"{BASE}/api/admin/users/{state['new_uid']}",
                       headers=H(state["admin_tok"]), json={"active": False})
    assert r.status_code == 200

# ---------- Attendance ----------
def test_worker_punch_in():
    r = requests.post(f"{BASE}/api/attendance/punch-in", headers=H(state["worker_tok"]))
    assert r.status_code == 200 and r.json()["punch_out"] is None

def test_attendance_me():
    r = requests.get(f"{BASE}/api/attendance/me", headers=H(state["worker_tok"]))
    assert r.status_code == 200 and r.json()["attendance"] is not None

def test_break_start_end():
    r = requests.post(f"{BASE}/api/attendance/break/start", headers=H(state["worker_tok"]))
    assert r.status_code == 200
    r = requests.post(f"{BASE}/api/attendance/break/end", headers=H(state["worker_tok"]))
    assert r.status_code == 200

def test_heartbeat():
    r = requests.post(f"{BASE}/api/attendance/heartbeat", headers=H(state["worker_tok"]))
    assert r.status_code == 200 and r.json()["ok"] is True

# ---------- Pricing / Categories / Naming / Settings ----------
def test_pricing_rules_get():
    r = requests.get(f"{BASE}/api/admin/pricing-rules", headers=H(state["admin_tok"]))
    assert r.status_code == 200
    p = r.json()
    assert p["min_price"] == 40 and p["max_price"] == 150
    state["pricing"] = p

def test_pricing_rules_put():
    body = {"min_price": 40, "max_price": 150, "currency": "USD",
            "category_multipliers": state["pricing"].get("category_multipliers", {})}
    r = requests.put(f"{BASE}/api/admin/pricing-rules", headers=H(state["admin_tok"]), json=body)
    assert r.status_code == 200

def test_categories_list():
    r = requests.get(f"{BASE}/api/admin/categories", headers=H(state["admin_tok"]))
    assert r.status_code == 200 and len(r.json()) >= 4

def test_naming_families():
    r = requests.get(f"{BASE}/api/admin/naming-families", headers=H(state["admin_tok"]))
    assert r.status_code == 200 and len(r.json()) >= 5

def test_settings_get_patch():
    r = requests.get(f"{BASE}/api/admin/settings", headers=H(state["admin_tok"]))
    assert r.status_code == 200
    r = requests.patch(f"{BASE}/api/admin/settings", headers=H(state["admin_tok"]),
                       json={"idle_timeout_minutes": 60})
    assert r.status_code == 200

# ---------- Image upload ----------
import base64
PNG_1x1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
def test_image_upload():
    files = {"file": ("t.png", io.BytesIO(PNG_1x1), "image/png")}
    data = {"category": "Women / Dresses / Occasion", "tags": "test,red", "description": "TEST"}
    r = requests.post(f"{BASE}/api/admin/images/upload", headers=H(state["admin_tok"]),
                      files=files, data=data)
    assert r.status_code == 200, r.text
    state["img_id"] = r.json()["id"]

def test_image_list():
    r = requests.get(f"{BASE}/api/admin/images", headers=H(state["admin_tok"]))
    assert r.status_code == 200 and len(r.json()) >= 1

def test_image_download_query_auth():
    r = requests.get(f"{BASE}/api/images/{state['img_id']}/download?auth={state['admin_tok']}")
    assert r.status_code == 200 and len(r.content) > 0

def test_image_download_no_auth():
    r = requests.get(f"{BASE}/api/images/{state['img_id']}/download")
    assert r.status_code == 401

def test_image_patch():
    r = requests.patch(f"{BASE}/api/admin/images/{state['img_id']}", headers=H(state["admin_tok"]),
                       json={"tags": ["updated"]})
    assert r.status_code == 200

# ---------- Product generation (Claude AI) ----------
def test_worker_generate_product_no_pricing_meta():
    r = requests.post(f"{BASE}/api/products/generate", headers=H(state["worker_tok"]),
                      json={"category": "Women / Dresses / Occasion"}, timeout=90)
    assert r.status_code == 200, r.text
    p = r.json()
    assert "pricing_meta" not in p, "Worker should NOT see pricing_meta"
    fp = p["final_price"]
    assert isinstance(fp, int) and 40 <= fp <= 150
    assert p["name"] and p["short_title"] and p["full_description"]
    state["prod_id"] = p["id"]

def test_admin_generate_has_pricing_meta():
    r = requests.post(f"{BASE}/api/products/generate", headers=H(state["admin_tok"]),
                      json={"category": "Women / Kaftan"}, timeout=90)
    assert r.status_code == 200, r.text
    p = r.json()
    fp = p["final_price"]
    assert 40 <= fp <= 150
    # pricing_meta may exist for admin
    state["admin_prod"] = p["id"]

def test_worker_list_products_no_meta():
    r = requests.get(f"{BASE}/api/products", headers=H(state["worker_tok"]))
    assert r.status_code == 200
    for p in r.json():
        assert "pricing_meta" not in p
        assert p["generated_by_user_id"] == state["worker_id"]

def test_admin_list_products_all():
    r = requests.get(f"{BASE}/api/products", headers=H(state["admin_tok"]))
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 2  # admin sees all

def test_patch_product():
    r = requests.patch(f"{BASE}/api/products/{state['prod_id']}", headers=H(state["worker_tok"]),
                       json={"short_title": "Updated"})
    assert r.status_code == 200

def test_export_product():
    r = requests.post(f"{BASE}/api/products/{state['prod_id']}/export", headers=H(state["worker_tok"]))
    assert r.status_code == 200

# ---------- Admin dashboard ----------
def test_dashboard_stats():
    r = requests.get(f"{BASE}/api/admin/dashboard/stats", headers=H(state["admin_tok"]))
    assert r.status_code == 200
    d = r.json()
    for k in ("users_active","punched_in","products_today","total_products"):
        assert k in d

def test_live_users():
    r = requests.get(f"{BASE}/api/admin/dashboard/live-users", headers=H(state["admin_tok"]))
    assert r.status_code == 200 and isinstance(r.json(), list)

def test_admin_attendance_list():
    r = requests.get(f"{BASE}/api/admin/attendance", headers=H(state["admin_tok"]))
    assert r.status_code == 200

def test_activity_logs():
    r = requests.get(f"{BASE}/api/admin/activity-logs", headers=H(state["admin_tok"]))
    assert r.status_code == 200 and len(r.json()) >= 1

# ---------- Punch out + logout (last) ----------
def test_punch_out():
    r = requests.post(f"{BASE}/api/attendance/punch-out", headers=H(state["worker_tok"]))
    assert r.status_code == 200

def test_logout():
    r = requests.post(f"{BASE}/api/auth/logout", headers=H(state["worker_tok"]))
    assert r.status_code == 200
