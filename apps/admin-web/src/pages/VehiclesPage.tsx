import React, { useState, useEffect, useMemo } from "react";
import { useSearchParams, useNavigate, useLocation } from "react-router-dom";
import { apiFetch } from "../api/api";
import {
  Plus,
  Search,
  Truck,
  Edit2,
  ArchiveX,
  Network,
  Route as RouteIcon,
  AlertTriangle,
  RefreshCw,
  Users,
  ArrowLeft,
  Unlink,
  Check,
  Info,
} from "lucide-react";
import {
  SearchableServiceSelect,
  type ServiceOption,
} from "../components/SearchableServiceSelect";
import { VehicleDetailsModal } from "../components/VehicleDetailsModal";

interface PersonnelBrief {
  id: string;
  name: string;
  employee_code?: string | null;
  role: string;
  phone?: string | null;
  email?: string | null;
}

interface Vehicle {
  id: string;
  vehicle_number: string;
  registration_number: string | null;
  vehicle_type: string;
  status: string;
  driver?: PersonnelBrief | null;
  conductor?: PersonnelBrief | null;
}

interface ServiceSummaryBrief {
  id?: string;
  service_code?: string;
  service_name?: string;
  route_id?: string;
}

interface AvailableVehicle {
  id: string;
  vehicle_number: string;
  registration_number: string | null;
  vehicle_type: string;
  status: string;
  is_assigned_to_current_service: boolean;
  assigned_services: (string | ServiceSummaryBrief)[];
}

function formatAssignedServices(
  services?: (string | ServiceSummaryBrief)[] | null
): string {
  if (!services || services.length === 0) return "";
  return services
    .map((s) => {
      if (typeof s === "string") return s.trim();
      if (s && typeof s === "object") {
        return s.service_name?.trim() || s.service_code?.trim() || "";
      }
      return "";
    })
    .filter(Boolean)
    .join(", ");
}

export default function VehiclesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = (location.state as any)?.returnTo || searchParams.get("returnTo");
  const returnLabel = (location.state as any)?.returnLabel || "Service";

  const [services, setServices] = useState<ServiceOption[]>([]);
  const [selectedServiceId, setSelectedServiceId] = useState<string>("");
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loadingServices, setLoadingServices] = useState(true);
  const [loadingVehicles, setLoadingVehicles] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [viewingVehicle, setViewingVehicle] = useState<Vehicle | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Workflow tabs: Assign Existing vs Register New
  const [modalTab, setModalTab] = useState<"assign" | "register">("assign");
  const [availableVehicles, setAvailableVehicles] = useState<AvailableVehicle[]>([]);
  const [loadingAvailable, setLoadingAvailable] = useState(false);
  const [selectedVehicleIdToAssign, setSelectedVehicleIdToAssign] = useState<string>("");
  const [assignSearchQuery, setAssignSearchQuery] = useState<string>("");

  const [formData, setFormData] = useState({
    vehicle_number: "",
    registration_number: "",
    vehicle_type: "BUS",
    status: "ACTIVE",
  });

  const loadServices = async () => {
    try {
      setLoadingServices(true);
      const data: ServiceOption[] = await apiFetch("/admin/services");
      setServices(data || []);

      // Check URL query param for initial service selection (e.g. ?serviceId=...)
      const paramServiceId = searchParams.get("serviceId");
      if (paramServiceId && data?.some((s) => s.id === paramServiceId)) {
        setSelectedServiceId(paramServiceId);
      }
    } catch (err) {
      console.error("Failed to load services", err);
    } finally {
      setLoadingServices(false);
    }
  };

  // Load all available services on mount
  useEffect(() => {
    loadServices();
  }, []);

  // Currently selected service object
  const selectedService = useMemo(() => {
    return services.find((s) => s.id === selectedServiceId) || null;
  }, [services, selectedServiceId]);

  const loadScopedVehicles = async (serviceId: string) => {
    try {
      setLoadingVehicles(true);
      const data = await apiFetch(`/admin/vehicles?service_id=${serviceId}`);
      setVehicles(data || []);
    } catch (err) {
      console.error("Failed to load vehicles for service", err);
      setVehicles([]);
    } finally {
      setLoadingVehicles(false);
    }
  };

  const loadAvailableVehicles = async (serviceId: string) => {
    try {
      setLoadingAvailable(true);
      const data: AvailableVehicle[] = await apiFetch(
        `/admin/services/${serviceId}/available-vehicles`
      );
      setAvailableVehicles(data || []);
    } catch (err) {
      console.error("Failed to load available vehicles", err);
      setAvailableVehicles([]);
    } finally {
      setLoadingAvailable(false);
    }
  };

  // Load vehicles scoped to the currently selected service
  useEffect(() => {
    if (selectedServiceId) {
      loadScopedVehicles(selectedServiceId);
    } else {
      setVehicles([]);
      setLoadingVehicles(false);
    }
  }, [selectedServiceId]);

  const handleSelectService = (serviceId: string) => {
    setSelectedServiceId(serviceId);
    setSearchQuery("");
    setFormError(null);
    if (serviceId) {
      setSearchParams({ serviceId });
    } else {
      setSearchParams({});
    }
  };

  const openCreateModal = () => {
    if (!selectedService) return;
    setEditingId(null);
    setFormError(null);
    setModalTab("assign");
    setSelectedVehicleIdToAssign("");
    setAssignSearchQuery("");
    setFormData({
      vehicle_number: "",
      registration_number: "",
      vehicle_type: "BUS",
      status: "ACTIVE",
    });
    setShowModal(true);
    if (selectedServiceId) {
      loadAvailableVehicles(selectedServiceId);
    }
  };

  const openEditModal = (vehicle: Vehicle) => {
    setEditingId(vehicle.id);
    setFormError(null);
    setFormData({
      vehicle_number: vehicle.vehicle_number,
      registration_number: vehicle.registration_number || "",
      vehicle_type: vehicle.vehicle_type,
      status: vehicle.status,
    });
    setShowModal(true);
  };

  const handleAssignExisting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedServiceId) {
      setFormError("A service must be selected before assigning a vehicle.");
      return;
    }
    if (!selectedVehicleIdToAssign) {
      setFormError("Please select a vehicle to assign.");
      return;
    }
    const chosen = availableVehicles.find((v) => v.id === selectedVehicleIdToAssign);
    if (chosen?.is_assigned_to_current_service) {
      setFormError("This vehicle is already assigned to this service.");
      return;
    }

    setSubmitting(true);
    setFormError(null);

    try {
      await apiFetch(`/admin/services/${selectedServiceId}/vehicles`, {
        method: "POST",
        body: JSON.stringify({ vehicle_id: selectedVehicleIdToAssign }),
      });
      setShowModal(false);
      await loadScopedVehicles(selectedServiceId);
    } catch (err: any) {
      setFormError(err.message || "Failed to assign vehicle to service.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedServiceId && !editingId) {
      setFormError("A service must be selected before adding a vehicle.");
      return;
    }

    if (!formData.vehicle_number.trim()) {
      setFormError("Vehicle Number is required.");
      return;
    }

    setSubmitting(true);
    setFormError(null);

    try {
      if (editingId) {
        await apiFetch(`/admin/vehicles/${editingId}`, {
          method: "PUT",
          body: JSON.stringify({
            vehicle_number: formData.vehicle_number.trim(),
            registration_number: formData.registration_number.trim() || null,
            vehicle_type: formData.vehicle_type,
            status: formData.status,
          }),
        });
      } else {
        // Send vehicle creation with selected service context
        await apiFetch("/admin/vehicles", {
          method: "POST",
          body: JSON.stringify({
            vehicle_number: formData.vehicle_number.trim(),
            registration_number: formData.registration_number.trim() || null,
            vehicle_type: formData.vehicle_type,
            status: formData.status,
            service_id: selectedServiceId,
          }),
        });
      }

      setShowModal(false);
      setFormData({
        vehicle_number: "",
        registration_number: "",
        vehicle_type: "BUS",
        status: "ACTIVE",
      });
      setFormError(null);
      if (selectedServiceId) {
        await loadScopedVehicles(selectedServiceId);
      }
    } catch (err: any) {
      setFormError(err.message || "Failed to save vehicle.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleUnassignVehicle = async (vehicle: Vehicle) => {
    if (!selectedServiceId) return;
    if (
      confirm(
        `Are you sure you want to unassign vehicle ${vehicle.vehicle_number} from ${selectedService?.service_name}? The vehicle will remain in the organization fleet.`
      )
    ) {
      try {
        await apiFetch(
          `/admin/services/${selectedServiceId}/vehicles/${vehicle.id}`,
          { method: "DELETE" }
        );
        await loadScopedVehicles(selectedServiceId);
      } catch (err: any) {
        alert(`Failed to unassign vehicle: ${err.message}`);
      }
    }
  };

  const handleDecommission = async (id: string) => {
    if (
      confirm(
        "Are you sure you want to decommission this vehicle? This action changes its status and cannot be undone via this UI."
      )
    ) {
      try {
        await apiFetch(`/admin/vehicles/${id}`, { method: "DELETE" });
        if (selectedServiceId) {
          loadScopedVehicles(selectedServiceId);
        }
      } catch (err: any) {
        alert(`Failed to decommission vehicle: ${err.message}`);
      }
    }
  };

  // Client-side vehicle filter by number or registration within the selected service
  const filteredVehicles = vehicles.filter(
    (v) =>
      v.vehicle_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (v.registration_number &&
        v.registration_number.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="page-container">
      {/* Return Context Navigation */}
      {returnTo && (
        <div style={{ marginBottom: "1rem" }}>
          <button
            type="button"
            onClick={() => navigate(returnTo, { state: location.state })}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: "pointer",
              padding: "4px 0",
              transition: "color 0.15s ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#f8fafc")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#94a3b8")}
          >
            <ArrowLeft size={16} /> Back to {returnLabel}
          </button>
        </div>
      )}

      {/* PAGE HEADER */}
      <div className="page-header">
        <div>
          <h1
            className="page-title"
            style={{ display: "flex", alignItems: "center", gap: "10px" }}
          >
            <Truck className="text-[var(--accent)]" size={28} />
            Fleet Management
          </h1>
          <p className="page-subtitle">
            Manage organization vehicles and fleet assignment scoped by service.
          </p>
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* SECTION 1: SERVICE SELECTION BAR / CONTEXT CARD */}
      {/* ───────────────────────────────────────────────────────────── */}
      <div
        className="data-table-card"
        style={{
          marginBottom: "20px",
          padding: "20px",
          border: selectedService
            ? "1px solid rgba(59, 130, 246, 0.3)"
            : "1px solid var(--border)",
          background: selectedService
            ? "linear-gradient(180deg, rgba(22, 31, 48, 0.95) 0%, rgba(15, 23, 42, 0.9) 100%)"
            : "var(--bg-card)",
          borderRadius: "var(--radius)",
          overflow: "visible",
          position: "relative",
          zIndex: 20,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "16px",
          }}
        >
          <div style={{ flex: 1, minWidth: "280px" }}>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "0.85rem",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "var(--text-main)",
                marginBottom: "8px",
              }}
            >
              <Network size={16} color="var(--accent)" />
              Select Service
            </label>
            <p
              style={{
                fontSize: "0.8rem",
                color: "var(--text-muted)",
                margin: "0 0 12px 0",
              }}
            >
              Choose a passenger service to view and manage its assigned fleet.
            </p>

            {/* ZERO-SERVICE STATE */}
            {!loadingServices && services.length === 0 ? (
              <div
                style={{
                  padding: "14px 16px",
                  background: "rgba(245, 158, 11, 0.12)",
                  border: "1px solid rgba(245, 158, 11, 0.3)",
                  color: "#fbbf24",
                  borderRadius: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  fontSize: "0.9rem",
                }}
              >
                <AlertTriangle size={20} className="shrink-0 text-amber-500" />
                <span>
                  No services available. Create a Service before managing fleet.
                </span>
              </div>
            ) : (
              <div style={{ maxWidth: "480px" }}>
                <SearchableServiceSelect
                  services={services}
                  value={selectedServiceId}
                  onChange={handleSelectService}
                  isLoading={loadingServices}
                  placeholder="-- Search by Service Code or Name --"
                />
              </div>
            )}
          </div>

          {/* ACTIVE SERVICE CONTEXT BADGE / SWITCHER */}
          {selectedService && (
            <div
              style={{
                background: "rgba(59, 130, 246, 0.08)",
                border: "1px solid rgba(59, 130, 246, 0.25)",
                borderRadius: "10px",
                padding: "14px 18px",
                minWidth: "260px",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
              }}
            >
              <div
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  color: "var(--accent)",
                }}
              >
                Active Service Context
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  marginTop: "2px",
                }}
              >
                <span
                  style={{
                    fontSize: "1.1rem",
                    fontWeight: 700,
                    color: "var(--text-main)",
                  }}
                >
                  {selectedService.service_name}
                </span>
                <span
                  style={{
                    fontWeight: 700,
                    fontFamily: "monospace",
                    color: "var(--accent)",
                    background: "rgba(59, 130, 246, 0.15)",
                    padding: "2px 6px",
                    borderRadius: "4px",
                    fontSize: "0.85rem",
                  }}
                >
                  {selectedService.service_code}
                </span>
              </div>

              {(selectedService.route_code || selectedService.route_name) && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "0.85rem",
                    color: "var(--text-muted)",
                    marginTop: "2px",
                  }}
                >
                  <RouteIcon size={14} style={{ color: "var(--accent)", flexShrink: 0 }} />
                  <span>
                    Route:{" "}
                    <strong style={{ color: "var(--text-main)" }}>
                      {selectedService.route_code || ""}
                    </strong>
                    {selectedService.route_code && selectedService.route_name ? " — " : ""}
                    {selectedService.route_name || ""}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* SECTION 2: SERVICE-SCOPED FLEET AREA */}
      {/* ───────────────────────────────────────────────────────────── */}
      {!selectedService ? (
        <div
          className="data-table-card"
          style={{
            position: "relative",
            zIndex: 1,
            padding: "48px 24px",
            textAlign: "center",
            color: "var(--text-muted)",
          }}
        >
          <Truck
            size={48}
            style={{
              margin: "0 auto 16px auto",
              opacity: 0.3,
              color: "var(--text-muted)",
            }}
          />
          <h3
            style={{
              fontSize: "1.1rem",
              fontWeight: 600,
              color: "var(--text-main)",
              margin: "0 0 8px 0",
            }}
          >
            {services.length === 0
              ? "No services available."
              : "Select a Service to View Fleet"}
          </h3>
          <p style={{ margin: 0, fontSize: "0.85rem" }}>
            {services.length === 0
              ? "Create a Service before managing fleet."
              : "Fleet is service-scoped. Choose a service above to inspect and assign vehicles."}
          </p>
        </div>
      ) : (
        <div
          className="data-table-card"
          style={{
            position: "relative",
            zIndex: 1,
          }}
        >
          {/* SERVICE FLEET HEADER */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "18px 20px",
              borderBottom: "1px solid var(--border)",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <div>
              <h2
                style={{
                  fontSize: "1.15rem",
                  fontWeight: 700,
                  color: "var(--text-main)",
                  margin: "0 0 4px 0",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                Fleet — {selectedService.service_name}
              </h2>
              <p
                style={{
                  margin: 0,
                  fontSize: "0.8rem",
                  color: "var(--text-muted)",
                }}
              >
                Vehicles assigned to this service
              </p>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <button
                className="btn-primary"
                onClick={openCreateModal}
                style={{ display: "flex", alignItems: "center", gap: "6px" }}
              >
                <Plus size={18} /> Add Vehicle
              </button>
            </div>
          </div>

          {/* TABLE TOOLBAR */}
          <div className="table-toolbar">
            <div className="search-box">
              <Search size={16} className="search-icon" />
              <input
                type="text"
                placeholder={`Search vehicles in ${selectedService.service_name}...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
              Showing <strong>{filteredVehicles.length}</strong> of{" "}
              <strong>{vehicles.length}</strong> assigned vehicles
            </div>
          </div>

          {/* TABLE */}
          {loadingVehicles ? (
            <div className="loading-state">
              <RefreshCw size={20} className="animate-spin text-accent" />
              <span>Loading fleet for {selectedService.service_name}...</span>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: "160px" }}>Vehicle #</th>
                  <th style={{ width: "160px" }}>Registration</th>
                  <th style={{ width: "120px" }}>Type</th>
                  <th style={{ width: "130px" }}>Status</th>
                  <th style={{ width: "170px" }}>Driver</th>
                  <th style={{ width: "170px" }}>Conductor</th>
                  <th className="text-right" style={{ width: "150px" }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredVehicles.map((vehicle) => (
                  <tr
                    key={vehicle.id}
                    style={{ cursor: "pointer" }}
                    onClick={() => setViewingVehicle(vehicle)}
                    className="hover:bg-slate-800/40 transition-colors"
                  >
                    <td>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <Truck size={15} className="text-muted" />
                        <span className="code-badge font-mono font-semibold text-[var(--accent)] hover:underline">
                          {vehicle.vehicle_number}
                        </span>
                      </div>
                    </td>
                    <td className="font-medium">
                      {vehicle.registration_number || "-"}
                    </td>
                    <td>{vehicle.vehicle_type}</td>
                    <td>
                      <span
                        className={`status-badge ${vehicle.status.toLowerCase()}`}
                      >
                        {vehicle.status}
                      </span>
                    </td>
                    <td>
                      {vehicle.driver ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          {vehicle.driver.employee_code && (
                            <span
                              style={{
                                fontWeight: 700,
                                fontFamily: "monospace",
                                fontSize: "0.75rem",
                                background: "rgba(59, 130, 246, 0.15)",
                                color: "var(--accent)",
                                padding: "2px 5px",
                                borderRadius: "4px",
                              }}
                            >
                              {vehicle.driver.employee_code}
                            </span>
                          )}
                          <span style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--text-main)" }}>
                            {vehicle.driver.name}
                          </span>
                        </div>
                      ) : (
                        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                          Unassigned
                        </span>
                      )}
                    </td>
                    <td>
                      {vehicle.conductor ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          {vehicle.conductor.employee_code && (
                            <span
                              style={{
                                fontWeight: 700,
                                fontFamily: "monospace",
                                fontSize: "0.75rem",
                                background: "rgba(59, 130, 246, 0.15)",
                                color: "var(--accent)",
                                padding: "2px 5px",
                                borderRadius: "4px",
                              }}
                            >
                              {vehicle.conductor.employee_code}
                            </span>
                          )}
                          <span style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--text-main)" }}>
                            {vehicle.conductor.name}
                          </span>
                        </div>
                      ) : (
                        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                          Unassigned
                        </span>
                      )}
                    </td>
                    <td className="text-right" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="action-btn text-accent"
                        title="Vehicle Details & Crew"
                        onClick={() => setViewingVehicle(vehicle)}
                      >
                        <Users size={16} />
                      </button>
                      <button
                        className="action-btn"
                        title="Edit Vehicle"
                        onClick={() => openEditModal(vehicle)}
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        className="action-btn text-amber-400 hover:text-amber-300"
                        title="Unassign from Service"
                        onClick={() => handleUnassignVehicle(vehicle)}
                      >
                        <Unlink size={16} />
                      </button>
                      {vehicle.status !== "DECOMMISSIONED" && (
                        <button
                          className="action-btn text-danger"
                          title="Decommission Vehicle"
                          onClick={() => handleDecommission(vehicle.id)}
                        >
                          <ArchiveX size={16} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {filteredVehicles.length === 0 && (
                  <tr>
                    <td
                      colSpan={7}
                      className="empty-state"
                      style={{ padding: "40px 16px" }}
                    >
                      {searchQuery
                        ? "No vehicles match your search query."
                        : `No vehicles assigned to ${selectedService.service_name}. Click "+ Add Vehicle" to assign one.`}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────── */}
      {/* ADD / EDIT VEHICLE MODAL */}
      {/* ───────────────────────────────────────────────────────────── */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "540px" }}>
            <div className="modal-header">
              <h2>
                {editingId
                  ? "Edit Vehicle"
                  : modalTab === "assign"
                  ? `Assign Existing Vehicle — ${selectedService?.service_name || "Fleet"}`
                  : `Register New Vehicle — ${selectedService?.service_name || "Fleet"}`}
              </h2>
              <button
                className="close-btn"
                onClick={() => setShowModal(false)}
                title="Close"
              >
                ×
              </button>
            </div>

            {/* WORKFLOW TABS (Only shown when creating/adding, not editing) */}
            {!editingId && (
              <div
                style={{
                  display: "flex",
                  borderBottom: "1px solid var(--border)",
                  padding: "0 20px",
                  background: "rgba(15, 23, 42, 0.4)",
                  gap: "12px",
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    setModalTab("assign");
                    setFormError(null);
                  }}
                  style={{
                    padding: "12px 14px",
                    fontSize: "0.85rem",
                    fontWeight: 600,
                    background: "transparent",
                    border: "none",
                    borderBottom:
                      modalTab === "assign"
                        ? "2px solid var(--accent)"
                        : "2px solid transparent",
                    color:
                      modalTab === "assign"
                        ? "var(--accent)"
                        : "var(--text-muted)",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <Truck size={15} />
                  Assign Existing Vehicle
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setModalTab("register");
                    setFormError(null);
                  }}
                  style={{
                    padding: "12px 14px",
                    fontSize: "0.85rem",
                    fontWeight: 600,
                    background: "transparent",
                    border: "none",
                    borderBottom:
                      modalTab === "register"
                        ? "2px solid var(--accent)"
                        : "2px solid transparent",
                    color:
                      modalTab === "register"
                        ? "var(--accent)"
                        : "var(--text-muted)",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <Plus size={15} />
                  Register New Vehicle
                </button>
              </div>
            )}

            {/* TAB 1: ASSIGN EXISTING VEHICLE */}
            {!editingId && modalTab === "assign" ? (
              <form onSubmit={handleAssignExisting} className="modal-form">
                {/* SERVICE CONTEXT BANNER */}
                {selectedService && (
                  <div
                    style={{
                      padding: "10px 14px",
                      background: "rgba(59, 130, 246, 0.08)",
                      border: "1px solid rgba(59, 130, 246, 0.2)",
                      borderRadius: "6px",
                      fontSize: "0.85rem",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <Network size={16} color="var(--accent)" />
                    <span style={{ color: "var(--text-muted)" }}>Target Service:</span>
                    <strong style={{ color: "var(--text-main)" }}>
                      {selectedService.service_name} ({selectedService.service_code})
                    </strong>
                  </div>
                )}

                {/* FORM ERROR */}
                {formError && (
                  <div
                    style={{
                      padding: "10px 14px",
                      background: "rgba(239, 68, 68, 0.12)",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      color: "#f87171",
                      borderRadius: "6px",
                      fontSize: "0.85rem",
                    }}
                  >
                    {formError}
                  </div>
                )}

                {/* VEHICLE SEARCH & SELECTOR */}
                <div className="input-group">
                  <label style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Select Organization Vehicle</span>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {availableVehicles.length} total vehicles in org
                    </span>
                  </label>

                  <div className="search-box" style={{ marginBottom: "10px" }}>
                    <Search size={15} className="search-icon" />
                    <input
                      type="text"
                      placeholder="Search by vehicle #, registration, or type..."
                      value={assignSearchQuery}
                      onChange={(e) => {
                        setAssignSearchQuery(e.target.value);
                        if (formError) setFormError(null);
                      }}
                    />
                  </div>

                  {loadingAvailable ? (
                    <div className="loading-state" style={{ padding: "20px" }}>
                      <RefreshCw size={18} className="animate-spin text-accent" />
                      <span>Loading organization vehicles...</span>
                    </div>
                  ) : (
                    <div
                      style={{
                        maxHeight: "220px",
                        overflowY: "auto",
                        border: "1px solid var(--border)",
                        borderRadius: "8px",
                        background: "rgba(15, 23, 42, 0.6)",
                        display: "flex",
                        flexDirection: "column",
                      }}
                    >
                      {availableVehicles
                        .filter((v) => {
                          if (!assignSearchQuery.trim()) return true;
                          const q = assignSearchQuery.toLowerCase().trim();
                          const svcMatches = formatAssignedServices(v.assigned_services)
                            .toLowerCase()
                            .includes(q);
                          return (
                            v.vehicle_number.toLowerCase().includes(q) ||
                            (v.registration_number &&
                              v.registration_number.toLowerCase().includes(q)) ||
                            v.vehicle_type.toLowerCase().includes(q) ||
                            svcMatches
                          );
                        })
                        .map((v) => {
                          const isSelected = selectedVehicleIdToAssign === v.id;
                          const assignedLabel = formatAssignedServices(v.assigned_services);
                          return (
                            <div
                              key={v.id}
                              onClick={() => {
                                setSelectedVehicleIdToAssign(v.id);
                                if (formError) setFormError(null);
                              }}
                              style={{
                                padding: "10px 14px",
                                borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                gap: "10px",
                                background: isSelected
                                  ? "rgba(59, 130, 246, 0.16)"
                                  : "transparent",
                                borderLeft: isSelected
                                  ? "3px solid var(--accent)"
                                  : "3px solid transparent",
                                transition: "all 0.12s ease",
                              }}
                              className="hover:bg-slate-800/50"
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "10px",
                                }}
                              >
                                <span
                                  className="font-mono font-bold"
                                  style={{
                                    color: isSelected
                                      ? "var(--accent)"
                                      : "var(--text-main)",
                                    fontSize: "0.95rem",
                                  }}
                                >
                                  {v.vehicle_number}
                                </span>
                                <span
                                  style={{
                                    color: "var(--text-muted)",
                                    fontSize: "0.85rem",
                                  }}
                                >
                                  {v.registration_number || "—"}
                                </span>
                                <span
                                  style={{
                                    fontSize: "0.72rem",
                                    fontWeight: 600,
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                    background: "rgba(255, 255, 255, 0.06)",
                                    color: "var(--text-muted)",
                                    textTransform: "uppercase",
                                  }}
                                >
                                  {v.vehicle_type}
                                </span>
                              </div>

                              <div style={{ flexShrink: 0 }}>
                                {v.is_assigned_to_current_service ? (
                                  <span
                                    style={{
                                      fontSize: "0.75rem",
                                      fontWeight: 600,
                                      background: "rgba(245, 158, 11, 0.15)",
                                      color: "#fbbf24",
                                      padding: "2px 8px",
                                      borderRadius: "4px",
                                      border: "1px solid rgba(245, 158, 11, 0.3)",
                                    }}
                                  >
                                    Already Assigned
                                  </span>
                                ) : assignedLabel ? (
                                  <span
                                    style={{
                                      fontSize: "0.75rem",
                                      fontWeight: 500,
                                      background: "rgba(59, 130, 246, 0.12)",
                                      color: "var(--accent)",
                                      padding: "2px 8px",
                                      borderRadius: "4px",
                                      border: "1px solid rgba(59, 130, 246, 0.25)",
                                    }}
                                  >
                                    Currently assigned to: {assignedLabel}
                                  </span>
                                ) : (
                                  <span
                                    style={{
                                      fontSize: "0.75rem",
                                      fontWeight: 500,
                                      background: "rgba(16, 185, 129, 0.12)",
                                      color: "#34d399",
                                      padding: "2px 8px",
                                      borderRadius: "4px",
                                    }}
                                  >
                                    Available
                                  </span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      {availableVehicles.length === 0 && (
                        <div
                          style={{
                            padding: "24px",
                            textAlign: "center",
                            color: "var(--text-muted)",
                            fontSize: "0.85rem",
                          }}
                        >
                          No vehicles found in organization. Use the "Register New Vehicle" tab to create one.
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* SELECTED VEHICLE CONTEXT CARD */}
                {(() => {
                  const selected = availableVehicles.find(
                    (v) => v.id === selectedVehicleIdToAssign
                  );
                  if (!selected) return null;

                  return (
                    <div
                      style={{
                        padding: "14px",
                        background: "rgba(30, 41, 59, 0.6)",
                        border: "1px solid var(--border)",
                        borderRadius: "8px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "8px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <Truck size={16} color="var(--accent)" />
                          <span
                            style={{
                              fontFamily: "monospace",
                              fontWeight: 700,
                              fontSize: "1rem",
                              color: "var(--text-main)",
                            }}
                          >
                            {selected.vehicle_number}
                          </span>
                          <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                            • {selected.registration_number || "No Registration"}
                          </span>
                        </div>
                        <span className={`status-badge ${selected.status.toLowerCase()}`}>
                          {selected.status}
                        </span>
                      </div>

                      {selected.is_assigned_to_current_service ? (
                        <div
                          style={{
                            fontSize: "0.8rem",
                            color: "#fbbf24",
                            background: "rgba(245, 158, 11, 0.1)",
                            border: "1px solid rgba(245, 158, 11, 0.25)",
                            padding: "8px 12px",
                            borderRadius: "6px",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <AlertTriangle size={15} />
                          <span>
                            <strong>Already Assigned:</strong> This vehicle is already part of{" "}
                            {selectedService?.service_name}. Duplicate assignment is not allowed.
                          </span>
                        </div>
                      ) : formatAssignedServices(selected.assigned_services) ? (
                        <div
                          style={{
                            fontSize: "0.8rem",
                            color: "var(--accent)",
                            background: "rgba(59, 130, 246, 0.08)",
                            border: "1px solid rgba(59, 130, 246, 0.2)",
                            padding: "8px 12px",
                            borderRadius: "6px",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Info size={15} />
                          <span>
                            Currently assigned to:{" "}
                            <strong>{formatAssignedServices(selected.assigned_services)}</strong>. Assigning
                            will add it to <strong>{selectedService?.service_name}</strong> while
                            preserving existing service memberships.
                          </span>
                        </div>
                      ) : (
                        <div
                          style={{
                            fontSize: "0.8rem",
                            color: "#34d399",
                            background: "rgba(16, 185, 129, 0.08)",
                            border: "1px solid rgba(16, 185, 129, 0.2)",
                            padding: "8px 12px",
                            borderRadius: "6px",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Check size={15} />
                          <span>
                            Ready to assign to <strong>{selectedService?.service_name}</strong>.
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })()}

                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setShowModal(false)}
                    disabled={submitting}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={
                      submitting ||
                      !selectedVehicleIdToAssign ||
                      availableVehicles.find((v) => v.id === selectedVehicleIdToAssign)
                        ?.is_assigned_to_current_service
                    }
                  >
                    {submitting
                      ? "Assigning..."
                      : availableVehicles.find((v) => v.id === selectedVehicleIdToAssign)
                          ?.is_assigned_to_current_service
                      ? "Already Assigned"
                      : "Assign Vehicle to Service"}
                  </button>
                </div>
              </form>
            ) : (
              /* TAB 2: REGISTER NEW VEHICLE (OR EDIT VEHICLE) */
              <form onSubmit={handleSubmit} className="modal-form">
                {/* SERVICE CONTEXT BANNER IN MODAL */}
                {selectedService && !editingId && (
                  <div
                    style={{
                      padding: "10px 14px",
                      background: "rgba(59, 130, 246, 0.08)",
                      border: "1px solid rgba(59, 130, 246, 0.2)",
                      borderRadius: "6px",
                      fontSize: "0.85rem",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <Network size={16} color="var(--accent)" />
                    <span style={{ color: "var(--text-muted)" }}>Target Service:</span>
                    <strong style={{ color: "var(--text-main)" }}>
                      {selectedService.service_name} ({selectedService.service_code})
                    </strong>
                  </div>
                )}

                {/* FORM ERROR */}
                {formError && (
                  <div
                    style={{
                      padding: "10px 14px",
                      background: "rgba(239, 68, 68, 0.12)",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      color: "#f87171",
                      borderRadius: "6px",
                      fontSize: "0.85rem",
                    }}
                  >
                    {formError}
                  </div>
                )}

                <div className="form-row">
                  <div className="input-group" style={{ flex: 1 }}>
                    <label>
                      Vehicle Number <span style={{ color: "var(--danger)" }}>*</span>
                    </label>
                    <input
                      required
                      value={formData.vehicle_number}
                      onChange={(e) => {
                        setFormData({ ...formData, vehicle_number: e.target.value });
                        if (formError) setFormError(null);
                      }}
                      placeholder="e.g. V-101"
                      style={{ fontFamily: "monospace" }}
                    />
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Internal identifier for this vehicle.
                    </span>
                  </div>

                  <div className="input-group" style={{ flex: 1 }}>
                    <label>Registration Number</label>
                    <input
                      value={formData.registration_number}
                      onChange={(e) => {
                        setFormData({
                          ...formData,
                          registration_number: e.target.value,
                        });
                        if (formError) setFormError(null);
                      }}
                      placeholder="e.g. WB-01-AB-1234"
                    />
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Official RTO license plate number.
                    </span>
                  </div>
                </div>

                <div className="form-row">
                  <div className="input-group" style={{ flex: 1 }}>
                    <label>Vehicle Type</label>
                    <select
                      required
                      value={formData.vehicle_type}
                      onChange={(e) => {
                        setFormData({ ...formData, vehicle_type: e.target.value });
                        if (formError) setFormError(null);
                      }}
                    >
                      <option value="BUS">Bus</option>
                      <option value="MINIBUS">Minibus</option>
                      <option value="VAN">Van</option>
                      <option value="TRAM">Tram</option>
                    </select>
                  </div>

                  <div className="input-group" style={{ flex: 1 }}>
                    <label>Status</label>
                    <select
                      required
                      value={formData.status}
                      onChange={(e) => {
                        setFormData({ ...formData, status: e.target.value });
                        if (formError) setFormError(null);
                      }}
                    >
                      <option value="ACTIVE">Active</option>
                      <option value="MAINTENANCE">Maintenance</option>
                      <option value="INACTIVE">Inactive</option>
                      <option value="DECOMMISSIONED">Decommissioned</option>
                    </select>
                  </div>
                </div>

                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setShowModal(false)}
                    disabled={submitting}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={submitting || !formData.vehicle_number.trim()}
                  >
                    {submitting
                      ? editingId
                        ? "Saving..."
                        : "Registering..."
                      : editingId
                      ? "Save Changes"
                      : "Create & Assign Vehicle"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────── */}
      {/* VEHICLE DETAILS & CREW ASSIGNMENT MODAL */}
      {/* ───────────────────────────────────────────────────────────── */}
      {viewingVehicle && selectedService && (
        <VehicleDetailsModal
          isOpen={!!viewingVehicle}
          onClose={() => setViewingVehicle(null)}
          vehicle={viewingVehicle}
          service={selectedService}
          onSuccess={() => {
            if (selectedServiceId) {
              loadScopedVehicles(selectedServiceId);
            }
          }}
        />
      )}
    </div>
  );
}
