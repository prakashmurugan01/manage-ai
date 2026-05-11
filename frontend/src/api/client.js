import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

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
