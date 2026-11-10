from tests.conftest import get_auth_headers


def test_linkedin_url_only_compliance_notice(client):
    hdrs = get_auth_headers(client, "admin@test.edxso", "AdminPass!123")
    create_resp = client.post(
        "/api/reference-profiles",
        headers=hdrs,
        json={"linkedin_url": "https://www.linkedin.com/in/example-reference-id"},
    )
    assert create_resp.status_code == 201
    ref_id = create_resp.json()["id"]

    analyze_resp = client.post(f"/api/reference-profiles/{ref_id}/analyze", headers=hdrs)
    assert analyze_resp.status_code == 200
    body = analyze_resp.json()
    assert body["reference_profile"]["analysis_status"] == "NEEDS_MORE_INFO"
    assert "prohibited" in (body["compliance_notice"] or "").lower()
    assert body["missing_count"] >= 1
    assert "full_name" in body["missing_critical_fields"]


def test_rich_profile_analysis_attributes_and_provenance(client):
    hdrs = get_auth_headers(client, "admin@test.edxso", "AdminPass!123")
    create_resp = client.post(
        "/api/reference-profiles",
        headers=hdrs,
        json={
            "full_name": "Fixture Reference Consultant",
            "current_designation": "Senior K-12 Education Consultant & Former Principal",
            "current_organization": "Unit School Advisory Group",
            "location": "Pune, India",
            "professional_bio": (
                "Former CBSE school principal for 12 years and education entrepreneur advising "
                "school founders, trustees, and multi-school groups across 25 partner K-12 campuses."
            ),
            "career_history": "2010-2022 Principal; 2022-Present Managing Consultant",
            "skills": ["School Turnaround", "Teacher Development", "School Accreditation"],
        },
    )
    assert create_resp.status_code == 201
    ref_id = create_resp.json()["id"]

    analyze_resp = client.post(f"/api/reference-profiles/{ref_id}/analyze", headers=hdrs)
    assert analyze_resp.status_code == 200
    body = analyze_resp.json()
    assert body["reference_profile"]["analysis_status"] == "ANALYZED"
    assert body["observed_count"] >= 3
    assert body["ai_derived_count"] >= 4

    summary = body["reference_profile"]["analysis_summary"]
    assert "Principal Experience" in summary["school_indicators"]
    assert "Education Consultancy" in summary["school_indicators"]
    assert "Multi-School Relationships" in summary["school_indicators"]
    assert summary["experience_years"] >= 12.0

    # Verify every attribute records evidence_text, source_reference, and valid classification_type
    for ind in body["reference_profile"]["indicators"]:
        assert ind["classification_type"] in (
            "OBSERVED_FACT",
            "AI_DERIVED_CLASSIFICATION",
            "MISSING_INFORMATION",
        )
        assert ind["evidence_text"]
        assert ind["source_reference"]
