"""Iteration 3 backend tests — prompts, fuzzy duplicate, password change/reset, role assignment, timesheet PDF."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@gemsandluxury.com", "password": "Admin@123"}
WORKER = {"email": "worker@gemsandluxury.com", "password": "Worker@123"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"], r.json()["user"]


@pytest.fixture(scope="module")
def admin_token():
    tok, _ = _login(ADMIN)
    return tok


@pytest.fixture(scope="module")
def worker_token():
    tok, _ = _login(WORKER)
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def worker_headers(worker_token):
    return {"Authorization": f"Bearer {worker_token}"}


# ---------- Prompts ----------
class TestPrompts:
    def test_list_seeded(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/prompts", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        items = r.json()
        keys = {i["key"] for i in items}
        assert {"product_draft", "image_enhance", "image_alternate"}.issubset(keys), keys
        assert len(items) >= 3

    def test_worker_forbidden_list(self, worker_headers):
        r = requests.get(f"{BASE_URL}/api/admin/prompts", headers=worker_headers, timeout=15)
        # require_role admin/manager → worker 403
        assert r.status_code == 403

    def test_patch_persists(self, admin_headers):
        items = requests.get(f"{BASE_URL}/api/admin/prompts", headers=admin_headers, timeout=15).json()
        target = next(i for i in items if i["key"] == "product_draft")
        original_sys = target["system_prompt"]
        new_desc = f"updated-{int(time.time())}"
        r = requests.patch(
            f"{BASE_URL}/api/admin/prompts/{target['id']}",
            headers=admin_headers,
            json={"description": new_desc},
            timeout=15,
        )
        assert r.status_code == 200
        items2 = requests.get(f"{BASE_URL}/api/admin/prompts", headers=admin_headers, timeout=15).json()
        updated = next(i for i in items2 if i["id"] == target["id"])
        assert updated["description"] == new_desc
        assert updated["system_prompt"] == original_sys  # untouched

    def test_worker_patch_forbidden(self, admin_headers, worker_headers):
        items = requests.get(f"{BASE_URL}/api/admin/prompts", headers=admin_headers, timeout=15).json()
        pid = items[0]["id"]
        r = requests.patch(
            f"{BASE_URL}/api/admin/prompts/{pid}",
            headers=worker_headers,
            json={"description": "hack"},
            timeout=15,
        )
        assert r.status_code == 403


# ---------- Product generation reads from MongoDB prompts + fuzzy dup ----------
class TestProductGenerationFromDb:
    def test_generate_three_unique(self, admin_headers):
        from rapidfuzz import fuzz
        names = []
        for _ in range(3):
            r = requests.post(f"{BASE_URL}/api/products/generate", headers=admin_headers, json={}, timeout=120)
            assert r.status_code == 200, r.text
            names.append(r.json()["name"])
        # pairwise token_set_ratio < 85
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                ratio = fuzz.token_set_ratio(names[i].lower(), names[j].lower())
                assert ratio < 85, f"Names too similar: '{names[i]}' vs '{names[j]}' ratio={ratio}"


# ---------- Password change ----------
class TestChangePassword:
    def test_wrong_current_400(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/auth/change-password",
            headers=admin_headers,
            json={"current_password": "WRONG_xxxx", "new_password": "Temp@1234"},
            timeout=15,
        )
        assert r.status_code == 400

    def test_change_then_login_then_revert(self):
        tok, _ = _login(ADMIN)
        h = {"Authorization": f"Bearer {tok}"}
        new_pw = "Tmp@Iter3!"
        r = requests.post(
            f"{BASE_URL}/api/auth/change-password",
            headers=h,
            json={"current_password": ADMIN["password"], "new_password": new_pw},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        # Old password no longer works
        bad = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
        assert bad.status_code == 401
        # New works
        good = requests.post(f"{BASE_URL}/api/auth/login", json={**ADMIN, "password": new_pw}, timeout=15)
        assert good.status_code == 200
        # Revert
        h2 = {"Authorization": f"Bearer {good.json()['token']}"}
        r = requests.post(
            f"{BASE_URL}/api/auth/change-password",
            headers=h2,
            json={"current_password": new_pw, "new_password": ADMIN["password"]},
            timeout=15,
        )
        assert r.status_code == 200
        # confirm original works
        confirm = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
        assert confirm.status_code == 200


# ---------- Admin reset password ----------
class TestAdminResetPassword:
    def test_admin_can_reset_worker_then_revert(self, admin_headers, worker_headers):
        # find worker id
        users = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers, timeout=15).json()
        worker = next(u for u in users if u["email"] == "worker@gemsandluxury.com")
        new_pw = "WorkerTmp@9!"
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{worker['id']}/reset-password",
            headers=admin_headers,
            json={"new_password": new_pw},
            timeout=15,
        )
        assert r.status_code == 200
        # worker logs in with new
        good = requests.post(f"{BASE_URL}/api/auth/login", json={**WORKER, "password": new_pw}, timeout=15)
        assert good.status_code == 200
        # revert
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{worker['id']}/reset-password",
            headers=admin_headers,
            json={"new_password": WORKER["password"]},
            timeout=15,
        )
        assert r.status_code == 200
        confirm = requests.post(f"{BASE_URL}/api/auth/login", json=WORKER, timeout=15)
        assert confirm.status_code == 200

    def test_worker_cannot_reset(self, admin_headers, worker_headers):
        users = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers, timeout=15).json()
        any_user = users[0]
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{any_user['id']}/reset-password",
            headers=worker_headers,
            json={"new_password": "ShouldFail@123"},
            timeout=15,
        )
        assert r.status_code == 403


# ---------- Role change ----------
class TestRoleChange:
    def test_admin_can_change_role(self, admin_headers):
        # create a temp user
        email = f"TEST_role_{int(time.time())}@gemsandluxury.com"
        cu = requests.post(
            f"{BASE_URL}/api/admin/users",
            headers=admin_headers,
            json={"email": email, "name": "TEST Role", "password": "Temp@1234", "role": "worker"},
            timeout=15,
        )
        assert cu.status_code == 200, cu.text
        uid = cu.json()["id"]
        # promote to admin
        r = requests.patch(f"{BASE_URL}/api/admin/users/{uid}", headers=admin_headers, json={"role": "admin"}, timeout=15)
        assert r.status_code == 200
        # verify
        users = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers, timeout=15).json()
        u = next(x for x in users if x["id"] == uid)
        assert u["role"] == "admin"
        # demote back to worker, then deactivate to clean up
        requests.patch(f"{BASE_URL}/api/admin/users/{uid}", headers=admin_headers, json={"role": "manager"}, timeout=15)
        users2 = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers, timeout=15).json()
        assert next(x for x in users2 if x["id"] == uid)["role"] == "manager"
        requests.patch(f"{BASE_URL}/api/admin/users/{uid}", headers=admin_headers, json={"active": False}, timeout=15)


# ---------- Timesheet PDF ----------
class TestTimesheetPDF:
    def test_admin_pdf_7d(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/reports/timesheet?days=7", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd and "filename" in cd, cd
        assert r.content[:4] == b"%PDF"

    def test_admin_pdf_30d(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/reports/timesheet?days=30", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_worker_forbidden(self, worker_headers):
        r = requests.get(f"{BASE_URL}/api/admin/reports/timesheet?days=7", headers=worker_headers, timeout=15)
        assert r.status_code == 403
