"""API verification script testing health, auth, profile analysis, real-data discovery empty state, and exports."""

import os
import sys
import time
import uuid
import httpx

BASE_URL = os.environ.get("EDXSO_API_URL", "http://127.0.0.1:8010").rstrip("/")


def main():
    with httpx.Client(base_url=BASE_URL, timeout=20.0) as client:
        h = client.get("/api/health")
        assert h.status_code == 200, h.text
        print("Health:", h.json())

        email = os.environ.get("EDXSO_VERIFY_EMAIL") or f"verify_{uuid.uuid4().hex[:8]}@edxso.org"
        pw = os.environ.get("EDXSO_VERIFY_PASSWORD") or "VerifyPass!2026"
        reg = client.post("/api/auth/register", json={"email": email, "password": pw, "full_name": "API Verifier"})
        if reg.status_code in (200, 201):
            token = reg.json()["access_token"]
        else:
            login = client.post("/api/auth/login", json={"email": email, "password": pw})
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]
        hdrs = {"Authorization": f"Bearer {token}"}

        prov = client.get("/api/discovery/providers", headers=hdrs)
        assert prov.status_code == 200, prov.text
        print("Providers env counts:", prov.json()["environment_counts"])

        created = client.post(
            "/api/reference-profiles",
            headers=hdrs,
            json={
                "full_name": "Verification Reference Profile",
                "current_designation": "Senior K-12 Academic Advisor",
                "professional_bio": "Advises independent schools and principals on accreditation and school leadership.",
                "skills": ["Academic Leadership", "Principal Mentoring"],
            },
        )
        assert created.status_code == 201, created.text
        ref_id = created.json()["id"]

        analyzed = client.post(f"/api/reference-profiles/{ref_id}/analyze", headers=hdrs)
        assert analyzed.status_code == 200, analyzed.text
        print("Reference analysis indicators:", analyzed.json()["ai_derived_count"])

        job_resp = client.post(
            "/api/discovery",
            headers=hdrs,
            json={"reference_profile_id": ref_id, "discovery_mode": "REAL_DATA"},
        )
        assert job_resp.status_code == 202, job_resp.text
        job_id = job_resp.json()["id"]

        deadline = time.time() + 45
        job = None
        while time.time() < deadline:
            job = client.get(f"/api/discovery/{job_id}", headers=hdrs).json()
            if job["status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.5)
        assert job and job["status"] == "COMPLETED", f"Job failed: {job}"

        res = client.get(f"/api/discovery/{job_id}/results", headers=hdrs).json()
        print("Real-data evaluated:", res["job"]["total_candidates_evaluated"])
        csv_exp = client.get(f"/api/discovery/{job_id}/export/csv", headers=hdrs)
        xlsx_exp = client.get(f"/api/discovery/{job_id}/export/xlsx", headers=hdrs)
        assert csv_exp.status_code == 200 and xlsx_exp.status_code == 200
        print("Live real-data-only API checks PASSED!")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Verification failed:", exc, file=sys.stderr)
        sys.exit(1)
