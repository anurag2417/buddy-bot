import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

// This component is no longer needed with Firebase popup auth flow.
// It redirects to login for backward compatibility.
export default function AuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    // Firebase uses popup flow, not redirect-based callbacks.
    // If someone lands here, redirect them to login.
    navigate("/login", { replace: true });
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-sky-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-lg font-bold text-slate-400">Redirecting...</p>
      </div>
    </div>
  );
}
