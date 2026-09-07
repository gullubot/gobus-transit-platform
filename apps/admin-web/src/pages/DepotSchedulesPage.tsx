import { useState, useEffect, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Building2,
  Clock,
  Search,
  ExternalLink,
  Eye,
  Bus,
  MapPin,
  ArrowRight,
  RefreshCw,
  X,
} from "lucide-react";
import {
  getMajorDepots,
  getDepotDepartures,
  type MajorDepot,
  type DepotDepartureItem,
} from "../api/api";
import { SearchableDepotSelect } from "../components/SearchableDepotSelect";

export default function DepotSchedulesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [depots, setDepots] = useState<MajorDepot[]>([]);
  const [selectedDepotId, setSelectedDepotId] = useState<string>("");
  const [departures, setDepartures] = useState<DepotDepartureItem[]>([]);
  const [loadingDepots, setLoadingDepots] = useState(true);
  const [loadingDepartures, setLoadingDepartures] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDetail, setSelectedDetail] = useState<DepotDepartureItem | null>(null);

  // Load Major Depots on mount
  useEffect(() => {
    async function loadDepots() {
      try {
        setLoadingDepots(true);
        const data = await getMajorDepots();
        setDepots(data);

        // Check if query param specifies a depot
        const urlDepotId = searchParams.get("depotId");
        if (urlDepotId && data.some((d) => d.id === urlDepotId)) {
          setSelectedDepotId(urlDepotId);
        }
      } catch (err) {
        console.error("Failed to load major depots:", err);
      } finally {
        setLoadingDepots(false);
      }
    }
    loadDepots();
  }, []);

  // Fetch departures whenever selected depot changes
  useEffect(() => {
    if (!selectedDepotId) {
      setDepartures([]);
      return;
    }

    // Immediately clear stale departures to prevent stale data flashing
    setDepartures([]);

    // Sync URL search param
    const currentParam = searchParams.get("depotId");
    if (currentParam !== selectedDepotId) {
      setSearchParams({ depotId: selectedDepotId });
    }

    async function fetchDepartures() {
      try {
        setLoadingDepartures(true);
        const data = await getDepotDepartures(selectedDepotId);
        setDepartures(data);
      } catch (err) {
        console.error("Failed to load depot departures:", err);
      } finally {
        setLoadingDepartures(false);
      }
    }

    fetchDepartures();
  }, [selectedDepotId]);

  const selectedDepot = useMemo(() => {
    return depots.find((d) => d.id === selectedDepotId) || null;
  }, [depots, selectedDepotId]);

  // Client-side search within the departures list
  const filteredDepartures = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return departures;

    return departures.filter((item) => {
      const matchVeh = item.vehicle_number.toLowerCase().includes(q);
      const matchReg = (item.registration_number || "").toLowerCase().includes(q);
      const matchSvcCode = item.service_code.toLowerCase().includes(q);
      const matchSvcName = item.service_name.toLowerCase().includes(q);
      const matchDest = item.destination_stop_name.toLowerCase().includes(q);
      const matchTime = item.formatted_departure_time.toLowerCase().includes(q) || item.departure_time.includes(q);
      return matchVeh || matchReg || matchSvcCode || matchSvcName || matchDest || matchTime;
    });
  }, [departures, searchQuery]);

  const handleRefresh = async () => {
    if (!selectedDepotId) return;
    try {
      setLoadingDepartures(true);
      const data = await getDepotDepartures(selectedDepotId);
      setDepartures(data);
    } catch (err) {
      console.error("Failed to refresh departures:", err);
    } finally {
      setLoadingDepartures(false);
    }
  };

  return (
    <div style={{ padding: "28px 36px", maxWidth: "1500px", margin: "0 auto", color: "#f8fafc" }}>
      {/* Page Header */}
      <div style={{ marginBottom: "28px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
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
            <Building2 size={22} style={{ color: "#818cf8" }} />
          </div>
          <div>
            <h1 style={{ fontSize: "24px", fontWeight: 700, letterSpacing: "-0.02em", margin: 0 }}>
              Depot Schedule
            </h1>
            <p style={{ fontSize: "14px", color: "#94a3b8", margin: 0, marginTop: "2px" }}>
              Major-depot-centric combined daily operational dispatch timetable
            </p>
          </div>
        </div>
      </div>

      {/* Layer 1: Depot Selection Card */}
      <div
        style={{
          backgroundColor: "#161922",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: "12px",
          padding: "20px 24px",
          marginBottom: "24px",
          boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.2)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
          <label style={{ fontSize: "13px", fontWeight: 600, color: "#cbd5e1", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Select Major Depot
          </label>
          {depots.length > 0 && (
            <span style={{ fontSize: "12px", color: "#64748b" }}>
              {depots.length} Major Depots available across active routes
            </span>
          )}
        </div>

        <div style={{ maxWidth: "600px" }}>
          <SearchableDepotSelect
            depots={depots}
            value={selectedDepotId}
            onChange={(id) => setSelectedDepotId(id)}
            placeholder="Search or choose a Major Depot (e.g. Sonarpur, Howrah, Garia)..."
            isLoading={loadingDepots}
          />
        </div>

        {selectedDepot && (
          <div
            style={{
              marginTop: "16px",
              paddingTop: "14px",
              borderTop: "1px solid rgba(255, 255, 255, 0.06)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontSize: "13px",
                  color: "#cbd5e1",
                }}
              >
                <MapPin size={15} style={{ color: "#818cf8" }} />
                <span>Selected Origin:</span>
                <strong style={{ color: "#f8fafc" }}>{selectedDepot.stop_name}</strong>
                <span
                  style={{
                    fontSize: "11px",
                    fontFamily: "monospace",
                    color: "#94a3b8",
                    backgroundColor: "rgba(255, 255, 255, 0.06)",
                    padding: "1px 6px",
                    borderRadius: "4px",
                  }}
                >
                  {selectedDepot.stop_code}
                </span>
              </div>
              <span style={{ color: "rgba(255, 255, 255, 0.2)" }}>•</span>
              <span style={{ fontSize: "13px", color: "#94a3b8" }}>
                Endpoint for <strong style={{ color: "#cbd5e1" }}>{selectedDepot.routes_count}</strong> {selectedDepot.routes_count === 1 ? "route" : "routes"}
              </span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                style={{
                  fontSize: "12px",
                  padding: "3px 10px",
                  borderRadius: "20px",
                  backgroundColor: departures.length > 0 ? "rgba(34, 197, 94, 0.12)" : "rgba(148, 163, 184, 0.12)",
                  color: departures.length > 0 ? "#4ade80" : "#94a3b8",
                  border: departures.length > 0 ? "1px solid rgba(34, 197, 94, 0.25)" : "1px solid rgba(148, 163, 184, 0.2)",
                  fontWeight: 600,
                }}
              >
                {departures.length} {departures.length === 1 ? "Daily Departure" : "Daily Departures"}
              </span>
              <button
                type="button"
                onClick={handleRefresh}
                disabled={loadingDepartures}
                title="Refresh timetable"
                style={{
                  background: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: "6px",
                  padding: "6px 10px",
                  color: "#cbd5e1",
                  fontSize: "12px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <RefreshCw size={13} style={{ animation: loadingDepartures ? "spin 1s linear infinite" : "none" }} />
                Refresh
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Layer 2: Departures Timetable */}
      {!selectedDepotId ? (
        <div
          style={{
            backgroundColor: "#161922",
            border: "1px dashed rgba(255, 255, 255, 0.15)",
            borderRadius: "12px",
            padding: "60px 20px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "12px",
          }}
        >
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              backgroundColor: "rgba(99, 102, 241, 0.1)",
              border: "1px solid rgba(99, 102, 241, 0.25)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Building2 size={24} style={{ color: "#818cf8" }} />
          </div>
          <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#f8fafc", margin: 0 }}>
            Select a Major Depot
          </h3>
          <p style={{ fontSize: "13px", color: "#94a3b8", maxWidth: "440px", margin: 0 }}>
            Choose any Major Depot above to view the combined daily operational timetable across all routes and services originating from it.
          </p>
        </div>
      ) : (
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
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ position: "relative", width: "300px" }}>
                <Search size={15} style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
                <input
                  type="text"
                  placeholder="Filter departures by bus, reg, service, dest..."
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
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "12px", color: "#94a3b8" }}>
              <span>Sorted chronologically (ASC)</span>
            </div>
          </div>

          {/* Timetable Table */}
          {loadingDepartures ? (
            <div style={{ padding: "60px 20px", textAlign: "center", color: "#94a3b8", fontSize: "14px" }}>
              <RefreshCw size={24} style={{ animation: "spin 1s linear infinite", marginBottom: "8px", color: "#818cf8" }} />
              <div>Loading combined departures timetable...</div>
            </div>
          ) : departures.length === 0 ? (
            <div style={{ padding: "60px 20px", textAlign: "center" }}>
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
                <Clock size={20} style={{ color: "#94a3b8" }} />
              </div>
              <h4 style={{ fontSize: "15px", fontWeight: 600, color: "#f8fafc", margin: "0 0 4px" }}>
                No Recurring Departures Scheduled
              </h4>
              <p style={{ fontSize: "13px", color: "#94a3b8", maxWidth: "420px", margin: "0 auto 16px" }}>
                There are currently no recurring departures originating from {selectedDepot?.stop_name}. Manage Fleet Schedules to add daily service departures.
              </p>
              <button
                type="button"
                onClick={() => navigate("/fleet-schedules")}
                style={{
                  padding: "7px 14px",
                  backgroundColor: "#4f46e5",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                Go to Fleet Schedule <ExternalLink size={13} />
              </button>
            </div>
          ) : filteredDepartures.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "#94a3b8", fontSize: "13px" }}>
              No departures match your filter query "{searchQuery}".
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "13px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.08)", backgroundColor: "rgba(255, 255, 255, 0.02)" }}>
                    <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em" }}>
                      DEPARTURE TIME
                    </th>
                    <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em" }}>
                      BUS / VEHICLE
                    </th>
                    <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em" }}>
                      SERVICE
                    </th>
                    <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em" }}>
                      ROUTE (ORIGIN → DESTINATION)
                    </th>
                    <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em" }}>
                      STATUS
                    </th>
                    <th style={{ padding: "12px 18px", color: "#94a3b8", fontWeight: 600, fontSize: "12px", letterSpacing: "0.03em", textAlign: "right" }}>
                      ACTIONS
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDepartures.map((item) => (
                    <tr
                      key={item.id}
                      style={{
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                        transition: "background-color 0.15s ease",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.02)")}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                    >
                      {/* Departure Time */}
                      <td style={{ padding: "14px 18px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
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
                            <Clock size={15} style={{ color: "#818cf8" }} />
                          </div>
                          <div>
                            <span style={{ fontSize: "14px", fontWeight: 700, color: "#f8fafc" }}>
                              {item.formatted_departure_time}
                            </span>
                            <div style={{ display: "flex", alignItems: "center", gap: "4px", marginTop: "2px" }}>
                              <span
                                style={{
                                  fontSize: "10px",
                                  fontWeight: 600,
                                  color: "#38bdf8",
                                  backgroundColor: "rgba(56, 189, 248, 0.1)",
                                  padding: "1px 5px",
                                  borderRadius: "3px",
                                  border: "1px solid rgba(56, 189, 248, 0.2)",
                                }}
                              >
                                Daily
                              </span>
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Bus / Vehicle (BOTH vehicle_number AND registration_number) */}
                      <td style={{ padding: "14px 18px" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            <Bus size={13} style={{ color: "#94a3b8" }} />
                            <span
                              style={{
                                fontWeight: 600,
                                color: "#f8fafc",
                                fontFamily: "monospace",
                                fontSize: "13px",
                              }}
                            >
                              {item.vehicle_number}
                            </span>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            <span
                              style={{
                                fontSize: "11px",
                                fontFamily: "monospace",
                                color: "#94a3b8",
                                backgroundColor: "rgba(255, 255, 255, 0.05)",
                                padding: "1px 6px",
                                borderRadius: "3px",
                                border: "1px solid rgba(255, 255, 255, 0.08)",
                              }}
                            >
                              {item.registration_number || "No Reg"}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Service */}
                      <td style={{ padding: "14px 18px" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            <span
                              style={{
                                fontWeight: 600,
                                color: "#f8fafc",
                                fontSize: "13px",
                              }}
                            >
                              {item.service_code}
                            </span>
                          </div>
                          <span style={{ fontSize: "12px", color: "#94a3b8" }}>
                            {item.service_name}
                          </span>
                        </div>
                      </td>

                      {/* Route (Dynamically derived Origin -> Destination) */}
                      <td style={{ padding: "14px 18px" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
                            <span style={{ fontWeight: 600, color: "#818cf8", fontSize: "13px" }}>
                              {item.origin_stop_name}
                            </span>
                            <ArrowRight size={13} style={{ color: "#64748b" }} />
                            <span style={{ fontWeight: 600, color: "#e2e8f0", fontSize: "13px" }}>
                              {item.destination_stop_name}
                            </span>
                          </div>
                          {item.route_name && (
                            <span style={{ fontSize: "11px", color: "#64748b" }}>
                              Route: {item.route_code ? `${item.route_code} • ` : ""}{item.route_name}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Status */}
                      <td style={{ padding: "14px 18px" }}>
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            padding: "3px 8px",
                            borderRadius: "4px",
                            backgroundColor: "rgba(59, 130, 246, 0.12)",
                            color: "#60a5fa",
                            border: "1px solid rgba(59, 130, 246, 0.25)",
                            display: "inline-block",
                          }}
                        >
                          {item.status}
                        </span>
                      </td>

                      {/* Actions */}
                      <td style={{ padding: "14px 18px", textAlign: "right" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "8px" }}>
                          <button
                            type="button"
                            onClick={() => setSelectedDetail(item)}
                            title="View full dispatch metadata"
                            style={{
                              padding: "5px 10px",
                              backgroundColor: "rgba(255, 255, 255, 0.05)",
                              border: "1px solid rgba(255, 255, 255, 0.1)",
                              borderRadius: "6px",
                              color: "#cbd5e1",
                              fontSize: "12px",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              gap: "5px",
                              transition: "all 0.15s ease",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = "rgba(99, 102, 241, 0.15)";
                              e.currentTarget.style.color = "#c7d2fe";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.05)";
                              e.currentTarget.style.color = "#cbd5e1";
                            }}
                          >
                            <Eye size={13} /> View
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              navigate(
                                `/fleet-schedules?serviceId=${item.service_id}&direction=${item.direction}`
                              )
                            }
                            title="Manage timetable entry in Fleet Schedule"
                            style={{
                              padding: "5px 10px",
                              backgroundColor: "rgba(99, 102, 241, 0.1)",
                              border: "1px solid rgba(99, 102, 241, 0.25)",
                              borderRadius: "6px",
                              color: "#818cf8",
                              fontSize: "12px",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              gap: "5px",
                              transition: "all 0.15s ease",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = "#4f46e5";
                              e.currentTarget.style.color = "#ffffff";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = "rgba(99, 102, 241, 0.1)";
                              e.currentTarget.style.color = "#818cf8";
                            }}
                          >
                            <ExternalLink size={13} /> Fleet Schedule
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
      )}

      {/* Details Modal */}
      {selectedDetail && (
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
          onClick={() => setSelectedDetail(null)}
        >
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "14px",
              width: "100%",
              maxWidth: "560px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
              overflow: "hidden",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
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
                <div
                  style={{
                    padding: "6px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(99, 102, 241, 0.15)",
                    border: "1px solid rgba(99, 102, 241, 0.3)",
                  }}
                >
                  <Clock size={18} style={{ color: "#818cf8" }} />
                </div>
                <div>
                  <h3 style={{ fontSize: "16px", fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                    Departure Details
                  </h3>
                  <p style={{ fontSize: "12px", color: "#94a3b8", margin: 0 }}>
                    Dispatch timetable metadata for {selectedDetail.formatted_departure_time}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDetail(null)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  padding: "4px",
                  borderRadius: "4px",
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "20px" }}>
              {/* Derived Route & Major Depots */}
              <div
                style={{
                  padding: "14px 16px",
                  borderRadius: "8px",
                  backgroundColor: "rgba(0, 0, 0, 0.25)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" }}>
                  Operational Route (Major Depots)
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                  <div style={{ flex: 1 }}>
                    <span style={{ fontSize: "11px", color: "#94a3b8" }}>Origin Major Depot:</span>
                    <div style={{ fontWeight: 600, color: "#818cf8", fontSize: "14px" }}>
                      {selectedDetail.origin_stop_name}
                    </div>
                    {selectedDetail.origin_stop_code && (
                      <span style={{ fontSize: "11px", fontFamily: "monospace", color: "#64748b" }}>
                        {selectedDetail.origin_stop_code}
                      </span>
                    )}
                  </div>
                  <ArrowRight size={18} style={{ color: "#64748b", flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <span style={{ fontSize: "11px", color: "#94a3b8" }}>Destination Major Depot:</span>
                    <div style={{ fontWeight: 600, color: "#f8fafc", fontSize: "14px" }}>
                      {selectedDetail.destination_stop_name}
                    </div>
                    {selectedDetail.destination_stop_code && (
                      <span style={{ fontSize: "11px", fontFamily: "monospace", color: "#64748b" }}>
                        {selectedDetail.destination_stop_code}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Service & Route Details */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
                <div
                  style={{
                    padding: "12px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid rgba(255, 255, 255, 0.06)",
                  }}
                >
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Service</span>
                  <div style={{ fontWeight: 600, color: "#f8fafc", fontSize: "14px", marginTop: "2px" }}>
                    {selectedDetail.service_code}
                  </div>
                  <div style={{ fontSize: "12px", color: "#94a3b8" }}>{selectedDetail.service_name}</div>
                </div>

                <div
                  style={{
                    padding: "12px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid rgba(255, 255, 255, 0.06)",
                  }}
                >
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Direction</span>
                  <div style={{ fontWeight: 600, color: "#38bdf8", fontSize: "14px", marginTop: "2px" }}>
                    {selectedDetail.direction === "A_TO_B" ? "Outbound (A → B)" : "Inbound (B → A)"}
                  </div>
                  <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                    {selectedDetail.route_code || selectedDetail.route_name || "Route Assignment"}
                  </div>
                </div>
              </div>

              {/* Vehicle & Registration */}
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: "8px",
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Assigned Vehicle</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
                    <span style={{ fontWeight: 700, fontSize: "14px", color: "#f8fafc", fontFamily: "monospace" }}>
                      {selectedDetail.vehicle_number}
                    </span>
                    <span
                      style={{
                        fontSize: "12px",
                        fontFamily: "monospace",
                        color: "#94a3b8",
                        backgroundColor: "rgba(255, 255, 255, 0.06)",
                        padding: "2px 6px",
                        borderRadius: "4px",
                      }}
                    >
                      {selectedDetail.registration_number || "No Registration"}
                    </span>
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Status</span>
                  <div style={{ marginTop: "4px" }}>
                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        padding: "2px 8px",
                        borderRadius: "4px",
                        backgroundColor: "rgba(34, 197, 94, 0.12)",
                        color: "#4ade80",
                      }}
                    >
                      {selectedDetail.vehicle_status}
                    </span>
                  </div>
                </div>
              </div>

              {/* Timetable Schedule info */}
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: "8px",
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  fontSize: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#cbd5e1" }}>
                  <Clock size={15} style={{ color: "#818cf8" }} />
                  <span>Scheduled Time: <strong>{selectedDetail.formatted_departure_time}</strong></span>
                </div>
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "#38bdf8",
                    backgroundColor: "rgba(56, 189, 248, 0.1)",
                    padding: "2px 8px",
                    borderRadius: "4px",
                  }}
                >
                  Recurring Daily
                </span>
              </div>
            </div>

            {/* Modal Actions */}
            <div
              style={{
                padding: "16px 24px",
                borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
                gap: "10px",
                backgroundColor: "rgba(0, 0, 0, 0.2)",
              }}
            >
              <button
                type="button"
                onClick={() => setSelectedDetail(null)}
                style={{
                  padding: "8px 16px",
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: "6px",
                  color: "#cbd5e1",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                Close
              </button>

              <button
                type="button"
                onClick={() => {
                  const s = selectedDetail;
                  setSelectedDetail(null);
                  navigate(`/fleet-schedules?serviceId=${s.service_id}&direction=${s.direction}`);
                }}
                style={{
                  padding: "8px 16px",
                  backgroundColor: "#4f46e5",
                  border: "none",
                  borderRadius: "6px",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                Manage in Fleet Schedule <ExternalLink size={14} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
