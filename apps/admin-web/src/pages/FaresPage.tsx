import { useState, useEffect, useMemo } from "react";
import {
  Banknote,
  Edit2,
  Search,
  Eye,
  Calendar,
  Layers,
  CheckCircle,
  XCircle,
  X,
} from "lucide-react";
import {
  apiFetch,
  getFareConfigurations,
  activateFareConfiguration,
  deactivateFareConfiguration,
  type FareConfigurationItem,
} from "../api/api";
import { FareDetailModal } from "../components/FareDetailModal";

// Date formatting helper for consistent "DD MMM YYYY" format
function formatDate(isoStr: string | null | undefined): string {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }); // e.g. "04 Sep 2026"
  } catch {
    return isoStr;
  }
}

export default function FaresPage() {
  const [configs, setConfigs] = useState<FareConfigurationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFareId, setActiveFareId] = useState<string | null>(null);
  const [openInEditMode, setOpenInEditMode] = useState(false);

  // Preview Fare State
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewRouteId, setPreviewRouteId] = useState("");
  const [previewOriginStopId, setPreviewOriginStopId] = useState("");
  const [previewDestStopId, setPreviewDestStopId] = useState("");
  const [previewResult, setPreviewResult] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [routes, setRoutes] = useState<any[]>([]);
  const [stops, setStops] = useState<any[]>([]);

  useEffect(() => {
    loadData();
    loadPreviewDependencies();

    // Deep link query param support
    const params = new URLSearchParams(window.location.search);
    const urlFareId = params.get("fareId");
    if (urlFareId) {
      setActiveFareId(urlFareId);
    }
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await getFareConfigurations();
      setConfigs(data);
    } catch (err) {
      console.error("Failed to load fare configurations", err);
    } finally {
      setLoading(false);
    }
  };

  const loadPreviewDependencies = async () => {
    try {
      const [rData, sData] = await Promise.all([
        apiFetch("/admin/routes"),
        apiFetch("/admin/stops"),
      ]);
      setRoutes(rData);
      setStops(sData);
    } catch (err) {
      console.error("Failed to load preview dependencies", err);
    }
  };

  const handleOpenDetails = (fareId: string, edit = false) => {
    setOpenInEditMode(edit);
    setActiveFareId(fareId);
  };

  const handleCloseModal = () => {
    setActiveFareId(null);
    setOpenInEditMode(false);
  };

  const handleFareUpdated = (updated: FareConfigurationItem) => {
    setConfigs((prev) =>
      prev.map((c) => (c.id === updated.id ? updated : c))
    );
  };

  const handleToggleActive = async (e: React.MouseEvent, config: FareConfigurationItem) => {
    e.stopPropagation();
    try {
      if (config.is_active) {
        const res = await deactivateFareConfiguration(config.id);
        handleFareUpdated(res);
      } else {
        const res = await activateFareConfiguration(config.id);
        handleFareUpdated(res);
      }
    } catch (err: any) {
      alert(`Action failed: ${err.message}`);
    }
  };

  const filteredConfigs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return configs;

    return configs.filter((c) => {
      const nameMatch = (c.name || "").toLowerCase().includes(q);
      const svcCodeMatch = (c.service_code || "").toLowerCase().includes(q);
      const svcNameMatch = (c.service_name || "").toLowerCase().includes(q);
      const slabsMatch = `${c.slabs.length} slabs`.includes(q);
      return nameMatch || svcCodeMatch || svcNameMatch || slabsMatch;
    });
  }, [configs, searchQuery]);

  return (
    <div style={{ padding: "28px 36px", maxWidth: "1500px", margin: "0 auto", color: "#f8fafc" }}>
      {/* Page Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "28px",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              padding: "8px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(168, 85, 247, 0.2))",
              border: "1px solid rgba(99, 102, 241, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Banknote size={22} style={{ color: "#818cf8" }} />
          </div>
          <div>
            <h1 style={{ fontSize: "24px", fontWeight: 700, letterSpacing: "-0.02em", margin: 0 }}>
              Fare Management
            </h1>
            <p style={{ fontSize: "14px", color: "#94a3b8", margin: 0, marginTop: "2px" }}>
              View and manage fare configurations attached to services.
            </p>
          </div>
        </div>

        {/* Secondary Tool: Preview Fare (Notice NO independent Create Fare Config button) */}
        <button
          type="button"
          onClick={() => setShowPreviewModal(true)}
          style={{
            padding: "8px 16px",
            backgroundColor: "rgba(255, 255, 255, 0.05)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            borderRadius: "8px",
            color: "#cbd5e1",
            fontSize: "13px",
            fontWeight: 500,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.08)";
            e.currentTarget.style.color = "#f8fafc";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.05)";
            e.currentTarget.style.color = "#cbd5e1";
          }}
        >
          <Banknote size={16} style={{ color: "#818cf8" }} />
          Preview Fare Calculation
        </button>
      </div>

      {/* Main Table Card */}
      <div
        style={{
          backgroundColor: "#161922",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: "12px",
          boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.2)",
          overflow: "hidden",
        }}
      >
        {/* Table Toolbar */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
            backgroundColor: "rgba(0, 0, 0, 0.15)",
          }}
        >
          <div style={{ position: "relative", width: "320px" }}>
            <Search
              size={15}
              style={{
                position: "absolute",
                left: "10px",
                top: "50%",
                transform: "translateY(-50%)",
                color: "#64748b",
              }}
            />
            <input
              type="text"
              placeholder="Search fares by name, service code..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: "100%",
                padding: "7px 10px 7px 32px",
                backgroundColor: "rgba(255, 255, 255, 0.04)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "6px",
                color: "#f8fafc",
                fontSize: "13px",
                outline: "none",
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                style={{
                  position: "absolute",
                  right: "8px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>

          <div style={{ fontSize: "12px", color: "#94a3b8" }}>
            Showing {filteredConfigs.length} of {configs.length} fare configurations
          </div>
        </div>

        {/* Fares Table */}
        {loading ? (
          <div style={{ padding: "60px 20px", textAlign: "center", color: "#94a3b8", fontSize: "14px" }}>
            Loading fare configurations...
          </div>
        ) : configs.length === 0 ? (
          <div style={{ padding: "60px 20px", textAlign: "center", color: "#94a3b8" }}>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "10px",
                backgroundColor: "rgba(148, 163, 184, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 12px",
              }}
            >
              <Banknote size={20} style={{ color: "#94a3b8" }} />
            </div>
            <h4 style={{ fontSize: "15px", fontWeight: 600, color: "#f8fafc", margin: "0 0 4px" }}>
              No Fare Configurations Found
            </h4>
            <p style={{ fontSize: "13px", color: "#94a3b8", maxWidth: "420px", margin: "0 auto" }}>
              Fare configurations are created during Service creation in the Services module.
            </p>
          </div>
        ) : filteredConfigs.length === 0 ? (
          <div style={{ padding: "40px 20px", textAlign: "center", color: "#94a3b8", fontSize: "13px" }}>
            No fare configurations match your search query "{searchQuery}".
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "13px" }}>
              <thead>
                <tr
                  style={{
                    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                  }}
                >
                  <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em" }}>
                    FARE CONFIGURATION / NAME
                  </th>
                  <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em" }}>
                    ATTACHED SERVICE
                  </th>
                  <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em" }}>
                    STATUS
                  </th>
                  <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em" }}>
                    EFFECTIVE FROM
                  </th>
                  <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em" }}>
                    RATE SLABS
                  </th>
                  <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em", textAlign: "right" }}>
                    ACTIONS
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredConfigs.map((config) => (
                  <tr
                    key={config.id}
                    onClick={() => handleOpenDetails(config.id, false)}
                    style={{
                      borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      cursor: "pointer",
                      transition: "background-color 0.15s ease",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.02)")}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                  >
                    {/* Name */}
                    <td style={{ padding: "14px 18px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <div
                          style={{
                            width: "30px",
                            height: "30px",
                            borderRadius: "6px",
                            backgroundColor: "rgba(99, 102, 241, 0.12)",
                            border: "1px solid rgba(99, 102, 241, 0.25)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                          }}
                        >
                          <Banknote size={15} style={{ color: "#818cf8" }} />
                        </div>
                        <div>
                          <span style={{ fontWeight: 600, color: "#f8fafc", fontSize: "14px" }}>
                            {config.name}
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Attached Service */}
                    <td style={{ padding: "14px 18px" }}>
                      {config.service_code ? (
                        <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                          <span
                            style={{
                              fontSize: "12px",
                              color: "#c7d2fe",
                              backgroundColor: "rgba(99, 102, 241, 0.14)",
                              border: "1px solid rgba(99, 102, 241, 0.28)",
                              padding: "3px 8px",
                              borderRadius: "5px",
                              fontWeight: 600,
                              letterSpacing: "0.01em",
                            }}
                          >
                            {config.service_name ? `${config.service_name} · ${config.service_code}` : config.service_code}
                          </span>
                        </div>
                      ) : (
                        <span style={{ color: "#64748b", fontSize: "12px", fontStyle: "italic" }}>
                          Unassigned
                        </span>
                      )}
                    </td>

                    {/* Status */}
                    <td style={{ padding: "14px 18px" }}>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          padding: "3px 8px",
                          borderRadius: "4px",
                          backgroundColor: config.is_active
                            ? "rgba(34, 197, 94, 0.12)"
                            : "rgba(148, 163, 184, 0.12)",
                          color: config.is_active ? "#4ade80" : "#94a3b8",
                          border: config.is_active
                            ? "1px solid rgba(34, 197, 94, 0.25)"
                            : "1px solid rgba(148, 163, 184, 0.2)",
                          display: "inline-block",
                        }}
                      >
                        {config.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>

                    {/* Effective From */}
                    <td style={{ padding: "14px 18px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#cbd5e1" }}>
                        <Calendar size={13} style={{ color: "#94a3b8" }} />
                        <span>{formatDate(config.effective_from)}</span>
                      </div>
                    </td>

                    {/* Rate Slabs Count */}
                    <td style={{ padding: "14px 18px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#cbd5e1" }}>
                        <Layers size={13} style={{ color: "#818cf8" }} />
                        <span style={{ fontWeight: 600 }}>{config.slabs.length}</span>
                        <span style={{ color: "#94a3b8", fontSize: "12px" }}>
                          {config.slabs.length === 1 ? "slab" : "slabs"}
                        </span>
                      </div>
                    </td>

                    {/* Actions */}
                    <td style={{ padding: "14px 18px", textAlign: "right" }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "flex-end",
                          gap: "8px",
                        }}
                      >
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenDetails(config.id, false);
                          }}
                          title="View Rate Chart & Details"
                          style={{
                            padding: "5px 10px",
                            backgroundColor: "rgba(255, 255, 255, 0.05)",
                            border: "1px solid rgba(255, 255, 255, 0.1)",
                            borderRadius: "6px",
                            color: "#cbd5e1",
                            fontSize: "12px",
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                          }}
                        >
                          <Eye size={13} /> View
                        </button>

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenDetails(config.id, true);
                          }}
                          title="Edit Fare Configuration & Slabs"
                          style={{
                            padding: "5px 10px",
                            backgroundColor: "rgba(99, 102, 241, 0.1)",
                            border: "1px solid rgba(99, 102, 241, 0.25)",
                            borderRadius: "6px",
                            color: "#818cf8",
                            fontSize: "12px",
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                          }}
                        >
                          <Edit2 size={13} /> Edit
                        </button>

                        <button
                          type="button"
                          onClick={(e) => handleToggleActive(e, config)}
                          title={config.is_active ? "Deactivate fare" : "Activate fare"}
                          style={{
                            padding: "5px 8px",
                            backgroundColor: "transparent",
                            border: "none",
                            color: config.is_active ? "#f59e0b" : "#10b981",
                            cursor: "pointer",
                            borderRadius: "4px",
                          }}
                        >
                          {config.is_active ? <XCircle size={15} /> : <CheckCircle size={15} />}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Fare Details / Rate Chart / Edit Modal */}
      {activeFareId && (
        <FareDetailModal
          fareId={activeFareId}
          initialEdit={openInEditMode}
          onClose={handleCloseModal}
          onFareUpdated={handleFareUpdated}
        />
      )}

      {/* Preview Fare Calculation Modal */}
      {showPreviewModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10000,
            padding: "20px",
          }}
          onClick={() => {
            setShowPreviewModal(false);
            setPreviewResult(null);
            setPreviewError(null);
          }}
        >
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "14px",
              width: "100%",
              maxWidth: "520px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
              overflow: "hidden",
              color: "#f8fafc",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: "18px 24px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                backgroundColor: "rgba(255, 255, 255, 0.02)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Banknote size={18} style={{ color: "#818cf8" }} />
                <h3 style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>
                  Preview Fare Calculation
                </h3>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowPreviewModal(false);
                  setPreviewResult(null);
                  setPreviewError(null);
                }}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  padding: "4px",
                }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "16px" }}>
              {previewError && (
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "6px",
                    backgroundColor: "rgba(239, 68, 68, 0.12)",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                    color: "#f87171",
                    fontSize: "13px",
                  }}
                >
                  {previewError}
                </div>
              )}

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                  Route
                </label>
                <select
                  value={previewRouteId}
                  onChange={(e) => setPreviewRouteId(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    backgroundColor: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "6px",
                    color: "#f8fafc",
                    fontSize: "13px",
                    outline: "none",
                  }}
                >
                  <option value="" style={{ background: "#161922" }}>Select a route</option>
                  {routes.map((r: any) => (
                    <option key={r.id} value={r.id} style={{ background: "#161922" }}>
                      {r.route_code} — {r.route_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                  Origin Stop
                </label>
                <select
                  value={previewOriginStopId}
                  onChange={(e) => setPreviewOriginStopId(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    backgroundColor: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "6px",
                    color: "#f8fafc",
                    fontSize: "13px",
                    outline: "none",
                  }}
                >
                  <option value="" style={{ background: "#161922" }}>Select origin stop</option>
                  {stops.map((s: any) => (
                    <option key={s.id} value={s.id} style={{ background: "#161922" }}>
                      {s.name} ({s.stop_code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                  Destination Stop
                </label>
                <select
                  value={previewDestStopId}
                  onChange={(e) => setPreviewDestStopId(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    backgroundColor: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "6px",
                    color: "#f8fafc",
                    fontSize: "13px",
                    outline: "none",
                  }}
                >
                  <option value="" style={{ background: "#161922" }}>Select destination stop</option>
                  {stops.map((s: any) => (
                    <option key={s.id} value={s.id} style={{ background: "#161922" }}>
                      {s.name} ({s.stop_code})
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                disabled={previewLoading || !previewRouteId || !previewOriginStopId || !previewDestStopId}
                onClick={async () => {
                  try {
                    setPreviewLoading(true);
                    setPreviewError(null);
                    const { previewFare } = await import("../api/api");
                    const res = await previewFare({
                      route_id: previewRouteId,
                      origin_stop_id: previewOriginStopId,
                      destination_stop_id: previewDestStopId,
                    });
                    setPreviewResult(res);
                  } catch (err: any) {
                    setPreviewError(err.message || "Failed to calculate fare preview.");
                    setPreviewResult(null);
                  } finally {
                    setPreviewLoading(false);
                  }
                }}
                style={{
                  padding: "9px 16px",
                  backgroundColor: "#4f46e5",
                  border: "none",
                  borderRadius: "6px",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {previewLoading ? "Calculating..." : "Calculate Fare"}
              </button>

              {previewResult && (
                <div
                  style={{
                    padding: "16px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    fontSize: "13px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#94a3b8" }}>Calculated Distance:</span>
                    <strong>{Number(previewResult.distance_km).toFixed(2)} km</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#94a3b8" }}>Matched Slab:</span>
                    <span>
                      {Number(previewResult.matched_slab.min_distance_km).toFixed(2)} km
                      {" → "}
                      {previewResult.matched_slab.max_distance_km !== null
                        ? `${Number(previewResult.matched_slab.max_distance_km).toFixed(2)} km`
                        : "Open-ended (∞)"}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#94a3b8" }}>Configuration:</span>
                    <span>{previewResult.fare_configuration_name}</span>
                  </div>
                  <div
                    style={{
                      borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                      paddingTop: "10px",
                      marginTop: "4px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span style={{ fontSize: "14px", fontWeight: 600, color: "#cbd5e1" }}>Total Fare:</span>
                    <span style={{ fontSize: "18px", fontWeight: 700, color: "#4ade80" }}>
                      {previewResult.currency === "INR" ? "₹" : `${previewResult.currency} `}
                      {Number(previewResult.fare_amount).toFixed(2)}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
