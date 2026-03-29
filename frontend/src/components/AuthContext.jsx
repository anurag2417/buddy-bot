import { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    // CRITICAL: If returning from OAuth callback, skip the /me check.
    // AuthCallback will exchange the session_id and establish the session first.
    if (window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    try {
      const token = localStorage.getItem("buddybot_token");
      if (!token) { setLoading(false); return; }
      const res = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
        withCredentials: true,
      });
      setUser(res.data);
    } catch {
      localStorage.removeItem("buddybot_token");
      setUser(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  const login = (userData) => {
    setUser(userData);
    if (userData.token) localStorage.setItem("buddybot_token", userData.token);
  };

  const logout = async () => {
    try {
      const token = localStorage.getItem("buddybot_token");
      await axios.post(`${API}/auth/logout`, {}, {
        headers: { Authorization: `Bearer ${token}` },
        withCredentials: true,
      });
    } catch { /* ignore */ }
    localStorage.removeItem("buddybot_token");
    localStorage.removeItem("buddybot_active_conv");
    setUser(null);
    window.location.href = "/login";
  };

  // Refresh user data (useful after extension confirmation)
  const refreshUser = async () => {
    try {
      const token = localStorage.getItem("buddybot_token");
      if (!token) return;
      const res = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
        withCredentials: true,
      });
      setUser(res.data);
    } catch {
      // Ignore errors
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, checkAuth, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
