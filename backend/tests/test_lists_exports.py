import csv
import io
import json
import time
from openpyxl import load_workbook
from tests.conftest import get_auth_headers


def test_saved_lists_and_csv_xlsx_json_exports(client):
    hdrs = get_auth_headers(client, "admin@test.edxso", "AdminPass!123")
    csv_bytes = (
        b"full_name,current_role,organization,location,professional_bio,experience_years,school_indicators,skills,verification_status\n"
        b"Fixture Leader Export A,K-12 Principal,Fixture Oak School,Pune,12 years leading CBSE K-12 academics and school turnaround.,12,Principal Experience;K-12 Education,School Leadership;Turnaround,verified\n"
        b"Fixture Leader Export B,Education Consultant,Fixture Advisory Group,Bengaluru,Advises 10 school trustees on academic strategy.,10,Education Consultancy;School Advisory,Advisory;Mentoring,unverified\n"
    )
    imp = client.post(
        "/api/candidates/import",
        headers=hdrs,
        files={"file": ("export_fixture.csv", csv_bytes, "text/csv")},
        data={
            "source_name": "test_authorized_crm_export",
            "verification_status": "verified",
            "dataset_type": "USER_PROVIDED",
            "authorization_confirmed": "true",
            "authorization_note": "Test export authorized records",
        },
    )
    assert imp.status_code == 200

    ref_resp = client.post(
        "/api/reference-profiles",
        headers=hdrs,
        json={
            "full_name": "Export Test Reference",
            "current_designation": "K-12 School Consultant",
            "professional_bio": "Advisor to schools and former principal.",
        },
    )
    ref_id = ref_resp.json()["id"]
    job_id = client.post(
        "/api/discovery",
        headers=hdrs,
        json={"reference_profile_id": ref_id, "discovery_mode": "USER_PROVIDED"},
    ).json()["id"]

    deadline = time.time() + 25
    while time.time() < deadline:
        if client.get(f"/api/discovery/{job_id}", headers=hdrs).json()["status"] == "COMPLETED":
            break
        time.sleep(0.2)

    results = client.get(f"/api/discovery/{job_id}/results", headers=hdrs).json()
    assert len(results["items"]) >= 2
    cand_id = results["items"][0]["candidate"]["id"]

    # Create saved list, add & remove candidate
    lst = client.post("/api/lists", headers=hdrs, json={"name": "Top Leaders Shortlist", "description": "Real test"}).json()
    list_id = lst["id"]
    add_r = client.post(f"/api/lists/{list_id}/candidates", headers=hdrs, json={"candidate_id": cand_id, "discovery_job_id": job_id})
    assert add_r.status_code == 200
    assert add_r.json()["candidate_count"] == 1

    del_r = client.delete(f"/api/lists/{list_id}/candidates/{cand_id}", headers=hdrs)
    assert del_r.status_code == 200
    assert del_r.json()["candidate_count"] == 0

    # CSV export
    csv_resp = client.get(f"/api/discovery/{job_id}/export/csv", headers=hdrs)
    assert csv_resp.status_code == 200
    csv_rows = list(csv.DictReader(io.StringIO(csv_resp.text)))
    assert len(csv_rows) >= 2
    assert csv_rows[0]["verification_status"] in ("verified", "unverified")
    assert csv_rows[0]["dataset_type"] == "USER_PROVIDED"
    assert "data_source" in csv_rows[0]

    # XLSX export
    xlsx_resp = client.get(f"/api/discovery/{job_id}/export/xlsx", headers=hdrs)
    assert xlsx_resp.status_code == 200
    wb = load_workbook(io.BytesIO(xlsx_resp.content))
    assert "Discovery Results" in wb.sheetnames
    assert "Provenance & Model Info" in wb.sheetnames

    # JSON export
    json_resp = client.get(f"/api/discovery/{job_id}/export/json", headers=hdrs)
    assert json_resp.status_code == 200
    parsed = json.loads(json_resp.text)
    assert parsed["discovery_mode"] == "USER_PROVIDED"
    assert parsed["total_candidates"] >= 2
    assert parsed["results"][0]["verification_status"] in ("verified", "unverified")
