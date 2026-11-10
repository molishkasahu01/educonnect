"use client";

import React, { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert, Card, Select } from "@/components/ui/primitives";

interface AnalyticsPayload {
  active_dataset_filter?: string;
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
    location_distribution: { location: string; count: number }[];
    discovery_history: { job_id: string; created_at: string; evaluated: number; relevant: number }[];
    source_distribution: { source: string; count: number }[];
    verification_distribution: { status: string; count: number }[];
  };
}

const COLORS = ["#10b981", "#64748b", "#f59e0b", "#38bdf8", "#6366f1"];
const TOOLTIP_STYLE = {
  backgroundColor: "#0b1222",
  border: "1px solid #334155",
  borderRadius: "8px",
  color: "#f1f5f9",
};

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsPayload | null>(null);
  const [datasetType, setDatasetType] = useState("ALL_AUTHORIZED");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    const qs = datasetType ? `?dataset_type=${encodeURIComponent(datasetType)}` : "";
    apiRequest<AnalyticsPayload>(`/api/analytics/dashboard${qs}`)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load analytics"));
  }, [datasetType]);

  if (error) return <Alert tone="error">{error}</Alert>;
  if (!data) return <Card className="h-72 animate-pulse p-6" />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Discovery &amp; Pool Analytics</h1>
          <p className="mt-1 text-sm text-slate-400">
            Real-time SQL aggregations computed strictly from genuine authorized candidate profiles and discovery runs.
          </p>
        </div>
        <Select
          aria-label="Filter analytics environment"
          value={datasetType}
          onChange={(e) => setDatasetType(e.target.value)}
          className="w-64"
        >
          <option value="ALL_AUTHORIZED">All Authorized Real Sources</option>
          <option value="REAL_DATA">Real External Sources Only</option>
          <option value="USER_PROVIDED">Authorized Uploads Only</option>
        </Select>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold text-white">Relevance Score Distribution</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.charts.relevance_distribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="range" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="count" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold text-white">Candidate Location Distribution</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.charts.location_distribution.slice(0, 8)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="location" stroke="#94a3b8" fontSize={10} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold text-white">Discovery History Trend</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.charts.discovery_history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="job_id" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Line type="monotone" dataKey="evaluated" stroke="#6366f1" strokeWidth={2} />
                <Line type="monotone" dataKey="relevant" stroke="#10b981" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold text-white">Data Source & Verification Breakdown</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.charts.source_distribution}
                  dataKey="count"
                  nameKey="source"
                  innerRadius={50}
                  outerRadius={85}
                >
                  {data.charts.source_distribution.map((s, idx) => (
                    <Cell key={s.source} fill={COLORS[idx % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}
