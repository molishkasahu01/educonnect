"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Play, Shield } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert, Badge, Button, buttonVariants, Card } from "@/components/ui/primitives";
import { formatDateTime } from "@/lib/utils";

interface EvalMetrics {
  precision_at_10: number;
  precision_at_20: number;
  recall_at_20: number;
  ndcg_at_10: number;
  mrr: number;
}

interface EvaluationRunItem {
  id: string;
  benchmark_name: string;
  total_candidates: number;
  relevance_treatment_note: string;
  dataset_disclaimer: string;
  created_at: string;
  model_comparison: {
    keyword_baseline: EvalMetrics;
    semantic_baseline: EvalMetrics;
    hybrid_ranking: EvalMetrics;
    embedding_model: string;
    ranking_model_version: string;
  };
}

interface AuditLogItem {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  created_at: string;
}

export default function AdminPanelPage() {
  const { user } = useAuth();
  const [runs, setRuns] = useState<EvaluationRunItem[]>([]);
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [runningEval, setRunningEval] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [ev, al] = await Promise.all([
        apiRequest<EvaluationRunItem[]>("/api/admin/evaluation"),
        apiRequest<AuditLogItem[]>("/api/admin/audit-logs"),
      ]);
      setRuns(ev);
      setLogs(al);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Admin data unavailable");
    }
  };

  useEffect(() => {
    if (user?.role === "ADMIN") {
      loadData();
    }
  }, [user]);

  const handleRunEvaluation = async () => {
    setRunningEval(true);
    setError(null);
    try {
      await apiRequest("/api/admin/evaluation/run", { method: "POST" });
      await loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Evaluation run failed");
    } finally {
      setRunningEval(false);
    }
  };

  if (user?.role !== "ADMIN") {
    return (
      <Alert tone="error" title="Access Denied">
        Administrator privileges are required to view benchmark evaluation runs and audit logs.
      </Alert>
    );
  }

  const latest = runs[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Admin &amp; Real-Data Evaluation</h1>
          <p className="mt-1 text-sm text-slate-400">
            Compare Keyword, Semantic, and Hybrid ranking on genuine human-labeled evaluation sets and inspect security audit logs.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/admin/models" className={buttonVariants({ variant: "outline" })}>
            AI Models
          </Link>
          <Link href="/admin/ranking" className={buttonVariants({ variant: "outline" })}>
            Ranking Weights
          </Link>
          <Button onClick={handleRunEvaluation} disabled={runningEval}>
            <Play className="h-4 w-4" aria-hidden="true" />
            {runningEval ? "Running Evaluation…" : "Run IR Evaluation"}
          </Button>
        </div>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">
            Model Comparison (Keyword vs. Semantic vs. Hybrid)
          </h2>
          {latest && (
            <Badge tone="indigo">
              {latest.model_comparison.embedding_model} · {latest.model_comparison.ranking_model_version}
            </Badge>
          )}
        </div>

        {!latest ? (
          <p className="text-sm text-slate-400">
            No evaluation runs recorded yet. Evaluation requires an actual genuine labeled evaluation dataset of verified/authorized candidates and reference profiles.
          </p>
        ) : (
          <>
            <Alert tone="warning" title="Benchmark Scope Disclaimer">
              {latest.dataset_disclaimer}
            </Alert>

            <div tabIndex={0} role="region" aria-label="Evaluation benchmark results" className="table-wrapper">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">IR evaluation comparison across models</caption>
                <thead className="border-b border-slate-800 text-xs uppercase text-slate-400">
                  <tr>
                    <th scope="col" className="py-2.5 pr-4">Model Strategy</th>
                    <th scope="col" className="py-2.5 pr-4">Precision@10</th>
                    <th scope="col" className="py-2.5 pr-4">Precision@20</th>
                    <th scope="col" className="py-2.5 pr-4">Recall@20</th>
                    <th scope="col" className="py-2.5 pr-4">NDCG@10</th>
                    <th scope="col" className="py-2.5">MRR</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {(
                    [
                      ["Keyword-Only Baseline", latest.model_comparison.keyword_baseline],
                      ["Semantic Similarity Baseline", latest.model_comparison.semantic_baseline],
                      ["Hybrid Ranking Model", latest.model_comparison.hybrid_ranking],
                    ] as [string, EvalMetrics][]
                  ).map(([label, m]) => (
                    <tr key={label}>
                      <th scope="row" className="py-3 pr-4 font-medium text-white">
                        {label}
                      </th>
                      <td className="py-3 pr-4 font-mono text-sky-300">{m.precision_at_10.toFixed(4)}</td>
                      <td className="py-3 pr-4 font-mono text-sky-300">{m.precision_at_20.toFixed(4)}</td>
                      <td className="py-3 pr-4 font-mono text-emerald-300">{m.recall_at_20.toFixed(4)}</td>
                      <td className="py-3 pr-4 font-mono text-indigo-300">{m.ndcg_at_10.toFixed(4)}</td>
                      <td className="py-3 font-mono text-slate-200">{m.mrr.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-xs text-slate-400">{latest.relevance_treatment_note}</p>
          </>
        )}
      </Card>

      <Card className="p-6">
        <div className="mb-3 flex items-center gap-2">
          <Shield className="h-4 w-4 text-sky-400" aria-hidden="true" />
          <h2 className="text-base font-semibold text-white">Security & Compliance Audit Logs</h2>
        </div>
        <div tabIndex={0} role="region" aria-label="Audit logs" className="table-wrapper max-h-80">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Audit logs</caption>
            <thead className="border-b border-slate-800 uppercase text-slate-400">
              <tr>
                <th scope="col" className="py-2 pr-4">Action</th>
                <th scope="col" className="py-2 pr-4">Resource</th>
                <th scope="col" className="py-2 pr-4">Resource ID</th>
                <th scope="col" className="py-2">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {logs.slice(0, 25).map((log) => (
                <tr key={log.id}>
                  <th scope="row" className="py-2 pr-4 font-mono text-slate-200">
                    {log.action}
                  </th>
                  <td className="py-2 pr-4 text-slate-400">{log.resource_type}</td>
                  <td className="py-2 pr-4 font-mono text-slate-500">{log.resource_id || "—"}</td>
                  <td className="py-2 text-slate-400">{formatDateTime(log.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
