import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/components/AuthContext";
import axios from "axios";
import {
  MessageCircle, AlertTriangle, Shield, CheckCircle,
  ArrowLeft, Eye, Bell, ChevronRight, Clock,
  Globe, Search, Activity, Wifi, BarChart3, LogOut
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function authHeaders() {
  const token = localStorage.getItem("buddybot_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function StatCard({ icon: Icon, label, value, color, testId }) {
  const colorMap = {
    sky: "bg-sky-100 text-sky-600",
    emerald: "bg-emerald-100 text-emerald-600",
    amber: "bg-amber-100 text-amber-600",
    rose: "bg-rose-100 text-rose-600",
    violet: "bg-violet-100 text-violet-600",
    orange: "bg-orange-100 text-orange-600",
  };
  return (
    <div
      data-testid={testId}
      className="bg-white rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border-2 border-slate-100/50 p-6 hover:shadow-[0_8px_30px_rgb(0,0,0,0.08)] transition-all duration-300"
    >
      <div className="flex items-center gap-4">
        <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${colorMap[color]}`}>
          <Icon className="w-7 h-7" strokeWidth={2.5} />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-500 uppercase tracking-wider">{label}</p>
          <p className="font-['Nunito'] text-3xl font-extrabold text-slate-800">{value}</p>
        </div>
      </div>
    </div>
  );
}

function SeverityBadge({ severity }) {
  const styles = {
    high: "bg-rose-100 text-rose-800 border border-rose-300",
    medium: "bg-amber-100 text-amber-800 border border-amber-300",
    low: "bg-emerald-100 text-emerald-800 border border-emerald-300",
  };
  return (
    <span
      data-testid={`severity-badge-${severity}`}
      className={`inline-flex px-3 py-1 rounded-full text-sm font-bold ${styles[severity] || styles.medium}`}
    >
      {severity?.toUpperCase()}
    </span>
  );
}

export default function ParentDashboard() {
  const { user, logout } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [activeTab, setActiveTab] = useState("overview");
  const [browsingStats, setBrowsingStats] = useState(null);
  const [browsingSearches, setBrowsingSearches] = useState([]);
  const [browsingVisits, setBrowsingVisits] = useState([]);
  const [browsingAnalysis, setBrowsingAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const h = { headers: authHeaders(), withCredentials: true };
      const [dashRes, convRes, alertRes] = await Promise.all([
        axios.get(`${API}/parent/dashboard`, h),
        axios.get(`${API}/parent/conversations`, h),
        axios.get(`${API}/parent/alerts`, h),
      ]);
      setDashboard(dashRes.data);
      setConversations(convRes.data);
      setAlerts(alertRes.data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchBrowsingData = useCallback(async () => {
    try {
      const h = { headers: authHeaders(), withCredentials: true };
      const [statsRes, searchRes, visitRes] = await Promise.all([
        axios.get(`${API}/parent/browsing/stats`, h),
        axios.get(`${API}/parent/browsing/searches?limit=30`, h),
        axios.get(`${API}/parent/browsing/visits?limit=30`, h),
      ]);
      setBrowsingStats(statsRes.data);
      setBrowsingSearches(searchRes.data);
      setBrowsingVisits(visitRes.data);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    fetchData();
    fetchBrowsingData();
  }, [fetchData, fetchBrowsingData]);

  const resolveAlert = async (alertId) => {
    try {
      await axios.put(`${API}/parent/alerts/${alertId}/resolve`, {}, { headers: authHeaders(), withCredentials: true });
      fetchData();
    } catch (e) { console.error(e); }
  };

  const runAnalysis = async () => {
    setAnalysisLoading(true);
    try {
      const res = await axios.get(`${API}/parent/browsing/analysis`, { headers: authHeaders(), withCredentials: true });
      setBrowsingAnalysis(res.data);
    } catch (e) { console.error(e); }
    setAnalysisLoading(false);
  };

  const stats = dashboard?.stats || {};

  const tabs = [
    { key: "overview", label: "Overview", icon: Eye },
    { key: "alerts", label: "Alerts", icon: Bell },
    { key: "conversations", label: "Conversations", icon: MessageCircle },
    { key: "browsing", label: "Browsing Activity", icon: Globe },
  ];

  return (
    <div data-testid="parent-dashboard" className="min-h-screen bg-slate-50">
      {/* Top Bar */}
      <header
        data-testid="parent-header"
        className="bg-white/80 backdrop-blur-xl border-b border-slate-100 px-6 py-4 flex items-center gap-4 sticky top-0 z-10"
      >
        <Link to="/" data-testid="back-to-chat-link" className="p-2 rounded-xl hover:bg-slate-100 transition-colors text-slate-500">
          <ArrowLeft className="w-6 h-6" strokeWidth={2.5} />
        </Link>
        <Shield className="w-8 h-8 text-emerald-500" strokeWidth={2.5} />
        <h1 className="font-['Nunito'] text-2xl font-extrabold text-slate-800">Parent Dashboard</h1>
        {stats.unresolved_alerts > 0 && (
          <span data-testid="unresolved-alert-badge" className="ml-auto bg-rose-100 text-rose-700 border border-rose-300 rounded-full px-4 py-1.5 text-sm font-bold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" strokeWidth={3} />
            {stats.unresolved_alerts} Unresolved
          </span>
        )}
        {!stats.unresolved_alerts && <div className="ml-auto" />}
        {user && (
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-slate-500">{user.name}</span>
            <button
              data-testid="logout-btn"
              onClick={logout}
              className="p-2 rounded-xl hover:bg-slate-100 transition-colors text-slate-400 hover:text-rose-500"
              title="Logout"
            >
              <LogOut className="w-5 h-5" strokeWidth={2.5} />
            </button>
          </div>
        )}
      </header>

      <div className="max-w-6xl mx-auto px-4 md:px-8 py-8">
        {/* Tabs */}
        <div data-testid="dashboard-tabs" className="flex gap-2 mb-8 flex-wrap">
          {tabs.map(({ key, label, icon: TabIcon }) => (
            <button
              key={key}
              data-testid={`tab-${key}`}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-2 px-6 py-3 rounded-full text-base font-bold transition-all duration-200 ${
                activeTab === key
                  ? "bg-sky-400 text-white shadow-[0_4px_0_0_rgba(14,165,233,0.3)]"
                  : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
              }`}
            >
              <TabIcon className="w-5 h-5" strokeWidth={2.5} />
              {label}
            </button>
          ))}
        </div>

        {/* Overview tab */}
        {activeTab === "overview" && (
          <div data-testid="overview-content">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-6">
              <StatCard icon={MessageCircle} label="Conversations" value={stats.total_conversations || 0} color="sky" testId="stat-conversations" />
              <StatCard icon={MessageCircle} label="Messages" value={stats.total_messages || 0} color="emerald" testId="stat-messages" />
              <StatCard icon={AlertTriangle} label="Total Alerts" value={stats.total_alerts || 0} color="amber" testId="stat-alerts" />
              <StatCard icon={Shield} label="Flagged Chats" value={stats.flagged_conversations || 0} color="rose" testId="stat-flagged" />
            </div>

            {/* Browsing stats row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-8">
              <StatCard icon={Globe} label="Browsing Packets" value={stats.total_packets || 0} color="violet" testId="stat-packets" />
              <StatCard icon={Wifi} label="Browsing Alerts" value={stats.browsing_alerts || 0} color="orange" testId="stat-browsing-alerts" />
              <StatCard icon={Activity} label="Incognito Activity" value={stats.incognito_searches || 0} color="rose" testId="stat-incognito" />
            </div>

            {/* Recent Alerts */}
            <div className="bg-white rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border-2 border-slate-100/50 p-6">
              <h3 className="font-['Nunito'] text-xl font-bold text-slate-800 mb-4 flex items-center gap-2">
                <Bell className="w-6 h-6 text-amber-500" strokeWidth={2.5} />
                Recent Alerts
              </h3>
              {(dashboard?.recent_alerts || []).length === 0 ? (
                <p data-testid="no-alerts-message" className="text-slate-400 text-lg font-medium py-8 text-center">
                  No alerts yet. Everything looks safe!
                </p>
              ) : (
                <div className="space-y-3">
                  {(dashboard?.recent_alerts || []).slice(0, 5).map((alert) => (
                    <AlertRow key={alert.id} alert={alert} onResolve={resolveAlert} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Alerts tab */}
        {activeTab === "alerts" && (
          <div data-testid="alerts-content" className="space-y-4">
            <h3 className="font-['Nunito'] text-2xl font-bold text-slate-800 mb-2">All Alerts</h3>
            {alerts.length === 0 ? (
              <div className="bg-white rounded-3xl p-12 text-center border-2 border-slate-100/50">
                <CheckCircle className="w-16 h-16 text-emerald-400 mx-auto mb-4" strokeWidth={2} />
                <p data-testid="no-alerts-all-message" className="text-lg font-medium text-slate-500">All clear! No alerts to show.</p>
              </div>
            ) : (
              alerts.map((alert) => (
                <AlertRow key={alert.id} alert={alert} onResolve={resolveAlert} />
              ))
            )}
          </div>
        )}

        {/* Conversations tab */}
        {activeTab === "conversations" && (
          <div data-testid="conversations-content" className="space-y-3">
            <h3 className="font-['Nunito'] text-2xl font-bold text-slate-800 mb-2">Conversation Logs</h3>
            {conversations.length === 0 ? (
              <div className="bg-white rounded-3xl p-12 text-center border-2 border-slate-100/50">
                <MessageCircle className="w-16 h-16 text-sky-300 mx-auto mb-4" strokeWidth={2} />
                <p className="text-lg font-medium text-slate-500">No conversations yet.</p>
              </div>
            ) : (
              conversations.map((conv) => (
                <Link
                  key={conv.id}
                  to={`/parent/conversation/${conv.id}`}
                  data-testid={`parent-conv-${conv.id}`}
                  className="block bg-white rounded-2xl p-5 border-2 border-slate-100/50 hover:shadow-[0_8px_30px_rgb(0,0,0,0.06)] transition-all duration-200 group"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <MessageCircle className="w-6 h-6 text-sky-400" strokeWidth={2.5} />
                      <div>
                        <p className="font-bold text-slate-800 text-lg">{conv.title}</p>
                        <p className="text-sm text-slate-400 flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5" />
                          {new Date(conv.created_at).toLocaleDateString()} &middot; {conv.message_count || 0} messages
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {conv.has_flags && (
                        <span className="bg-rose-100 text-rose-700 border border-rose-300 rounded-full px-3 py-1 text-sm font-bold">
                          {conv.flag_count} flags
                        </span>
                      )}
                      <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-sky-400 transition-colors" />
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        )}

        {/* Browsing Activity tab */}
        {activeTab === "browsing" && (
          <div data-testid="browsing-content" className="space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="font-['Nunito'] text-2xl font-bold text-slate-800">Browsing Activity</h3>
              <button
                data-testid="run-analysis-btn"
                onClick={runAnalysis}
                disabled={analysisLoading}
                className="flex items-center gap-2 bg-violet-500 hover:bg-violet-600 text-white rounded-full px-5 py-2.5 text-sm font-bold shadow-[0_3px_0_0_rgba(139,92,246,0.3)] hover:translate-y-[1px] hover:shadow-[0_1px_0_0_rgba(139,92,246,0.3)] transition-all duration-150 disabled:opacity-50"
              >
                <BarChart3 className="w-4 h-4" strokeWidth={3} />
                {analysisLoading ? "Analyzing..." : "Run AI Analysis"}
              </button>
            </div>

            {/* Browsing Stats */}
            {browsingStats && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-white rounded-2xl p-4 border-2 border-slate-100/50 text-center">
                  <Search className="w-6 h-6 text-sky-400 mx-auto mb-2" strokeWidth={2.5} />
                  <p className="font-['Nunito'] text-2xl font-extrabold text-slate-800">{browsingStats.search_count}</p>
                  <p className="text-xs font-bold text-slate-400 uppercase">Searches</p>
                </div>
                <div className="bg-white rounded-2xl p-4 border-2 border-slate-100/50 text-center">
                  <Globe className="w-6 h-6 text-emerald-400 mx-auto mb-2" strokeWidth={2.5} />
                  <p className="font-['Nunito'] text-2xl font-extrabold text-slate-800">{browsingStats.visit_count}</p>
                  <p className="text-xs font-bold text-slate-400 uppercase">Visits</p>
                </div>
                <div className="bg-white rounded-2xl p-4 border-2 border-slate-100/50 text-center">
                  <Activity className="w-6 h-6 text-violet-400 mx-auto mb-2" strokeWidth={2.5} />
                  <p className="font-['Nunito'] text-2xl font-extrabold text-slate-800">{browsingStats.incognito_count}</p>
                  <p className="text-xs font-bold text-slate-400 uppercase">Incognito</p>
                </div>
                <div className="bg-white rounded-2xl p-4 border-2 border-slate-100/50 text-center">
                  <AlertTriangle className="w-6 h-6 text-rose-400 mx-auto mb-2" strokeWidth={2.5} />
                  <p className="font-['Nunito'] text-2xl font-extrabold text-slate-800">{browsingStats.flagged_searches}</p>
                  <p className="text-xs font-bold text-slate-400 uppercase">Flagged</p>
                </div>
              </div>
            )}

            {/* AI Analysis Result */}
            {browsingAnalysis && (
              <div data-testid="browsing-analysis" className={`rounded-3xl p-6 border-2 ${
                browsingAnalysis.safety_level === "ALERT" ? "bg-rose-50 border-rose-200" :
                browsingAnalysis.safety_level === "CAUTION" ? "bg-amber-50 border-amber-200" :
                "bg-emerald-50 border-emerald-200"
              }`}>
                <div className="flex items-center gap-3 mb-3">
                  <BarChart3 className="w-6 h-6" strokeWidth={2.5} />
                  <h4 className="font-['Nunito'] text-lg font-bold">AI Browsing Analysis</h4>
                  <span className={`px-3 py-1 rounded-full text-xs font-bold border ${
                    browsingAnalysis.safety_level === "ALERT" ? "bg-rose-100 text-rose-800 border-rose-300" :
                    browsingAnalysis.safety_level === "CAUTION" ? "bg-amber-100 text-amber-800 border-amber-300" :
                    "bg-emerald-100 text-emerald-800 border-emerald-300"
                  }`}>
                    {browsingAnalysis.safety_level}
                  </span>
                </div>
                <p className="text-base font-medium text-slate-700 mb-2">{browsingAnalysis.analysis}</p>
                {browsingAnalysis.positive && (
                  <p className="text-sm font-medium text-emerald-700 bg-emerald-100 rounded-xl p-3 mt-2">
                    {browsingAnalysis.positive}
                  </p>
                )}
                <div className="flex gap-4 mt-3 text-sm font-semibold text-slate-500">
                  <span>{browsingAnalysis.total_searches || 0} searches analyzed</span>
                  <span>{browsingAnalysis.total_visits || 0} visits analyzed</span>
                  <span>{browsingAnalysis.incognito_count || 0} incognito</span>
                </div>
                {browsingAnalysis.flagged_searches?.length > 0 && (
                  <div className="mt-4">
                    <h5 className="font-bold text-sm text-slate-600 mb-2">Flagged Searches:</h5>
                    <div className="space-y-2">
                      {browsingAnalysis.flagged_searches.map((s, i) => (
                        <div key={i} className="bg-white/80 rounded-xl p-3 border border-slate-200 text-sm">
                          <span className="font-bold text-slate-700">"{s.query}"</span>
                          {s.tab_type === "incognito" && (
                            <span className="ml-2 text-xs font-bold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700">Incognito</span>
                          )}
                          {Object.keys(s.topics || {}).length > 0 && (
                            <span className="ml-2 text-xs text-amber-600 font-semibold">
                              Topics: {Object.keys(s.topics).join(", ")}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Recent Searches */}
            <div className="bg-white rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border-2 border-slate-100/50 p-6">
              <h4 className="font-['Nunito'] text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                <Search className="w-5 h-5 text-sky-400" strokeWidth={2.5} />
                Recent Searches
              </h4>
              {browsingSearches.length === 0 ? (
                <div className="text-center py-8">
                  <Globe className="w-12 h-12 text-slate-200 mx-auto mb-3" strokeWidth={2} />
                  <p className="text-slate-400 text-base font-medium">No search data yet.</p>
                  <p className="text-slate-300 text-sm font-medium mt-1">Install the BuddyBot Chrome extension to start tracking.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {browsingSearches.map((s, i) => (
                    <div
                      key={s.id || i}
                      data-testid={`search-packet-${i}`}
                      className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
                        s.profanity_flagged
                          ? "bg-rose-50 border-rose-200"
                          : s.restricted_topics
                          ? "bg-amber-50 border-amber-200"
                          : "bg-slate-50 border-slate-100"
                      }`}
                    >
                      <Search className="w-4 h-4 text-slate-400 flex-shrink-0" strokeWidth={2.5} />
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-sm text-slate-700 truncate">{s.search_query}</p>
                        <p className="text-xs text-slate-400">{s.search_engine} &middot; {new Date(s.timestamp).toLocaleString()}</p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {s.tab_type === "incognito" && (
                          <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700">Incognito</span>
                        )}
                        {s.profanity_flagged && (
                          <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-700">Blocked</span>
                        )}
                        {s.restricted_topics && !s.profanity_flagged && (
                          <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">Flagged</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Recent Visits */}
            <div className="bg-white rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border-2 border-slate-100/50 p-6">
              <h4 className="font-['Nunito'] text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                <Globe className="w-5 h-5 text-emerald-400" strokeWidth={2.5} />
                Recent Visits
              </h4>
              {browsingVisits.length === 0 ? (
                <p className="text-slate-400 text-base font-medium py-6 text-center">No visit data yet.</p>
              ) : (
                <div className="space-y-2">
                  {browsingVisits.slice(0, 15).map((v, i) => (
                    <div key={v.id || i} data-testid={`visit-packet-${i}`} className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 border border-slate-100">
                      <Globe className="w-4 h-4 text-emerald-400 flex-shrink-0" strokeWidth={2.5} />
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-sm text-slate-700 truncate">{v.title || v.domain}</p>
                        <p className="text-xs text-slate-400 truncate">{v.domain} &middot; {new Date(v.timestamp).toLocaleString()}</p>
                      </div>
                      {v.tab_type === "incognito" && (
                        <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 flex-shrink-0">Incognito</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function AlertRow({ alert, onResolve }) {
  const isExtension = alert.source === "extension";
  return (
    <div
      data-testid={`alert-row-${alert.id}`}
      className={`rounded-2xl p-5 border-2 flex flex-col md:flex-row md:items-center gap-4 ${
        alert.resolved ? "bg-slate-50 border-slate-200" : "bg-rose-50 border-rose-200"
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 mb-2 flex-wrap">
          <SeverityBadge severity={alert.severity} />
          <span className="text-sm font-semibold text-slate-500 capitalize">{alert.type?.replace("_", " ")}</span>
          {isExtension && (
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700">Browser</span>
          )}
          {alert.tab_type === "incognito" && (
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700">Incognito</span>
          )}
          {alert.resolved && (
            <span className="text-emerald-600 text-sm font-bold flex items-center gap-1">
              <CheckCircle className="w-4 h-4" /> Resolved
            </span>
          )}
        </div>
        <p className="text-base font-medium text-slate-700 truncate">{alert.details}</p>
        <p className="text-sm text-slate-400 mt-1">
          Child {isExtension ? "searched" : "said"}: "<span className="italic text-slate-500">{alert.child_message}</span>"
        </p>
      </div>
      {!alert.resolved && (
        <button
          data-testid={`resolve-alert-${alert.id}`}
          onClick={() => onResolve(alert.id)}
          className="bg-emerald-400 hover:bg-emerald-500 text-white rounded-full px-5 py-2.5 text-sm font-bold shadow-[0_3px_0_0_rgba(16,185,129,0.3)] hover:translate-y-[1px] hover:shadow-[0_1px_0_0_rgba(16,185,129,0.3)] active:translate-y-[3px] active:shadow-none transition-all duration-150 whitespace-nowrap"
        >
          Mark Resolved
        </button>
      )}
    </div>
  );
}
