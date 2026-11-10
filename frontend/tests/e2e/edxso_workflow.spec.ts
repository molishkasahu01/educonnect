import { expect, test } from "@playwright/test";

test("real-data EDXSO workflow: register, zero analytics, empty-state discovery, authorized upload, rank, shortlist, export", async ({
  page,
}) => {
  const uniqueEmail = `e2e_realonly_${Date.now()}@edxso.org`;

  // 1. Register new workspace user
  await page.goto("/register");
  await page.getByLabel(/Full Name/i).fill("Real E2E Analyst");
  await page.getByLabel(/Work Email/i).fill(uniqueEmail);
  await page.getByLabel(/Password/i).first().fill("StrongPass!2026");
  await page.getByRole("button", { name: /Create account/i }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });

  // Verify dashboard shows 0 synthetic data & 0 initial profiles
  await expect(page.getByText(/Indexed Real Profiles/i)).toBeVisible();
  await expect(page.getByText(/SYNTHETIC DEMO/i)).toHaveCount(0);

  // 2. Navigate to New Discovery, confirm no Benchmark Archetype / Synthetic mode options exist
  await page.getByRole("link", { name: /New Discovery/i }).first().click();
  await expect(page).toHaveURL(/\/discovery\/new/);
  await expect(page.getByText(/Synthetic Benchmark/i)).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Load K-12 Benchmark Archetype/i })).toHaveCount(0);

  // Check LinkedIn-only policy block
  await page.getByLabel(/LinkedIn Profile URL/i).fill("https://www.linkedin.com/in/policy-check");
  await page.getByRole("button", { name: /ANALYZE REFERENCE PROFILE/i }).click();
  await expect(page.getByText(/prohibited/i).first()).toBeVisible();

  // 3. Submit structured reference profile in default REAL_DATA mode -> expect honest empty state
  await page.getByLabel(/Full Name/i).fill("Reference Education Leader");
  await page.getByLabel(/Current Designation/i).fill("Senior K-12 Education Consultant & Former Principal");
  await page.getByLabel(/Professional Biography/i).fill(
    "Advises school founders, managing trustees, and principals on K-12 school turnaround and academic leadership."
  );
  await page.getByRole("button", { name: /ANALYZE REFERENCE PROFILE/i }).click();
  await expect(page.getByText(/Detected School Ecosystem Indicators/i)).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: /Start Discovery & Hybrid Ranking/i }).click();
  await expect(page).toHaveURL(/\/discovery\/[0-9a-f-]+$/);
  await expect(page.getByText(/COMPLETED/i)).toBeVisible({ timeout: 30_000 });

  await page.getByRole("link", { name: /View Ranked Results/i }).click();
  await expect(page).toHaveURL(/\/results/);
  await expect(
    page.getByText(
      /No verified or authorized professional profiles were found for this discovery/i
    )
  ).toBeVisible();

  // 4. Upload authorized CSV dataset via Dataset Import UI (exact software test fixture records)
  await page.getByRole("link", { name: /Upload Authorized CSV/i }).click();
  await expect(page).toHaveURL(/\/datasets\/import/);

  const csvContent = [
    "full_name,current_role,organization,location,professional_bio,experience_years,school_indicators,skills,verification_status",
    "E2E Authorized Fixture Principal,Former Principal & Academic Director,Authorized Partner School Network,Pune,16 years leading CBSE schools and advising principals on accreditation and school turnaround.,16,Principal Experience;Education Consultancy,Principal Coaching;School Turnaround,verified",
    "E2E Authorized Fixture Trustee,Education Advisory Consultant,Partner School Collective,Mumbai,Advises K-12 school founders and managing trustees on institutional partnerships.,11,Education Consultancy;Multi-School Relationships,School Partnerships,unverified",
  ].join("\n");

  await page.locator("#csv-file").setInputFiles({
    name: "authorized_test_fixture.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csvContent, "utf-8"),
  });
  await page.locator("#auth-confirm").check();
  await page.getByRole("button", { name: /Upload & Ingest CSV/i }).click();
  await expect(page.getByText(/Imported 2 new profiles/i)).toBeVisible({ timeout: 25_000 });

  // 5. Run Authorized Uploads discovery and inspect genuine results, shortlisting, exports & candidate detail
  await page.getByRole("link", { name: /New Discovery/i }).first().click();
  await page.getByText(/Authorized Uploads/i).first().click();
  await page.getByLabel(/Full Name/i).fill("Authorized Discovery Ref");
  await page.getByLabel(/Current Designation/i).fill("Senior K-12 Education Consultant");
  await page.getByLabel(/Professional Biography/i).fill(
    "Advises CBSE school founders and principals on K-12 school turnaround and partnerships."
  );
  await page.getByRole("button", { name: /ANALYZE REFERENCE PROFILE/i }).click();
  await expect(page.getByText(/Start Discovery & Hybrid Ranking/i)).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: /Start Discovery & Hybrid Ranking/i }).click();
  await expect(page.getByText(/COMPLETED/i)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: /View Ranked Results/i }).click();
  await expect(page).toHaveURL(/\/results/);

  // Returns strictly the 2 real uploaded records, never padded to 20
  await expect(page.getByText(/Showing all 2 real profiles found/i)).toBeVisible();
  await expect(page.getByText(/E2E Authorized Fixture Principal/i)).toBeVisible();
  await expect(page.getByText(/SYNTHETIC/i)).toHaveCount(0);

  // Score breakdown + shortlist + export
  await page.getByRole("button", { name: /Score Breakdown/i }).first().click();
  await expect(page.getByText(/Semantic Similarity \(30%\)/i)).toBeVisible();
  await page.getByRole("button", { name: /^Shortlist$/i }).first().click();
  await expect(page.getByText(/Candidate added to shortlist/i)).toBeVisible();

  const [csvDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: /Export CSV/i }).click(),
  ]);
  expect(csvDownload.suggestedFilename()).toContain(".csv");

  const [xlsxDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: /Export XLSX/i }).click(),
  ]);
  expect(xlsxDownload.suggestedFilename()).toContain(".xlsx");

  // Candidate detail verification
  await page.getByRole("link", { name: /Inspect/i }).first().click();
  await expect(page).toHaveURL(/\/candidates\/[0-9a-f-]+/);
  await expect(page.getByText(/Record Provenance & Usage Restrictions/i)).toBeVisible();
});
