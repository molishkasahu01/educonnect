"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Building2, ExternalLink, MapPin } from "lucide-react";
import { apiRequest, ApiError } from "@/lib/api";
import {
  Alert,
  Badge,
  Card,
  ClassificationBadge,
  DatasetEnvironmentBadge,
  VerificationBadge,
} from "@/components/ui/primitives";
import { formatDateTime } from "@/lib/utils";

interface CandidateDetail {
  id: string;
  full_name: string;
  linkedin_url: string | null;
  current_role: string | null;
  organization_name: string | null;
  location: string | null;
  professional_bio: string | null;
  experience_years: number | null;
  education_segments: string[];
  school_indicators: string[];
  organizations_list: string[];
  skills: string[];
  influence_indicators: string[];
  primary_source: string;
  source_url: string | null;
  source_record_id: string;
  verification_status: string;
  dataset_type?: string;
  data_confidence: number;
  data_freshness_days: number;
  usage_restrictions: string;
  last_updated: string;
  indicators: {
    id: string;
    category: string;
    attribute_name: string;
    attribute_value: string;
    evidence_text: string;
    source_reference: string;
    classification_type: string;
    confidence: number;
    extraction_timestamp: string;
  }[];
  sources: {
    id: string;
    source_name: string;
    source_url: string | null;
    source_record_id: string;
    collection_timestamp: string;
    verification_status: string;
    data_confidence: number;
    data_freshness: string;
    usage_restrictions: string;
    upload_authorization_note: string | null;
  }[];
}

export default function CandidateDetailPage() {
  const params = useParams<{ id: string }>();
  const [cand, setCand] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<CandidateDetail>(`/api/candidates/${params.id}`)
      .then(setCand)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load candidate"))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) return <Card className="h-72 animate-pulse p-6" />;
  if (error || !cand) {
    return (
      <Alert tone="error" title="Error">
        {error || "Candidate not found"}
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/candidates"
          className="mb-2 inline-flex items-center gap-1 text-xs text-sky-400 hover:underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> Back to Candidate Pool
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-white">{cand.full_name}</h1>
          <VerificationBadge status={cand.verification_status} />
          <DatasetEnvironmentBadge datasetType={cand.dataset_type} />
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-4 text-sm text-slate-400">
          <span>{cand.current_role || "Role unspecified"}</span>
          {cand.organization_name && (
            <span className="inline-flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5" aria-hidden="true" /> {cand.organization_name}
            </span>
          )}
          {cand.location && (
            <span className="inline-flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5" aria-hidden="true" /> {cand.location}
            </span>
          )}
          {cand.experience_years != null && <span>{cand.experience_years} years documented</span>}
        </div>
      </div>

      {cand.verification_status === "unverified" && (
        <Alert tone="warning" title="Unverified Real Record Notice">
          This record comes from a user-authorized upload or unverified directory source ({cand.primary_source}).
          Verify source links and credentials manually before outreach.
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="space-y-4 p-5 lg:col-span-1">
          <h2 className="text-sm font-semibold text-white">Profile Overview</h2>
          <p className="text-xs leading-relaxed text-slate-300">
            {cand.professional_bio || "No professional biography documented in source record."}
          </p>

          <div>
            <h3 className="mb-1.5 text-xs font-medium text-slate-400">School Ecosystem Indicators</h3>
            <div className="flex flex-wrap gap-1.5">
              {cand.school_indicators.length > 0 ? (
                cand.school_indicators.map((ind) => (
                  <Badge key={ind} tone="indigo">
                    {ind}
                  </Badge>
                ))
              ) : (
                <span className="text-xs text-slate-500">None documented</span>
              )}
            </div>
          </div>

          <div>
            <h3 className="mb-1.5 text-xs font-medium text-slate-400">Documented Organizations</h3>
            <ul className="space-y-1 text-xs text-slate-300">
              {cand.organizations_list.map((o) => (
                <li key={o}>• {o}</li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="mb-1.5 text-xs font-medium text-slate-400">Influence Signals</h3>
            <ul className="space-y-1 text-xs text-slate-300">
              {cand.influence_indicators.length > 0 ? (
                cand.influence_indicators.map((inf) => <li key={inf}>• {inf}</li>)
              ) : (
                <li className="text-slate-500">No explicit influence indicators</li>
              )}
            </ul>
          </div>

          <div>
            <h3 className="mb-1.5 text-xs font-medium text-slate-400">Skills</h3>
            <div className="flex flex-wrap gap-1.5">
              {cand.skills.map((s) => (
                <Badge key={s} tone="neutral">
                  {s}
                </Badge>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-3 pt-1">
            {cand.source_url && (
              <a
                href={cand.source_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-emerald-300 hover:underline"
              >
                Original Source Page <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
            {cand.linkedin_url && (
              <a
                href={cand.linkedin_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-sky-400 hover:underline"
              >
                Sourced LinkedIn Reference <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
        </Card>

        <div className="space-y-6 lg:col-span-2">
          <Card className="p-5">
            <h2 className="mb-2 text-sm font-semibold text-white">
              Attribute Evidence &amp; Classification ({cand.indicators.length})
            </h2>
            <p className="mb-3 text-xs text-slate-400">
              Attributes distinguish{" "}
              <strong className="text-emerald-300">OBSERVED FACT</strong> and{" "}
              <strong className="text-sky-300">SOURCE-SUPPORTED FACT</strong> from{" "}
              <strong className="text-indigo-300">AI-DERIVED CLASSIFICATION</strong> and{" "}
              <strong className="text-amber-300">UNVERIFIED INFORMATION</strong>. Undocumented school relationships are never claimed as verified.
            </p>
            <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4 text-center text-xs">
              <div className="rounded border border-slate-800 bg-navy-950 p-2">
                <div className="font-bold text-emerald-400">
                  {cand.indicators.filter((i) => ["OBSERVED_FACT", "DIRECTLY_OBSERVED"].includes(i.classification_type.toUpperCase())).length}
                </div>
                <div className="text-[10px] text-slate-400">Observed Facts</div>
              </div>
              <div className="rounded border border-slate-800 bg-navy-950 p-2">
                <div className="font-bold text-sky-400">
                  {cand.indicators.filter((i) => i.classification_type.toUpperCase().startsWith("SOURCE_SUPPORTED")).length}
                </div>
                <div className="text-[10px] text-slate-400">Source-Supported</div>
              </div>
              <div className="rounded border border-slate-800 bg-navy-950 p-2">
                <div className="font-bold text-indigo-400">
                  {cand.indicators.filter((i) => i.classification_type.toUpperCase().startsWith("AI_DERIVED")).length}
                </div>
                <div className="text-[10px] text-slate-400">AI-Derived</div>
              </div>
              <div className="rounded border border-slate-800 bg-navy-950 p-2">
                <div className="font-bold text-amber-400">
                  {cand.indicators.filter((i) => i.classification_type.toUpperCase().includes("UNVERIFIED")).length}
                </div>
                <div className="text-[10px] text-slate-400">Unverified</div>
              </div>
            </div>
            <div className="space-y-2.5">
              {cand.indicators.map((ind) => (
                <div
                  key={ind.id}
                  className="rounded-lg border border-slate-800 bg-navy-950/70 p-3 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-slate-100">
                      {ind.attribute_name}: {ind.attribute_value}
                    </span>
                    <ClassificationBadge type={ind.classification_type} />
                  </div>
                  <p className="mt-1 text-slate-400">Supporting Evidence: {ind.evidence_text}</p>
                  <p className="mt-0.5 font-mono text-[10px] text-slate-500">
                    Source Ref: {ind.source_reference} · Confidence: {(ind.confidence * 100).toFixed(0)}%
                  </p>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="mb-3 text-sm font-semibold text-white">
              Record Provenance & Usage Restrictions
            </h2>
            <div className="space-y-3">
              {cand.sources.map((src) => (
                <div
                  key={src.id}
                  className="rounded-lg border border-slate-800 bg-navy-950/70 p-3 text-xs space-y-1"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-slate-200">{src.source_name}</span>
                    <VerificationBadge status={src.verification_status} />
                  </div>
                  <div className="font-mono text-[11px] text-slate-400">
                    Record ID: {src.source_record_id} · Freshness: {src.data_freshness} ·
                    Collected: {formatDateTime(src.collection_timestamp)}
                  </div>
                  {src.source_url && (
                    <div>
                      <a
                        href={src.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-emerald-300 hover:underline break-all"
                      >
                        {src.source_url} <ExternalLink className="h-3 w-3 shrink-0" />
                      </a>
                    </div>
                  )}
                  <div className="text-slate-400">Restrictions: {src.usage_restrictions}</div>
                  {src.upload_authorization_note && (
                    <div className="text-emerald-300">
                      Authorization Note: {src.upload_authorization_note}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
