"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Sparkles } from "lucide-react";
import { apiRequest, ApiError } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  ClassificationBadge,
} from "@/components/ui/primitives";
import { formatDateTime } from "@/lib/utils";

interface ReferenceDetail {
  id: string;
  full_name: string | null;
  linkedin_url: string | null;
  current_designation: string | null;
  current_organization: string | null;
  location: string | null;
  professional_bio: string | null;
  career_history: string | null;
  education_sector_experience: string | null;
  skills: string[];
  analysis_status: string;
  analysis_summary: {
    school_indicators?: string[];
    influence_indicators?: string[];
    organizations?: string[];
    experience_years?: number | null;
    seniority?: string;
    compliance_notice?: string | null;
  } | null;
  created_at: string;
  indicators: {
    id: string;
    category: string;
    attribute_name: string;
    attribute_value: string;
    evidence_text: string;
    source_reference: string;
    classification_type: string;
    confidence: number;
  }[];
}

export default function ReferenceProfileDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [profile, setProfile] = useState<ReferenceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    apiRequest<ReferenceDetail>(`/api/reference-profiles/${params.id}`)
      .then(setProfile)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load reference profile"))
      .finally(() => setLoading(false));
  }, [params.id]);

  const startDiscovery = async () => {
    if (!profile) return;
    setRunning(true);
    try {
      const job = await apiRequest<{ id: string }>("/api/discovery", {
        method: "POST",
        body: JSON.stringify({ reference_profile_id: profile.id }),
      });
      router.push(`/discovery/${job.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to start discovery");
      setRunning(false);
    }
  };

  if (loading) return <Card className="h-64 animate-pulse p-6" />;
  if (error || !profile) {
    return (
      <Alert tone="error" title="Error">
        {error || "Reference profile not found"}
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link
            href="/discovery/new"
            className="mb-2 inline-flex items-center gap-1 text-xs text-sky-400 hover:underline"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> Back to Reference Input
          </Link>
          <h1 className="text-2xl font-bold text-white">
            {profile.full_name || "Reference Profile Analysis"}
          </h1>
          <p className="text-sm text-slate-400">
            {profile.current_designation || "Unspecified Role"} ·{" "}
            {profile.current_organization || "Unspecified Org"} · Created{" "}
            {formatDateTime(profile.created_at)}
          </p>
        </div>
        <Button onClick={startDiscovery} disabled={running}>
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          {running ? "Starting Discovery…" : "Launch Discovery Run"}
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>

      {profile.analysis_summary?.compliance_notice && (
        <Alert tone="info" title="Compliance Note">
          {profile.analysis_summary.compliance_notice}
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="space-y-4 p-5 lg:col-span-1">
          <h2 className="text-sm font-semibold text-white">Extracted Summary</h2>
          <div className="space-y-2 text-xs">
            <div>
              <span className="text-slate-400">Analysis Status:</span>{" "}
              <Badge tone="emerald">{profile.analysis_status}</Badge>
            </div>
            <div>
              <span className="text-slate-400">Seniority:</span>{" "}
              <span className="text-slate-200">
                {profile.analysis_summary?.seniority || "Not classified"}
              </span>
            </div>
            <div>
              <span className="text-slate-400">Documented Tenure:</span>{" "}
              <span className="text-slate-200">
                {profile.analysis_summary?.experience_years
                  ? `${profile.analysis_summary.experience_years} years`
                  : "Not documented"}
              </span>
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-xs font-medium text-slate-400">School Ecosystem Indicators</h3>
            <div className="flex flex-wrap gap-1.5">
              {(profile.analysis_summary?.school_indicators || []).map((ind) => (
                <Badge key={ind} tone="indigo">
                  {ind}
                </Badge>
              ))}
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-xs font-medium text-slate-400">Biography</h3>
            <p className="text-xs leading-relaxed text-slate-300">
              {profile.professional_bio || "No biography supplied."}
            </p>
          </div>
        </Card>

        <Card className="p-5 lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold text-white">
            Structured Attribute Provenance ({profile.indicators.length})
          </h2>
          <div className="space-y-2.5">
            {profile.indicators.map((ind) => (
              <div
                key={ind.id}
                className="rounded-lg border border-slate-800 bg-navy-950/70 p-3 text-xs"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-medium text-slate-100">
                    <span className="uppercase text-slate-500">{ind.category}</span> ·{" "}
                    {ind.attribute_name}: {ind.attribute_value}
                  </div>
                  <ClassificationBadge type={ind.classification_type} />
                </div>
                <p className="mt-1 text-slate-400">Evidence: {ind.evidence_text}</p>
                <p className="mt-0.5 font-mono text-[10px] text-slate-500">
                  Source: {ind.source_reference} · Confidence: {(ind.confidence * 100).toFixed(0)}%
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
