"use client";

import React, { useEffect, useState } from "react";
import { Cpu, Save } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert, Badge, Button, Card, Input, Select } from "@/components/ui/primitives";

interface ModelsPayload {
  active_config: {
    embedding_model_name: string;
    embedding_dimension: number;
    cross_encoder_enabled: boolean;
    cross_encoder_model_name: string;
    llm_provider: string;
  };
  registered_versions: {
    id: string;
    name: string;
    model_type: string;
    version: string;
    dimension: number | null;
    is_active: boolean;
  }[];
}

export default function AdminModelsPage() {
  const { user } = useAuth();
  const [data, setData] = useState<ModelsPayload | null>(null);
  const [embeddingModel, setEmbeddingModel] = useState("BAAI/bge-small-en-v1.5");
  const [crossEnabled, setCrossEnabled] = useState(false);
  const [crossModel, setCrossModel] = useState("cross-encoder/ms-marco-MiniLM-L-6-v2");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadModels = async () => {
    try {
      const res = await apiRequest<ModelsPayload>("/api/admin/models");
      setData(res);
      setEmbeddingModel(res.active_config.embedding_model_name);
      setCrossEnabled(res.active_config.cross_encoder_enabled);
      setCrossModel(res.active_config.cross_encoder_model_name);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load model config");
    }
  };

  useEffect(() => {
    if (user?.role === "ADMIN") loadModels();
  }, [user]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    setError(null);
    try {
      await apiRequest("/api/admin/models", {
        method: "PUT",
        body: JSON.stringify({
          embedding_model_name: embeddingModel,
          cross_encoder_enabled: crossEnabled,
          cross_encoder_model_name: crossModel,
        }),
      });
      setMessage("AI model runtime configuration updated.");
      await loadModels();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Update failed");
    }
  };

  if (user?.role !== "ADMIN") {
    return <Alert tone="error">Administrator access required.</Alert>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">AI Model Configuration</h1>
        <p className="mt-1 text-sm text-slate-400">
          Configure Sentence Transformers embedding backend, optional Cross-Encoder reranking, and inspect registered model versions.
        </p>
      </div>

      {message && <Alert tone="success">{message}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <div className="mb-4 flex items-center gap-2">
            <Cpu className="h-5 w-5 text-sky-400" aria-hidden="true" />
            <h2 className="text-base font-semibold text-white">Runtime Model Settings</h2>
          </div>
          <form onSubmit={handleSave} className="space-y-4">
            <div>
              <label htmlFor="emb-model" className="mb-1 block text-xs font-medium text-slate-300">
                Sentence Transformer Model
              </label>
              <Select
                id="emb-model"
                value={embeddingModel}
                onChange={(e) => setEmbeddingModel(e.target.value)}
              >
                <option value="BAAI/bge-small-en-v1.5">BAAI/bge-small-en-v1.5 (384-dim, low RAM CPU)</option>
                <option value="BAAI/bge-m3">BAAI/bge-m3 (1024-dim, high-capacity production)</option>
                <option value="sentence-transformers/all-MiniLM-L6-v2">all-MiniLM-L6-v2 (384-dim)</option>
              </Select>
            </div>

            <div className="flex items-center gap-2.5 rounded-lg border border-slate-800 bg-navy-950 p-3">
              <input
                id="ce-toggle"
                type="checkbox"
                checked={crossEnabled}
                onChange={(e) => setCrossEnabled(e.target.checked)}
                className="h-4 w-4"
              />
              <label htmlFor="ce-toggle" className="text-xs text-slate-300">
                Enable Cross-Encoder reranking on top 40 retrieved candidates
              </label>
            </div>

            <div>
              <label htmlFor="ce-model" className="mb-1 block text-xs font-medium text-slate-300">
                Cross-Encoder Model ID
              </label>
              <Input
                id="ce-model"
                value={crossModel}
                onChange={(e) => setCrossModel(e.target.value)}
              />
            </div>

            <Button type="submit">
              <Save className="h-4 w-4" aria-hidden="true" /> Save Model Configuration
            </Button>
          </form>
        </Card>

        <Card className="p-6">
          <h2 className="mb-4 text-base font-semibold text-white">Registered Model Versions</h2>
          <div className="space-y-2.5">
            {(data?.registered_versions || []).map((mv) => (
              <div
                key={mv.id}
                className="flex items-center justify-between rounded-lg border border-slate-800 bg-navy-950 p-3 text-xs"
              >
                <div>
                  <div className="font-semibold text-slate-200">{mv.name}</div>
                  <div className="font-mono text-slate-400">
                    {mv.model_type} · {mv.version}
                    {mv.dimension ? ` · ${mv.dimension}-dim` : ""}
                  </div>
                </div>
                <Badge tone={mv.is_active ? "emerald" : "neutral"}>
                  {mv.is_active ? "ACTIVE" : "ARCHIVED"}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
