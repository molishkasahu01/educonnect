import time
from app.ai.embeddings import embedding_service
from app.ranking.engine import HybridRankingEngine
from app.ranking.explainability import build_candidate_explanation
from tests.conftest import get_auth_headers


def test_hybrid_ranking_and_missing_evidence_normalization():
    engine = HybridRankingEngine()
    ref = {
        "current_designation": "Senior K-12 Education Consultant & Former Principal",
        "professional_bio": "18 years leading CBSE schools, advising school founders and trustees.",
        "experience_years": 18.0,
        "school_indicators": ["Principal Experience", "Education Consultancy", "Multi-School Relationships", "K-12 Education"],
        "organizations": ["Apex Advisory"],
        "influence_indicators": ["Advisor to school founders", "Keynote speaker"],
        "skills": ["School Turnaround", "Principal Coaching"],
    }

    strong_candidate = {
        "full_name": "Strong K12 Test Fixture",
        "current_role": "Former Principal & Education Consultant",
        "organization_name": "Horizon Schools Advisory",
        "professional_bio": "16 years as K-12 Principal and strategic advisor to 20 CBSE school founders.",
        "experience_years": 16.0,
        "education_segments": ["K-12", "CBSE"],
        "school_indicators": ["Principal Experience", "Education Consultancy", "Multi-School Relationships", "K-12 Education"],
        "organizations_list": ["Horizon Schools Advisory"],
        "skills": ["School Turnaround", "Principal Coaching"],
        "influence_indicators": ["Advisor to 20 school founders"],
        "verification_status": "verified",
        "data_confidence": 0.90,
        "data_freshness_days": 5,
        "primary_source": "test_source",
        "source_record_id": "rec-strong",
    }

    sparse_candidate = {
        "full_name": "Sparse Test Fixture",
        "current_role": "K-12 Education Consultant",
        "organization_name": None,
        "professional_bio": None,
        "experience_years": None,
        "education_segments": [],
        "school_indicators": [],
        "organizations_list": [],
        "skills": [],
        "influence_indicators": [],
        "verification_status": "unverified",
        "data_confidence": 0.40,
        "data_freshness_days": 90,
        "primary_source": "test_source",
        "source_record_id": "rec-sparse",
    }

    strong_res = engine.score_candidate(ref, strong_candidate, semantic_score_100=85.0)
    sparse_res = engine.score_candidate(ref, sparse_candidate, semantic_score_100=65.0)

    assert strong_res.relevance_score > sparse_res.relevance_score
    assert strong_res.evidence_confidence > sparse_res.evidence_confidence
    assert strong_res.meets_minimum_evidence is True
    assert sparse_res.meets_minimum_evidence is False
    assert sparse_res.evidence_confidence <= 42.0
    assert sparse_res.relevance_score != sparse_res.evidence_confidence
    assert len(sparse_res.missing_evidence_notes) >= 2

    expl = build_candidate_explanation(strong_candidate, strong_res)
    assert "reference profile" in expl["summary_explanation"].lower()
    assert len(expl["evidence_links"]) >= 1


def test_real_semantic_embeddings_and_exact_candidate_count_without_padding(client):
    # Confirm actual Sentence Transformers encoding works
    v1 = embedding_service.encode_text("Senior K-12 Principal and school founder advisor")
    v2 = embedding_service.encode_text("K-12 school chain executive and education consultant")
    v3 = embedding_service.encode_text("Kubernetes cloud infrastructure engineer for banking")
    sim_edu = embedding_service.cosine_similarity(v1, v2)
    sim_cloud = embedding_service.cosine_similarity(v1, v3)
    assert sim_edu > sim_cloud

    # Register fresh isolated user with 3 uploaded fixture profiles -> must return strictly 3, never pad to 20
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "ranking_exact@edxso.org",
            "password": "RankExact!2026",
            "full_name": "Ranking Fixture User",
        },
    )
    hdrs = (
        {"Authorization": f"Bearer {reg.json()['access_token']}"}
        if reg.status_code in (200, 201)
        else get_auth_headers(client, "ranking_exact@edxso.org", "RankExact!2026")
    )

    csv_bytes = (
        b"full_name,current_role,organization,location,professional_bio,experience_years,school_indicators,skills,verification_status,data_confidence\n"
        b"Unit Candidate Alpha,Principal & K-12 Consultant,Alpha Education Trust,Delhi,18 years leading CBSE schools and mentoring school principals across 15 campuses.,18,Principal Experience;Education Consultancy;Multi-School Relationships,School Turnaround;Principal Coaching,verified,0.92\n"
        b"Unit Candidate Beta,Managing Trustee,Beta Academy Network,Mumbai,12 years governing school foundations and school partnerships.,12,Trustee Governance;School Partnerships,Governance,verified,0.85\n"
        b"Unit Candidate Gamma,Cloud Backend Engineer,Gamma Software Ltd,Bengaluru,Builds containerized Go microservices for banking payments.,7,Software Engineering,Golang;Docker,verified,0.90\n"
    )
    up = client.post(
        "/api/candidates/import",
        headers=hdrs,
        files={"file": ("rank_fixture.csv", csv_bytes, "text/csv")},
        data={
            "source_name": "authorized_fixture_csv",
            "verification_status": "verified",
            "dataset_type": "USER_PROVIDED",
            "authorization_confirmed": "true",
            "authorization_note": "Unit test authorized fixture",
        },
    )
    assert up.status_code == 200
    assert up.json()["imported_count"] == 3

    ref_resp = client.post(
        "/api/reference-profiles",
        headers=hdrs,
        json={
            "full_name": "Reference K12 Advisor Fixture",
            "current_designation": "Senior K-12 Education Consultant & Former Principal",
            "professional_bio": "Senior K-12 education consultant leading school turnaround and principal mentoring across CBSE schools.",
            "skills": ["School Turnaround", "Principal Coaching"],
        },
    )
    assert ref_resp.status_code == 201
    ref_id = ref_resp.json()["id"]

    job_resp = client.post(
        "/api/discovery",
        headers=hdrs,
        json={"reference_profile_id": ref_id, "discovery_mode": "USER_PROVIDED"},
    )
    assert job_resp.status_code == 202
    job_id = job_resp.json()["id"]

    deadline = time.time() + 30
    status = "PENDING"
    while time.time() < deadline:
        j = client.get(f"/api/discovery/{job_id}", headers=hdrs).json()
        status = j["status"]
        if status in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.25)

    assert status == "COMPLETED"
    res_page = client.get(f"/api/discovery/{job_id}/results?page_size=50", headers=hdrs).json()
    # Strictly 3 records evaluated & returned — NEVER padded with fabricated records
    assert res_page["job"]["total_candidates_evaluated"] == 3
    assert len(res_page["items"]) == 3
    assert res_page["items"][0]["candidate"]["full_name"] == "Unit Candidate Alpha"
    assert res_page["items"][-1]["candidate"]["full_name"] == "Unit Candidate Gamma"
    assert res_page["items"][0]["relevance_score"] > res_page["items"][-1]["relevance_score"]
