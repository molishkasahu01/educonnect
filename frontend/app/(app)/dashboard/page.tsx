"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Compass,
  Database,
  FileSpreadsheet,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiRequest } from "@/lib/api";
import { Alert, Badge, buttonVariants, Card } from "@/components/ui/primitives";
import { formatDateTime } from "@/lib/utils";

interface DashboardData {
  metrics: {
    total_discovery_jobs: number;
    total_candidate_profiles: number;
    real_data_profiles?: number;
    user_provided_profiles?: number;
    relevant_professionals_discovered: number;
    verified_profiles: number;
    unverified_profiles: number;
    average_relevance_score: number;
    average_evidence_confidence: number;
  };
  charts: {
    segment_distribution: { name: string; count: number }[];
    relevance_distribution: { range: string; count: number }[];
    verification_distribution: { status: string; count: number }[];
  };
}

interface DiscoveryJobRow {
  id: string;
  status: string;
  current_stage: string;
  progress_percent: number;
  total_candidates_evaluated: number;
  relevant_candidates_count: number;
  processing_time_ms: number | null;
  created_at: string;
}

const PIE_COLORS = ["#10b981", "#f59e0b"];

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [jobs, setJobs] = useState<DiscoveryJobRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      apiRequest<DashboardData>("/api/analytics/dashboard"),
      apiRequest<DiscoveryJobRow[]>("/api/discovery"),
    ])
      .then(([dash, jobList]) => {
        if (!active) return;
        setData(dash);
        setJobs(jobList.slice(0, 6));
      })
      .catch((err) => {
        if (active) setError(err?.message || "Failed to load dashboard metrics");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Intelligence Dashboard</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} className="h-28 animate-pulse p-5" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-white">Intelligence Dashboard</h1>
        <Alert tone="error" title="Unable to load backend metrics">
          {error || "No dashboard data returned"}
        </Alert>
      </div>
    );
  }

  const m = data.metrics;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            School Influencer Intelligence
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Live database metrics across semantic candidate pools, provenance status, and discovery runs.
          </p>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <Link href="/datasets/import" className={buttonVariants({ variant: "outline" })}>
            <FileSpreadsheet className="h-4 w-4" aria-hidden="true" />
            Import CSV Dataset
          </Link>
          <Link href="/discovery/new" className={buttonVariants()}>
            <Compass className="h-4 w-4" aria-hidden="true" />
            New Discovery Run
          </Link>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Indexed Real Profiles</span>
            <Users className="h-4 w-4 text-sky-400" aria-hidden="true" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {m.total_candidate_profiles}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            {m.real_data_profiles ?? 0} external · {m.user_provided_profiles ?? 0} uploaded
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Discovery Jobs Executed</span>
            <Activity className="h-4 w-4 text-indigo-400" aria-hidden="true" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{m.total_discovery_jobs}</div>
          <div className="mt-1 text-xs text-slate-400">
            {m.relevant_professionals_discovered} highly relevant matches surfaced
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Avg. Hybrid Relevance</span>
            <Sparkles className="h-4 w-4 text-emerald-400" aria-hidden="true" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{m.average_relevance_score.toFixed(1)}</div>
          <div className="mt-1 text-xs text-slate-400">Weighted 0–100 hybrid score</div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Avg. Evidence Confidence</span>
            <ShieldCheck className="h-4 w-4 text-amber-400" aria-hidden="true" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{m.average_evidence_confidence.toFixed(1)}%</div>
          <div className="mt-1 text-xs text-slate-400">Tracked separately from relevance</div>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <h2 className="mb-1 text-sm font-semibold text-white">Candidate Segment Distribution</h2>
          <p className="mb-4 text-xs text-slate-400">
            Primary education & domain segments across indexed records
          </p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.charts.segment_distribution.slice(0, 7)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0b1222",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                    color: "#f1f5f9",
                  }}
                />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="mb-1 text-sm font-semibold text-white">Verification Breakdown</h2>
          <p className="mb-4 text-xs text-slate-400">
            Verified vs. unverified real profiles in database
          </p>
          <div className="h-52 w-full">
            {m.total_candidate_profiles === 0 ? (
              <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-slate-800 text-xs text-slate-500">
                0 real profiles indexed yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.charts.verification_distribution}
                    dataKey="count"
                    nameKey="status"
                    innerRadius={45}
                    outerRadius={75}
                    paddingAngle={3}
                  >
                    {data.charts.verification_distribution.map((entry, idx) => (
                      <Cell key={entry.status} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0b1222",
                      border: "1px solid #334155",
                      borderRadius: "8px",
                      color: "#f1f5f9",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="mt-2 flex flex-wrap justify-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-emerald-300">
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Verified Real: {m.verified_profiles}
            </span>
            <span className="flex items-center gap-1.5 text-amber-300">
              <Database className="h-3.5 w-3.5" aria-hidden="true" /> Unverified Real: {m.unverified_profiles}
            </span>
          </div>
        </Card>
      </div>

      {/* Recent Discovery Runs */}
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Recent Discovery Jobs</h2>
            <p className="text-xs text-slate-400">Asynchronous semantic & hybrid ranking runs</p>
          </div>
          <Link href="/discovery/history" className="text-xs font-medium text-sky-400 hover:underline">
            View all history →
          </Link>
        </div>

        {jobs.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-700 p-8 text-center">
            <p className="text-sm text-slate-300">No discovery runs yet.</p>
            <p className="mt-1 text-xs text-slate-400">
              Analyze a reference K-12 education consultant profile to discover ranked candidates.
            </p>
            <Link href="/discovery/new" className={buttonVariants({ size: "sm", className: "mt-4" })}>
              Start First Discovery
            </Link>
          </div>
        ) : (
          <div tabIndex={0} role="region" aria-label="Recent discovery jobs" className="table-wrapper">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Recent discovery jobs</caption>
              <thead className="border-b border-slate-800 text-xs uppercase text-slate-400">
                <tr>
                  <th scope="col" className="py-2.5 pr-4">Job ID</th>
                  <th scope="col" className="py-2.5 pr-4">Status</th>
                  <th scope="col" className="py-2.5 pr-4">Evaluated</th>
                  <th scope="col" className="py-2.5 pr-4">Relevant</th>
                  <th scope="col" className="py-2.5 pr-4">Created</th>
                  <th scope="col" className="py-2.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-800/30">
                    <th scope="row" className="py-3 pr-4 font-mono text-xs text-slate-300">
                      {job.id.slice(0, 8)}…
                    </th>
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
                        {job.status}
                      </Badge>
                    </td>
                    <td className="py-3 pr-4 text-slate-300">{job.total_candidates_evaluated}</td>
                    <td className="py-3 pr-4 font-medium text-sky-300">{job.relevant_candidates_count}</td>
                    <td className="py-3 pr-4 text-xs text-slate-400">{formatDateTime(job.created_at)}</td>
                    <td className="py-3 text-right">
                      <Link
                        href={
                          job.status === "COMPLETED"
                            ? `/discovery/${job.id}/results`
                            : `/discovery/${job.id}`
                        }
                        className="inline-flex items-center gap-1 text-xs font-medium text-sky-400 hover:underline"
                      >
                        {job.status === "COMPLETED" ? "Results" : "Track"}{" "}
                        <ArrowRight className="h-3 w-3" aria-hidden="true" />
                      </Link>
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
