import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/components/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AuthCallback() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash;
    const sessionIdMatch = hash.match(/session_id=([^&]+)/);

    if (!sessionIdMatch) {
      navigate("/login");
      return;
    }

    const sessionId = sessionIdMatch[1];

    (async () => {
      try {
        const res = await axios.post(`${API}/auth/google`, { session_id: sessionId }, { withCredentials: true });
        login(res.data);
        navigate("/parent", { replace: true });
      } catch (err) {
        console.error("Google auth failed:", err);
        navigate("/login", { replace: true });
      }
    })();
  }, [navigate, login]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-sky-100 via-white to-slate-50">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-sky-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-lg font-bold text-slate-600">Signing you in...</p>
      </div>
    </div>
  );
}
