"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { apiRequest, ApiError } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  buttonVariants,
  Card,
  DatasetEnvironmentBadge,
  Input,
  Select,
  VerificationBadge,
} from "@/components/ui/primitives";

interface CandidateRow {
  id: string;
  full_name: string;
  current_role: string | null;
  organization_name: string | null;
  location: string | null;
  experience_years: number | null;
  school_indicators: string[];
  primary_source: string;
  verification_status: string;
  dataset_type?: string;
}

export default function CandidatesDirectoryPage() {
  const [items, setItems] = useState<CandidateRow[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [verificationStatus, setVerificationStatus] = useState("");
  const [datasetType, setDatasetType] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCandidates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ page: String(page), page_size: "25" });
      if (q.trim()) qs.set("q", q.trim());
      if (verificationStatus) qs.set("verification_status", verificationStatus);
      if (datasetType) qs.set("dataset_type", datasetType);
      const res = await apiRequest<{ total: number; items: CandidateRow[] }>(
        `/api/candidates?${qs.toString()}`
      );
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to load candidates");
    } finally {
      setLoading(false);
    }
  }, [page, q, verificationStatus, datasetType]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Candidate Pool</h1>
          <p className="mt-1 text-sm text-slate-400">
            Showing {total} accessible real &amp; authorized profiles in{" "}
            <strong className="text-slate-200">
              {datasetType === "REAL_DATA"
                ? "Real External Sources"
                : datasetType === "USER_PROVIDED"
                ? "Authorized Uploads"
                : "All Authorized Real Sources"}
            </strong>
            .
          </p>
        </div>
        <Link href="/datasets/import" className={buttonVariants({ variant: "outline" })}>
          Import Real Profiles
        </Link>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <Card className="p-4">
        <search>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              loadCandidates();
            }}
            className="flex flex-wrap gap-3"
          >
            <div className="relative flex-1 min-w-[220px]">
              <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-500" />
              <Input
                aria-label="Search candidate pool"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPage(1);
                }}
                placeholder="Search name, role, organization, bio..."
                className="pl-9"
              />
            </div>
            <Select
              aria-label="Filter data environment"
              value={datasetType}
              onChange={(e) => {
                setDatasetType(e.target.value);
                setPage(1);
              }}
              className="w-56"
            >
              <option value="">All Authorized Real Sources</option>
              <option value="REAL_DATA">Real External Sources Only</option>
              <option value="USER_PROVIDED">Authorized Uploads Only</option>
            </Select>
            <Select
              aria-label="Filter verification status"
              value={verificationStatus}
              onChange={(e) => {
                setVerificationStatus(e.target.value);
                setPage(1);
              }}
              className="w-48"
            >
              <option value="">All Real Provenance</option>
              <option value="verified">Verified Real</option>
              <option value="unverified">Unverified Real</option>
            </Select>
          </form>
        </search>
      </Card>

      <Card className="p-5">
        {loading ? (
          <div className="h-48 animate-pulse rounded bg-slate-800/40" />
        ) : items.length === 0 ? (
          <div className="py-10 text-center space-y-3">
            <p className="text-sm text-slate-300">
              No verified or authorized real professional profiles have been indexed yet.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              <Link href="/datasets/import" className={buttonVariants({ size: "sm" })}>
                Import Authorized CSV or Permitted Web URLs
              </Link>
              <Link href="/datasets/sources" className={buttonVariants({ variant: "outline", size: "sm" })}>
                Inspect Data Sources
              </Link>
            </div>
          </div>
        ) : (
          <div tabIndex={0} role="region" aria-label="Candidate pool table" className="table-wrapper">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Indexed candidate profiles</caption>
              <thead className="border-b border-slate-800 text-xs uppercase text-slate-400">
                <tr>
                  <th scope="col" className="py-3 pr-4">Candidate</th>
                  <th scope="col" className="py-3 pr-4">Role & Organization</th>
                  <th scope="col" className="py-3 pr-4">Location</th>
                  <th scope="col" className="py-3 pr-4">School Indicators</th>
                  <th scope="col" className="py-3 pr-4">Provenance</th>
                  <th scope="col" className="py-3 text-right">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {items.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-800/30">
                    <th scope="row" className="py-3 pr-4 font-medium text-white">
                      {c.full_name}
                    </th>
                    <td className="py-3 pr-4 text-xs text-slate-300">
                      <div>{c.current_role || "—"}</div>
                      <div className="text-slate-400">{c.organization_name || "—"}</div>
                    </td>
                    <td className="py-3 pr-4 text-xs text-slate-400">{c.location || "—"}</td>
                    <td className="py-3 pr-4">
                      <div className="flex flex-wrap gap-1">
                        {c.school_indicators.slice(0, 3).map((ind) => (
                          <Badge key={ind} tone="indigo">
                            {ind}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 pr-4">
                      <div className="flex flex-wrap gap-1.5">
                        <VerificationBadge status={c.verification_status} />
                        <DatasetEnvironmentBadge datasetType={c.dataset_type} />
                      </div>
                    </td>
                    <td className="py-3 text-right">
                      <Link href={`/candidates/${c.id}`} className="text-xs text-sky-400 hover:underline">
                        View Profile →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
          <span>Total: {total} profiles · Page {page}</span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page * 25 >= total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
