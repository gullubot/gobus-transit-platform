import { useState, useEffect, useMemo } from "react";
import { apiFetch } from "../api/api";
import {
  Plus,
  Search,
  Route as RouteIcon,
  Edit2,
  Trash2,
  AlertTriangle,
  Layers,
  Banknote,
  Info,
  CheckCircle2,
  X,
  Eye,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { SearchableRouteSelect, type RouteOption } from "../components/SearchableRouteSelect";

interface Service {
  id: string;
  service_code: string;
  service_name: string;
  route_id: string;
  status: "ACTIVE" | "INACTIVE";
  fare_configuration_id?: string | null;
  created_at?: string;
  updated_at?: string;
  route_code?: string;
  route_name?: string;
  fare_configuration_name?: string;
  fare_is_active?: boolean;
  fare_slabs_count?: number;
  fare_currency?: string;
}

interface FareConfig {
  id: string;
  name: string;
  currency?: string;
  is_active?: boolean;
  slabs?: any[];
}

interface FareSlabRow {
  min_distance_km: string;
  max_distance_km: string;
  fare_amount: string;
}

const DEFAULT_INITIAL_SLABS: FareSlabRow[] = [
  { min_distance_km: "0", max_distance_km: "", fare_amount: "" },
];

export default function ServicesPage() {
  const [services, setServices] = useState<Service[]>([]);
  const [routes, setRoutes] = useState<RouteOption[]>([]);
  const [fareConfigs, setFareConfigs] = useState<FareConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    service_code: "",
    service_name: "",
    route_id: "",
    status: "ACTIVE" as "ACTIVE" | "INACTIVE",
    fare_configuration_id: "",
  });

  const [fareSlabs, setFareSlabs] = useState<FareSlabRow[]>(DEFAULT_INITIAL_SLABS);

  const navigate = useNavigate();

  const loadData = async () => {
    try {
      const [svcData, rData, fareData] = await Promise.all([
        apiFetch("/admin/services"),
        apiFetch("/admin/routes"),
        apiFetch("/admin/fares").catch(() => []),
      ]);
      setServices(svcData || []);
      setRoutes(rData || []);
      setFareConfigs(fareData || []);
    } catch (err) {
      console.error("Failed to load services data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // ─────────────────────────────────────────────────────────────
  // FARE SLAB VALIDATION
  // ─────────────────────────────────────────────────────────────
  const validateFareSlabs = (slabs: FareSlabRow[]): string | null => {
    if (!slabs || slabs.length === 0) {
      return "Initial Fare Configuration requires at least one distance slab.";
    }

    // Check individual inputs
    for (let i = 0; i < slabs.length; i++) {
      const slab = slabs[i];
      if (slab.min_distance_km === "" || isNaN(Number(slab.min_distance_km))) {
        return `Slab ${i + 1}: Minimum distance must be a valid number.`;
      }
      const min = parseFloat(slab.min_distance_km);
      if (min < 0) {
        return `Slab ${i + 1}: Minimum distance cannot be negative.`;
      }

      if (slab.fare_amount === "" || isNaN(Number(slab.fare_amount))) {
        return `Slab ${i + 1}: Ticket price must be a valid number.`;
      }
      const price = parseFloat(slab.fare_amount);
      if (price < 0) {
        return `Slab ${i + 1}: Ticket price cannot be negative.`;
      }

      const hasMax = slab.max_distance_km.trim() !== "";
      if (hasMax) {
        if (isNaN(Number(slab.max_distance_km))) {
          return `Slab ${i + 1}: Maximum distance must be a valid number.`;
        }
        const max = parseFloat(slab.max_distance_km);
        if (max <= min) {
          return `Slab ${i + 1}: Maximum distance (${max} km) must be strictly greater than minimum distance (${min} km).`;
        }
      } else {
        // Open-ended slab
        if (i !== slabs.length - 1) {
          return `Slab ${i + 1}: Only the final slab can be open-ended (unbounded maximum distance).`;
        }
      }
    }

    // First slab must start at 0.0
    if (parseFloat(slabs[0].min_distance_km) !== 0) {
      return "The first fare slab must start at 0.0 km.";
    }

    // Continuity and overlap check
    for (let i = 0; i < slabs.length - 1; i++) {
      const curr = slabs[i];
      const next = slabs[i + 1];

      if (curr.max_distance_km.trim() === "") {
        return `Slab ${i + 1} is open-ended. No further slabs can follow an open-ended slab.`;
      }

      const currMax = parseFloat(curr.max_distance_km);
      const nextMin = parseFloat(next.min_distance_km);

      if (currMax !== nextMin) {
        return `Slab gap or overlap detected between Slab ${i + 1} and Slab ${i + 2}: Slab ${i + 1} ends at ${currMax} km, but Slab ${i + 2} starts at ${nextMin} km. Slabs must connect seamlessly.`;
      }
    }

    return null;
  };

  const currentSlabError = useMemo(() => {
    if (editingId) return null; // Editing existing service does not re-validate new slabs
    return validateFareSlabs(fareSlabs);
  }, [fareSlabs, editingId]);

  // ─────────────────────────────────────────────────────────────
  // SLAB ROW MANIPULATION
  // ─────────────────────────────────────────────────────────────
  const handleAddSlab = () => {
    setFareSlabs((prev) => {
      if (prev.length === 0) {
        return [{ min_distance_km: "0", max_distance_km: "", fare_amount: "" }];
      }
      const last = prev[prev.length - 1];
      const lastMax = parseFloat(last.max_distance_km);
      const nextMin = !isNaN(lastMax) && lastMax > 0 ? lastMax.toString() : "";

      return [
        ...prev,
        {
          min_distance_km: nextMin,
          max_distance_km: "",
          fare_amount: "",
        },
      ];
    });
  };

  const handleRemoveSlab = (index: number) => {
    if (fareSlabs.length <= 1) return;
    setFareSlabs((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleSlabChange = (index: number, field: keyof FareSlabRow, value: string) => {
    setFareSlabs((prev) =>
      prev.map((slab, idx) => {
        if (idx === index) {
          return { ...slab, [field]: value };
        }
        return slab;
      })
    );
  };

  // ─────────────────────────────────────────────────────────────
  // MODAL ACTIONS
  // ─────────────────────────────────────────────────────────────
  const openCreateModal = () => {
    setEditingId(null);
    setFormData({
      service_code: "",
      service_name: "",
      route_id: routes.length > 0 ? routes[0].id : "",
      status: "ACTIVE",
      fare_configuration_id: "",
    });
    setFareSlabs(DEFAULT_INITIAL_SLABS);
    setFormError(null);
    setShowModal(true);
  };

  const handleEdit = (svc: Service) => {
    setFormData({
      service_code: svc.service_code,
      service_name: svc.service_name,
      route_id: svc.route_id,
      status: (svc.status as "ACTIVE" | "INACTIVE") || "ACTIVE",
      fare_configuration_id: svc.fare_configuration_id || "",
    });
    setEditingId(svc.id);
    setFormError(null);
    setShowModal(true);
  };

  const handleDelete = async (id: string) => {
    const target = services.find((s) => s.id === id);
    const identifier = target ? `${target.service_code} (${target.service_name})` : "this service";
    if (!confirm(`Are you sure you want to delete ${identifier}?\n\nThis action cannot be undone.`)) {
      return;
    }
    try {
      await apiFetch(`/admin/services/${id}`, { method: "DELETE" });
      await loadData();
    } catch (err: any) {
      alert(`Failed to delete service: ${err.message || "It might be referenced by schedules or trips."}`);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    // Basic Validation
    const trimmedCode = formData.service_code.trim();
    const trimmedName = formData.service_name.trim();

    if (!trimmedCode) {
      setFormError("Service Code is required.");
      return;
    }
    if (trimmedCode.length > 50) {
      setFormError("Service Code must be 50 characters or fewer.");
      return;
    }
    if (!trimmedName) {
      setFormError("Service Name is required.");
      return;
    }
    if (trimmedName.length > 100) {
      setFormError("Service Name must be 100 characters or fewer.");
      return;
    }
    if (!formData.route_id) {
      setFormError("Please select an existing route for this service.");
      return;
    }

    if (!editingId) {
      // Validate Slabs in create mode
      const slabError = validateFareSlabs(fareSlabs);
      if (slabError) {
        setFormError(slabError);
        return;
      }
    }

    setSubmitting(true);
    try {
      if (editingId) {
        // Edit Service
        const payload: any = {
          service_code: formData.service_code.trim(),
          service_name: formData.service_name.trim(),
          route_id: formData.route_id,
          status: formData.status,
          fare_configuration_id: formData.fare_configuration_id || null,
        };

        await apiFetch(`/admin/services/${editingId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        // Create Service with atomic Initial Fare Configuration
        const parsedSlabs = fareSlabs.map((s) => ({
          min_distance_km: parseFloat(s.min_distance_km),
          max_distance_km: s.max_distance_km.trim() === "" ? null : parseFloat(s.max_distance_km),
          fare_amount: parseFloat(s.fare_amount),
        }));

        const payload = {
          service_code: formData.service_code.trim(),
          service_name: formData.service_name.trim(),
          route_id: formData.route_id,
          status: formData.status,
          initial_fare_slabs: parsedSlabs,
        };

        await apiFetch("/admin/services", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      setShowModal(false);
      setEditingId(null);
      await loadData();
    } catch (err: any) {
      setFormError(err.message || `Failed to ${editingId ? "update" : "create"} service.`);
    } finally {
      setSubmitting(false);
    }
  };

  // ─────────────────────────────────────────────────────────────
  // FILTERING & SEARCH
  // ─────────────────────────────────────────────────────────────
  const filteredServices = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return services;

    return services.filter((s) => {
      const codeMatch = s.service_code.toLowerCase().includes(q);
      const nameMatch = s.service_name.toLowerCase().includes(q);
      const routeCodeMatch = (s.route_code || "").toLowerCase().includes(q);
      const routeNameMatch = (s.route_name || "").toLowerCase().includes(q);
      const fareMatch = (s.fare_configuration_name || "").toLowerCase().includes(q);

      // Also search in routes list fallback
      const fallbackRoute = routes.find((r) => r.id === s.route_id);
      const fallbackCodeMatch = fallbackRoute ? fallbackRoute.route_code.toLowerCase().includes(q) : false;
      const fallbackNameMatch = fallbackRoute ? fallbackRoute.route_name.toLowerCase().includes(q) : false;

      return codeMatch || nameMatch || routeCodeMatch || routeNameMatch || fareMatch || fallbackCodeMatch || fallbackNameMatch;
    });
  }, [services, routes, searchQuery]);

  const getRouteDisplay = (service: Service) => {
    const route = routes.find((r) => r.id === service.route_id);
    const code = service.route_code || (route ? route.route_code : "Unknown");
    const name = service.route_name || (route ? route.route_name : null);
    const dist = route?.distance_km;

    return { code, name, dist };
  };

  const selectedRouteObj = useMemo(() => {
    return routes.find((r) => r.id === formData.route_id) || null;
  }, [routes, formData.route_id]);

  return (
    <div className="page-container">
      {/* PAGE HEADER */}
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Layers className="text-[var(--accent)]" size={28} />
            Services Management
          </h1>
          <p className="page-subtitle">
            Manage passenger-facing transport services and their associated routes and fare structures.
          </p>
        </div>
        <button className="btn-primary" onClick={openCreateModal}>
          <Plus size={18} /> Add New Service
        </button>
      </div>

      {/* DATA TABLE CARD */}
      <div className="data-table-card">
        <div className="table-toolbar">
          <div className="search-box" style={{ maxWidth: "420px" }}>
            <Search size={16} className="search-icon" />
            <input
              type="text"
              placeholder="Search by code, name, route, or fare..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
            Showing <strong>{filteredServices.length}</strong> of <strong>{services.length}</strong> services
          </div>
        </div>

        {loading ? (
          <div className="loading-state">Loading services and routes...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "160px" }}>Service Code</th>
                <th style={{ width: "200px" }}>Service Name</th>
                <th>Associated Route</th>
                <th style={{ width: "180px" }}>Fare Status</th>
                <th className="text-right" style={{ width: "150px" }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredServices.map((svc) => {
                const { code, name, dist } = getRouteDisplay(svc);
                const hasFare = Boolean(svc.fare_configuration_id || svc.fare_configuration_name);

                return (
                  <tr
                    key={svc.id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => navigate(`/services/${svc.id}`)}
                  >
                    {/* CODE */}
                    <td>
                      <span className="code-badge font-mono font-semibold text-[var(--accent)]">
                        {svc.service_code}
                      </span>
                    </td>

                    {/* NAME */}
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span className="font-semibold text-white">{svc.service_name}</span>
                        {svc.status === "INACTIVE" && (
                          <span
                            style={{
                              fontSize: "0.7rem",
                              background: "rgba(239, 68, 68, 0.15)",
                              color: "#ef4444",
                              padding: "2px 6px",
                              borderRadius: "4px",
                              fontWeight: 700,
                            }}
                          >
                            INACTIVE
                          </span>
                        )}
                      </div>
                    </td>

                    {/* ASSOCIATED ROUTE */}
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <RouteIcon size={15} style={{ color: "var(--accent)", flexShrink: 0 }} />
                        <span
                          style={{
                            fontWeight: 700,
                            fontFamily: "monospace",
                            color: "var(--text-main)",
                            fontSize: "0.85rem",
                          }}
                        >
                          {code}
                        </span>
                        {name && (
                          <>
                            <span style={{ color: "var(--text-muted)", margin: "0 2px" }}>|</span>
                            <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>{name}</span>
                          </>
                        )}
                        {dist != null && (
                          <span
                            style={{
                              fontSize: "0.75rem",
                              color: "var(--text-muted)",
                              background: "rgba(255, 255, 255, 0.05)",
                              padding: "1px 6px",
                              borderRadius: "4px",
                              marginLeft: "auto",
                            }}
                          >
                            {Number(dist).toFixed(1)} km
                          </span>
                        )}
                      </div>
                    </td>

                    {/* FARE STATUS */}
                    <td>
                      {hasFare ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "5px",
                              background: "rgba(16, 185, 129, 0.15)",
                              color: "#10b981",
                              padding: "2px 8px",
                              borderRadius: "4px",
                              fontSize: "0.75rem",
                              fontWeight: 600,
                              width: "fit-content",
                            }}
                          >
                            <CheckCircle2 size={12} />
                            Configured
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", paddingLeft: "2px" }}>
                            {svc.fare_slabs_count != null
                              ? `${svc.fare_slabs_count} slabs`
                              : svc.fare_configuration_name || "Active"}
                          </span>
                        </div>
                      ) : (
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            background: "rgba(245, 158, 11, 0.12)",
                            color: "#f59e0b",
                            padding: "2px 8px",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                          }}
                        >
                          Unconfigured
                        </span>
                      )}
                    </td>

                    {/* ACTIONS */}
                    <td className="text-right">
                      <button
                        className="action-btn text-[var(--accent)]"
                        title="View Details"
                        aria-label="View Service Details"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/services/${svc.id}`);
                        }}
                      >
                        <Eye size={16} />
                      </button>
                      <button
                        className="action-btn"
                        title="Edit Service"
                        aria-label="Edit Service"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEdit(svc);
                        }}
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        className="action-btn text-danger"
                        title="Delete Service"
                        aria-label="Delete Service"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(svc.id);
                        }}
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                );
              })}
              {filteredServices.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty-state">
                    {searchQuery ? "No services match your search query." : "No services found in your organization."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* CREATE / EDIT SERVICE MODAL */}
      {/* ───────────────────────────────────────────────────────────── */}
      {showModal && (
        <div className="modal-overlay" style={{ padding: "16px" }}>
          <div
            className="modal-content"
            style={{
              maxWidth: "860px",
              width: "100%",
              maxHeight: "calc(100vh - 32px)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              borderRadius: "var(--radius)",
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
            }}
          >
            {/* FIXED HEADER */}
            <div
              className="modal-header"
              style={{
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "18px 24px",
                borderBottom: "1px solid var(--border)",
                background: "var(--bg-card)",
              }}
            >
              <h2
                style={{
                  fontSize: "1.2rem",
                  fontWeight: 700,
                  color: "var(--text-main)",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  margin: 0,
                }}
              >
                <Layers size={22} color="var(--accent)" />
                {editingId ? "EDIT SERVICE" : "CREATE NEW SERVICE"}
              </h2>
              <button
                type="button"
                className="close-btn"
                onClick={() => setShowModal(false)}
                title="Close"
              >
                <X size={20} />
              </button>
            </div>

            {/* FORM WRAPPER: BODY (SCROLLABLE) + FOOTER (FIXED) */}
            <form
              onSubmit={handleSubmit}
              style={{
                flex: 1,
                minHeight: 0,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                margin: 0,
              }}
            >
              {/* SCROLLABLE MODAL BODY */}
              <div
                style={{
                  flex: 1,
                  overflowY: "auto",
                  padding: "24px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "24px",
                }}
              >
                {/* PREREQUISITE WARNING: NO ROUTES */}
                {routes.length === 0 && (
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
                    <span>No routes available. Create a Route before adding a Service.</span>
                  </div>
                )}

                {/* FORM ERROR BANNER */}
                {formError && (
                  <div
                    style={{
                      padding: "12px 16px",
                      background: "rgba(239, 68, 68, 0.12)",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      color: "#f87171",
                      borderRadius: "8px",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      fontSize: "0.85rem",
                    }}
                  >
                    <AlertTriangle size={18} className="shrink-0 text-red-500" />
                    <span>{formError}</span>
                  </div>
                )}

                {/* ───────────────────────────────────────────────────────────── */}
                {/* SECTION A — SERVICE DETAILS */}
                {/* ───────────────────────────────────────────────────────────── */}
                <div
                  style={{
                    background: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid var(--border)",
                    borderRadius: "10px",
                    padding: "20px",
                  }}
                >
                  <div style={{ marginBottom: "16px" }}>
                    <h3
                      style={{
                        margin: "0 0 4px 0",
                        fontSize: "0.95rem",
                        fontWeight: 700,
                        color: "var(--text-main)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      Section A — Service Details
                    </h3>
                    <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      Define both internal identifier and passenger-facing service name.
                    </p>
                  </div>

                  <div className="form-row" style={{ marginBottom: "16px", gap: "16px" }}>
                    <div className="input-group" style={{ flex: 1 }}>
                      <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                        Service Code <span style={{ color: "var(--danger)" }}>*</span>
                      </label>
                      <input
                        required
                        value={formData.service_code}
                        onChange={(e) => setFormData({ ...formData, service_code: e.target.value })}
                        placeholder="e.g. SVC-SD5"
                        style={{ fontFamily: "monospace" }}
                      />
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        Internal unique identifier for this service.
                      </span>
                    </div>

                    <div className="input-group" style={{ flex: 1 }}>
                      <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                        Service Name <span style={{ color: "var(--danger)" }}>*</span>
                      </label>
                      <input
                        required
                        value={formData.service_name}
                        onChange={(e) => setFormData({ ...formData, service_name: e.target.value })}
                        placeholder="e.g. SD5"
                      />
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        Passenger-facing service name/number.
                      </span>
                    </div>
                  </div>

                  <div className="form-row" style={{ marginBottom: 0, gap: "16px" }}>
                    <div className="input-group" style={{ maxWidth: "240px" }}>
                      <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>Status</label>
                      <select
                        value={formData.status}
                        onChange={(e) =>
                          setFormData({ ...formData, status: e.target.value as "ACTIVE" | "INACTIVE" })
                        }
                      >
                        <option value="ACTIVE">ACTIVE</option>
                        <option value="INACTIVE">INACTIVE</option>
                      </select>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        Controls whether service is visible to passengers.
                      </span>
                    </div>

                    {/* Edit mode: existing fare configuration selector */}
                    {editingId && (
                      <div className="input-group" style={{ flex: 1 }}>
                        <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>Fare Configuration</label>
                        <select
                          value={formData.fare_configuration_id}
                          onChange={(e) =>
                            setFormData({ ...formData, fare_configuration_id: e.target.value })
                          }
                        >
                          <option value="">None (Unconfigured)</option>
                          {fareConfigs.map((f) => (
                            <option key={f.id} value={f.id}>
                              {f.name} {f.currency ? `(${f.currency})` : ""}
                            </option>
                          ))}
                        </select>
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          Linked distance-based fare chart for this service.
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* ───────────────────────────────────────────────────────────── */}
                {/* SECTION B — ROUTE SELECTION */}
                {/* ───────────────────────────────────────────────────────────── */}
                <div
                  style={{
                    background: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid var(--border)",
                    borderRadius: "10px",
                    padding: "20px",
                  }}
                >
                  <div style={{ marginBottom: "16px" }}>
                    <h3
                      style={{
                        margin: "0 0 4px 0",
                        fontSize: "0.95rem",
                        fontWeight: 700,
                        color: "var(--text-main)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      Section B — Route Selection
                    </h3>
                    <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      Select the single existing route this service operates on.
                    </p>
                  </div>

                  <div className="input-group">
                    <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                      Associated Route <span style={{ color: "var(--danger)" }}>*</span>
                    </label>
                    <SearchableRouteSelect
                      routes={routes}
                      value={formData.route_id}
                      onChange={(routeId) => setFormData({ ...formData, route_id: routeId })}
                      disabled={routes.length === 0}
                      isLoading={loading}
                      placeholder={routes.length === 0 ? "No routes available. Create a Route before adding a Service." : "-- Search & Select Existing Route --"}
                    />
                    <span style={{ fontSize: "0.75rem", color: routes.length === 0 ? "var(--warning, #f59e0b)" : "var(--text-muted)" }}>
                      {routes.length === 0
                        ? "No routes available. Create a Route before adding a Service."
                        : "Search by Route Code (e.g. R-KOL-001) or Route Name (e.g. Esplanade → Garia)."}
                    </span>
                  </div>

                  {/* SELECTED ROUTE CONTEXT CARD */}
                  {selectedRouteObj && (
                    <div
                      style={{
                        marginTop: "12px",
                        padding: "10px 14px",
                        borderRadius: "8px",
                        background: "rgba(59, 130, 246, 0.08)",
                        border: "1px solid rgba(59, 130, 246, 0.2)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        fontSize: "0.85rem",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Info size={16} color="var(--accent)" />
                        <span style={{ color: "var(--text-main)", fontWeight: 600 }}>
                          {selectedRouteObj.route_code}
                        </span>
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                        <span style={{ color: "var(--text-muted)" }}>{selectedRouteObj.route_name}</span>
                      </div>
                      {selectedRouteObj.distance_km != null && (
                        <span
                          style={{
                            background: "rgba(255, 255, 255, 0.08)",
                            padding: "2px 8px",
                            borderRadius: "4px",
                            fontWeight: 600,
                            color: "var(--text-main)",
                          }}
                        >
                          {Number(selectedRouteObj.distance_km).toFixed(1)} km total
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* ───────────────────────────────────────────────────────────── */}
                {/* SECTION C — INITIAL FARE CONFIGURATION (CREATE MODE ONLY) */}
                {/* ───────────────────────────────────────────────────────────── */}
                {!editingId && (
                  <div
                    style={{
                      background: "rgba(255, 255, 255, 0.02)",
                      border: "1px solid var(--border)",
                      borderRadius: "10px",
                      padding: "20px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "16px",
                      }}
                    >
                      <div>
                        <h3
                          style={{
                            margin: "0 0 4px 0",
                            fontSize: "0.95rem",
                            fontWeight: 700,
                            color: "var(--text-main)",
                            textTransform: "uppercase",
                            letterSpacing: "0.05em",
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                          }}
                        >
                          <Banknote size={18} color="var(--accent)" />
                          Section C — Initial Fare Configuration
                        </h3>
                        <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-muted)" }}>
                          Set the distance-based fares used by this service.
                        </p>
                      </div>

                      <span
                        style={{
                          fontSize: "0.8rem",
                          color: currentSlabError ? "#f87171" : "#10b981",
                          fontWeight: 600,
                          background: currentSlabError ? "rgba(239, 68, 68, 0.1)" : "rgba(16, 185, 129, 0.1)",
                          padding: "4px 10px",
                          borderRadius: "6px",
                        }}
                      >
                        {fareSlabs.length} fare slab{fareSlabs.length === 1 ? "" : "s"}
                      </span>
                    </div>

                    {/* FARE SLAB ROW EDITOR */}
                    <div
                      style={{
                        background: "var(--bg-dark)",
                        border: "1px solid var(--border)",
                        borderRadius: "8px",
                        overflow: "hidden",
                      }}
                    >
                      {/* TABLE HEADER */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr 1fr 1fr 48px",
                          gap: "12px",
                          padding: "10px 14px",
                          background: "rgba(255, 255, 255, 0.04)",
                          borderBottom: "1px solid var(--border)",
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                          color: "var(--text-muted)",
                        }}
                      >
                        <div>Min km</div>
                        <div>Max km</div>
                        <div>Ticket Price (₹)</div>
                        <div style={{ textAlign: "center" }}>Remove</div>
                      </div>

                      {/* SLAB ROWS */}
                      <div style={{ padding: "8px" }}>
                        {fareSlabs.map((slab, index) => {
                          const isFirst = index === 0;
                          const isLast = index === fareSlabs.length - 1;

                          return (
                            <div
                              key={index}
                              style={{
                                display: "grid",
                                gridTemplateColumns: "1fr 1fr 1fr 48px",
                                gap: "12px",
                                alignItems: "center",
                                padding: "6px",
                                borderRadius: "6px",
                                background: index % 2 === 0 ? "rgba(255, 255, 255, 0.01)" : "transparent",
                              }}
                            >
                              {/* MIN DISTANCE */}
                              <div>
                                <input
                                  type="number"
                                  step="0.1"
                                  min="0"
                                  value={slab.min_distance_km}
                                  onChange={(e) => handleSlabChange(index, "min_distance_km", e.target.value)}
                                  placeholder="0.0"
                                  disabled={isFirst} // First must always be 0
                                  style={{
                                    width: "100%",
                                    padding: "8px 10px",
                                    borderRadius: "6px",
                                    border: "1px solid var(--border)",
                                    background: isFirst ? "rgba(255, 255, 255, 0.03)" : "var(--bg-card)",
                                    color: "white",
                                    fontSize: "0.85rem",
                                    fontFamily: "monospace",
                                  }}
                                />
                              </div>

                              {/* MAX DISTANCE */}
                              <div>
                                <input
                                  type="number"
                                  step="0.1"
                                  min="0.1"
                                  value={slab.max_distance_km}
                                  onChange={(e) => handleSlabChange(index, "max_distance_km", e.target.value)}
                                  placeholder={isLast ? "Open (∞)" : "e.g. 10.0"}
                                  style={{
                                    width: "100%",
                                    padding: "8px 10px",
                                    borderRadius: "6px",
                                    border: "1px solid var(--border)",
                                    background: "var(--bg-card)",
                                    color: "white",
                                    fontSize: "0.85rem",
                                    fontFamily: "monospace",
                                  }}
                                />
                              </div>

                              {/* TICKET PRICE */}
                              <div>
                                <div style={{ position: "relative" }}>
                                  <span
                                    style={{
                                      position: "absolute",
                                      left: "10px",
                                      top: "50%",
                                      transform: "translateY(-50%)",
                                      color: "var(--text-muted)",
                                      fontSize: "0.85rem",
                                      fontWeight: 600,
                                    }}
                                  >
                                    ₹
                                  </span>
                                  <input
                                    type="number"
                                    step="0.5"
                                    min="0"
                                    value={slab.fare_amount}
                                    onChange={(e) => handleSlabChange(index, "fare_amount", e.target.value)}
                                    placeholder="10"
                                    style={{
                                      width: "100%",
                                      padding: "8px 10px 8px 24px",
                                      borderRadius: "6px",
                                      border: "1px solid var(--border)",
                                      background: "var(--bg-card)",
                                      color: "white",
                                      fontSize: "0.85rem",
                                      fontWeight: 600,
                                    }}
                                  />
                                </div>
                              </div>

                              {/* REMOVE BUTTON */}
                              <div style={{ display: "flex", justifyContent: "center" }}>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveSlab(index)}
                                  disabled={fareSlabs.length <= 1}
                                  title={fareSlabs.length <= 1 ? "At least one slab required" : "Remove slab"}
                                  style={{
                                    background: "transparent",
                                    border: "none",
                                    color: fareSlabs.length <= 1 ? "var(--text-muted)" : "var(--danger)",
                                    cursor: fareSlabs.length <= 1 ? "not-allowed" : "pointer",
                                    padding: "6px",
                                    borderRadius: "4px",
                                    opacity: fareSlabs.length <= 1 ? 0.4 : 1,
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                  }}
                                >
                                  <Trash2 size={16} />
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* ADD ROW BUTTON */}
                      <div
                        style={{
                          padding: "10px 14px",
                          borderTop: "1px solid var(--border)",
                          background: "rgba(255, 255, 255, 0.02)",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <button
                          type="button"
                          onClick={handleAddSlab}
                          style={{
                            background: "transparent",
                            border: "1px dashed var(--border)",
                            color: "var(--accent)",
                            padding: "6px 14px",
                            borderRadius: "6px",
                            fontSize: "0.85rem",
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Plus size={15} /> Add Fare Slab
                        </button>
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          Leave final max distance empty for an open-ended (unbounded) slab.
                        </span>
                      </div>
                    </div>

                    {/* LIVE INLINE FARE ERROR */}
                    {currentSlabError && (
                      <div
                        style={{
                          marginTop: "10px",
                          padding: "8px 12px",
                          borderRadius: "6px",
                          background: "rgba(239, 68, 68, 0.1)",
                          border: "1px solid rgba(239, 68, 68, 0.25)",
                          color: "#f87171",
                          fontSize: "0.8rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <AlertTriangle size={15} className="shrink-0 text-red-500" />
                        <span>{currentSlabError}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* FIXED FOOTER */}
              <div
                className="modal-actions"
                style={{
                  flexShrink: 0,
                  margin: 0,
                  padding: "16px 24px",
                  borderTop: "1px solid var(--border)",
                  background: "var(--bg-card)",
                }}
              >
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
                    routes.length === 0 ||
                    !formData.service_code.trim() ||
                    !formData.service_name.trim() ||
                    !formData.route_id ||
                    Boolean(!editingId && currentSlabError)
                  }
                >
                  {submitting
                    ? editingId
                      ? "Saving Changes..."
                      : "Creating Service..."
                    : editingId
                    ? "Save Changes"
                    : "Create Service"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
