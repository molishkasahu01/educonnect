"use client";

import React, { useState } from "react";
import { Download, Save, Trash2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiRequest, ApiError } from "@/lib/api";
import { Alert, Button, Card, Input } from "@/components/ui/primitives";

export default function SettingsPage() {
  const { user, refreshUser, logout } = useAuth();
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [retentionDays, setRetentionDays] = useState(String(user?.retention_days || 365));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      await apiRequest("/api/auth/me", {
        method: "PATCH",
        body: JSON.stringify({
          full_name: fullName,
          retention_days: Number(retentionDays),
        }),
      });
      await refreshUser();
      setMessage("Workspace & retention settings saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleExportMyData = async () => {
    try {
      const data = await apiRequest<object>("/api/auth/me/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "educonnect_user_data_export.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Export failed");
    }
  };

  const handleDeleteAccount = async () => {
    if (!window.confirm("Soft-delete your account and remove private discovery/uploaded data?")) {
      return;
    }
    try {
      await apiRequest("/api/auth/me", { method: "DELETE" });
      await logout();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Deletion failed");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Account & Privacy Settings</h1>
        <p className="mt-1 text-sm text-slate-400">
          Manage your profile, private data retention policy, personal data export, and account deletion.
        </p>
      </div>

      {message && <Alert tone="success">{message}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="mb-4 text-base font-semibold text-white">Profile & Retention</h2>
          <form onSubmit={handleSave} className="space-y-4">
            <div>
              <label htmlFor="settings-name" className="mb-1 block text-xs font-medium text-slate-300">
                Full Name
              </label>
              <Input
                id="settings-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="settings-retention" className="mb-1 block text-xs font-medium text-slate-300">
                Private Data Retention Window (days)
              </label>
              <Input
                id="settings-retention"
                type="number"
                min={30}
                max={3650}
                value={retentionDays}
                onChange={(e) => setRetentionDays(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={saving}>
              <Save className="h-4 w-4" aria-hidden="true" />
              {saving ? "Saving…" : "Save Changes"}
            </Button>
          </form>
        </Card>

        <Card className="space-y-4 p-6">
          <h2 className="text-base font-semibold text-white">Privacy & Data Governance</h2>
          <p className="text-xs text-slate-400">
            Export all reference profiles, discovery jobs, saved lists, and private upload counts owned by {user?.email}.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={handleExportMyData}>
              <Download className="h-4 w-4" aria-hidden="true" /> Export My Data (JSON)
            </Button>
            <Button variant="danger" onClick={handleDeleteAccount}>
              <Trash2 className="h-4 w-4" aria-hidden="true" /> Delete Account & Private Data
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
