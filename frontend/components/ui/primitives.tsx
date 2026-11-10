import React from "react";
import { AlertCircle, CheckCircle2, Database, FileSpreadsheet, HelpCircle, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

export function Card({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "surface-card rounded-xl border border-slate-800/90 bg-navy-900/90 shadow-lg shadow-black/20 backdrop-blur-sm",
        className
      )}
    >
      {children}
    </div>
  );
}

export function buttonVariants({
  variant = "primary",
  size = "md",
  className,
}: {
  variant?: "primary" | "secondary" | "outline" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  className?: string;
} = {}) {
  const variants: Record<string, string> = {
    primary:
      "bg-indigo-600 text-white hover:bg-indigo-500 border border-indigo-500/60 shadow-sm shadow-indigo-950/50",
    secondary:
      "bg-slate-800 text-slate-100 hover:bg-slate-700 border border-slate-700",
    outline:
      "bg-transparent text-slate-200 hover:bg-slate-800/70 border border-slate-700",
    danger:
      "bg-rose-600/90 text-white hover:bg-rose-500 border border-rose-500/60",
    ghost: "bg-transparent text-slate-300 hover:bg-slate-800/60 border border-transparent",
  };
  const sizes: Record<string, string> = {
    sm: "px-3 py-1.5 text-xs min-h-[32px]",
    md: "px-4 py-2 text-sm min-h-[40px]",
    lg: "px-5 py-2.5 text-sm min-h-[44px]",
  };
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
    variants[variant],
    sizes[size],
    className
  );
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={buttonVariants({ variant, size, className })}
      {...props}
    />
  )
);
Button.displayName = "Button";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "w-full rounded-lg border border-slate-700 bg-navy-950/90 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-400 focus:outline-none min-h-[42px]",
      className
    )}
    {...props}
  />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full rounded-lg border border-slate-700 bg-navy-950/90 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-400 focus:outline-none",
      className
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      "w-full rounded-lg border border-slate-700 bg-navy-950/90 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none min-h-[42px]",
      className
    )}
    {...props}
  >
    {children}
  </select>
));
Select.displayName = "Select";

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "indigo" | "emerald" | "amber" | "rose" | "sky";
  className?: string;
}) {
  const tones: Record<string, string> = {
    neutral: "bg-slate-800/90 text-slate-300 border-slate-700",
    indigo: "bg-indigo-950/80 text-indigo-300 border-indigo-700/70",
    emerald: "bg-emerald-950/80 text-emerald-300 border-emerald-700/70",
    amber: "bg-amber-950/80 text-amber-300 border-amber-700/70",
    rose: "bg-rose-950/80 text-rose-300 border-rose-700/70",
    sky: "bg-sky-950/80 text-sky-300 border-sky-700/70",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium",
        tones[tone],
        className
      )}
    >
      {children}
    </span>
  );
}

export function VerificationBadge({ status }: { status: string }) {
  const norm = (status || "unverified").toLowerCase();
  if (norm === "verified") {
    return (
      <Badge tone="emerald">
        <ShieldCheck className="h-3 w-3" aria-hidden="true" />
        VERIFIED REAL
      </Badge>
    );
  }
  return (
    <Badge tone="amber">
      <HelpCircle className="h-3 w-3" aria-hidden="true" />
      UNVERIFIED REAL
    </Badge>
  );
}

export function DatasetEnvironmentBadge({ datasetType }: { datasetType?: string | null }) {
  const dt = (datasetType || "REAL_DATA").toUpperCase();
  if (dt === "USER_PROVIDED") {
    return (
      <Badge tone="sky">
        <FileSpreadsheet className="h-3 w-3" aria-hidden="true" />
        AUTHORIZED UPLOAD
      </Badge>
    );
  }
  if (dt === "ALL_AUTHORIZED") {
    return (
      <Badge tone="indigo">
        <Database className="h-3 w-3" aria-hidden="true" />
        ALL AUTHORIZED SOURCES
      </Badge>
    );
  }
  return (
    <Badge tone="emerald">
      <Database className="h-3 w-3" aria-hidden="true" />
      REAL EXTERNAL SOURCE
    </Badge>
  );
}

export function ClassificationBadge({ type }: { type: string }) {
  const up = (type || "").toUpperCase();
  if (up === "OBSERVED_FACT" || up === "DIRECTLY_OBSERVED") {
    return <Badge tone="emerald">OBSERVED FACT</Badge>;
  }
  if (up === "SOURCE_SUPPORTED" || up === "SOURCE_SUPPORTED_FACT") {
    return <Badge tone="sky">SOURCE-SUPPORTED FACT</Badge>;
  }
  if (up === "AI_DERIVED_CLASSIFICATION" || up === "AI_DERIVED") {
    return <Badge tone="indigo">AI-DERIVED CLASSIFICATION</Badge>;
  }
  if (up === "MISSING_INFORMATION") {
    return <Badge tone="rose">MISSING INFORMATION</Badge>;
  }
  return <Badge tone="amber">UNVERIFIED INFORMATION</Badge>;
}

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "success" | "warning" | "error";
  title?: string;
  children: React.ReactNode;
}) {
  const styles: Record<string, string> = {
    info: "border-sky-800/80 bg-sky-950/40 text-sky-200",
    success: "border-emerald-800/80 bg-emerald-950/40 text-emerald-200",
    warning: "border-amber-800/80 bg-amber-950/40 text-amber-200",
    error: "border-rose-800/80 bg-rose-950/40 text-rose-200",
  };
  const Icon = tone === "success" ? CheckCircle2 : AlertCircle;
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("flex items-start gap-3 rounded-lg border p-3.5 text-sm", styles[tone])}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="space-y-1">
        {title && <div className="font-semibold">{title}</div>}
        <div>{children}</div>
      </div>
    </div>
  );
}

export function ScoreBar({ label, value }: { label: string; value: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono font-medium text-slate-200">{clamped.toFixed(1)}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-sky-400 transition-all"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
