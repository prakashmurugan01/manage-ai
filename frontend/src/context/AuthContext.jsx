import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { authApi } from "../api/services.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("user");
    try {
      return raw ? JSON.parse(raw) : null;
    } catch {
      localStorage.removeItem("user");
      return null;
    }
  });
  const [loading, setLoading] = useState(Boolean(localStorage.getItem("accessToken")));

  useEffect(() => {
    let mounted = true;
    if (!localStorage.getItem("accessToken")) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then(({ data }) => {
        if (mounted) {
          setUser(data);
          localStorage.setItem("user", JSON.stringify(data));
        }
      })
      .catch(() => logout())
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, []);

  async function login(email, password) {
    const { data } = await authApi.login({ email, password });
    persistSession(data);
    return data.user;
  }

  async function faceLogin(formData) {
    const { data } = await authApi.faceLogin(formData);
    persistSession(data);
    return data.user;
  }

  function persistSession(data) {
    localStorage.setItem("accessToken", data.access);
    localStorage.setItem("refreshToken", data.refresh);
    localStorage.setItem("user", JSON.stringify(data.user));
    setUser(data.user);
  }

  async function register(payload) {
    const { data } = await authApi.register(payload);
    return data;
  }

  function logout() {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("user");
    setUser(null);
  }

  const value = useMemo(() => ({ user, loading, login, faceLogin, register, logout, isAuthenticated: Boolean(user) }), [user, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
