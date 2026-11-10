import time
from tests.conftest import get_auth_headers


def test_discovery_job_idempotency_progress_and_retry(client):
    hdrs = get_auth_headers(client, "admin@test.edxso", "AdminPass!123")
    ref_resp = client.post(
        "/api/reference-profiles",
        headers=hdrs,
        json={
            "full_name": "Discovery Job Test Reference",
            "current_designation": "Managing Trustee & School Advisor",
            "professional_bio": "15 years governing multi-campus K-12 schools and mentoring principals.",
        },
    )
    assert ref_resp.status_code == 201
    ref_id = ref_resp.json()["id"]

    j1 = client.post(
        "/api/discovery",
        headers=hdrs,
        json={
            "reference_profile_id": ref_id,
            "discovery_mode": "REAL_DATA",
            "idempotency_key": "idem-job-test-001",
        },
    )
    j2 = client.post(
        "/api/discovery",
        headers=hdrs,
        json={
            "reference_profile_id": ref_id,
            "discovery_mode": "REAL_DATA",
            "idempotency_key": "idem-job-test-001",
        },
    )
    assert j1.status_code == 202
    assert j2.status_code == 202
    assert j1.json()["id"] == j2.json()["id"]

    job_id = j1.json()["id"]
    deadline = time.time() + 25
    job_data = None
    while time.time() < deadline:
        job_data = client.get(f"/api/discovery/{job_id}", headers=hdrs).json()
        if job_data["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.2)

    assert job_data is not None
    assert job_data["status"] == "COMPLETED"
    assert job_data["progress_percent"] == 100
    assert job_data["discovery_mode"] == "REAL_DATA"
    assert len(job_data["stage_logs"]) >= 3

    # Retry on completed job re-runs cleanly and increments retry_count
    retry_resp = client.post(f"/api/discovery/{job_id}/retry", headers=hdrs)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["retry_count"] == 1
    deadline2 = time.time() + 25
    while time.time() < deadline2:
        jd = client.get(f"/api/discovery/{job_id}", headers=hdrs).json()
        if jd["status"] == "COMPLETED":
            break
        time.sleep(0.2)
    assert client.get(f"/api/discovery/{job_id}", headers=hdrs).json()["status"] == "COMPLETED"
