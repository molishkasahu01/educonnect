function resolveApiBase(rawValue: string | undefined): string {
  const raw = rawValue?.trim();
  if (!raw) return "http://localhost:8000";
  if (raw === "same-origin" || raw === "/") return "";
  if (raw.startsWith("http://") || raw.startsWith("https://") || raw.startsWith("/")) {
    return raw.replace(/\/$/, "");
  }
  return `https://${raw.replace(/\/$/, "")}`;
}

const API_BASE = resolveApiBase(process.env.NEXT_PUBLIC_API_URL);

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    const s = window.localStorage;
    if (!s || typeof s.getItem !== "function") return null;
    return s;
  } catch {
    return null;
  }
}

export const tokenStore = {
  getAccess(): string | null {
    return getStorage()?.getItem("edxso_access_token") ?? null;
  },
  getRefresh(): string | null {
    return getStorage()?.getItem("edxso_refresh_token") ?? null;
  },
  setTokens(access: string, refresh: string) {
    const s = getStorage();
    if (!s) return;
    s.setItem("edxso_access_token", access);
    s.setItem("edxso_refresh_token", refresh);
  },
  clear() {
    const s = getStorage();
    if (!s) return;
    s.removeItem("edxso_access_token");
    s.removeItem("edxso_refresh_token");
  },
};

async function tryRefreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) return null;
  try {
    const resp = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!resp.ok) {
      tokenStore.clear();
      return null;
    }
    const data = await resp.json();
    tokenStore.setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  retryOnAuth = true
): Promise<T> {
  const token = tokenStore.getAccess();
  const headers = new Headers(options.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (resp.status === 401 && retryOnAuth && tokenStore.getRefresh()) {
    const newToken = await tryRefreshAccessToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      const retryResp = await fetch(`${API_BASE}${path}`, { ...options, headers });
      if (retryResp.ok) {
        return (await retryResp.json()) as T;
      }
    }
  }

  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const errJson = await resp.json();
      if (Array.isArray(errJson.detail)) {
        detail = errJson.detail
          .map((item: { msg?: string; loc?: unknown[] }) =>
            item?.msg ? String(item.msg) : JSON.stringify(item)
          )
          .join("; ");
      } else if (typeof errJson.detail === "string") {
        detail = errJson.detail;
      } else if (errJson.detail && typeof errJson.detail === "object") {
        detail = JSON.stringify(errJson.detail);
      } else if (typeof errJson.message === "string") {
        detail = errJson.message;
      }
    } catch {
      // ignore parse failure
    }
    throw new ApiError(resp.status, detail);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export async function downloadAuthorizedFile(path: string, filename: string): Promise<void> {
  const token = tokenStore.getAccess();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const resp = await fetch(`${API_BASE}${path}`, { headers });
  if (!resp.ok) {
    throw new ApiError(resp.status, "Export download failed");
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
