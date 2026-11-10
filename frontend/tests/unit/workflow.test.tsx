import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock next/navigation for page components
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/login",
}));

import { AuthProvider } from "@/hooks/useAuth";
import LoginPage from "@/app/(auth)/login/page";

describe("Authentication Form Validation", () => {
  it("shows validation feedback when submitting empty login form", async () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    );

    const submitBtn = screen.getByRole("button", { name: /^Sign in$/i });
    fireEvent.click(submitBtn);

    expect(await screen.findByText(/Enter a valid email address/i)).toBeInTheDocument();
    expect(await screen.findByText(/Password is required/i)).toBeInTheDocument();
  });

  it("provides link to create a workspace account without seeded demo shortcuts", () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    );

    expect(screen.queryByText(/Demo Seed Accounts/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Create an account/i })).toHaveAttribute("href", "/register");
  });
});
