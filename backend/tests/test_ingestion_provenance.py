from app.data_sources import (
    AuthorizedAPIAdapter,
    CRMAdapter,
    CSVAdapter,
    OrganizationWebsiteAdapter,
    PublicDirectoryAdapter,
)
from tests.conftest import get_auth_headers


def test_synthetic_data_rejected_and_restricted_domains_blocked():
    # CSVAdapter drops any row labeled verification_status=synthetic
    csv_text = (
        "full_name,linkedin_url,current_role,organization,verification_status,professional_bio\n"
        "Synthetic Rejected,https://linkedin.com/in/invalid,Principal,School X,synthetic,K-12 leader\n"
        "Authorized Entry,https://linkedin.com/in/valid-crm,Principal,Oakridge School,verified,Leads CBSE school group.\n"
    )
    recs = CSVAdapter().ingest(csv_text)
    assert len(recs) == 1
    assert recs[0].name == "Authorized Entry"
    assert recs[0].verification_status == "verified"

    # PublicDirectoryAdapter skips linkedin.com links
    dir_recs = PublicDirectoryAdapter().ingest([
        {"name": "Blocked Entry", "directory_url": "https://www.linkedin.com/in/abc", "title": "Principal"},
        {"name": "Permitted Directory Entry", "directory_url": "https://directory.k12.org/leader/1", "title": "School Director", "school_name": "Oak School", "verified": True},
    ])
    assert len(dir_recs) == 1
    assert dir_recs[0].name == "Permitted Directory Entry"
    assert dir_recs[0].verification_status == "verified"

    # Org website & CRM adapters normalize strictly to verified/unverified
    org_recs = OrganizationWebsiteAdapter().ingest([
        {"person_name": "Org Leader Fixture", "designation": "Managing Trustee", "organization": "Beacon Trust", "page_url": "https://beacontrust.edu/leadership"}
    ])
    assert org_recs[0].verification_status == "verified"

    crm_recs = CRMAdapter().ingest([
        {"first_name": "CRM", "last_name": "Fixture", "job_title": "School Advisor", "account_name": "EduPartner CRM", "crm_verified": True}
    ])
    assert crm_recs[0].name == "CRM Fixture"
    assert crm_recs[0].verification_status == "verified"

    # Licensed API adapter reports unconfigured honestly
    api_adapter = AuthorizedAPIAdapter()
    assert api_adapter.is_configured() is False


def test_csv_upload_rejects_synthetic_and_requires_authorization(client):
    hdrs = get_auth_headers(client, "admin@test.edxso", "AdminPass!123")
    csv_bytes = (
        b"full_name,current_role,organization,location,professional_bio,experience_years,school_indicators,verification_status\n"
        b"Test Fixture Principal,School Director,Test Crestwood School,Bengaluru,Leads 3 K-12 campuses.,14,School Directorship;K-12 Education,unverified\n"
    )

    # Missing authorization_confirmed rejected
    bad_resp = client.post(
        "/api/candidates/import",
        headers=hdrs,
        files={"file": ("test.csv", csv_bytes, "text/csv")},
        data={"source_name": "partner_csv", "verification_status": "unverified", "authorization_confirmed": "false"},
    )
    assert bad_resp.status_code == 400

    # Synthetic verification_status rejected with 400
    syn_resp = client.post(
        "/api/candidates/import",
        headers=hdrs,
        files={"file": ("test.csv", csv_bytes, "text/csv")},
        data={"source_name": "partner_csv", "verification_status": "synthetic", "authorization_confirmed": "true"},
    )
    assert syn_resp.status_code == 400

    # Authorized unverified real upload succeeds
    ok_resp = client.post(
        "/api/candidates/import",
        headers=hdrs,
        files={"file": ("test.csv", csv_bytes, "text/csv")},
        data={
            "source_name": "partner_csv",
            "verification_status": "unverified",
            "dataset_type": "USER_PROVIDED",
            "authorization_confirmed": "true",
            "authorization_note": "Authorized export fixture",
        },
    )
    assert ok_resp.status_code == 200, ok_resp.text
    body = ok_resp.json()
    assert body["imported_count"] == 1
    assert body["dataset_type"] == "USER_PROVIDED"
    assert body["authorization_recorded"] is True

    cand_id = body["candidate_ids"][0]
    detail = client.get(f"/api/candidates/{cand_id}", headers=hdrs)
    assert detail.status_code == 200
    assert detail.json()["sources"][0]["upload_authorization_note"] == "Authorized export fixture"
