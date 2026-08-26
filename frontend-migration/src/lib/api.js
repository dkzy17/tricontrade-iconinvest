// Put this file in the existing Next.js frontend as src/lib/api.js.
// It centralizes API calls so the old Render URL is not hard-coded throughout the UI.

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch(path, options = {}) {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || data.msg || "Request failed");
  }

  return data;
}

export async function signIn(email, password) {
  const data = await apiFetch("/api/v1/users/signin", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  if (data.token) {
    localStorage.setItem("access_token", data.token);
  }

  if (data.user) {
    localStorage.setItem("user", JSON.stringify(data.user));
  }

  return data;
}

export function signOut() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
  }
}
