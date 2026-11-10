"use client";

import React, { useEffect, useState } from "react";
import { RotateCcw, Save, Scale } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert, Badge, Button, Card, Input } from "@/components/ui/primitives";

type Weights = {
  semantic_similarity: number;
  school_ecosystem_relevance: number;
  professional_role_similarity: number;
  experience_similarity: number;
  organization_network_overlap: number;
  influence_indicators_score: number;
};

const DEFAULT_WEIGHTS: Weights = {
  semantic_similarity: 0.3,
  school_ecosystem_relevance: 0.25,
  professional_role_similarity: 0.15,
  experience_similarity: 0.1,
  organization_network_overlap: 0.1,
  influence_indicators_score: 0.1,
};

export default function AdminRankingWeightsPage() {
  const { user } = useAuth();
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [version, setVersion] = useState("hybrid-v1.0");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<{ version: string; weights: Weights }>("/api/admin/ranking-weights")
      .then((res) => {
        setVersion(res.version);
        setWeights(res.weights);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load weights"));
  }, []);

  const total =
    weights.semantic_similarity +
    weights.school_ecosystem_relevance +
    weights.professional_role_similarity +
    weights.experience_similarity +
    weights.organization_network_overlap +
    weights.influence_indicators_score;

  const isSumValid = Math.abs(total - 1.0) <= 0.001;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    setError(null);
    if (!isSumValid) {
      setError(`Weights must total 1.00 (currently ${total.toFixed(3)}).`);
      return;
    }
    try {
      const res = await apiRequest<{ version: string; weights: Weights }>(
        "/api/admin/ranking-weights",
        {
          method: "PUT",
          body: JSON.stringify(weights),
        }
      );
      setVersion(res.version);
      setWeights(res.weights);
      setMessage(`Updated active ranking model to ${res.version}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to update weights");
    }
  };

  if (user?.role !== "ADMIN") {
    return <Alert tone="error">Administrator privileges required to modify ranking weights.</Alert>;
  }

  const fields: [keyof Weights, string][] = [
    ["semantic_similarity", "Semantic Similarity"],
    ["school_ecosystem_relevance", "School Ecosystem Relevance"],
    ["professional_role_similarity", "Professional Role Similarity"],
    ["experience_similarity", "Experience Similarity"],
    ["organization_network_overlap", "Organization & Network Overlap"],
    ["influence_indicators_score", "Influence Indicators"],
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Hybrid Ranking Configuration</h1>
          <p className="mt-1 text-sm text-slate-400">
            Configure the 6-factor explainable hybrid formula. Weights must sum exactly to 1.00.
          </p>
        </div>
        <Badge tone="indigo">Active Version: {version}</Badge>
      </div>

      {message && <Alert tone="success">{message}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      <Card className="max-w-2xl p-6">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Scale className="h-5 w-5 text-sky-400" aria-hidden="true" />
            <h2 className="text-base font-semibold text-white">Component Weights</h2>
          </div>
          <Badge tone={isSumValid ? "emerald" : "rose"}>Total: {total.toFixed(2)}</Badge>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          {fields.map(([key, label]) => (
            <div key={key} className="grid items-center gap-3 sm:grid-cols-3">
              <label htmlFor={`w-${key}`} className="text-xs font-medium text-slate-300 sm:col-span-2">
                {label}
              </label>
              <Input
                id={`w-${key}`}
                type="number"
                step="0.05"
                min={0}
                max={1}
                value={weights[key]}
                onChange={(e) =>
                  setWeights({ ...weights, [key]: Number(e.target.value) || 0 })
                }
              />
            </div>
          ))}

          <div className="flex flex-wrap gap-3 pt-2">
            <Button type="submit" disabled={!isSumValid}>
              <Save className="h-4 w-4" aria-hidden="true" /> Save Ranking Weights
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setWeights(DEFAULT_WEIGHTS)}
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" /> Reset Defaults (0.30/0.25/0.15/0.10/0.10/0.10)
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
