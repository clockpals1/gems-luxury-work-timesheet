"""Iteration 2 backend tests — CMS payload, pricing_meta patch, bulk upload, variations."""
import io
import os
import struct
import zlib
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN = {"email": "admin@gemsandluxury.com", "password": "Admin@123"}
WORKER = {"email": "worker@gemsandluxury.com", "password": "Worker@123"}


def _png_bytes(color=(255, 0, 0)):
    """Build a tiny valid 1x1 PNG."""
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00" + bytes(color)
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def worker_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=WORKER, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def worker_h(worker_token):
    return {"Authorization": f"Bearer {worker_token}"}


@pytest.fixture(scope="module")
def uploaded_image_id(admin_h):
    files = {"file": ("seed.png", _png_bytes(), "image/png")}
    r = requests.post(f"{BASE_URL}/api/admin/images/upload", headers=admin_h, files=files, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
def product_id(admin_h, uploaded_image_id):
    # Need an existing product. Try list first.
    r = requests.get(f"{BASE_URL}/api/products", headers=admin_h, timeout=20)
    assert r.status_code == 200
    items = r.json()
    if items:
        return items[0]["id"]
    # else generate
    r = requests.post(f"{BASE_URL}/api/products/generate", headers=admin_h,
                      json={"image_asset_id": uploaded_image_id}, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---------- CMS payload ----------
class TestCMSPayload:
    def test_admin_can_get_cms_payload(self, admin_h, product_id):
        r = requests.get(f"{BASE_URL}/api/products/{product_id}/cms-payload", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("handle", "title", "body_html", "vendor", "product_type", "tags", "options", "variants", "images", "metafields"):
            assert k in d, f"missing {k}"
        assert isinstance(d["variants"], list)
        assert isinstance(d["images"], list)
        assert d["vendor"] == "Gems & Luxury"
        if d["variants"]:
            v = d["variants"][0]
            assert "sku" in v and "price" in v and "option1" in v

    def test_worker_forbidden_cms_payload(self, worker_h, product_id):
        r = requests.get(f"{BASE_URL}/api/products/{product_id}/cms-payload", headers=worker_h, timeout=20)
        assert r.status_code == 403


# ---------- pricing_meta PATCH ----------
class TestPricingMetaPatch:
    def test_admin_can_set_pricing_meta_and_final_price(self, admin_h, product_id):
        meta = {"base": 100, "multiplier": 1.5, "TEST": "iter2"}
        r = requests.patch(f"{BASE_URL}/api/products/{product_id}", headers=admin_h,
                           json={"pricing_meta": meta, "final_price": 199}, timeout=20)
        assert r.status_code == 200, r.text
        # GET to verify persistence
        g = requests.get(f"{BASE_URL}/api/products/{product_id}", headers=admin_h, timeout=20)
        assert g.status_code == 200
        d = g.json()
        assert d.get("final_price") == 199
        assert d.get("pricing_meta", {}).get("TEST") == "iter2"

    def test_worker_pricing_meta_silently_stripped(self, admin_h, worker_h, product_id):
        # First, set known meta as admin
        baseline_meta = {"sentinel": "ADMIN_VALUE"}
        requests.patch(f"{BASE_URL}/api/products/{product_id}", headers=admin_h,
                       json={"pricing_meta": baseline_meta}, timeout=20)
        # Worker tries to overwrite — must succeed but pricing_meta not changed
        # Worker can only patch own products. Need a product owned by worker.
        # Generate product as worker (after punch-in)
        requests.post(f"{BASE_URL}/api/attendance/punch-in", headers=worker_h, timeout=10)
        gen = requests.post(f"{BASE_URL}/api/products/generate", headers=worker_h, json={}, timeout=60)
        if gen.status_code != 200:
            pytest.skip(f"could not generate worker product: {gen.text}")
        wp_id = gen.json()["id"]
        # Worker's GET should not include pricing_meta
        wg = requests.get(f"{BASE_URL}/api/products/{wp_id}", headers=worker_h, timeout=20).json()
        assert "pricing_meta" not in wg
        # Worker patch with pricing_meta — should succeed silently
        rp = requests.patch(f"{BASE_URL}/api/products/{wp_id}", headers=worker_h,
                            json={"pricing_meta": {"hacker": True}, "short_title": "WT"}, timeout=20)
        assert rp.status_code == 200, rp.text
        # Admin GET to confirm pricing_meta NOT modified by worker
        ag = requests.get(f"{BASE_URL}/api/products/{wp_id}", headers=admin_h, timeout=20).json()
        # pricing_meta from generation only — should not contain "hacker"
        assert ag.get("pricing_meta", {}).get("hacker") is not True
        assert ag.get("short_title") == "WT"


# ---------- Bulk upload ----------
class TestBulkUpload:
    def test_admin_bulk_upload(self, admin_h):
        files = [
            ("files", ("a.png", _png_bytes((255, 0, 0)), "image/png")),
            ("files", ("b.png", _png_bytes((0, 255, 0)), "image/png")),
            ("files", ("c.png", _png_bytes((0, 0, 255)), "image/png")),
        ]
        r = requests.post(f"{BASE_URL}/api/admin/images/upload-bulk",
                          headers=admin_h, files=files, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "uploaded" in d and "errors" in d and "count" in d
        assert d["count"] == 3
        for u in d["uploaded"]:
            assert "id" in u and "storage_path" in u and u["status"] == "available"

    def test_worker_bulk_upload_forbidden(self, worker_h):
        files = [("files", ("x.png", _png_bytes(), "image/png"))]
        r = requests.post(f"{BASE_URL}/api/admin/images/upload-bulk",
                          headers=worker_h, files=files, timeout=30)
        assert r.status_code == 403


# ---------- Variations ----------
class TestVariations:
    def test_list_variations_shape(self, admin_h, uploaded_image_id):
        r = requests.get(f"{BASE_URL}/api/admin/images/{uploaded_image_id}/variations",
                         headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "source" in d and "variations" in d
        assert isinstance(d["variations"], list)
        assert d["source"]["id"] == uploaded_image_id

    def test_enhance_then_list_grows_or_500(self, admin_h, uploaded_image_id):
        before = requests.get(f"{BASE_URL}/api/admin/images/{uploaded_image_id}/variations",
                              headers=admin_h, timeout=20).json()
        before_count = len(before["variations"])
        r = requests.post(f"{BASE_URL}/api/admin/images/{uploaded_image_id}/enhance",
                         headers=admin_h, timeout=90)
        # Per spec, 500 acceptable for tiny PNG; 200 means grew
        assert r.status_code in (200, 500), r.text
        after = requests.get(f"{BASE_URL}/api/admin/images/{uploaded_image_id}/variations",
                             headers=admin_h, timeout=20).json()
        assert "source" in after and "variations" in after
        if r.status_code == 200:
            assert len(after["variations"]) > before_count


# ---------- Sanity (dashboard) ----------
class TestDashboardSanity:
    def test_dashboard_stats(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/stats", headers=admin_h, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("users_active", "punched_in", "on_break", "idle",
                  "products_today", "products_week", "available_images", "total_products"):
            assert k in d

    def test_live_users(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/dashboard/live-users", headers=admin_h, timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
