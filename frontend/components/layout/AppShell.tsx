"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  BookmarkCheck,
  Compass,
  Cpu,
  Database,
  FileSpreadsheet,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Scale,
  Settings,
  Shield,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";
import { Badge, Button } from "@/components/ui/primitives";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/discovery/new", label: "New Discovery", icon: Compass },
  { href: "/discovery/history", label: "Discovery History", icon: History },
  { href: "/candidates", label: "Candidate Pool", icon: Users },
  { href: "/lists", label: "Saved Lists", icon: BookmarkCheck },
  { href: "/datasets/import", label: "Dataset Import", icon: FileSpreadsheet },
  { href: "/datasets/sources", label: "Data Sources", icon: Database },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

const ADMIN_ITEMS = [
  { href: "/admin", label: "Admin & Evaluation", icon: Shield },
  { href: "/admin/models", label: "AI Models", icon: Cpu },
  { href: "/admin/ranking", label: "Ranking Weights", icon: Scale },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-navy-950 text-slate-300">
        <div className="flex items-center gap-3 text-sm">
          <Sparkles className="h-5 w-5 animate-pulse text-sky-400" />
          <span>Authenticating EduConnect Intelligence Workspace…</span>
        </div>
      </div>
    );
  }

  const NavLink = ({
    href,
    label,
    icon: Icon,
  }: {
    href: string;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
  }) => {
    const active = pathname === href || (href !== "/admin" && pathname.startsWith(href + "/"));
    return (
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        onClick={() => setMobileOpen(false)}
        className={cn(
          "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          active
            ? "bg-indigo-600/20 text-sky-300 border border-indigo-500/40"
            : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-100 border border-transparent"
        )}
      >
        <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{label}</span>
      </Link>
    );
  };

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100">
      <a
        href="#main-content"
        className="visually-hidden fixed left-4 top-4 z-50 rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white"
      >
        Skip to main content
      </a>

      {/* Mobile Header */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-800 bg-navy-900/95 px-4 py-3 backdrop-blur lg:hidden">
        <Link href="/dashboard" className="flex items-center gap-2 font-semibold text-slate-100">
          <Sparkles className="h-5 w-5 text-sky-400" aria-hidden="true" />
          <span>EduConnect Intelligence</span>
        </Link>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle navigation menu"
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </Button>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-800/90 bg-navy-900/95 transition-transform lg:static lg:translate-x-0",
            mobileOpen ? "translate-x-0" : "-translate-x-full"
          )}
        >
          <div className="flex items-center gap-2.5 border-b border-slate-800/80 px-5 py-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-sky-500 text-white shadow-md shadow-indigo-950/60">
              <Sparkles className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight text-white">EduConnect AI</div>
              <div className="text-[11px] text-slate-400">School Influencer Intel</div>
            </div>
          </div>

          <nav aria-label="Primary" className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.href} {...item} />
            ))}

            {user.role === "ADMIN" && (
              <div className="pt-4">
                <div className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Administration
                </div>
                <div className="space-y-1">
                  {ADMIN_ITEMS.map((item) => (
                    <NavLink key={item.href} {...item} />
                  ))}
                </div>
              </div>
            )}
          </nav>

          <div className="border-t border-slate-800/80 p-3">
            <div className="mb-2 rounded-lg bg-navy-950/80 p-2.5 border border-slate-800">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-xs font-medium text-slate-200">{user.full_name}</span>
                <Badge tone={user.role === "ADMIN" ? "indigo" : "sky"}>{user.role}</Badge>
              </div>
              <div className="mt-0.5 truncate text-[11px] text-slate-400">{user.email}</div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start text-slate-400 hover:text-rose-300"
              onClick={logout}
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span>Sign out</span>
            </Button>
          </div>
        </aside>

        <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
