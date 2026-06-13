import axios from "axios";

function resolveApiBaseUrl() {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL;
  const isLocalVite =
    typeof window !== "undefined" &&
    ["5173", "5174", "5175"].includes(window.location.port);

  if (isLocalVite) {
    return "/api";
  }

  return configuredUrl || "/api";
}

const API_BASE_URL = resolveApiBaseUrl();

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("accessToken");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const refresh = localStorage.getItem("refreshToken");
    if (error.response?.status === 401 && refresh && !original._retry) {
      original._retry = true;
      const { data } = await axios.post(`${API_BASE_URL}/auth/refresh/`, { refresh });
      localStorage.setItem("accessToken", data.access);
      if (data.refresh) {
        localStorage.setItem("refreshToken", data.refresh);
      }
      original.headers.Authorization = `Bearer ${data.access}`;
      return api(original);
    }
    return Promise.reject(error);
  }
);

export function listFrom(response) {
  const payload = response?.data ?? response;
  return Array.isArray(payload) ? payload : payload?.results ?? [];
}

export function countFrom(response) {
  const payload = response?.data ?? response;
  return Array.isArray(payload) ? payload.length : payload?.count ?? 0;
}

export function apiErrorMessage(error, fallback = "Live provider data could not be loaded.") {
  const payload = error?.response?.data;
  if (!error?.response && error?.message === "Network Error") {
    return "Cannot reach the backend API. Start Django on 127.0.0.1:8001, then refresh this page.";
  }
  const messageFromValue = (value) => {
    if (!value) return "";
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.map(messageFromValue).filter(Boolean).join(" ");
    if (typeof value === "object") {
      return value.detail || value.message || value.error || Object.values(value).map(messageFromValue).filter(Boolean).join(" ");
    }
    return String(value);
  };
  if (typeof payload === "string") {
    if (payload.trim().startsWith("<!DOCTYPE") || payload.trim().startsWith("<html")) {
      const title = payload.match(/<title>(.*?)<\/title>/i)?.[1];
      const exception = payload.match(/<pre class="exception_value">([\s\S]*?)<\/pre>/i)?.[1];
      return [title, exception].filter(Boolean).join(": ") || fallback;
    }
    return payload.length > 400 ? `${payload.slice(0, 400)}...` : payload;
  }
  return messageFromValue(payload) || error?.message || fallback;
}
