import http.server
import json
import threading
import time
from tests.conftest import get_auth_headers


def _register_and_headers(client, email: str, password: str, full_name: str = "Test Analyst") -> dict:
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    if resp.status_code in (200, 201):
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return get_auth_headers(client, email, password)


def _poll_job(client, hdrs: dict, job_id: str, timeout: float = 25.0) -> dict:
    deadline = time.time() + timeout
    data = {}
    while time.time() < deadline:
        data = client.get(f"/api/discovery/{job_id}", headers=hdrs).json()
        if data["status"] in ("COMPLETED", "FAILED"):
            return data
        time.sleep(0.2)
    return data


def test_real_data_default_honest_empty_state_and_no_synthetic_mode(client):
    """Default discovery (REAL_DATA) completes cleanly with 0 results and rejects synthetic mode."""
    hdrs = _register_and_headers(client, "real_empty@edxso.org", "RealPass!2026")
    ref_resp = client.post(
        "/api/reference-profiles",
        headers=hdrs,
        json={
            "full_name": "K-12 Advisor Ref",
            "current_designation": "Senior K-12 Education Consultant & Former Principal",
            "professional_bio": "15 years leading CBSE/IB schools and mentoring principals.",
        },
    )
    assert ref_resp.status_code == 201
    ref_id = ref_resp.json()["id"]

    # Attempting hidden synthetic discovery mode fails strict 422 schema validation
    bad_mode = client.post(
        "/api/discovery",
        headers=hdrs,
        json={"reference_profile_id": ref_id, "discovery_mode": "SYNTHETIC_BENCHMARK"},
    )
    assert bad_mode.status_code == 422

    # Default REAL_DATA discovery completes honestly with 0 results
    job_resp = client.post(
        "/api/discovery",
        headers=hdrs,
        json={"reference_profile_id": ref_id},
    )
    assert job_resp.status_code == 202
    job_body = job_resp.json()
    assert job_body["discovery_mode"] == "REAL_DATA"

    finished = _poll_job(client, hdrs, job_body["id"])
    assert finished["status"] == "COMPLETED"
    assert finished["progress_percent"] == 100
    assert finished["total_candidates_evaluated"] == 0

    results = client.get(f"/api/discovery/{job_body['id']}/results", headers=hdrs).json()
    assert results["discovery_mode"] == "REAL_DATA"
    assert results["items"] == []
    assert (
        "No verified or authorized professional profiles were found for this discovery. Connect an authorized source or import genuine professional records."
        in results["empty_state_message"]
    )
    assert "licensed_api" in (results["provider_diagnostics"].get("unconfigured_providers") or [])

    # Fresh user analytics dashboard returns strict zeros (zero illustrative metrics)
    dash = client.get("/api/analytics/dashboard", headers=hdrs).json()
    assert dash["metrics"]["total_candidate_profiles"] == 0
    assert dash["metrics"]["relevant_professionals_discovered"] == 0
    assert dash["charts"]["segment_distribution"] == []

    # Candidate listing returns empty for user without uploaded/real records and rejects synthetic dataset_type
    assert client.get("/api/candidates", headers=hdrs).json()["total"] == 0
    assert client.get("/api/candidates?dataset_type=SYNTHETIC_BENCHMARK", headers=hdrs).status_code == 400


def test_real_html_website_and_json_directory_retrieval_compliance(client):
    """Real HTML school leadership page + JSON speaker directory + robots.txt + blocked LinkedIn URL."""
    html_page = """<!doctype html>
    <html><head><title>Crestwood Public Schools Trust | Leadership</title></head>
    <body>
      <main>
        <div class="leadership-card">
          <h3>Leadership Fixture Officer</h3>
          <span class="role">Director of K-12 Academics & Former Principal</span>
          <p>20 years advising CBSE school boards, mentoring principals, and leading curriculum innovation across 14 schools.</p>
        </div>
        <div class="leadership-card">
          <h3>Trust Governance Chair Fixture</h3>
          <span class="role">Managing Trustee & School Founder</span>
          <p>Founder of independent K-12 school trust with active multi-school advisory board partnerships.</p>
        </div>
      </main>
    </body></html>"""

    json_speakers = {
        "speakers": [
            {
                "directory_id": "spk-201",
                "name": "Education Conference Speaker Fixture",
                "title": "Senior K-12 Education Consultant",
                "school_name": "National School Leaders Forum",
                "city": "Bengaluru, India",
                "bio": "Advises independent schools on accreditation, turnaround, and principal leadership.",
                "experience_years": 16,
                "skills": ["School Turnaround", "Principal Coaching"],
                "verified": True,
            }
        ]
    }

    class _MockWebHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/robots.txt":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"User-agent: *\nAllow: /\nDisallow: /restricted-private\n")
                return
            if self.path == "/leadership":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_page.encode("utf-8"))
                return
            if self.path == "/speakers.json":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(json_speakers).encode("utf-8"))
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):
            return

    server = http.server.HTTPServer(("127.0.0.1", 0), _MockWebHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        hdrs = _register_and_headers(client, "web_real_tester@edxso.org", "WebReal!2026")

        # 1. Explicit linkedin.com fetch-url blocked with 403
        blocked = client.post(
            "/api/candidates/fetch-url",
            headers=hdrs,
            json={
                "urls": ["https://www.linkedin.com/in/blocked-user"],
                "source_type": "organization_website",
                "source_name": "blocked_check",
                "authorization_confirmed": True,
            },
        )
        assert blocked.status_code == 403

        # 2. HTML school leadership page extraction via /api/candidates/fetch-url
        html_fetch = client.post(
            "/api/candidates/fetch-url",
            headers=hdrs,
            json={
                "urls": [f"http://127.0.0.1:{port}/leadership"],
                "source_type": "organization_website",
                "source_name": "official_school_leadership_page",
                "authorization_confirmed": True,
                "authorization_note": "Permitted public school trust leadership page",
            },
        )
        assert html_fetch.status_code == 200, html_fetch.text
        assert html_fetch.json()["imported_count"] == 2
        assert html_fetch.json()["dataset_type"] == "REAL_DATA"

        # 3. Run REAL_DATA discovery pulling JSON speaker directory + ranked alongside HTML records,
        # while robots.txt disallows /restricted-private
        ref = client.post(
            "/api/reference-profiles",
            headers=hdrs,
            json={
                "full_name": "Real Web Discovery Ref",
                "current_designation": "Senior K-12 Education Consultant & Former Principal",
                "professional_bio": "Advising school trusts and principals across K-12 school networks.",
                "skills": ["Principal Coaching", "School Turnaround"],
            },
        ).json()

        job = client.post(
            "/api/discovery",
            headers=hdrs,
            json={
                "reference_profile_id": ref["id"],
                "discovery_mode": "REAL_DATA",
                "selected_sources": ["public_directory", "organization_website"],
                "filters": {
                    "permitted_urls": [
                        f"http://127.0.0.1:{port}/speakers.json",
                        f"http://127.0.0.1:{port}/restricted-private",
                    ]
                },
            },
        ).json()
        finished = _poll_job(client, hdrs, job["id"])
        assert finished["status"] == "COMPLETED"
        assert finished["total_candidates_evaluated"] == 3

        results = client.get(f"/api/discovery/{job['id']}/results", headers=hdrs).json()
        assert results["discovery_mode"] == "REAL_DATA"
        assert len(results["items"]) == 3
        names = {r["candidate"]["full_name"] for r in results["items"]}
        assert "Leadership Fixture Officer" in names
        assert "Trust Governance Chair Fixture" in names
        assert "Education Conference Speaker Fixture" in names
        assert all(r["candidate"]["dataset_type"] == "REAL_DATA" for r in results["items"])
        assert any("robots.txt disallows" in e for e in results["provider_diagnostics"].get("errors", []))
        assert results["provider_diagnostics"]["live_fetched_count"] == 1
    finally:
        server.shutdown()


def test_user_provided_cross_user_isolation_and_providers_endpoint(client):
    user1_hdrs = _register_and_headers(client, "isolated1@edxso.org", "IsoPass!2026")
    user2_hdrs = _register_and_headers(client, "isolated2@edxso.org", "IsoPass!2026")

    prov = client.get("/api/discovery/providers", headers=user1_hdrs)
    assert prov.status_code == 200
    prov_body = prov.json()
    assert "SYNTHETIC_BENCHMARK" not in prov_body["environment_counts"]
    assert all(p["id"] != "synthetic_benchmark" for p in prov_body["providers"])
    assert prov_body["compliance_policy"]["automated_linkedin_scraping_allowed"] is False

    csv_bytes = (
        b"full_name,current_role,organization,location,professional_bio,experience_years,school_indicators,skills,verification_status,data_confidence\n"
        b"User1 Leader Fixture,School Director,User1 Academy,Pune,Leads K-12 curriculum turnaround.,14,Principal Experience;K-12 Education,School Turnaround,verified,0.92\n"
        b"User1 Unverified Fixture,Advisor,User1 Consultancy,Mumbai,School advisory engagement.,8,Education Consultancy,Advisory,unverified,0.60\n"
    )
    up = client.post(
        "/api/candidates/import",
        headers=user1_hdrs,
        files={"file": ("iso.csv", csv_bytes, "text/csv")},
        data={
            "source_name": "authorized_partner_csv",
            "verification_status": "verified",
            "dataset_type": "USER_PROVIDED",
            "authorization_confirmed": "true",
            "authorization_note": "Partner consent fixture",
        },
    )
    assert up.status_code == 200
    assert up.json()["imported_count"] == 2

    # User 2 cannot discover User 1's private uploaded profiles
    ref2 = client.post(
        "/api/reference-profiles",
        headers=user2_hdrs,
        json={"full_name": "User2 Ref", "current_designation": "Principal", "professional_bio": "School leadership"},
    ).json()
    job2 = client.post(
        "/api/discovery",
        headers=user2_hdrs,
        json={"reference_profile_id": ref2["id"], "discovery_mode": "USER_PROVIDED"},
    ).json()
    fin2 = _poll_job(client, user2_hdrs, job2["id"])
    assert fin2["status"] == "COMPLETED"
    assert fin2["total_candidates_evaluated"] == 0


def test_dom_tree_html_extractor_elementor_listing_and_linkedin_preservation():
    """Verify DOM-tree extraction across Elementor, list-item, speaker-card patterns and deterministic IDs."""
    from app.data_sources import OrganizationWebsiteAdapter
    from app.data_sources.base import _extract_html_profiles

    elementor_html = """<!doctype html>
    <html><head><title>Team at Praxis School Consultancy</title></head>
    <body>
      <main>
        <h2>Meet Our Team</h2>
        <div class="elementor-element">
          <div><h2>Dr. Asha Deshmukh</h2></div>
          <div><h2>Founder &amp; Director</h2></div>
          <div><p>Advises K-12 school boards and trustees across Pune and Nagpur.</p></div>
          <div><a href="https://www.linkedin.com/in/asha-deshmukh-fixture?lipi=urn%3Ali%3Apage">Read More</a></div>
        </div>
        <div class="elementor-element">
          <div><h2>Mr. Vivek Kulkarni</h2></div>
          <div><h2>Head - Human Resource\u200b</h2></div>
          <div><p>Leads school leadership hiring across CBSE campuses.</p></div>
          <div><a href="https://linkedin.com/in/vivek-kulkarni-fixture">Profile</a></div>
        </div>
        <ul class="listing-grid">
          <li class="listing-item">
            <a class="title">Meenakshi Rao CEO, Horizon Schools Trust</a>
            <span class="excerpt">Meenakshi Rao is the Chief Executive Officer of Horizon Schools Trust.</span>
          </li>
        </ul>
        <article class="speaker-card">
          <h3 class="speaker-name">Prof. Anand Verma</h3>
          <p class="speaker-role">Director Principal</p>
          <p class="speaker-org">Gwalior Public Academy , Gwalior</p>
          <div class="speaker-tag-wrap">Keynote Speaker</div>
        </article>
      </main>
      <footer><div><h2>Our Offices</h2><p>Raipur</p><p>Bengaluru</p></div></footer>
    </body></html>"""

    extracted = _extract_html_profiles(elementor_html, "https://example.org/team/")
    by_name = {item["name"]: item for item in extracted}
    assert "Meet Our Team" not in by_name
    assert "Our Offices" not in by_name
    assert "Dr. Asha Deshmukh" in by_name
    assert by_name["Dr. Asha Deshmukh"]["title"] == "Founder & Director"
    assert by_name["Dr. Asha Deshmukh"]["linkedin_url"] == "https://www.linkedin.com/in/asha-deshmukh-fixture/"
    assert "Mr. Vivek Kulkarni" in by_name
    assert by_name["Mr. Vivek Kulkarni"]["title"] == "Head - Human Resource"
    assert by_name["Mr. Vivek Kulkarni"]["linkedin_url"] == "https://www.linkedin.com/in/vivek-kulkarni-fixture/"
    assert "Meenakshi Rao" in by_name
    assert by_name["Meenakshi Rao"]["title"] == "CEO"
    assert by_name["Meenakshi Rao"]["organization"] == "Horizon Schools Trust"
    assert "Prof. Anand Verma" in by_name
    assert by_name["Prof. Anand Verma"]["location"] == "Gwalior"
    assert by_name["Prof. Anand Verma"]["organization"] == "Gwalior Public Academy, Gwalior"

    # Distinct URLs must produce distinct deterministic source_record_id values (no orgweb-1 collision)
    ad = OrganizationWebsiteAdapter()
    recs_a = ad.ingest([{"name": "Alpha Leader", "title": "Principal", "page_url": "https://site-a.edu/team"}])
    recs_b = ad.ingest([{"name": "Beta Leader", "title": "Director", "page_url": "https://site-b.edu/team"}])
    assert recs_a[0].source_record_id != recs_b[0].source_record_id
    assert recs_a[0].id != recs_b[0].id


def test_cloud_database_url_and_cors_normalization():
    """Verify Render postgres:// URLs and bare frontend hostnames normalize cleanly."""
    from app.core.config import Settings, normalize_database_url

    assert normalize_database_url("postgres://u:p@dpg-host:5432/educonnect") == "postgresql+psycopg2://u:p@dpg-host:5432/educonnect"
    assert normalize_database_url("postgresql://u:p@dpg-host:5432/educonnect") == "postgresql+psycopg2://u:p@dpg-host:5432/educonnect"

    s = Settings(
        database_url="postgres://u:p@h/db",
        cors_origins="https://app.example.com",
        frontend_host="educonnect-web.onrender.com",
    )
    assert s.database_url == "postgresql+psycopg2://u:p@h/db"
    assert s.is_postgres is True
    assert "https://educonnect-web.onrender.com" in s.cors_origin_list
