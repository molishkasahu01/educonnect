"use client";

import React, { useState } from "react";
import { FileSpreadsheet, Globe, PlusCircle, Upload } from "lucide-react";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert, Button, Card, Input, Select, Textarea } from "@/components/ui/primitives";

interface ImportResult {
  imported_count: number;
  merged_duplicates_count: number;
  skipped_count: number;
  source_name: string;
  verification_status: string;
  authorization_recorded: boolean;
  warnings: string[];
}

export default function DatasetImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [sourceName, setSourceName] = useState("user_authorized_csv");
  const [verificationStatus, setVerificationStatus] = useState("unverified");
  const [datasetType, setDatasetType] = useState("USER_PROVIDED");
  const [authNote, setAuthNote] = useState("User confirmed authorized partner export");
  const [authConfirmed, setAuthConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  // Manual entry state
  const [manual, setManual] = useState({
    full_name: "",
    current_role: "",
    organization_name: "",
    location: "",
    professional_bio: "",
    experience_years: "",
    school_indicators: "",
    skills: "",
    verification_status: "unverified",
    authorization_confirmed: false,
  });
  const [manualMsg, setManualMsg] = useState<string | null>(null);

  // Permitted web source URL ingestion state
  const [webUrls, setWebUrls] = useState("");
  const [webSourceType, setWebSourceType] = useState<"organization_website" | "public_directory">("organization_website");
  const [webSourceName, setWebSourceName] = useState("official_org_website");
  const [webAuthNote, setWebAuthNote] = useState("Permitted public school/directory leadership page");
  const [webAuthConfirmed, setWebAuthConfirmed] = useState(false);
  const [webFetching, setWebFetching] = useState(false);

  const handleCsvSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!file) {
      setError("Please select a .csv file to upload.");
      return;
    }
    if (!authConfirmed) {
      setError("You must confirm upload authorization and compliance terms before ingesting data.");
      return;
    }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("source_name", sourceName);
      fd.append("verification_status", verificationStatus);
      fd.append("dataset_type", datasetType);
      fd.append("authorization_confirmed", "true");
      fd.append("authorization_note", authNote);

      const res = await apiRequest<ImportResult>("/api/candidates/import", {
        method: "POST",
        body: fd,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "CSV import failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setManualMsg(null);
    if (!manual.authorization_confirmed) {
      setError("Please confirm authorization before saving a manual candidate record.");
      return;
    }
    try {
      const res = await apiRequest<ImportResult>("/api/candidates/manual", {
        method: "POST",
        body: JSON.stringify({
          full_name: manual.full_name,
          current_role: manual.current_role || null,
          organization_name: manual.organization_name || null,
          location: manual.location || null,
          professional_bio: manual.professional_bio || null,
          experience_years: manual.experience_years ? Number(manual.experience_years) : null,
          school_indicators: manual.school_indicators
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          skills: manual.skills
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          verification_status: manual.verification_status,
          authorization_confirmed: true,
        }),
      });
      setManualMsg(
        `Added ${res.imported_count} candidate record (${res.merged_duplicates_count} duplicate merged).`
      );
      setManual({
        full_name: "",
        current_role: "",
        organization_name: "",
        location: "",
        professional_bio: "",
        experience_years: "",
        school_indicators: "",
        skills: "",
        verification_status: "unverified",
        authorization_confirmed: false,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Manual entry failed");
    }
  };

  const handleWebFetchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    const urls = webUrls
      .split(/[\n,]/)
      .map((u) => u.trim())
      .filter(Boolean);
    if (urls.length === 0) {
      setError("Please enter one or more permitted http(s) URLs.");
      return;
    }
    if (!webAuthConfirmed) {
      setError("Please confirm permitted public access and compliance terms.");
      return;
    }
    setWebFetching(true);
    try {
      const res = await apiRequest<ImportResult>("/api/candidates/fetch-url", {
        method: "POST",
        body: JSON.stringify({
          urls,
          source_type: webSourceType,
          source_name: webSourceName,
          authorization_confirmed: true,
          authorization_note: webAuthNote,
        }),
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to retrieve profiles from permitted URLs");
    } finally {
      setWebFetching(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Authorized Dataset Import</h1>
        <p className="mt-1 text-sm text-slate-400">
          Ingest user-authorized CSV exports or individual profiles through the canonical normalization & embedding pipeline.
        </p>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {manualMsg && <Alert tone="success">{manualMsg}</Alert>}
      {result && (
        <Alert tone="success" title="Ingestion Complete">
          Imported {result.imported_count} new profiles, merged {result.merged_duplicates_count}{" "}
          duplicates, skipped {result.skipped_count}. Authorization record saved.
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <div className="mb-4 flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-sky-400" aria-hidden="true" />
            <h2 className="text-base font-semibold text-white">CSV Bulk Import</h2>
          </div>

          <form onSubmit={handleCsvSubmit} className="space-y-4">
            <div>
              <label htmlFor="csv-file" className="mb-1 block text-xs font-medium text-slate-300">
                CSV File (max 10 MB)
              </label>
              <input
                id="csv-file"
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="block w-full rounded-lg border border-slate-700 bg-navy-950 p-2 text-xs text-slate-300 file:mr-3 file:rounded file:border-0 file:bg-indigo-600 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white"
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="src-name" className="mb-1 block text-xs font-medium text-slate-300">
                  Source Identifier
                </label>
                <Input
                  id="src-name"
                  value={sourceName}
                  onChange={(e) => setSourceName(e.target.value)}
                  required
                />
              </div>
              <div>
                <label htmlFor="ver-status" className="mb-1 block text-xs font-medium text-slate-300">
                  Verification Classification
                </label>
                <Select
                  id="ver-status"
                  value={verificationStatus}
                  onChange={(e) => setVerificationStatus(e.target.value)}
                >
                  <option value="verified">VERIFIED REAL</option>
                  <option value="unverified">UNVERIFIED REAL</option>
                </Select>
              </div>
            </div>

            <div>
              <label htmlFor="dataset-env" className="mb-1 block text-xs font-medium text-slate-300">
                Dataset Environment Tag
              </label>
              <Select
                id="dataset-env"
                value={datasetType}
                onChange={(e) => setDatasetType(e.target.value)}
              >
                <option value="USER_PROVIDED">USER_PROVIDED (Uploaded CSV / CRM Dataset)</option>
                <option value="REAL_DATA">REAL_DATA (Authorized Real Directory / Licensed Export)</option>
              </Select>
            </div>

            <div>
              <label htmlFor="auth-note" className="mb-1 block text-xs font-medium text-slate-300">
                Upload Authorization & Provenance Note
              </label>
              <Input
                id="auth-note"
                value={authNote}
                onChange={(e) => setAuthNote(e.target.value)}
                required
              />
            </div>

            <div className="flex items-start gap-2.5 rounded-lg border border-slate-800 bg-navy-950 p-3">
              <input
                id="auth-confirm"
                type="checkbox"
                checked={authConfirmed}
                onChange={(e) => setAuthConfirmed(e.target.checked)}
                className="mt-0.5 h-4 w-4"
              />
              <label htmlFor="auth-confirm" className="text-xs text-slate-300">
                I confirm this dataset was lawfully obtained without unauthorized LinkedIn scraping
                or access-control circumvention, and EduConnect is authorized to index it for my private workspace.
              </label>
            </div>

            <Button type="submit" className="w-full" disabled={submitting}>
              <Upload className="h-4 w-4" aria-hidden="true" />
              {submitting ? "Ingesting & Generating Embeddings…" : "Upload & Ingest CSV"}
            </Button>
          </form>
        </Card>

        <Card className="p-6">
          <div className="mb-4 flex items-center gap-2">
            <PlusCircle className="h-5 w-5 text-indigo-400" aria-hidden="true" />
            <h2 className="text-base font-semibold text-white">Manual Candidate Entry</h2>
          </div>

          <form onSubmit={handleManualSubmit} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                aria-label="Candidate full name"
                value={manual.full_name}
                onChange={(e) => setManual({ ...manual, full_name: e.target.value })}
                placeholder="Full Name *"
                required
              />
              <Input
                aria-label="Current role"
                value={manual.current_role}
                onChange={(e) => setManual({ ...manual, current_role: e.target.value })}
                placeholder="Current Role"
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                aria-label="Organization"
                value={manual.organization_name}
                onChange={(e) => setManual({ ...manual, organization_name: e.target.value })}
                placeholder="Organization"
              />
              <Input
                aria-label="Location"
                value={manual.location}
                onChange={(e) => setManual({ ...manual, location: e.target.value })}
                placeholder="City / Location"
              />
            </div>
            <Textarea
              aria-label="Professional biography"
              rows={3}
              value={manual.professional_bio}
              onChange={(e) => setManual({ ...manual, professional_bio: e.target.value })}
              placeholder="Biography & school ecosystem experience"
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                aria-label="School indicators"
                value={manual.school_indicators}
                onChange={(e) => setManual({ ...manual, school_indicators: e.target.value })}
                placeholder="School indicators (comma-separated)"
              />
              <Input
                aria-label="Experience years"
                type="number"
                min={0}
                max={65}
                value={manual.experience_years}
                onChange={(e) => setManual({ ...manual, experience_years: e.target.value })}
                placeholder="Years experience"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                id="manual-auth"
                type="checkbox"
                checked={manual.authorization_confirmed}
                onChange={(e) =>
                  setManual({ ...manual, authorization_confirmed: e.target.checked })
                }
                className="h-4 w-4"
              />
              <label htmlFor="manual-auth" className="text-xs text-slate-300">
                Confirm authorized profile entry
              </label>
            </div>
            <Button type="submit" variant="secondary" className="w-full">
              Add & Index Profile
            </Button>
          </form>
        </Card>
      </div>

      {/* Permitted School Website / Directory Live Collection */}
      <Card className="p-6">
        <div className="mb-4 flex items-center gap-2">
          <Globe className="h-5 w-5 text-emerald-400" aria-hidden="true" />
          <h2 className="text-base font-semibold text-white">
            Permitted Official Websites &amp; Education Directories (Live Retrieval)
          </h2>
        </div>
        <form onSubmit={handleWebFetchSubmit} className="space-y-4">
          <div>
            <label htmlFor="web-urls" className="mb-1 block text-xs font-medium text-slate-300">
              Permitted URLs (official school leadership pages, consultancy teams, speaker/association directories; comma or newline separated)
            </label>
            <Textarea
              id="web-urls"
              rows={2}
              value={webUrls}
              onChange={(e) => setWebUrls(e.target.value)}
              placeholder="https://schoolgroup.example.edu/leadership"
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label htmlFor="web-src-type" className="mb-1 block text-xs font-medium text-slate-300">
                Adapter Type
              </label>
              <Select
                id="web-src-type"
                value={webSourceType}
                onChange={(e) => setWebSourceType(e.target.value as "organization_website" | "public_directory")}
              >
                <option value="organization_website">Official School / Consultancy Website</option>
                <option value="public_directory">Education / Speaker Directory</option>
              </Select>
            </div>
            <div>
              <label htmlFor="web-src-name" className="mb-1 block text-xs font-medium text-slate-300">
                Source Identifier
              </label>
              <Input
                id="web-src-name"
                value={webSourceName}
                onChange={(e) => setWebSourceName(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="web-auth-note" className="mb-1 block text-xs font-medium text-slate-300">
                Permission / Robots Note
              </label>
              <Input
                id="web-auth-note"
                value={webAuthNote}
                onChange={(e) => setWebAuthNote(e.target.value)}
                required
              />
            </div>
          </div>
          <div className="flex items-start gap-2.5 rounded-lg border border-slate-800 bg-navy-950 p-3">
            <input
              id="web-auth-confirm"
              type="checkbox"
              checked={webAuthConfirmed}
              onChange={(e) => setWebAuthConfirmed(e.target.checked)}
              className="mt-0.5 h-4 w-4"
            />
            <label htmlFor="web-auth-confirm" className="text-xs text-slate-300">
              Confirm these URLs are permitted public pages/feeds (not LinkedIn or auth-gated) and comply with robots.txt and source terms.
            </label>
          </div>
          <Button type="submit" disabled={webFetching}>
            <Globe className="h-4 w-4" aria-hidden="true" />
            {webFetching ? "Fetching & Extracting Permitted Pages…" : "Fetch & Index Real Profiles"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
