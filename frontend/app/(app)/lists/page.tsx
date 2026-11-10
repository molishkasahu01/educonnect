"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { BookmarkCheck, Plus, Trash2 } from "lucide-react";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert, Button, Card, Input, VerificationBadge } from "@/components/ui/primitives";
import { formatDateTime } from "@/lib/utils";

interface ListItem {
  id: string;
  candidate_id: string;
  added_at: string;
  candidate: {
    id: string;
    full_name: string;
    current_role: string | null;
    organization_name: string | null;
    verification_status: string;
  };
}

interface SavedList {
  id: string;
  name: string;
  description: string | null;
  candidate_count: number;
  updated_at: string;
  items: ListItem[];
}

export default function SavedListsPage() {
  const [lists, setLists] = useState<SavedList[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadLists = async () => {
    setLoading(true);
    try {
      const data = await apiRequest<SavedList[]>("/api/lists");
      setLists(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load saved lists");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLists();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError(null);
    try {
      await apiRequest("/api/lists", {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), description: description.trim() || null }),
      });
      setName("");
      setDescription("");
      await loadLists();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to create list");
    }
  };

  const handleRemoveCandidate = async (listId: string, candidateId: string) => {
    try {
      await apiRequest(`/api/lists/${listId}/candidates/${candidateId}`, { method: "DELETE" });
      await loadLists();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to remove candidate");
    }
  };

  const handleDeleteList = async (listId: string) => {
    try {
      await apiRequest(`/api/lists/${listId}`, { method: "DELETE" });
      await loadLists();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to delete list");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Saved Shortlists</h1>
        <p className="mt-1 text-sm text-slate-400">
          Curate private shortlists of K-12 education leaders discovered across runs.
        </p>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold text-white">Create New Shortlist</h2>
        <form onSubmit={handleCreate} className="grid gap-3 sm:grid-cols-3">
          <Input
            aria-label="List name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="List name (e.g. Q4 CBSE Advisors)"
            required
          />
          <Input
            aria-label="List description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
          />
          <Button type="submit">
            <Plus className="h-4 w-4" aria-hidden="true" /> Create List
          </Button>
        </form>
      </Card>

      {loading ? (
        <Card className="h-44 animate-pulse p-6" />
      ) : lists.length === 0 ? (
        <Card className="p-8 text-center text-sm text-slate-400">
          No saved lists yet. Create one above or shortlist candidates directly from Discovery Results.
        </Card>
      ) : (
        <div className="space-y-4">
          {lists.map((lst) => (
            <Card key={lst.id} className="p-5">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <BookmarkCheck className="h-5 w-5 text-indigo-400" aria-hidden="true" />
                  <h2 className="text-base font-semibold text-white">{lst.name}</h2>
                  <span className="text-xs text-slate-400">({lst.candidate_count} candidates)</span>
                </div>
                <Button variant="ghost" size="sm" onClick={() => handleDeleteList(lst.id)}>
                  <Trash2 className="h-4 w-4 text-rose-400" aria-hidden="true" /> Delete List
                </Button>
              </div>
              {lst.description && <p className="mb-3 text-xs text-slate-400">{lst.description}</p>}

              {lst.items.length === 0 ? (
                <p className="text-xs text-slate-500">No candidates shortlisted in this list yet.</p>
              ) : (
                <div className="divide-y divide-slate-800/80">
                  {lst.items.map((item) => (
                    <div
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/candidates/${item.candidate.id}`}
                            className="font-medium text-white hover:text-sky-300 hover:underline"
                          >
                            {item.candidate.full_name}
                          </Link>
                          <VerificationBadge status={item.candidate.verification_status} />
                        </div>
                        <div className="text-xs text-slate-400">
                          {item.candidate.current_role || "—"} ·{" "}
                          {item.candidate.organization_name || "—"} · Added{" "}
                          {formatDateTime(item.added_at)}
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRemoveCandidate(lst.id, item.candidate.id)}
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
