"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Sparkles } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Alert, Button, Card, Input } from "@/components/ui/primitives";
import { ApiError } from "@/lib/api";

const registerSchema = z.object({
  fullName: z.string().min(2, "Full name must be at least 2 characters"),
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type RegisterForm = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const { register: registerUser } = useAuth();
  const [showPw, setShowPw] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    mode: "onBlur",
  });

  const onSubmit = async (values: RegisterForm) => {
    setServerError(null);
    try {
      await registerUser(values.fullName, values.email, values.password);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.detail : "Registration failed");
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-navy-950 px-4 py-12">
      <Card className="w-full max-w-md p-7">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-sky-500">
            <Sparkles className="h-5 w-5 text-white" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-white">Create EduConnect Account</h1>
            <p className="text-xs text-slate-400">Private isolated workspace for discovery jobs & lists</p>
          </div>
        </div>

        {serverError && (
          <div className="mb-4">
            <Alert tone="error" title="Could not create account">
              {serverError}
            </Alert>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label htmlFor="fullName" className="mb-1.5 block text-xs font-medium text-slate-300">
              Full Name <span aria-hidden="true">*</span>
            </label>
            <Input
              id="fullName"
              type="text"
              autoComplete="name"
              aria-invalid={errors.fullName ? "true" : "false"}
              aria-describedby={errors.fullName ? "fullname-error" : undefined}
              placeholder="Priya Nair"
              {...register("fullName")}
            />
            {errors.fullName && (
              <p id="fullname-error" role="alert" className="mt-1 text-xs text-rose-400">
                {errors.fullName.message}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="reg-email" className="mb-1.5 block text-xs font-medium text-slate-300">
              Work Email <span aria-hidden="true">*</span>
            </label>
            <Input
              id="reg-email"
              type="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              aria-invalid={errors.email ? "true" : "false"}
              aria-describedby={errors.email ? "reg-email-error" : undefined}
              placeholder="priya@educationorg.org"
              {...register("email")}
            />
            {errors.email && (
              <p id="reg-email-error" role="alert" className="mt-1 text-xs text-rose-400">
                {errors.email.message}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="reg-password" className="mb-1.5 block text-xs font-medium text-slate-300">
              Password <span aria-hidden="true">*</span>
            </label>
            <span id="pw-hint" className="mb-1 block text-[11px] text-slate-400">
              Minimum 8 characters. Stored using bcrypt hashing.
            </span>
            <div className="relative">
              <Input
                id="reg-password"
                type={showPw ? "text" : "password"}
                autoComplete="new-password"
                aria-invalid={errors.password ? "true" : "false"}
                aria-describedby="pw-hint"
                className="pr-11"
                {...register("password")}
              />
              <button
                type="button"
                aria-pressed={showPw}
                aria-label={showPw ? "Hide password" : "Show password"}
                onClick={() => setShowPw(!showPw)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-slate-400 hover:text-slate-200"
              >
                {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.password && (
              <p role="alert" className="mt-1 text-xs text-rose-400">
                {errors.password.message}
              </p>
            )}
          </div>

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Creating account…" : "Create account"}
          </Button>
        </form>

        <p className="mt-5 text-center text-xs text-slate-400">
          Already registered?{" "}
          <Link href="/login" className="font-medium text-sky-400 hover:underline">
            Sign in
          </Link>
        </p>
      </Card>
    </main>
  );
}
