import React, { useState, useEffect } from "react";
import {
  Truck,
  Network,
  Users,
  Route as RouteIcon,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  X,
  ShieldCheck,
  UserCheck,
  Info,
  AlertTriangle,
} from "lucide-react";
import {
  SearchablePersonnelSelect,
  type PersonnelOption,
} from "./SearchablePersonnelSelect";
import { assignVehicleCrew, getVehicleCrew, getAdminUsers } from "../api/api";

export interface VehicleDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  vehicle: {
    id: string;
    vehicle_number: string;
    registration_number?: string | null;
    vehicle_type: string;
    status: string;
    driver?: {
      id: string;
      name: string;
      employee_code?: string | null;
      role: string;
      phone?: string | null;
      email?: string | null;
    } | null;
    conductor?: {
      id: string;
      name: string;
      employee_code?: string | null;
      role: string;
      phone?: string | null;
      email?: string | null;
    } | null;
  };
  service: {
    id: string;
    service_code: string;
    service_name: string;
    route_code?: string | null;
    route_name?: string | null;
  };
  onSuccess: () => void;
}

export const VehicleDetailsModal: React.FC<VehicleDetailsModalProps> = ({
  isOpen,
  onClose,
  vehicle,
  service,
  onSuccess,
}) => {
  const [drivers, setDrivers] = useState<PersonnelOption[]>([]);
  const [conductors, setConductors] = useState<PersonnelOption[]>([]);
  const [loadingPersonnel, setLoadingPersonnel] = useState(false);

  const [activeDriver, setActiveDriver] = useState<any>(vehicle?.driver || null);
  const [activeConductor, setActiveConductor] = useState<any>(vehicle?.conductor || null);

  const [selectedDriverId, setSelectedDriverId] = useState<string>("");
  const [selectedConductorId, setSelectedConductorId] = useState<string>("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Initialize selected driver and conductor from vehicle props or fetch fresh crew
  useEffect(() => {
    if (isOpen && vehicle) {
      setActiveDriver(vehicle.driver || null);
      setActiveConductor(vehicle.conductor || null);
      setSelectedDriverId(vehicle.driver?.id || "");
      setSelectedConductorId(vehicle.conductor?.id || "");
      setError(null);
      setSuccessMsg(null);

      // Load personnel and refresh crew data
      loadPersonnel();
      fetchLatestCrew();
    }
  }, [isOpen, vehicle?.id, service?.id]);

  const loadPersonnel = async () => {
    try {
      setLoadingPersonnel(true);
      const [driversData, conductorsData] = await Promise.all([
        getAdminUsers("DRIVER"),
        getAdminUsers("CONDUCTOR"),
      ]);

      setDrivers(
        (driversData || []).map((u: any) => ({
          id: u.id,
          name: u.name,
          employee_code: u.operator_profile?.employee_code || undefined,
          role: u.role,
          phone: u.phone || undefined,
          email: u.email || undefined,
          current_bus: u.active_vehicle?.vehicle_number || undefined,
          current_bus_id: u.active_vehicle?.id || undefined,
          registration_number: u.active_vehicle?.registration_number || undefined,
        }))
      );

      setConductors(
        (conductorsData || []).map((u: any) => ({
          id: u.id,
          name: u.name,
          employee_code: u.operator_profile?.employee_code || undefined,
          role: u.role,
          phone: u.phone || undefined,
          email: u.email || undefined,
          current_bus: u.active_vehicle?.vehicle_number || undefined,
          current_bus_id: u.active_vehicle?.id || undefined,
          registration_number: u.active_vehicle?.registration_number || undefined,
        }))
      );
    } catch (err: any) {
      console.error("Failed to load personnel", err);
    } finally {
      setLoadingPersonnel(false);
    }
  };

  const fetchLatestCrew = async () => {
    try {
      const crew = await getVehicleCrew(vehicle.id, service.id);
      if (crew) {
        setActiveDriver(crew.driver || null);
        setActiveConductor(crew.conductor || null);
        setSelectedDriverId(crew.driver?.id || "");
        setSelectedConductorId(crew.conductor?.id || "");
      }
    } catch (err) {
      // Fall back to vehicle prop defaults
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setSaving(true);

    try {
      const resp = await assignVehicleCrew(vehicle.id, {
        service_id: service.id,
        driver_id: selectedDriverId || null,
        conductor_id: selectedConductorId || null,
      });

      if (resp) {
        setActiveDriver(resp.driver || null);
        setActiveConductor(resp.conductor || null);
      }

      setSuccessMsg("Crew assignment saved successfully.");
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 500);
    } catch (err: any) {
      setError(err.message || "Failed to save crew assignment.");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const selectedDriverOption = drivers.find((d) => d.id === selectedDriverId) || null;
  const selectedConductorOption = conductors.find((c) => c.id === selectedConductorId) || null;

  return (
    <div className="modal-overlay" style={{ zIndex: 1100 }}>
      <div
        className="modal-content"
        style={{
          maxWidth: "640px",
          width: "95%",
          maxHeight: "85vh",
          display: "flex",
          flexDirection: "column",
          borderRadius: "12px",
          border: "1px solid var(--border)",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
          background: "var(--bg-card)",
          overflow: "visible",
        }}
      >
        {/* ── FIXED MODAL HEADER ── */}
        <div
          className="modal-header"
          style={{
            flexShrink: 0,
            padding: "18px 24px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "8px",
                background: "rgba(59, 130, 246, 0.12)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--accent)",
              }}
            >
              <Truck size={20} />
            </div>
            <div>
              <h2 style={{ fontSize: "1.15rem", fontWeight: 700, margin: 0, color: "var(--text-main)" }}>
                Vehicle Details & Crew
              </h2>
              <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-muted)" }}>
                Manage vehicle specifications and assigned operating crew
              </p>
            </div>
          </div>
          <button className="close-btn" onClick={onClose} title="Close">
            <X size={20} />
          </button>
        </div>

        {/* ── SCROLLABLE MODAL BODY ── */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "20px 24px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          {/* FEEDBACK ALERTS */}
          {error && (
            <div
              style={{
                padding: "12px 16px",
                background: "rgba(239, 68, 68, 0.12)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                color: "#ef4444",
                borderRadius: "8px",
                fontSize: "0.85rem",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <AlertCircle size={18} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div
              style={{
                padding: "12px 16px",
                background: "rgba(16, 185, 129, 0.12)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                color: "#10b981",
                borderRadius: "8px",
                fontSize: "0.85rem",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <CheckCircle2 size={18} style={{ flexShrink: 0 }} />
              <span>{successMsg}</span>
            </div>
          )}

          {/* ───────────────────────────────────────────────────────── */}
          {/* SECTION 1: VEHICLE OVERVIEW */}
          {/* ───────────────────────────────────────────────────────── */}
          <div
            style={{
              background: "var(--bg-dark, #0b0f17)",
              border: "1px solid var(--border)",
              borderRadius: "10px",
              padding: "16px 18px",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "var(--accent)",
                marginBottom: "12px",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <Truck size={14} />
              Vehicle Overview
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                gap: "12px",
              }}
            >
              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                  Vehicle Number
                </div>
                <div
                  style={{
                    fontFamily: "monospace",
                    fontSize: "1rem",
                    fontWeight: 700,
                    color: "var(--accent)",
                  }}
                >
                  {vehicle.vehicle_number}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                  Registration
                </div>
                <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-main)" }}>
                  {vehicle.registration_number || "—"}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                  Vehicle Type
                </div>
                <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-main)" }}>
                  {vehicle.vehicle_type}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                  Status
                </div>
                <span className={`status-badge ${vehicle.status.toLowerCase()}`}>
                  {vehicle.status}
                </span>
              </div>
            </div>

            {/* SERVICE CONTEXT BANNER */}
            <div
              style={{
                marginTop: "14px",
                padding: "10px 14px",
                background: "rgba(59, 130, 246, 0.08)",
                border: "1px solid rgba(59, 130, 246, 0.2)",
                borderRadius: "8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: "8px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Network size={16} style={{ color: "var(--accent)", flexShrink: 0 }} />
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Assigned Service:</span>
                <strong style={{ fontSize: "0.9rem", color: "var(--text-main)" }}>
                  {service.service_name}
                </strong>
                <span
                  style={{
                    fontWeight: 700,
                    fontFamily: "monospace",
                    fontSize: "0.8rem",
                    background: "rgba(59, 130, 246, 0.15)",
                    color: "var(--accent)",
                    padding: "2px 6px",
                    borderRadius: "4px",
                  }}
                >
                  {service.service_code}
                </span>
              </div>

              {(service.route_code || service.route_name) && (
                <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  <RouteIcon size={13} style={{ color: "var(--accent)" }} />
                  <span>
                    Route: <strong style={{ color: "var(--text-main)" }}>{service.route_code || ""}</strong>
                    {service.route_code && service.route_name ? " — " : ""}
                    {service.route_name || ""}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* ───────────────────────────────────────────────────────── */}
          {/* SECTION 2: CREW ASSIGNMENT */}
          {/* ───────────────────────────────────────────────────────── */}
          <div
            style={{
              background: "var(--bg-dark, #0b0f17)",
              border: "1px solid var(--border)",
              borderRadius: "10px",
              padding: "16px 18px",
              position: "relative",
              zIndex: 10,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "14px",
              }}
            >
              <div
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "var(--accent)",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Users size={14} />
                Crew Assignment
              </div>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Active Operating Duty
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* DRIVER SELECTOR */}
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "6px",
                  }}
                >
                  <label
                    style={{
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      color: "var(--text-main)",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <UserCheck size={14} style={{ color: "var(--accent)" }} />
                    Driver
                  </label>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      background: activeDriver ? "rgba(16, 185, 129, 0.12)" : "rgba(255, 255, 255, 0.05)",
                      color: activeDriver ? "#10b981" : "var(--text-muted)",
                      fontWeight: activeDriver ? 600 : 400,
                    }}
                  >
                    {activeDriver ? `Assigned: ${activeDriver.name}` : "Not Assigned"}
                  </span>
                </div>

                <SearchablePersonnelSelect
                  role="DRIVER"
                  personnel={drivers}
                  value={selectedDriverId}
                  onChange={setSelectedDriverId}
                  isLoading={loadingPersonnel}
                  placeholder="-- Search & Select Driver --"
                  currentVehicleId={vehicle.id}
                />

                {selectedDriverOption && selectedDriverOption.current_bus_id && selectedDriverOption.current_bus_id !== vehicle.id && (
                  <div
                    style={{
                      marginTop: "8px",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "rgba(59, 130, 246, 0.1)",
                      border: "1px solid rgba(59, 130, 246, 0.25)",
                      fontSize: "0.8rem",
                      color: "#93c5fd",
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "8px",
                      lineHeight: 1.4,
                    }}
                  >
                    <Info size={15} style={{ color: "#60a5fa", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <strong>Reassignment Notice:</strong> This driver is currently assigned to{" "}
                      <strong style={{ color: "#ffffff" }}>{selectedDriverOption.current_bus}</strong>. Assigning them here will release them from that vehicle.
                    </div>
                  </div>
                )}

                {selectedDriverId && activeDriver && activeDriver.id !== selectedDriverId && (
                  <div
                    style={{
                      marginTop: "8px",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "rgba(245, 158, 11, 0.1)",
                      border: "1px solid rgba(245, 158, 11, 0.25)",
                      fontSize: "0.8rem",
                      color: "#fcd34d",
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "8px",
                      lineHeight: 1.4,
                    }}
                  >
                    <AlertTriangle size={15} style={{ color: "#f59e0b", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <strong>Crew Displacement:</strong> This bus currently has driver{" "}
                      <strong style={{ color: "#ffffff" }}>{activeDriver.name}</strong>. Assigning {selectedDriverOption?.name || "the selected driver"} will release {activeDriver.name} (relieved of vehicle duty).
                    </div>
                  </div>
                )}

                {!selectedDriverId && activeDriver && (
                  <div
                    style={{
                      marginTop: "8px",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "rgba(148, 163, 184, 0.1)",
                      border: "1px solid rgba(148, 163, 184, 0.25)",
                      fontSize: "0.8rem",
                      color: "#cbd5e1",
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "8px",
                      lineHeight: 1.4,
                    }}
                  >
                    <Info size={15} style={{ color: "#94a3b8", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      Current driver <strong style={{ color: "#ffffff" }}>{activeDriver.name}</strong> will be released from this bus upon saving.
                    </div>
                  </div>
                )}
              </div>

              {/* CONDUCTOR SELECTOR */}
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "6px",
                  }}
                >
                  <label
                    style={{
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      color: "var(--text-main)",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <ShieldCheck size={14} style={{ color: "var(--accent)" }} />
                    Conductor
                  </label>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      background: activeConductor ? "rgba(16, 185, 129, 0.12)" : "rgba(255, 255, 255, 0.05)",
                      color: activeConductor ? "#10b981" : "var(--text-muted)",
                      fontWeight: activeConductor ? 600 : 400,
                    }}
                  >
                    {activeConductor ? `Assigned: ${activeConductor.name}` : "Not Assigned"}
                  </span>
                </div>

                <SearchablePersonnelSelect
                  role="CONDUCTOR"
                  personnel={conductors}
                  value={selectedConductorId}
                  onChange={setSelectedConductorId}
                  isLoading={loadingPersonnel}
                  placeholder="-- Search & Select Conductor --"
                  currentVehicleId={vehicle.id}
                />

                {selectedConductorOption && selectedConductorOption.current_bus_id && selectedConductorOption.current_bus_id !== vehicle.id && (
                  <div
                    style={{
                      marginTop: "8px",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "rgba(59, 130, 246, 0.1)",
                      border: "1px solid rgba(59, 130, 246, 0.25)",
                      fontSize: "0.8rem",
                      color: "#93c5fd",
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "8px",
                      lineHeight: 1.4,
                    }}
                  >
                    <Info size={15} style={{ color: "#60a5fa", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <strong>Reassignment Notice:</strong> This conductor is currently assigned to{" "}
                      <strong style={{ color: "#ffffff" }}>{selectedConductorOption.current_bus}</strong>. Assigning them here will release them from that vehicle.
                    </div>
                  </div>
                )}

                {selectedConductorId && activeConductor && activeConductor.id !== selectedConductorId && (
                  <div
                    style={{
                      marginTop: "8px",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "rgba(245, 158, 11, 0.1)",
                      border: "1px solid rgba(245, 158, 11, 0.25)",
                      fontSize: "0.8rem",
                      color: "#fcd34d",
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "8px",
                      lineHeight: 1.4,
                    }}
                  >
                    <AlertTriangle size={15} style={{ color: "#f59e0b", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <strong>Crew Displacement:</strong> This bus currently has conductor{" "}
                      <strong style={{ color: "#ffffff" }}>{activeConductor.name}</strong>. Assigning {selectedConductorOption?.name || "the selected conductor"} will release {activeConductor.name} (relieved of vehicle duty).
                    </div>
                  </div>
                )}

                {!selectedConductorId && activeConductor && (
                  <div
                    style={{
                      marginTop: "8px",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "rgba(148, 163, 184, 0.1)",
                      border: "1px solid rgba(148, 163, 184, 0.25)",
                      fontSize: "0.8rem",
                      color: "#cbd5e1",
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "8px",
                      lineHeight: 1.4,
                    }}
                  >
                    <Info size={15} style={{ color: "#94a3b8", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      Current conductor <strong style={{ color: "#ffffff" }}>{activeConductor.name}</strong> will be released from this bus upon saving.
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ── FIXED MODAL FOOTER ── */}
        <div
          style={{
            flexShrink: 0,
            padding: "16px 24px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: "12px",
            background: "var(--bg-card)",
            borderRadius: "0 0 12px 12px",
          }}
        >
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </button>

          <button
            type="button"
            className="btn-primary"
            onClick={handleSave}
            disabled={saving}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              minWidth: "150px",
              justifyContent: "center",
            }}
          >
            {saving ? (
              <>
                <RefreshCw size={16} className="animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              <span>Save Assignment</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
