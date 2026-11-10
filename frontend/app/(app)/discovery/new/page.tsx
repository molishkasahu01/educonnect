"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Compass,
  Database,
  FileSpreadsheet,
  Globe,
  Sparkles,
} from "lucide-react";
import { apiRequest, ApiError } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  buttonVariants,
  Card,
  ClassificationBadge,
  DatasetEnvironmentBadge,
  Input,
  Textarea,
} from "@/components/ui/primitives";

interface Indicator {
  id: string;
  category: string;
  attribute_name: string;
  attribute_value: string;
  evidence_text: string;
  source_reference: string;
  classification_type: string;
  confidence: number;
}

interface ReferenceProfile {
  id: string;
  full_name: string | null;
  linkedin_url: string | null;
  current_designation: string | null;
  current_organization: string | null;
  location: string | null;
  analysis_status: string;
  analysis_summary: {
    school_indicators?: string[];
    influence_indicators?: string[];
    organizations?: string[];
    experience_years?: number | null;
    seniority?: string;
    compliance_notice?: string | null;
  } | null;
  indicators: Indicator[];
}

interface AnalysisResp {
  reference_profile: ReferenceProfile;
  compliance_notice: string | null;
  missing_critical_fields: string[];
  observed_count: number;
  ai_derived_count: number;
  missing_count: number;
}

interface ProviderInfo {
  id: string;
  name: string;
  environment: string;
  configured: boolean;
  can_run: boolean;
  status_label: string;
  record_count: number;
  requires_credentials: boolean;
  missing_requirements: string[];
  compliance_note: string;
}

interface ProvidersStatusResp {
  environment_counts: {
    REAL_DATA: number;
    USER_PROVIDED: number;
  };
  providers: ProviderInfo[];
}

type DiscoveryMode = "REAL_DATA" | "USER_PROVIDED" | "ALL_AUTHORIZED";

export default function NewDiscoveryPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    linkedin_url: "",
    full_name: "",
    current_designation: "",
    current_organization: "",
    location: "",
    professional_bio: "",
    career_history: "",
    education_sector_experience: "",
    skills: "",
    additional_notes: "",
  });

  const [analyzing, setAnalyzing] = useState(false);
  const [startingJob, setStartingJob] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResp | null>(null);
  const [discoveryMode, setDiscoveryMode] = useState<DiscoveryMode>("REAL_DATA");
  const [selectedRealSources, setSelectedRealSources] = useState<string[]>([
    "organization_website",
    "public_directory",
    "licensed_api",
  ]);
  const [permittedUrls, setPermittedUrls] = useState("");
  const [providersStatus, setProvidersStatus] = useState<ProvidersStatusResp | null>(null);

  useEffect(() => {
    apiRequest<ProvidersStatusResp>("/api/discovery/providers")
      .then(setProvidersStatus)
      .catch(() => {
        // non-fatal
      });
  }, []);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setAnalyzing(true);
    try {
      const skillsList = form.skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const created = await apiRequest<ReferenceProfile>("/api/reference-profiles", {
        method: "POST",
        body: JSON.stringify({
          linkedin_url: form.linkedin_url || null,
          full_name: form.full_name || null,
          current_designation: form.current_designation || null,
          current_organization: form.current_organization || null,
          location: form.location || null,
          professional_bio: form.professional_bio || null,
          career_history: form.career_history || null,
          education_sector_experience: form.education_sector_experience || null,
          skills: skillsList,
          additional_notes: form.additional_notes || null,
        }),
      });

      const analyzed = await apiRequest<AnalysisResp>(
        `/api/reference-profiles/${created.id}/analyze`,
        { method: "POST" }
      );
      setAnalysisResult(analyzed);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to analyze reference profile");
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleRealSource = (id: string) => {
    setSelectedRealSources((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleStartDiscovery = async () => {
    if (!analysisResult) return;
    setError(null);
    setStartingJob(true);
    try {
      const sources =
        discoveryMode === "REAL_DATA"
          ? selectedRealSources
          : discoveryMode === "USER_PROVIDED"
          ? ["user_csv", "manual", "crm"]
          : [...selectedRealSources, "user_csv", "manual", "crm"];
      const urlsList = permittedUrls
        .split(",")
        .map((u) => u.trim())
        .filter(Boolean);
      const job = await apiRequest<{ id: string }>("/api/discovery", {
        method: "POST",
        body: JSON.stringify({
          reference_profile_id: analysisResult.reference_profile.id,
          discovery_mode: discoveryMode,
          selected_sources: sources,
          filters:
            urlsList.length > 0 && (discoveryMode === "REAL_DATA" || discoveryMode === "ALL_AUTHORIZED")
              ? { permitted_urls: urlsList }
              : {},
        }),
      });
      router.push(`/discovery/${job.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to start discovery job");
      setStartingJob(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">New Influencer Discovery</h1>
          <p className="mt-1 text-sm text-slate-400">
            Supply a genuine reference K-12 leader profile, inspect extracted indicators, and discover real professionals from authorized sources.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/datasets/import" className={buttonVariants({ variant: "outline" })}>
            <FileSpreadsheet className="h-4 w-4" aria-hidden="true" />
            Import Authorized CSV / Web URL
          </Link>
        </div>
      </div>

      <Alert tone="info" title="Ethical Access & Real-Data Compliance">
        LinkedIn URLs are treated strictly as reference identifiers. EduConnect never scrapes LinkedIn or
        bypasses authentication walls. Real profiles enter strictly via permitted public education/school
        websites, user-authorized CSV/CRM exports, or licensed professional data APIs.
      </Alert>

      {/* Discovery Environment & Data Source Selection */}
      <Card className="p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-white">Authorized Discovery Sources</h2>
            <p className="text-xs text-slate-400">
              Select which authorized real-world data environment to search. Synthetic and fabricated profiles are disabled.
            </p>
          </div>
          <DatasetEnvironmentBadge datasetType={discoveryMode} />
        </div>

        <fieldset>
          <legend className="sr-only">Discovery Mode</legend>
          <div className="grid gap-3 md:grid-cols-3">
            <label
              className={`cursor-pointer rounded-xl border p-3.5 transition-colors ${
                discoveryMode === "REAL_DATA"
                  ? "border-emerald-500/80 bg-emerald-950/30"
                  : "border-slate-800 bg-navy-950/60 hover:border-slate-700"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-white">
                  <input
                    type="radio"
                    name="discovery_mode"
                    value="REAL_DATA"
                    checked={discoveryMode === "REAL_DATA"}
                    onChange={() => setDiscoveryMode("REAL_DATA")}
                    className="accent-emerald-500"
                  />
                  <Database className="h-4 w-4 text-emerald-400" aria-hidden="true" />
                  <span>Real External Sources</span>
                </div>
                <Badge tone="emerald">
                  {providersStatus?.environment_counts.REAL_DATA ?? 0}
                </Badge>
              </div>
              <p className="mt-1.5 text-xs text-slate-400">
                Retrieves from permitted official school websites, leadership pages, education directories, and licensed APIs.
              </p>
            </label>

            <label
              className={`cursor-pointer rounded-xl border p-3.5 transition-colors ${
                discoveryMode === "USER_PROVIDED"
                  ? "border-sky-500/80 bg-sky-950/30"
                  : "border-slate-800 bg-navy-950/60 hover:border-slate-700"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-white">
                  <input
                    type="radio"
                    name="discovery_mode"
                    value="USER_PROVIDED"
                    checked={discoveryMode === "USER_PROVIDED"}
                    onChange={() => setDiscoveryMode("USER_PROVIDED")}
                    className="accent-sky-500"
                  />
                  <FileSpreadsheet className="h-4 w-4 text-sky-400" aria-hidden="true" />
                  <span>Authorized Uploads</span>
                </div>
                <Badge tone="sky">
                  {providersStatus?.environment_counts.USER_PROVIDED ?? 0}
                </Badge>
              </div>
              <p className="mt-1.5 text-xs text-slate-400">
                Searches your workspace CSV uploads, CRM partner exports, and manually entered profiles.
              </p>
            </label>

            <label
              className={`cursor-pointer rounded-xl border p-3.5 transition-colors ${
                discoveryMode === "ALL_AUTHORIZED"
                  ? "border-indigo-500/80 bg-indigo-950/30"
                  : "border-slate-800 bg-navy-950/60 hover:border-slate-700"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-white">
                  <input
                    type="radio"
                    name="discovery_mode"
                    value="ALL_AUTHORIZED"
                    checked={discoveryMode === "ALL_AUTHORIZED"}
                    onChange={() => setDiscoveryMode("ALL_AUTHORIZED")}
                    className="accent-indigo-500"
                  />
                  <Globe className="h-4 w-4 text-indigo-400" aria-hidden="true" />
                  <span>All Authorized Sources</span>
                </div>
                <Badge tone="indigo">
                  {(providersStatus?.environment_counts.REAL_DATA ?? 0) +
                    (providersStatus?.environment_counts.USER_PROVIDED ?? 0)}
                </Badge>
              </div>
              <p className="mt-1.5 text-xs text-slate-400">
                Combines external real-data adapters and your workspace authorized CSV/CRM uploads.
              </p>
            </label>
          </div>
        </fieldset>

        {(discoveryMode === "REAL_DATA" || discoveryMode === "ALL_AUTHORIZED") && (
          <div className="space-y-3 rounded-lg border border-slate-800 bg-navy-950/70 p-3.5 text-xs">
            <div className="font-medium text-slate-200">Select Real Data Sources</div>
            <div className="grid gap-2.5 sm:grid-cols-3">
              {(providersStatus?.providers || [])
                .filter((p) => p.environment === "REAL_DATA")
                .map((p) => (
                  <label
                    key={p.id}
                    className="flex cursor-pointer flex-col justify-between rounded-lg border border-slate-800 bg-navy-900/70 p-2.5"
                  >
                    <div className="flex items-center gap-2 font-medium text-slate-200">
                      <input
                        type="checkbox"
                        checked={selectedRealSources.includes(p.id)}
                        onChange={() => toggleRealSource(p.id)}
                        className="accent-emerald-500"
                      />
                      <span>{p.name}</span>
                    </div>
                    <div className="mt-1.5 flex items-center justify-between gap-1 text-[11px] text-slate-400">
                      <span>{p.status_label}</span>
                      <Badge tone={p.requires_credentials && !p.configured ? "amber" : "emerald"}>
                        {p.record_count} indexed
                      </Badge>
                    </div>
                  </label>
                ))}
            </div>
            <div>
              <label htmlFor="permitted-urls" className="mb-1 block text-[11px] text-slate-400">
                Optional Custom Permitted Official School / Consultancy / Directory URLs (comma-separated, never LinkedIn; curated public K-12 directories &amp; consultancy pages run automatically)
              </label>
              <Input
                id="permitted-urls"
                value={permittedUrls}
                onChange={(e) => setPermittedUrls(e.target.value)}
                placeholder="https://schoolgroup.example.edu/leadership, https://conference.example.org/speakers.json"
              />
            </div>
          </div>
        )}

        {discoveryMode === "USER_PROVIDED" && (providersStatus?.environment_counts.USER_PROVIDED ?? 0) === 0 && (
          <Alert tone="warning" title="No Uploaded Profiles Found Yet">
            Your workspace currently has 0 authorized CSV or manual profiles.{" "}
            <Link href="/datasets/import" className="underline font-semibold">
              Import an authorized CSV or add a real profile →
            </Link>
          </Alert>
        )}
      </Card>

      {error && (
        <Alert tone="error" title="Validation / Analysis Error">
          {error}
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-12">
        <Card className="p-6 lg:col-span-7">
          <h2 className="mb-4 text-base font-semibold text-white">Reference Profile Input</h2>
          <form onSubmit={handleAnalyze} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="ref-name" className="mb-1 block text-xs font-medium text-slate-300">
                  Full Name
                </label>
                <Input
                  id="ref-name"
                  name="full_name"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  placeholder="Enter reference professional full name"
                />
              </div>
              <div>
                <label htmlFor="ref-linkedin" className="mb-1 block text-xs font-medium text-slate-300">
                  LinkedIn Profile URL (Reference ID only)
                </label>
                <Input
                  id="ref-linkedin"
                  name="linkedin_url"
                  type="url"
                  value={form.linkedin_url}
                  onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })}
                  placeholder="https://www.linkedin.com/in/..."
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="ref-role" className="mb-1 block text-xs font-medium text-slate-300">
                  Current Designation
                </label>
                <Input
                  id="ref-role"
                  name="current_designation"
                  value={form.current_designation}
                  onChange={(e) => setForm({ ...form, current_designation: e.target.value })}
                  placeholder="Senior K-12 Education Consultant"
                />
              </div>
              <div>
                <label htmlFor="ref-org" className="mb-1 block text-xs font-medium text-slate-300">
                  Current Organization
                </label>
                <Input
                  id="ref-org"
                  name="current_organization"
                  value={form.current_organization}
                  onChange={(e) => setForm({ ...form, current_organization: e.target.value })}
                  placeholder="School trust, school chain, or consultancy"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="ref-location" className="mb-1 block text-xs font-medium text-slate-300">
                  Location
                </label>
                <Input
                  id="ref-location"
                  name="location"
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                  placeholder="Bengaluru, India"
                />
              </div>
              <div>
                <label htmlFor="ref-skills" className="mb-1 block text-xs font-medium text-slate-300">
                  Skills (comma-separated)
                </label>
                <Input
                  id="ref-skills"
                  name="skills"
                  value={form.skills}
                  onChange={(e) => setForm({ ...form, skills: e.target.value })}
                  placeholder="School Turnaround, Principal Coaching"
                />
              </div>
            </div>

            <div>
              <label htmlFor="ref-bio" className="mb-1 block text-xs font-medium text-slate-300">
                Professional Biography
              </label>
              <Textarea
                id="ref-bio"
                name="professional_bio"
                rows={4}
                value={form.professional_bio}
                onChange={(e) => setForm({ ...form, professional_bio: e.target.value })}
                placeholder="Describe school leadership tenure, multi-school advisory, and partnerships..."
              />
            </div>

            <div>
              <label htmlFor="ref-history" className="mb-1 block text-xs font-medium text-slate-300">
                Career History (with dates if known)
              </label>
              <Textarea
                id="ref-history"
                name="career_history"
                rows={3}
                value={form.career_history}
                onChange={(e) => setForm({ ...form, career_history: e.target.value })}
                placeholder="2010-2018: School Principal; 2018-Present: Education Consultant"
              />
            </div>

            <div>
              <label htmlFor="ref-edu" className="mb-1 block text-xs font-medium text-slate-300">
                Education-Sector Experience
              </label>
              <Input
                id="ref-edu"
                name="education_sector_experience"
                value={form.education_sector_experience}
                onChange={(e) => setForm({ ...form, education_sector_experience: e.target.value })}
                placeholder="K-12 CBSE/IB governance, accreditation, edupreneurship"
              />
            </div>

            <div>
              <label htmlFor="ref-notes" className="mb-1 block text-xs font-medium text-slate-300">
                Additional Notes
              </label>
              <Textarea
                id="ref-notes"
                name="additional_notes"
                rows={2}
                value={form.additional_notes}
                onChange={(e) => setForm({ ...form, additional_notes: e.target.value })}
                placeholder="Any specific target geography or school network criteria..."
              />
            </div>

            <Button type="submit" size="lg" className="w-full" disabled={analyzing}>
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {analyzing ? "Analyzing Reference Profile…" : "ANALYZE REFERENCE PROFILE"}
            </Button>
          </form>
        </Card>

        {/* Extracted Attributes Panel */}
        <Card className="p-6 lg:col-span-5">
          <h2 className="mb-3 text-base font-semibold text-white">AI Profile Analysis Output</h2>
          {!analysisResult ? (
            <div className="flex h-72 flex-col items-center justify-center rounded-lg border border-dashed border-slate-800 p-6 text-center">
              <Compass className="mb-3 h-8 w-8 text-slate-500" aria-hidden="true" />
              <p className="text-sm font-medium text-slate-300">Ready for AI Extraction</p>
              <p className="mt-1 text-xs text-slate-400">
                Click &ldquo;ANALYZE REFERENCE PROFILE&rdquo; to inspect observed facts, 19 school
                ecosystem indicators, and missing information before launching discovery.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {analysisResult.compliance_notice && (
                <Alert
                  tone={
                    analysisResult.reference_profile.analysis_status === "NEEDS_MORE_INFO"
                      ? "warning"
                      : "info"
                  }
                  title="Compliance & Data Notice"
                >
                  {analysisResult.compliance_notice}
                </Alert>
              )}

              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg border border-slate-800 bg-navy-950 p-2.5">
                  <div className="text-lg font-bold text-emerald-400">
                    {analysisResult.observed_count}
                  </div>
                  <div className="text-[11px] text-slate-400">Observed Facts</div>
                </div>
                <div className="rounded-lg border border-slate-800 bg-navy-950 p-2.5">
                  <div className="text-lg font-bold text-indigo-400">
                    {analysisResult.ai_derived_count}
                  </div>
                  <div className="text-[11px] text-slate-400">AI-Derived</div>
                </div>
                <div className="rounded-lg border border-slate-800 bg-navy-950 p-2.5">
                  <div className="text-lg font-bold text-rose-400">
                    {analysisResult.missing_count}
                  </div>
                  <div className="text-[11px] text-slate-400">Missing Info</div>
                </div>
              </div>

              {analysisResult.reference_profile.analysis_summary?.school_indicators &&
                analysisResult.reference_profile.analysis_summary.school_indicators.length > 0 && (
                  <div>
                    <div className="mb-1.5 text-xs font-medium text-slate-300">
                      Detected School Ecosystem Indicators
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {analysisResult.reference_profile.analysis_summary.school_indicators.map(
                        (ind) => (
                          <Badge key={ind} tone="indigo">
                            {ind}
                          </Badge>
                        )
                      )}
                    </div>
                  </div>
                )}

              <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                {analysisResult.reference_profile.indicators.map((ind) => (
                  <div
                    key={ind.id}
                    className="rounded-lg border border-slate-800 bg-navy-950/80 p-2.5 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-slate-200">{ind.attribute_value}</span>
                      <ClassificationBadge type={ind.classification_type} />
                    </div>
                    <p className="mt-1 text-slate-400">Evidence: {ind.evidence_text}</p>
                    <p className="mt-0.5 font-mono text-[10px] text-slate-500">
                      Source: {ind.source_reference} · Conf: {(ind.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                ))}
              </div>

              <div className="flex flex-col gap-2 pt-2">
                {analysisResult.reference_profile.analysis_status === "NEEDS_MORE_INFO" ? (
                  <Alert tone="warning" title="More information needed">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span>
                        Please fill missing fields ({analysisResult.missing_critical_fields.join(", ")})
                        and re-analyze before starting discovery.
                      </span>
                    </div>
                  </Alert>
                ) : (
                  <Button size="lg" onClick={handleStartDiscovery} disabled={startingJob}>
                    <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                    {startingJob ? "Starting Discovery Job…" : "Start Discovery & Hybrid Ranking"}
                    <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </Button>
                )}

                <Link
                  href={`/reference-profiles/${analysisResult.reference_profile.id}`}
                  className="text-center text-xs text-sky-400 hover:underline"
                >
                  Open full Reference Profile Analysis view →
                </Link>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
