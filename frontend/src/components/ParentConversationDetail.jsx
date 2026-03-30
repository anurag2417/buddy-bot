import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import {
  ArrowLeft, Brain, Shield, AlertTriangle, CheckCircle,
  MessageCircle, Clock
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BOT_AVATAR = "https://static.prod-images.emergentagent.com/jobs/c981f2d7-a198-4751-9292-bd3ea3733509/images/d376ea840d4cf39f522230889ca79fd1bbc7322d0f233bce72b70b50dca8ebdc.png";

function authHeaders() {
  const token = localStorage.getItem("buddybot_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function SafetyBadge({ level }) {
  const styles = {
    SAFE: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    CAUTION: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    ALERT: "bg-rose-500/15 text-rose-400 border-rose-500/30",
  };
  return (
    <span
      data-testid={`safety-badge-${level}`}
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${styles[level] || styles.SAFE}`}
    >
      <Shield className="w-3.5 h-3.5" strokeWidth={3} />
      {level}
    </span>
  );
}

export default function ParentConversationDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/parent/conversations/${id}`, { headers: authHeaders(), withCredentials: true });
      setData(res.data);
    } catch (e) { console.error(e); }
  }, [id]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (!data) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="pulse-soft text-xl font-bold text-slate-500">Loading...</div>
      </div>
    );
  }

  const { conversation, messages, alerts } = data;

  return (
    <div data-testid="parent-conversation-detail" className="min-h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950">
      {/* Header */}
      <header className="bg-slate-900/80 backdrop-blur-xl border-b border-slate-700/50 px-6 py-4 flex items-center gap-4 sticky top-0 z-10">
        <Link
          to="/parent"
          data-testid="back-to-dashboard-link"
          className="p-2 rounded-xl hover:bg-slate-800 transition-colors text-slate-400"
        >
          <ArrowLeft className="w-6 h-6" strokeWidth={2.5} />
        </Link>
        <div>
          <h1 className="font-['Nunito'] text-xl font-bold text-white">{conversation.title}</h1>
          <p className="text-sm text-slate-500 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            {new Date(conversation.created_at).toLocaleString()} &middot; {conversation.message_count || 0} messages
          </p>
        </div>
        {conversation.has_flags && (
          <span className="ml-auto bg-rose-500/15 text-rose-400 border border-rose-500/30 rounded-full px-4 py-1.5 text-sm font-bold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" strokeWidth={3} />
            {conversation.flag_count} flags
          </span>
        )}
      </header>

      <div className="max-w-4xl mx-auto px-4 md:px-8 py-8 space-y-8">
        {/* Alerts for this conversation */}
        {alerts.length > 0 && (
          <div data-testid="conversation-alerts" className="bg-slate-800/60 rounded-3xl border border-rose-500/30 p-6">
            <h3 className="font-['Nunito'] text-lg font-bold text-rose-400 flex items-center gap-2 mb-4">
              <AlertTriangle className="w-5 h-5" strokeWidth={2.5} />
              Alerts ({alerts.length})
            </h3>
            <div className="space-y-3">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  data-testid={`conv-alert-${alert.id}`}
                  className={`rounded-xl p-4 text-sm ${
                    alert.resolved
                      ? "bg-slate-800/40 border border-slate-700/50"
                      : "bg-rose-500/10 border border-rose-500/25"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                      alert.severity === "high"
                        ? "bg-rose-500/15 text-rose-400"
                        : "bg-amber-500/15 text-amber-400"
                    }`}>
                      {alert.severity?.toUpperCase()}
                    </span>
                    <span className="text-slate-500 capitalize">{alert.type?.replace("_", " ")}</span>
                    {alert.resolved && (
                      <CheckCircle className="w-4 h-4 text-emerald-400 ml-auto" />
                    )}
                  </div>
                  <p className="text-slate-300">{alert.details}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Message thread with thoughts */}
        <div data-testid="conversation-messages" className="space-y-6">
          <h3 className="font-['Nunito'] text-xl font-bold text-white flex items-center gap-2">
            <MessageCircle className="w-6 h-6 text-sky-400" strokeWidth={2.5} />
            Conversation Log
          </h3>
          {messages.map((msg, idx) => (
            <div key={msg.id || idx} data-testid={`parent-msg-${idx}`}>
              {msg.role === "user" ? (
                <div className="flex items-start gap-3 flex-row-reverse">
                  <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center flex-shrink-0 border border-amber-500/30 shadow-sm text-xl">
                    <span role="img" aria-label="child">&#x1F9D2;</span>
                  </div>
                  <div className="max-w-[70%]">
                    <div className={`bg-sky-500/20 text-sky-100 rounded-[2rem] rounded-br-lg p-4 text-base font-medium border border-sky-500/30 ${msg.blocked ? "opacity-60 line-through" : ""}`}>
                      {msg.text}
                      {msg.blocked && (
                        <span className="block text-sm text-rose-400 font-semibold mt-1" style={{textDecoration:'none'}}>
                          Blocked by profanity filter
                        </span>
                      )}
                    </div>
                    {msg.flagged_topics && (
                      <div className="mt-2 text-xs text-amber-400 font-semibold flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> Flagged topics: {Object.keys(msg.flagged_topics).join(", ")}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-3">
                  <img
                    src={BOT_AVATAR}
                    alt="BuddyBot"
                    className="w-10 h-10 rounded-full border-2 border-slate-700 shadow-sm flex-shrink-0"
                  />
                  <div className="max-w-[70%] space-y-2">
                    {/* AI Thought (visible to parent) */}
                    {msg.thought && (
                      <div
                        data-testid={`ai-thought-${idx}`}
                        className="bg-violet-500/10 border border-violet-500/25 rounded-xl p-3 text-sm"
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          <Brain className="w-4 h-4 text-violet-400" strokeWidth={2.5} />
                          <span className="font-bold text-violet-400 text-xs uppercase tracking-wider">AI Thought</span>
                          {msg.safety_level && <SafetyBadge level={msg.safety_level} />}
                        </div>
                        <p className="text-violet-300 leading-relaxed">{msg.thought}</p>
                      </div>
                    )}
                    {/* AI Response */}
                    <div className="bg-emerald-500/15 text-emerald-100 rounded-[2rem] rounded-bl-lg p-4 text-base font-medium border border-emerald-500/25">
                      {msg.text}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
