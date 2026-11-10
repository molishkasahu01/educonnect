from datetime import datetime, timezone
from uuid import uuid4
from app.models.list_eval import BenchmarkLabel
from app.models.profile import CandidateProfile
from tests.conftest import get_auth_headers


def test_real_evaluation_requires_genuine_dataset_and_admin_security(client, db_session):
    hdrs = get_auth_headers(client, "admin@test.edxso", "AdminPass!123")

    # Without genuine labeled evaluation data, evaluation refuses to fabricate metrics
    empty_eval = client.post("/api/admin/evaluation/run", headers=hdrs)
    assert empty_eval.status_code == 404
    assert "genuine labeled evaluation dataset" in empty_eval.json()["detail"].lower()

    # Invalid weights sum rejected with 422
    bad_weights = client.put(
        "/api/admin/ranking-weights",
        headers=hdrs,
        json={
            "semantic_similarity": 0.5,
            "school_ecosystem_relevance": 0.5,
            "professional_role_similarity": 0.5,
            "experience_similarity": 0.1,
            "organization_network_overlap": 0.1,
            "influence_indicators_score": 0.1,
        },
    )
    assert bad_weights.status_code == 422

    # Valid weight update succeeds
    ok_weights = client.put(
        "/api/admin/ranking-weights",
        headers=hdrs,
        json={
            "semantic_similarity": 0.35,
            "school_ecosystem_relevance": 0.25,
            "professional_role_similarity": 0.15,
            "experience_similarity": 0.10,
            "organization_network_overlap": 0.05,
            "influence_indicators_score": 0.10,
        },
    )
    assert ok_weights.status_code == 200

    # Security headers & real analytics endpoint check (zero synthetic counts)
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert health_resp.headers.get("X-Frame-Options") == "DENY"

    analytics_resp = client.get("/api/analytics/dashboard", headers=hdrs)
    assert analytics_resp.status_code == 200
    metrics = analytics_resp.json()["metrics"]
    assert "synthetic_benchmark_profiles" not in metrics
    for entry in analytics_resp.json()["charts"]["verification_distribution"]:
        assert entry["status"] in ("verified", "unverified")

    # Evaluation works cleanly ONLY when real non-synthetic labeled candidates + ReferenceProfile exist
    ref = client.post(
        "/api/reference-profiles",
        headers=hdrs,
        json={
            "full_name": "Evaluation Fixture Reference",
            "current_designation": "Senior K-12 Principal Advisor",
            "professional_bio": "Advising school leaders on CBSE turnaround.",
        },
    ).json()

    admin_id_row = client.get("/api/auth/me", headers=hdrs).json()["id"]
    from uuid import UUID
    c1 = CandidateProfile(
        id=uuid4(),
        owner_id=UUID(admin_id_row),
        full_name="Real Eval Positive Fixture",
        normalized_name="real eval positive fixture",
        current_role="Former CBSE Principal & School Advisor",
        professional_bio="15 years leading K-12 schools and school turnaround advisory.",
        experience_years=15.0,
        school_indicators=["Principal Experience", "Education Consultancy"],
        skills=["School Turnaround"],
        primary_source="official_org_website",
        source_record_id="real-eval-01",
        verification_status="verified",
        dataset_type="REAL_DATA",
        data_confidence=0.92,
        visibility="private",
        last_updated=datetime.now(timezone.utc),
    )
    c2 = CandidateProfile(
        id=uuid4(),
        owner_id=UUID(admin_id_row),
        full_name="Real Eval Negative Fixture",
        normalized_name="real eval negative fixture",
        current_role="Database Administrator",
        professional_bio="Manages banking PostgreSQL clusters.",
        experience_years=8.0,
        primary_source="official_org_website",
        source_record_id="real-eval-02",
        verification_status="verified",
        dataset_type="REAL_DATA",
        data_confidence=0.90,
        visibility="private",
        last_updated=datetime.now(timezone.utc),
    )
    db_session.add_all([c1, c2])
    db_session.flush()
    db_session.add_all([
        BenchmarkLabel(
            benchmark_name="real_k12_eval_v1",
            reference_key=ref["id"],
            candidate_source_record_id="real-eval-01",
            candidate_id=c1.id,
            label="RELEVANT",
            labeled_by="human_reviewer",
        ),
        BenchmarkLabel(
            benchmark_name="real_k12_eval_v1",
            reference_key=ref["id"],
            candidate_source_record_id="real-eval-02",
            candidate_id=c2.id,
            label="IRRELEVANT",
            labeled_by="human_reviewer",
        ),
    ])
    db_session.commit()

    eval_resp = client.post(f"/api/admin/evaluation/run?reference_profile_id={ref['id']}", headers=hdrs)
    assert eval_resp.status_code == 200, eval_resp.text
    ev = eval_resp.json()
    assert ev["total_candidates"] == 2
    assert "non-synthetic" in ev["dataset_disclaimer"].lower()
