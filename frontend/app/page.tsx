"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Button, buttonVariants, Card } from "@/components/ui/primitives";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/dashboard");
    }
  }, [loading, user, router]);

  return (
    <main className="min-h-screen bg-navy-950 px-6 py-16 text-slate-100">
      <div className="mx-auto max-w-4xl space-y-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-sky-500">
              <Sparkles className="h-5 w-5 text-white" aria-hidden="true" />
            </div>
            <span className="text-lg font-semibold tracking-tight">EduConnect Intelligence</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login" className={buttonVariants({ variant: "outline" })}>
              Sign in
            </Link>
            <Link href="/register" className={buttonVariants()}>
              Get started
            </Link>
          </div>
        </div>

        <div className="space-y-4">
          <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
            School Influencer Intelligence for K-12 Ecosystems
          </h1>
          <p className="max-w-2xl text-lg text-slate-300">
            Discover former principals, school founders, managing trustees, multi-campus directors,
            and K-12 education consultants using Sentence Transformer semantics and explainable
            hybrid ranking.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link href="/login" className={buttonVariants({ size: "lg" })}>
              Launch Platform <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Link href="/register" className={buttonVariants({ variant: "secondary", size: "lg" })}>
              Create Analyst Account
            </Link>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Card className="p-5">
            <CheckCircle2 className="mb-3 h-5 w-5 text-sky-400" aria-hidden="true" />
            <h2 className="font-semibold text-white">Semantic Discovery</h2>
            <p className="mt-1 text-sm text-slate-400">
              BGE dense embeddings + pgvector cosine retrieval across 19 K-12 ecosystem indicators.
            </p>
          </Card>
          <Card className="p-5">
            <Sparkles className="mb-3 h-5 w-5 text-indigo-400" aria-hidden="true" />
            <h2 className="font-semibold text-white">Evidence-Linked Ranking</h2>
            <p className="mt-1 text-sm text-slate-400">
              Separate Relevance Score and Evidence Confidence with missing-data-aware normalization.
            </p>
          </Card>
          <Card className="p-5">
            <ShieldCheck className="mb-3 h-5 w-5 text-emerald-400" aria-hidden="true" />
            <h2 className="font-semibold text-white">Ethical Provenance</h2>
            <p className="mt-1 text-sm text-slate-400">
              Zero unauthorized scraping. Strict source attribution distinguishing verified and unverified real records.
            </p>
          </Card>
        </div>
      </div>
    </main>
  );
}
