"use client";

import React, { useEffect, useState } from "react";
import { Database } from "lucide-react";
import { apiRequest, ApiError } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Alert, Badge, Button, Card } from "@/components/ui/primitives";
import { formatDateTime } from "@/lib/utils";

interface DataSourceItem {
  id: string;
  name: string;
  adapter_type: string;
  description: string | null;
  is_authorized: boolean;
  is_enabled: boolean;
  usage_restrictions: string;
  retention_policy_days: number;
  last_sync_at: string | null;
  record_count: number;
}

export default function DataSourcesPage() {
  const { user } = useAuth();
  const [sources, setSources] = useState<DataSourceItem[]>([]);
  const [providerStatus, setProviderStatus] = useState<{
    environment_counts: Record<string, number>;
    compliance_policy: { summary: string };
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSources = async () => {
    setLoading(true);
    try {
      const [data, prov] = await Promise.all([
        apiRequest<DataSourceItem[]>("/api/admin/data-sources"),
        apiRequest<{
          environment_counts: Record<string, number>;
          compliance_policy: { summary: string };
        }>("/api/discovery/providers").catch(() => null),
      ]);
      setSources(data);
      setProviderStatus(prov);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load data sources");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSources();
  }, []);

  const toggleSource = async (src: DataSourceItem) => {
    try {
      await apiRequest(`/api/admin/data-sources/${src.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_enabled: !src.is_enabled }),
      });
      await loadSources();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to update source");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Data Source Management</h1>
        <p className="mt-1 text-sm text-slate-400">
          Modular compliant adapters registered in EduConnect with authorization, retention, and usage policies.
        </p>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      {providerStatus && (
        <Alert tone="info" title="Compliant Real-Data Access Policy">
          <div className="space-y-1">
            <p>{providerStatus.compliance_policy.summary}</p>
            <p className="font-mono text-xs text-slate-300">
              Indexed counts — Real External Sources: {providerStatus.environment_counts.REAL_DATA ?? 0} · Authorized Uploads:{" "}
              {providerStatus.environment_counts.USER_PROVIDED ?? 0}
            </p>
          </div>
        </Alert>
      )}

      {loading ? (
        <Card className="h-48 animate-pulse p-6" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {sources.map((src) => (
            <Card key={src.id} className="p-5 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-sky-400" aria-hidden="true" />
                  <h2 className="text-sm font-semibold text-white">{src.name}</h2>
                </div>
                <div className="flex gap-1.5">
                  <Badge tone="indigo">{src.adapter_type}</Badge>
                  <Badge tone={src.is_enabled ? "emerald" : "neutral"}>
                    {src.is_enabled ? "ENABLED" : "DISABLED"}
                  </Badge>
                </div>
              </div>

              <p className="text-xs text-slate-400">{src.description || "Modular data adapter"}</p>

              <div className="rounded-lg border border-slate-800 bg-navy-950 p-2.5 text-xs space-y-1">
                <div className="text-slate-300">
                  Authorized: <strong>{src.is_authorized ? "Yes" : "No (Credentials Required)"}</strong> ·
                  Records Indexed: <strong>{src.record_count}</strong>
                </div>
                <div className="text-slate-400">Restrictions: {src.usage_restrictions}</div>
                <div className="text-slate-500">
                  Retention: {src.retention_policy_days} days · Last Sync:{" "}
                  {formatDateTime(src.last_sync_at)}
                </div>
              </div>

              {user?.role === "ADMIN" && (
                <Button variant="outline" size="sm" onClick={() => toggleSource(src)}>
                  {src.is_enabled ? "Disable Adapter" : "Enable Adapter"}
                </Button>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
