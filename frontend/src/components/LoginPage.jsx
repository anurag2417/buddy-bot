import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/components/AuthContext";
import { Shield, Mail, Lock, User, Phone, ArrowRight } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function formatError(detail) {
  if (!detail) return "Something went wrong.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(e => e?.msg || JSON.stringify(e)).join(" ");
  return String(detail);
}

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const url = isRegister ? `${API}/auth/register` : `${API}/auth/login`;
      const body = isRegister
        ? { name, email, phone, password }
        : { email, password };
      const res = await axios.post(url, body, { withCredentials: true });
      login(res.data);
      navigate("/parent");
    } catch (err) {
      setError(formatError(err.response?.data?.detail) || err.message);
    }
    setLoading(false);
  };

  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/auth/callback";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div
      data-testid="login-page"
      className="min-h-screen flex items-center justify-center bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-sky-100 via-white to-slate-50 px-4"
    >
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-emerald-100 mb-4">
            <Shield className="w-10 h-10 text-emerald-500" strokeWidth={2.5} />
          </div>
          <h1 className="font-['Nunito'] text-3xl font-extrabold text-sky-900">
            {isRegister ? "Create Parent Account" : "Parent Login"}
          </h1>
          <p className="text-base font-medium text-slate-500 mt-2">
            {isRegister ? "Set up your account to keep your child safe" : "Access your BuddyBot parent dashboard"}
          </p>
        </div>

        <div className="bg-white rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.06)] border-2 border-slate-100/50 p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <div className="relative">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" strokeWidth={2.5} />
                <input
                  data-testid="register-name-input"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  required
                  className="w-full pl-12 pr-4 py-3.5 rounded-full border-2 border-slate-200 text-base font-medium focus:border-sky-400 focus:ring-4 focus:ring-sky-100 outline-none transition-all"
                />
              </div>
            )}

            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" strokeWidth={2.5} />
              <input
                data-testid="login-email-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email address"
                required
                className="w-full pl-12 pr-4 py-3.5 rounded-full border-2 border-slate-200 text-base font-medium focus:border-sky-400 focus:ring-4 focus:ring-sky-100 outline-none transition-all"
              />
            </div>

            {isRegister && (
              <div className="relative">
                <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" strokeWidth={2.5} />
                <input
                  data-testid="register-phone-input"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="Phone number (optional)"
                  className="w-full pl-12 pr-4 py-3.5 rounded-full border-2 border-slate-200 text-base font-medium focus:border-sky-400 focus:ring-4 focus:ring-sky-100 outline-none transition-all"
                />
              </div>
            )}

            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" strokeWidth={2.5} />
              <input
                data-testid="login-password-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                required
                minLength={6}
                className="w-full pl-12 pr-4 py-3.5 rounded-full border-2 border-slate-200 text-base font-medium focus:border-sky-400 focus:ring-4 focus:ring-sky-100 outline-none transition-all"
              />
            </div>

            {error && (
              <p data-testid="auth-error" className="text-rose-500 text-sm font-semibold text-center bg-rose-50 rounded-xl p-3">
                {error}
              </p>
            )}

            <button
              data-testid="auth-submit-btn"
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-sky-400 hover:bg-sky-500 text-white rounded-full py-4 text-lg font-bold shadow-[0_4px_0_0_rgba(14,165,233,0.3)] hover:translate-y-[2px] hover:shadow-[0_2px_0_0_rgba(14,165,233,0.3)] active:translate-y-[4px] active:shadow-none disabled:opacity-50 transition-all duration-150"
            >
              {loading ? "Please wait..." : (isRegister ? "Create Account" : "Sign In")}
              <ArrowRight className="w-5 h-5" strokeWidth={3} />
            </button>
          </form>

          <div className="my-5 flex items-center gap-3">
            <div className="flex-1 h-px bg-slate-200" />
            <span className="text-sm font-semibold text-slate-400">OR</span>
            <div className="flex-1 h-px bg-slate-200" />
          </div>

          <button
            data-testid="google-login-btn"
            onClick={handleGoogleLogin}
            className="w-full flex items-center justify-center gap-3 bg-white hover:bg-slate-50 text-slate-700 rounded-full py-3.5 text-base font-bold border-2 border-slate-200 hover:border-slate-300 transition-all"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>

          <p className="text-center text-sm font-semibold text-slate-500 mt-5">
            {isRegister ? "Already have an account?" : "Don't have an account?"}{" "}
            <button
              data-testid="toggle-auth-mode"
              onClick={() => { setIsRegister(!isRegister); setError(""); }}
              className="text-sky-500 hover:text-sky-600 font-bold"
            >
              {isRegister ? "Sign In" : "Create Account"}
            </button>
          </p>
        </div>

        <div className="text-center mt-6">
          <Link to="/" data-testid="go-to-chat-link" className="text-sm font-semibold text-emerald-600 hover:text-emerald-700">
            Go to BuddyBot Chat (for kids)
          </Link>
        </div>
      </div>
    </div>
  );
}
