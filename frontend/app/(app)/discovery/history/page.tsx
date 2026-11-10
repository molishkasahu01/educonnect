"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Compass, RotateCcw } from "lucide-react";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert, Badge, Button, buttonVariants, Card, DatasetEnvironmentBadge } from "@/components/ui/primitives";
import { formatDateTime } from "@/lib/utils";

interface Job {
  id: string;
  reference_profile_id: string;
  status: string;
  current_stage: string;
  progress_percent: number;
  total_candidates_evaluated: number;
  relevant_candidates_count: number;
  processing_time_ms: number | null;
  ranking_model_version: string;
  embedding_model_name: string;
  discovery_mode?: string;
  created_at: string;
}

export default function DiscoveryHistoryPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const data = await apiRequest<Job[]>("/api/discovery");
      setJobs(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load discovery history");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleRetry = async (jobId: string) => {
    try {
      await apiRequest(`/api/discovery/${jobId}/retry`, { method: "POST" });
      await fetchJobs();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to re-run job");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Discovery History</h1>
          <p className="mt-1 text-sm text-slate-400">
            All private discovery runs owned by your workspace account.
          </p>
        </div>
        <Link href="/discovery/new" className={buttonVariants()}>
          <Compass className="h-4 w-4" aria-hidden="true" /> New Discovery
        </Link>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <Card className="p-5">
        {loading ? (
          <div className="h-40 animate-pulse rounded bg-slate-800/40" />
        ) : jobs.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-400">
            No discovery runs recorded yet.
          </p>
        ) : (
          <div tabIndex={0} role="region" aria-label="Discovery job history" className="table-wrapper">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Discovery job history</caption>
              <thead className="border-b border-slate-800 text-xs uppercase text-slate-400">
                <tr>
                  <th scope="col" className="py-3 pr-4">Job ID</th>
                  <th scope="col" className="py-3 pr-4">Mode</th>
                  <th scope="col" className="py-3 pr-4">Status</th>
                  <th scope="col" className="py-3 pr-4">Model / Ranker</th>
                  <th scope="col" className="py-3 pr-4">Evaluated</th>
                  <th scope="col" className="py-3 pr-4">Relevant</th>
                  <th scope="col" className="py-3 pr-4">Duration</th>
                  <th scope="col" className="py-3 pr-4">Created</th>
                  <th scope="col" className="py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-800/30">
                    <th scope="row" className="py-3 pr-4 font-mono text-xs text-slate-200">
                      {job.id.slice(0, 8)}…
                    </th>
                    <td className="py-3 pr-4">
                      <DatasetEnvironmentBadge datasetType={job.discovery_mode} />
                    </td>
                    <td className="py-3 pr-4">
                      <Badge
                        tone={
                          job.status === "COMPLETED"
                            ? "emerald"
                            : job.status === "FAILED"
                            ? "rose"
                            : "sky"
                        }
                      >
                        {job.status} ({job.progress_percent}%)
                      </Badge>
                    </td>
                    <td className="py-3 pr-4 text-xs text-slate-300">
                      {job.embedding_model_name} · {job.ranking_model_version}
                    </td>
                    <td className="py-3 pr-4 text-slate-300">{job.total_candidates_evaluated}</td>
                    <td className="py-3 pr-4 font-semibold text-emerald-400">
                      {job.relevant_candidates_count}
                    </td>
                    <td className="py-3 pr-4 text-xs text-slate-400">
                      {job.processing_time_ms ? `${job.processing_time_ms}ms` : "—"}
                    </td>
                    <td className="py-3 pr-4 text-xs text-slate-400">
                      {formatDateTime(job.created_at)}
                    </td>
                    <td className="py-3 text-right">
                      <div className="inline-flex items-center gap-2">
                        {(job.status === "FAILED" || job.status === "COMPLETED") && (
                          <Button variant="ghost" size="sm" onClick={() => handleRetry(job.id)}>
                            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" /> Re-run
                          </Button>
                        )}
                        <Link
                          href={
                            job.status === "COMPLETED"
                              ? `/discovery/${job.id}/results`
                              : `/discovery/${job.id}`
                          }
                          className={buttonVariants({ variant: "outline", size: "sm" })}
                        >
                          {job.status === "COMPLETED" ? "Results" : "Track"}{" "}
                          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
