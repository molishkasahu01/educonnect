"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Bookmark,
  ChevronDown,
  ChevronUp,
  Download,
  ExternalLink,
  Filter,
  Search,
  Sparkles,
} from "lucide-react";
import { apiRequest, ApiError, downloadAuthorizedFile } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  buttonVariants,
  Card,
  DatasetEnvironmentBadge,
  Input,
  ScoreBar,
  Select,
  VerificationBadge,
} from "@/components/ui/primitives";
import { scoreColorClass } from "@/lib/utils";

interface CandidateSummary {
  id: string;
  full_name: string;
  linkedin_url: string | null;
  current_role: string | null;
  organization_name: string | null;
  location: string | null;
  professional_bio: string | null;
  experience_years: number | null;
  school_indicators: string[];
  primary_source: string;
  source_url: string | null;
  source_record_id: string;
  verification_status: string;
  dataset_type?: string;
}

interface ResultItem {
  id: string;
  rank_position: number;
  relevance_score: number;
  evidence_confidence: number;
  meets_minimum_evidence: boolean;
  relevance_tier: string;
  candidate: CandidateSummary;
  ranking_score: {
    semantic_similarity: number;
    school_ecosystem_relevance: number;
    professional_role_similarity: number;
    experience_similarity: number;
    organization_network_overlap: number;
    influence_indicators_score: number;
    cross_encoder_score: number | null;
    available_components: Record<string, boolean>;
    ranking_model_version: string;
  };
  explanation: {
    summary_explanation: string;
    matched_attributes: { dimension: string; attribute: string; evidence: string; source_ref: string }[];
    missing_evidence_notes: string[];
  };
}

interface ResultsResponse {
  job: {
    id: string;
    total_candidates_evaluated: number;
    relevant_candidates_count: number;
    processing_time_ms: number | null;
    ranking_model_version: string;
    embedding_model_name: string;
  };
  reference_profile_summary: {
    id: string;
    full_name: string;
    current_designation: string;
    school_indicators: string[];
  };
  dataset_provenance_summary: Record<string, number>;
  discovery_mode?: string;
  selected_sources?: string[];
  provider_diagnostics?: {
    providers_checked?: string[];
    unconfigured_providers?: string[];
    errors?: string[];
    live_fetched_count?: number;
  };
  empty_state_message?: string | null;
  total_matched: number;
  page: number;
  page_size: number;
  items: ResultItem[];
}

interface SavedListSummary {
  id: string;
  name: string;
  items: { candidate_id: string }[];
}

export default function DiscoveryResultsPage() {
  const params = useParams<{ jobId: string }>();
  const [data, setData] = useState<ResultsResponse | null>(null);
  const [lists, setLists] = useState<SavedListSummary[]>([]);
  const [selectedListId, setSelectedListId] = useState<string>("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Filters & sorting
  const [q, setQ] = useState("");
  const [indicator, setIndicator] = useState("");
  const [location, setLocation] = useState("");
  const [verificationStatus, setVerificationStatus] = useState("");
  const [sortBy, setSortBy] = useState("relevance");
  const [page, setPage] = useState(1);

  const loadResults = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({
        page: String(page),
        page_size: "25",
        sort_by: sortBy,
      });
      if (q.trim()) qs.set("q", q.trim());
      if (indicator) qs.set("indicator", indicator);
      if (location.trim()) qs.set("location", location.trim());
      if (verificationStatus) qs.set("verification_status", verificationStatus);

      const resp = await apiRequest<ResultsResponse>(
        `/api/discovery/${params.jobId}/results?${qs.toString()}`
      );
      setData(resp);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load results");
    } finally {
      setLoading(false);
    }
  }, [params.jobId, page, sortBy, q, indicator, location, verificationStatus]);

  const loadLists = useCallback(async () => {
    try {
      const l = await apiRequest<SavedListSummary[]>("/api/lists");
      setLists(l);
      if (l.length > 0 && !selectedListId) {
        setSelectedListId(l[0].id);
      }
    } catch {
      // non-fatal
    }
  }, [selectedListId]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  useEffect(() => {
    loadLists();
  }, [loadLists]);

  const handleToggleShortlist = async (candidateId: string, alreadyInList: boolean) => {
    setToast(null);
    try {
      let targetListId = selectedListId;
      if (!targetListId) {
        const created = await apiRequest<SavedListSummary>("/api/lists", {
          method: "POST",
          body: JSON.stringify({
            name: "K-12 Discovery Shortlist",
            description: "Created from discovery results",
          }),
        });
        targetListId = created.id;
        setSelectedListId(created.id);
      }

      if (alreadyInList) {
        await apiRequest(`/api/lists/${targetListId}/candidates/${candidateId}`, {
          method: "DELETE",
        });
        setToast("Candidate removed from shortlist");
      } else {
        await apiRequest(`/api/lists/${targetListId}/candidates`, {
          method: "POST",
          body: JSON.stringify({ candidate_id: candidateId, discovery_job_id: params.jobId }),
        });
        setToast("Candidate added to shortlist");
      }
      await loadLists();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Shortlist update failed");
    }
  };

  const activeList = lists.find((l) => l.id === selectedListId);
  const shortlistedIds = new Set((activeList?.items || []).map((i) => i.candidate_id));

  return (
    <div className="space-y-6">
      {/* Header & Exports */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-bold text-white">Discovery Results</h1>
            {data?.discovery_mode && <DatasetEnvironmentBadge datasetType={data.discovery_mode} />}
          </div>
          {data && (
            <p className="mt-1 text-xs text-slate-400">
              Reference: <strong className="text-slate-200">{data.reference_profile_summary.full_name}</strong> ·
              Job <span className="font-mono">{data.job.id.slice(0, 8)}</span> ·{" "}
              {data.job.total_candidates_evaluated} evaluated ·{" "}
              <span className="text-emerald-400 font-medium">
                {data.job.relevant_candidates_count} relevant
              </span>{" "}
              · {data.job.processing_time_ms ?? 0}ms · {data.job.embedding_model_name} (
              {data.job.ranking_model_version})
            </p>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              downloadAuthorizedFile(
                `/api/discovery/${params.jobId}/export/csv`,
                `educonnect_discovery_${params.jobId}.csv`
              )
            }
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" /> Export CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              downloadAuthorizedFile(
                `/api/discovery/${params.jobId}/export/xlsx`,
                `educonnect_discovery_${params.jobId}.xlsx`
              )
            }
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" /> Export XLSX
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              downloadAuthorizedFile(
                `/api/discovery/${params.jobId}/export/json`,
                `educonnect_discovery_${params.jobId}.json`
              )
            }
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" /> Export JSON
          </Button>
        </div>
      </div>

      {data && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-800 bg-navy-900/70 px-4 py-2.5 text-xs text-slate-300">
          <span className="font-semibold text-slate-200">Record Provenance:</span>
          <Badge tone="emerald">Verified Real: {data.dataset_provenance_summary.verified || 0}</Badge>
          <Badge tone="amber">Unverified Real: {data.dataset_provenance_summary.unverified || 0}</Badge>
          {data.job.total_candidates_evaluated > 0 && data.job.total_candidates_evaluated < 20 && (
            <span className="text-[11px] text-slate-400">
              Showing all {data.job.total_candidates_evaluated} real profiles found (EduConnect never pads shortlists with fabricated data).
            </span>
          )}
          <div className="ml-auto flex items-center gap-2">
            <label htmlFor="shortlist-select" className="text-slate-400">
              Active Shortlist:
            </label>
            <Select
              id="shortlist-select"
              value={selectedListId}
              onChange={(e) => setSelectedListId(e.target.value)}
              className="w-48 min-h-[34px] py-1 text-xs"
            >
              {lists.length === 0 && <option value="">Auto-create Shortlist</option>}
              {lists.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name} ({l.items.length})
                </option>
              ))}
            </Select>
          </div>
        </div>
      )}

      {toast && (
        <Alert tone="success">{toast}</Alert>
      )}
      {error && (
        <Alert tone="error" title="Error">
          {error}
        </Alert>
      )}

      {/* Search & Faceted Filters */}
      <Card className="p-4">
        <search>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              loadResults();
            }}
            className="grid gap-3 md:grid-cols-12"
          >
            <div className="relative md:col-span-4">
              <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-500" />
              <Input
                aria-label="Search candidates"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPage(1);
                }}
                placeholder="Search name, role, org, or bio..."
                className="pl-9"
              />
            </div>

            <div className="md:col-span-3">
              <Select
                aria-label="Filter by ecosystem role or indicator"
                value={indicator}
                onChange={(e) => {
                  setIndicator(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All Roles / Indicators</option>
                <option value="principal">Principal</option>
                <option value="consultant">Education Consultant</option>
                <option value="school ownership">School Owner</option>
                <option value="school directorship">School Director</option>
                <option value="trustee">Trustee</option>
                <option value="entrepreneur">Education Entrepreneur</option>
              </Select>
            </div>

            <div className="md:col-span-2">
              <Input
                aria-label="Filter by location"
                value={location}
                onChange={(e) => {
                  setLocation(e.target.value);
                  setPage(1);
                }}
                placeholder="Location (e.g. Mumbai)"
              />
            </div>

            <div className="md:col-span-3">
              <Select
                aria-label="Sort results"
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value);
                  setPage(1);
                }}
              >
                <option value="relevance">Sort: Highest Relevance</option>
                <option value="confidence">Sort: Highest Confidence</option>
                <option value="school_indicators">Sort: School Indicators</option>
                <option value="role_similarity">Sort: Role Similarity</option>
              </Select>
            </div>
          </form>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <Filter className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
            <span className="text-slate-400">Verification filter:</span>
            {["", "verified", "unverified"].map((v) => (
              <button
                key={v || "all"}
                type="button"
                onClick={() => {
                  setVerificationStatus(v);
                  setPage(1);
                }}
                className={`rounded-md px-2.5 py-1 transition-colors ${
                  verificationStatus === v
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                {v ? v.toUpperCase() : "ALL"}
              </button>
            ))}
          </div>
        </search>
      </Card>

      {/* Results List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} className="h-36 animate-pulse p-5" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        data?.empty_state_message ? (
          <Card className="p-8 space-y-4">
            <Alert tone="info" title="No Verified or Authorized Professional Profiles Found">
              {data.empty_state_message}
            </Alert>
            {data.provider_diagnostics?.providers_checked && (
              <div className="rounded-lg border border-slate-800 bg-navy-950/70 p-4 text-xs text-slate-300 space-y-1.5">
                <div className="font-semibold text-slate-200">Provider Check Diagnostics</div>
                <div>Sources checked: {data.provider_diagnostics.providers_checked.join(", ")}</div>
                {data.provider_diagnostics.unconfigured_providers &&
                  data.provider_diagnostics.unconfigured_providers.length > 0 && (
                    <div className="text-amber-300">
                      Unconfigured credentialed providers:{" "}
                      {data.provider_diagnostics.unconfigured_providers.join(", ")} (set LICENSED_DATA_API_URL &amp; LICENSED_DATA_API_KEY)
                    </div>
                  )}
                {data.provider_diagnostics.errors && data.provider_diagnostics.errors.length > 0 && (
                  <div className="text-rose-300">
                    Provider notices: {data.provider_diagnostics.errors.join("; ")}
                  </div>
                )}
              </div>
            )}
            <div className="flex flex-wrap gap-2.5">
              <Link href="/datasets/import" className={buttonVariants()}>
                Upload Authorized CSV / CRM Export
              </Link>
              <Link href="/datasets/sources" className={buttonVariants({ variant: "outline" })}>
                Inspect Data Sources &amp; Compliance
              </Link>
              <Link href="/discovery/new" className={buttonVariants({ variant: "ghost" })}>
                Start New Discovery Run
              </Link>
            </div>
          </Card>
        ) : (
          <Card className="p-8 text-center">
            <p className="text-sm text-slate-300">No candidates match the active filters.</p>
          </Card>
        )
      ) : (
        <div className="space-y-3">
          {data.items.map((item) => {
            const expanded = expandedId === item.id;
            const isShortlisted = shortlistedIds.has(item.candidate.id);
            return (
              <Card key={item.id} className="p-5 transition-colors hover:border-slate-700">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-slate-500">#{item.rank_position}</span>
                      <Link
                        href={`/candidates/${item.candidate.id}`}
                        className="text-base font-semibold text-white hover:text-sky-300 hover:underline"
                      >
                        {item.candidate.full_name}
                      </Link>
                      <VerificationBadge status={item.candidate.verification_status} />
                      <DatasetEnvironmentBadge datasetType={item.candidate.dataset_type} />
                      <Badge
                        tone={
                          item.relevance_tier === "HIGHLY_RELEVANT"
                            ? "emerald"
                            : item.relevance_tier === "PARTIALLY_RELEVANT"
                            ? "sky"
                            : "neutral"
                        }
                      >
                        {item.relevance_tier.replace(/_/g, " ")}
                      </Badge>
                    </div>

                    <div className="text-sm text-slate-300">
                      {item.candidate.current_role || "Role unspecified"}
                      {item.candidate.organization_name && (
                        <span className="text-slate-400"> · {item.candidate.organization_name}</span>
                      )}
                      {item.candidate.location && (
                        <span className="text-slate-500"> · {item.candidate.location}</span>
                      )}
                      {item.candidate.experience_years != null && (
                        <span className="text-slate-400"> · {item.candidate.experience_years} yrs</span>
                      )}
                    </div>

                    <p className="text-xs leading-relaxed text-slate-300">
                      <Sparkles className="mr-1 inline h-3.5 w-3.5 text-indigo-400" aria-hidden="true" />
                      {item.explanation.summary_explanation}
                    </p>

                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {item.candidate.school_indicators.slice(0, 6).map((ind) => (
                        <Badge key={ind} tone="indigo">
                          {ind}
                        </Badge>
                      ))}
                      <Badge tone="neutral">Source: {item.candidate.primary_source}</Badge>
                      {item.candidate.source_url && (
                        <a
                          href={item.candidate.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 rounded border border-emerald-700/60 bg-emerald-950/30 px-2 py-0.5 text-xs text-emerald-300 hover:bg-emerald-950/60"
                        >
                          Original Source <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                      {item.candidate.linkedin_url && (
                        <a
                          href={item.candidate.linkedin_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 rounded border border-slate-700 px-2 py-0.5 text-xs text-sky-400 hover:bg-slate-800"
                        >
                          LinkedIn <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Scores & Actions */}
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <div className="flex items-center gap-4 rounded-lg border border-slate-800 bg-navy-950 px-3.5 py-2">
                      <div className="text-right">
                        <div className="text-[10px] uppercase tracking-wider text-slate-400">
                          Relevance
                        </div>
                        <div className={`text-lg font-bold ${scoreColorClass(item.relevance_score)}`}>
                          {item.relevance_score.toFixed(1)}
                        </div>
                      </div>
                      <div className="h-8 w-px bg-slate-800" />
                      <div className="text-right">
                        <div className="text-[10px] uppercase tracking-wider text-slate-400">
                          Confidence
                        </div>
                        <div className="text-lg font-bold text-slate-200">
                          {item.evidence_confidence.toFixed(0)}%
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant={isShortlisted ? "secondary" : "primary"}
                        size="sm"
                        onClick={() => handleToggleShortlist(item.candidate.id, isShortlisted)}
                      >
                        <Bookmark className="h-3.5 w-3.5" aria-hidden="true" />
                        {isShortlisted ? "Shortlisted" : "Shortlist"}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        aria-expanded={expanded}
                        onClick={() => setExpandedId(expanded ? null : item.id)}
                      >
                        Score Breakdown
                        {expanded ? (
                          <ChevronUp className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5" />
                        )}
                      </Button>
                      <Link
                        href={`/candidates/${item.candidate.id}`}
                        className={buttonVariants({ variant: "ghost", size: "sm" })}
                      >
                        Inspect
                      </Link>
                    </div>
                  </div>
                </div>

                {expanded && (
                  <div className="mt-4 border-t border-slate-800 pt-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2.5">
                        <div className="text-xs font-semibold text-slate-200">
                          Hybrid Score Breakdown ({item.ranking_score.ranking_model_version})
                        </div>
                        <ScoreBar
                          label="Semantic Similarity (30%)"
                          value={item.ranking_score.semantic_similarity}
                        />
                        <ScoreBar
                          label="School Ecosystem Relevance (25%)"
                          value={item.ranking_score.school_ecosystem_relevance}
                        />
                        <ScoreBar
                          label="Professional Role Similarity (15%)"
                          value={item.ranking_score.professional_role_similarity}
                        />
                        <ScoreBar
                          label="Experience Similarity (10%)"
                          value={item.ranking_score.experience_similarity}
                        />
                        <ScoreBar
                          label="Organization & Network Overlap (10%)"
                          value={item.ranking_score.organization_network_overlap}
                        />
                        <ScoreBar
                          label="Influence Indicators (10%)"
                          value={item.ranking_score.influence_indicators_score}
                        />
                      </div>

                      <div className="space-y-2.5 text-xs">
                        <div className="font-semibold text-slate-200">Supporting Evidence</div>
                        {item.explanation.matched_attributes.length === 0 ? (
                          <p className="text-slate-400">No strong attribute matches documented.</p>
                        ) : (
                          <ul className="space-y-1.5">
                            {item.explanation.matched_attributes.map((m, i) => (
                              <li
                                key={i}
                                className="rounded border border-slate-800 bg-navy-950 p-2 text-slate-300"
                              >
                                <span className="font-medium text-sky-300">{m.attribute}:</span>{" "}
                                {m.evidence}
                                <div className="mt-0.5 font-mono text-[10px] text-slate-500">
                                  Ref: {m.source_ref}
                                </div>
                              </li>
                            ))}
                          </ul>
                        )}
                        {item.explanation.missing_evidence_notes.length > 0 && (
                          <div className="rounded border border-amber-900/60 bg-amber-950/30 p-2 text-amber-200">
                            <div className="font-semibold">Missing Evidence Handling:</div>
                            {item.explanation.missing_evidence_notes.join(" ")}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}

          {/* Pagination */}
          <div className="flex items-center justify-between pt-2 text-xs text-slate-400">
            <span>
              Showing page {data.page} · {data.total_matched} matching candidates
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page * data.page_size >= data.total_matched}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
