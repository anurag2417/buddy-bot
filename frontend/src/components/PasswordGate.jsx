import { useState } from "react";
import { useAuth } from "@/components/AuthContext";
import { Lock, Shield } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PasswordGate({ children }) {
  const { user } = useAuth();
  const [verified, setVerified] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Google auth users without password skip the gate
  const isGoogleOnly = user?.auth_provider === "google" && !user?.has_password;

  if (verified || isGoogleOnly) {
    return children;
  }

  const handleVerify = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const token = localStorage.getItem("buddybot_token");
      await axios.post(`${API}/auth/verify-password`, { password }, {
        headers: { Authorization: `Bearer ${token}` },
        withCredentials: true,
      });
      setVerified(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Incorrect password");
    }
    setLoading(false);
  };

  return (
    <div
      data-testid="password-gate"
      className="min-h-screen flex items-center justify-center bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-sky-100 via-white to-slate-50 px-4"
    >
      <div className="w-full max-w-sm text-center">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-emerald-100 mb-5">
          <Shield className="w-10 h-10 text-emerald-500" strokeWidth={2.5} />
        </div>
        <h2 className="font-['Nunito'] text-2xl font-extrabold text-slate-800 mb-2">
          Parent Verification
        </h2>
        <p className="text-base font-medium text-slate-500 mb-6">
          Enter your password to access the dashboard
        </p>

        <form onSubmit={handleVerify} className="space-y-4">
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" strokeWidth={2.5} />
            <input
              data-testid="password-gate-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              autoFocus
              className="w-full pl-12 pr-4 py-3.5 rounded-full border-2 border-slate-200 text-base font-medium focus:border-sky-400 focus:ring-4 focus:ring-sky-100 outline-none transition-all"
            />
          </div>

          {error && (
            <p data-testid="password-gate-error" className="text-rose-500 text-sm font-semibold bg-rose-50 rounded-xl p-3">
              {error}
            </p>
          )}

          <button
            data-testid="password-gate-submit"
            type="submit"
            disabled={loading}
            className="w-full bg-emerald-400 hover:bg-emerald-500 text-white rounded-full py-3.5 text-lg font-bold shadow-[0_4px_0_0_rgba(16,185,129,0.3)] hover:translate-y-[2px] hover:shadow-[0_2px_0_0_rgba(16,185,129,0.3)] active:translate-y-[4px] active:shadow-none disabled:opacity-50 transition-all duration-150"
          >
            {loading ? "Verifying..." : "Unlock Dashboard"}
          </button>
        </form>
      </div>
    </div>
  );
}
