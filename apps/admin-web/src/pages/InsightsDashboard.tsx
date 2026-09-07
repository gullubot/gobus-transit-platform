import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { TrendingUp, Bus, AlertCircle, RefreshCw, Filter, CalendarClock } from "lucide-react";
import { getInsights } from "../api/api";

type Evidence = {
  statement: string;
  total_observations: number;
  matched_observations: number;
  ratio: number;
  window_start?: string;
  window_end?: string;
};

type Suggestion = {
  action: string;
  related_entity_type: string;
  related_entity_id?: string | null;
};

type Insight = {
  insight_type: "CROWDING" | "PERFORMANCE" | "FLEET";
  title: string;
  service_id: string;
  service_name: string;
  route_id: string;
  route_name: string;
  time_window: string;
  day_pattern: string;
  lookback_days: number;
  severity: "INFO" | "WARNING" | "CRITICAL";
  evidence: Evidence;
  suggestion: Suggestion;
  generated_at: string;
};

export default function InsightsDashboard() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterType, setFilterType] = useState<string>("ALL");

  const fetchInsights = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await getInsights("summary");
      setInsights(res.insights || []);
    } catch (err: any) {
      setError(err.message || "Unable to load operational insights.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
  }, []);

  const filteredInsights = insights.filter(
    (insight) => filterType === "ALL" || insight.insight_type === filterType
  );

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return "var(--danger)";
      case "WARNING":
        return "var(--warning)";
      case "INFO":
      default:
        return "var(--primary)";
    }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case "CROWDING":
        return <TrendingUp size={20} />;
      case "PERFORMANCE":
        return <CalendarClock size={20} />;
      case "FLEET":
        return <Bus size={20} />;
      default:
        return <AlertCircle size={20} />;
    }
  };

  const renderActionLinks = (insight: Insight) => {
    return (
      <div className="flex gap-4 mt-6 pt-4 border-t border-gray-800">
        <Link
          to={`/services`}
          className="px-4 py-2 text-sm font-medium rounded-lg text-white bg-[var(--surface-light)] hover:bg-[var(--surface-lighter)] transition-colors"
        >
          View Service
        </Link>
        {insight.suggestion.related_entity_type === "SERVICE_SCHEDULE" && (
          <Link
            to={`/services/${insight.service_id}/schedules`}
            className="px-4 py-2 text-sm font-medium rounded-lg text-white bg-[var(--primary)] hover:bg-[var(--primary-hover)] transition-colors"
          >
            Manage Schedule
          </Link>
        )}
      </div>
    );
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Operational Insights</h1>
          <p className="text-[var(--text-muted)] mt-2 text-lg">
            Deterministic, evidence-based recommendations derived from historical telemetry and capacity data.
          </p>
        </div>
        <button
          onClick={fetchInsights}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--surface-light)] hover:bg-[var(--surface-lighter)] text-white rounded-lg transition-colors"
          disabled={loading}
        >
          <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      <div className="flex items-center gap-4 bg-[var(--surface)] p-4 rounded-xl border border-gray-800 shadow-sm">
        <Filter size={18} className="text-gray-400" />
        <span className="text-sm font-medium text-gray-300">Filter by Type:</span>
        {["ALL", "CROWDING", "PERFORMANCE", "FLEET"].map((type) => (
          <button
            key={type}
            onClick={() => setFilterType(type)}
            className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${
              filterType === type
                ? "bg-[var(--primary)] text-white"
                : "bg-[var(--surface-light)] text-gray-400 hover:text-white"
            }`}
          >
            {type === "ALL" ? "All Insights" : type}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="animate-pulse bg-[var(--surface)] h-64 rounded-xl border border-gray-800"></div>
          ))}
        </div>
      ) : error ? (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-6 rounded-xl flex items-center gap-3">
          <AlertCircle size={24} />
          <p className="font-medium text-lg">{error}</p>
        </div>
      ) : filteredInsights.length === 0 ? (
        <div className="bg-[var(--surface)] border border-gray-800 text-center p-16 rounded-xl text-gray-400">
          <div className="flex justify-center mb-4">
            <TrendingUp size={48} className="opacity-20" />
          </div>
          <p className="text-xl font-medium">No operational insights available right now.</p>
          <p className="mt-2 text-sm">The system will generate insights when recurring patterns are detected.</p>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
          {filteredInsights.map((insight, index) => (
            <div
              key={`${insight.service_id}-${index}`}
              className="bg-[var(--surface)] border border-gray-800 rounded-xl overflow-hidden hover:border-gray-600 transition-colors flex flex-col group"
            >
              {/* Card Header */}
              <div className="p-6 pb-4 border-b border-gray-800 flex items-start justify-between bg-gradient-to-br from-[var(--surface)] to-[var(--surface-light)]">
                <div className="flex items-center gap-3">
                  <div
                    className="p-2.5 rounded-xl shadow-sm"
                    style={{ backgroundColor: `${getSeverityColor(insight.severity)}20`, color: getSeverityColor(insight.severity) }}
                  >
                    {getIcon(insight.insight_type)}
                  </div>
                  <div>
                    <h3 className="font-semibold text-lg text-white uppercase tracking-wider text-sm">{insight.title}</h3>
                    <p className="text-[var(--text-muted)] text-sm flex items-center gap-2 mt-1">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: getSeverityColor(insight.severity) }}></span>
                      {insight.severity} PRIORITY
                    </p>
                  </div>
                </div>
              </div>

              {/* Card Body */}
              <div className="p-6 flex-1 flex flex-col space-y-5">
                
                {/* Where / When */}
                <div className="bg-[#0f1115] rounded-lg p-4 grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-xs font-semibold text-gray-500 uppercase">Service</span>
                    <p className="text-white font-medium mt-1">{insight.service_name}</p>
                    <p className="text-gray-400 text-xs mt-0.5 truncate">{insight.route_name}</p>
                  </div>
                  <div>
                    <span className="text-xs font-semibold text-gray-500 uppercase">When</span>
                    <p className="text-white font-medium mt-1">{insight.time_window}</p>
                    <p className="text-gray-400 text-xs mt-0.5">{insight.day_pattern}</p>
                  </div>
                </div>

                {/* Evidence */}
                <div>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">The Evidence</h4>
                  <p className="text-gray-300 text-sm leading-relaxed">{insight.evidence.statement}</p>
                  
                  {/* Visual Evidence Bar */}
                  {insight.evidence.total_observations > 0 && (
                    <div className="mt-3 relative w-full h-2.5 bg-gray-800 rounded-full overflow-hidden">
                      <div 
                        className="absolute left-0 top-0 h-full rounded-full transition-all duration-1000 ease-out"
                        style={{ 
                          width: `${(insight.evidence.matched_observations / insight.evidence.total_observations) * 100}%`,
                          backgroundColor: getSeverityColor(insight.severity)
                        }}
                      />
                    </div>
                  )}
                </div>

                {/* Suggested Solution */}
                <div className="flex-1">
                  <h4 className="text-xs font-semibold text-[var(--primary)] uppercase tracking-wider mb-2">Suggested Next Step</h4>
                  <div className="p-4 rounded-lg bg-[var(--primary)] bg-opacity-10 border border-[var(--primary)] border-opacity-20">
                    <p className="text-white text-sm font-medium leading-relaxed">
                      {insight.suggestion.action}
                    </p>
                  </div>
                </div>

                {/* Actions */}
                {renderActionLinks(insight)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
