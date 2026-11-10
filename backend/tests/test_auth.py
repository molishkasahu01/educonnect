from tests.conftest import get_auth_headers


def test_register_login_refresh_logout_and_isolation(client):
    # 1. Register user A
    r1 = client.post(
        "/api/auth/register",
        json={
            "email": "usera@school.edu",
            "full_name": "User Alpha",
            "password": "StrongPassword!123",
        },
    )
    assert r1.status_code == 201, r1.text
    data1 = r1.json()
    assert data1["user"]["role"] == "USER"
    acc_a = data1["access_token"]
    ref_a = data1["refresh_token"]

    # 2. Register user B
    r2 = client.post(
        "/api/auth/register",
        json={
            "email": "userb@school.edu",
            "full_name": "User Beta",
            "password": "StrongPassword!123",
        },
    )
    assert r2.status_code == 201
    acc_b = r2.json()["access_token"]

    # 3. Non-admin USER cannot access admin endpoints
    adm_forbidden = client.get("/api/admin/models", headers={"Authorization": f"Bearer {acc_a}"})
    assert adm_forbidden.status_code == 403

    # 4. Admin CAN access admin endpoints
    admin_hdrs = get_auth_headers(client, "admin@test.edxso", "AdminPass!123")
    adm_ok = client.get("/api/admin/models", headers=admin_hdrs)
    assert adm_ok.status_code == 200

    # 5. User A creates private reference profile; User B cannot read it
    ref_create = client.post(
        "/api/reference-profiles",
        headers={"Authorization": f"Bearer {acc_a}"},
        json={"full_name": "Private Ref", "current_designation": "Principal", "professional_bio": "Led K-12 school."},
    )
    assert ref_create.status_code == 201
    ref_id = ref_create.json()["id"]

    b_get = client.get(f"/api/reference-profiles/{ref_id}", headers={"Authorization": f"Bearer {acc_b}"})
    assert b_get.status_code == 404

    # 6. Refresh token works and rotates access token
    ref_resp = client.post("/api/auth/refresh", json={"refresh_token": ref_a})
    assert ref_resp.status_code == 200
    new_acc_a = ref_resp.json()["access_token"]
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_acc_a}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "usera@school.edu"

    # 7. Logout revokes access token
    logout_resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {new_acc_a}"})
    assert logout_resp.status_code == 200
    revoked_check = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_acc_a}"})
    assert revoked_check.status_code == 401

    # 8. User B GDPR data export works
    export_resp = client.get("/api/auth/me/export", headers={"Authorization": f"Bearer {acc_b}"})
    assert export_resp.status_code == 200
    assert export_resp.json()["user"]["email"] == "userb@school.edu"
