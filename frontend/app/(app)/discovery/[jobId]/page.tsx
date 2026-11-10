"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Loader2,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert, Badge, Button, buttonVariants, Card, DatasetEnvironmentBadge } from "@/components/ui/primitives";
import { formatDateTime } from "@/lib/utils";

interface StageLog {
  stage: string;
  progress_percent: number;
  detail: string;
  timestamp: string;
}

interface DiscoveryJob {
  id: string;
  reference_profile_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "RETRYING";
  current_stage: string;
  progress_percent: number;
  stage_logs: StageLog[];
  total_candidates_evaluated: number;
  relevant_candidates_count: number;
  processing_time_ms: number | null;
  ranking_model_version: string;
  embedding_model_name: string;
  discovery_mode?: string;
  selected_sources?: string[];
  error_message: string | null;
  retry_count: number;
  created_at: string;
}

export default function DiscoveryProgressPage() {
  const params = useParams<{ jobId: string }>();
  const [job, setJob] = useState<DiscoveryJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const data = await apiRequest<DiscoveryJob>(`/api/discovery/${params.jobId}`);
        if (!active) return;
        setJob(data);
        if (data.status === "PENDING" || data.status === "RUNNING" || data.status === "RETRYING") {
          timer = setTimeout(poll, 750);
        }
      } catch (err) {
        if (active) setError(err instanceof ApiError ? err.detail : "Failed to fetch job status");
      }
    };

    poll();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [params.jobId]);

  const handleRetry = async () => {
    if (!job) return;
    setRetrying(true);
    setError(null);
    try {
      const updated = await apiRequest<DiscoveryJob>(`/api/discovery/${job.id}/retry`, {
        method: "POST",
      });
      setJob(updated);
      setTimeout(() => window.location.reload(), 800);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Retry failed");
    } finally {
      setRetrying(false);
    }
  };

  if (error) {
    return (
      <Alert tone="error" title="Job Monitoring Error">
        {error}
      </Alert>
    );
  }

  if (!job) {
    return <Card className="h-56 animate-pulse p-6" />;
  }

  const isFinished = job.status === "COMPLETED";
  const isFailed = job.status === "FAILED";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-bold text-white">Discovery Pipeline Progress</h1>
            <DatasetEnvironmentBadge datasetType={job.discovery_mode} />
          </div>
          <p className="mt-1 font-mono text-xs text-slate-400">
            Job ID: {job.id} · Model: {job.embedding_model_name} · Ranker: {job.ranking_model_version}
          </p>
        </div>
        <div className="flex gap-2">
          {(isFailed || isFinished) && (
            <Button variant="outline" onClick={handleRetry} disabled={retrying}>
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Re-run Discovery
            </Button>
          )}
          {isFinished && (
            <Link href={`/discovery/${job.id}/results`} className={buttonVariants()}>
              View Ranked Results ({job.total_candidates_evaluated})
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          )}
        </div>
      </div>

      {isFinished && job.total_candidates_evaluated === 0 && (
        <Alert tone="info" title="No Verified or Authorized Profiles Found">
          No verified or authorized professional profiles were found for this discovery.{" "}
          <Link href="/datasets/import" className="underline font-semibold">
            Connect an authorized source or import genuine professional records →
          </Link>
        </Alert>
      )}

      {isFailed && (
        <Alert tone="error" title="Discovery Job Failed">
          {job.error_message || "An unexpected error occurred in the background pipeline."}
        </Alert>
      )}

      <Card className="p-6">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            {isFinished ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-400" aria-hidden="true" />
            ) : isFailed ? (
              <XCircle className="h-5 w-5 text-rose-400" aria-hidden="true" />
            ) : (
              <Loader2 className="h-5 w-5 animate-spin text-sky-400" aria-hidden="true" />
            )}
            <span className="text-sm font-semibold text-white">
              Stage: {job.current_stage.replace(/_/g, " ")}
            </span>
            <Badge tone={isFinished ? "emerald" : isFailed ? "rose" : "sky"}>{job.status}</Badge>
          </div>
          <span className="font-mono text-sm font-bold text-sky-300">{job.progress_percent}%</span>
        </div>

        <progress
          value={job.progress_percent}
          max={100}
          aria-label="Discovery job progress"
          className="h-2.5 w-full overflow-hidden rounded-full [&::-webkit-progress-bar]:bg-slate-800 [&::-webkit-progress-value]:bg-gradient-to-r [&::-webkit-progress-value]:from-indigo-500 [&::-webkit-progress-value]:to-sky-400"
        />

        {isFinished && (
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-slate-800 bg-navy-950 p-3">
              <div className="text-xs text-slate-400">Candidates Evaluated</div>
              <div className="mt-1 text-xl font-bold text-white">
                {job.total_candidates_evaluated}
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-navy-950 p-3">
              <div className="text-xs text-slate-400">Relevant Discovered</div>
              <div className="mt-1 text-xl font-bold text-emerald-400">
                {job.relevant_candidates_count}
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-navy-950 p-3">
              <div className="text-xs text-slate-400">Processing Time</div>
              <div className="mt-1 text-xl font-bold text-sky-300">
                {job.processing_time_ms ? `${job.processing_time_ms} ms` : "—"}
              </div>
            </div>
          </div>
        )}
      </Card>

      <Card className="p-6">
        <h2 className="mb-4 text-sm font-semibold text-white">Execution Stage Trace</h2>
        <ol className="space-y-3">
          {job.stage_logs.map((log, idx) => (
            <li
              key={`${log.stage}-${idx}`}
              className="flex items-start justify-between gap-4 rounded-lg border border-slate-800/80 bg-navy-950/60 p-3 text-xs"
            >
              <div className="flex items-start gap-2.5">
                <Clock className="mt-0.5 h-3.5 w-3.5 text-indigo-400" aria-hidden="true" />
                <div>
                  <div className="font-semibold text-slate-200">{log.stage}</div>
                  <div className="text-slate-400">{log.detail}</div>
                </div>
              </div>
              <div className="shrink-0 text-right font-mono text-[11px] text-slate-500">
                <div>{log.progress_percent}%</div>
                <div>{formatDateTime(log.timestamp)}</div>
              </div>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
