import React, { useState, useEffect, useMemo } from "react";
import { useSearchParams, useNavigate, useLocation } from "react-router-dom";
import {
  Clock,
  Plus,
  Edit2,
  Trash2,
  Network,
  Route as RouteIcon,
  AlertTriangle,
  RefreshCw,
  Calendar,
  Check,
  X,
  Bus,
  ArrowRight,
  ArrowLeft,
  MapPin,
  Navigation,
  Info,
} from "lucide-react";
import {
  apiFetch,
  getFleetSchedules,
  createFleetSchedule,
  updateFleetSchedule,
  deleteFleetSchedule,
  type FleetScheduleItem,
} from "../api/api";
import {
  SearchableServiceSelect,
  type ServiceOption,
} from "../components/SearchableServiceSelect";

interface ServiceVehicleOption {
  id: string;
  vehicle_number: string;
  vehicle_type: string;
  registration_number?: string | null;
  status?: string;
}

interface RouteStopItem {
  id: string;
  route_id: string;
  stop_id: string;
  sequence_number: number;
  stop_code?: string | null;
  stop_name?: string | null;
}

interface RouteEndpoint {
  stop_id: string;
  stop_name: string;
  stop_code?: string | null;
  sequence_number: number;
}

export default function FleetSchedulesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = (location.state as any)?.returnTo || searchParams.get("returnTo");
  const returnLabel = (location.state as any)?.returnLabel || "Service";

  const [services, setServices] = useState<ServiceOption[]>([]);
  const [selectedServiceId, setSelectedServiceId] = useState<string>("");
  const [selectedDirection, setSelectedDirection] = useState<"A_TO_B" | "B_TO_A" | null>(null);

  const [routeEndpoints, setRouteEndpoints] = useState<{
    startStop: RouteEndpoint;
    endStop: RouteEndpoint;
  } | null>(null);
  const [loadingEndpoints, setLoadingEndpoints] = useState(false);
  const [endpointError, setEndpointError] = useState<string | null>(null);

  const [schedules, setSchedules] = useState<FleetScheduleItem[]>([]);
  const [serviceVehicles, setServiceVehicles] = useState<ServiceVehicleOption[]>([]);
  const [loadingServices, setLoadingServices] = useState(true);
  const [loadingSchedules, setLoadingSchedules] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<FleetScheduleItem | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    departure_time: "06:30",
    vehicle_id: "",
    every_day: true,
  });

  // 1. Load Services on Mount
  const loadServices = async () => {
    try {
      setLoadingServices(true);
      const [servicesData, routesData] = await Promise.all([
        apiFetch("/admin/services"),
        apiFetch("/admin/routes"),
      ]);

      const routeMap = new Map<string, any>();
      if (Array.isArray(routesData)) {
        routesData.forEach((r: any) => routeMap.set(r.id, r));
      }

      const mappedServices: ServiceOption[] = (servicesData || []).map((s: any) => {
        const route = routeMap.get(s.route_id);
        return {
          id: s.id,
          service_code: s.service_code,
          service_name: s.service_name,
          route_id: s.route_id,
          route_code: route?.route_code || "",
          route_name: route?.route_name || "",
          status: s.status,
        };
      });

      setServices(mappedServices);

      // Restore URL query params if present
      const urlServiceId = searchParams.get("serviceId");
      const urlDirection = searchParams.get("direction") as "A_TO_B" | "B_TO_A" | null;

      if (urlServiceId && mappedServices.some((s) => s.id === urlServiceId)) {
        setSelectedServiceId(urlServiceId);
        if (urlDirection === "A_TO_B" || urlDirection === "B_TO_A") {
          setSelectedDirection(urlDirection);
        }
      }
    } catch (err: any) {
      console.error("Failed to load services:", err);
    } finally {
      setLoadingServices(false);
    }
  };

  useEffect(() => {
    loadServices();
  }, []);

  // Find currently selected service details
  const currentService = useMemo(() => {
    return services.find((s) => s.id === selectedServiceId) || null;
  }, [services, selectedServiceId]);

  // 2. When Service changes, discover Route Endpoints & load Service Vehicles
  useEffect(() => {
    if (!selectedServiceId || !currentService?.route_id) {
      setRouteEndpoints(null);
      setEndpointError(null);
      setServiceVehicles([]);
      setSchedules([]);
      setSelectedDirection(null);
      return;
    }

    let isMounted = true;

    const fetchRouteData = async () => {
      try {
        setLoadingEndpoints(true);
        setEndpointError(null);

        const [stopsData, vehsData] = await Promise.all([
          apiFetch(`/admin/routes/${currentService.route_id}/stops`),
          apiFetch(`/admin/vehicles?service_id=${selectedServiceId}`),
        ]);

        if (!isMounted) return;

        setServiceVehicles(vehsData || []);

        const sortedStops: RouteStopItem[] = Array.isArray(stopsData)
          ? [...stopsData].sort((a, b) => a.sequence_number - b.sequence_number)
          : [];

        if (sortedStops.length < 2) {
          setRouteEndpoints(null);
          setEndpointError(
            "This service's route does not have sufficient ordered stops (minimum 2 required) to determine departure depot ends."
          );
          setSelectedDirection(null);
          setSchedules([]);
        } else {
          const first = sortedStops[0];
          const last = sortedStops[sortedStops.length - 1];

          setRouteEndpoints({
            startStop: {
              stop_id: first.stop_id,
              stop_name: first.stop_name || first.stop_code || "Start Depot",
              stop_code: first.stop_code,
              sequence_number: first.sequence_number,
            },
            endStop: {
              stop_id: last.stop_id,
              stop_name: last.stop_name || last.stop_code || "End Depot",
              stop_code: last.stop_code,
              sequence_number: last.sequence_number,
            },
          });
          setEndpointError(null);
        }
      } catch (err: any) {
        if (!isMounted) return;
        console.error("Failed to load route endpoints:", err);
        setEndpointError("Failed to retrieve route stops for this service.");
        setRouteEndpoints(null);
        setSelectedDirection(null);
        setSchedules([]);
      } finally {
        if (isMounted) setLoadingEndpoints(false);
      }
    };

    fetchRouteData();

    return () => {
      isMounted = false;
    };
  }, [selectedServiceId, currentService?.route_id]);

  // 3. Load Schedules when Service OR Direction changes
  useEffect(() => {
    if (!selectedServiceId || !selectedDirection) {
      setSchedules([]);
      return;
    }

    let isMounted = true;
    const fetchSchedules = async () => {
      try {
        setLoadingSchedules(true);
        // Clear old rows immediately to prevent stale data
        setSchedules([]);

        const schedsData = await getFleetSchedules(selectedServiceId, selectedDirection);
        if (isMounted) {
          setSchedules(schedsData || []);
        }
      } catch (err: any) {
        if (isMounted) {
          console.error("Failed to load directional schedules:", err);
          setSchedules([]);
        }
      } finally {
        if (isMounted) {
          setLoadingSchedules(false);
        }
      }
    };

    fetchSchedules();

    return () => {
      isMounted = false;
    };
  }, [selectedServiceId, selectedDirection]);

  // Service change handler
  const handleServiceChange = (serviceId: string) => {
    setSelectedServiceId(serviceId);
    setSelectedDirection(null);
    setSchedules([]);
    setFormError(null);
    if (serviceId) {
      setSearchParams({ serviceId });
    } else {
      setSearchParams({});
    }
  };

  // Direction tab change handler
  const handleDirectionChange = (direction: "A_TO_B" | "B_TO_A") => {
    if (selectedDirection === direction) return;
    setSchedules([]); // Clear old rows immediately
    setSelectedDirection(direction);
    setFormError(null);
    setSearchParams({
      serviceId: selectedServiceId,
      direction,
    });
  };

  // Derived current depot information based on selected direction
  const directionalInfo = useMemo(() => {
    if (!routeEndpoints) return null;
    const { startStop, endStop } = routeEndpoints;

    if (selectedDirection === "A_TO_B") {
      return {
        depotName: startStop.stop_name,
        depotCode: startStop.stop_code,
        destinationName: endStop.stop_name,
        pathDisplay: `${startStop.stop_name} → ${endStop.stop_name}`,
        directionLabel: "Outbound / Forward",
      };
    } else if (selectedDirection === "B_TO_A") {
      return {
        depotName: endStop.stop_name,
        depotCode: endStop.stop_code,
        destinationName: startStop.stop_name,
        pathDisplay: `${endStop.stop_name} → ${startStop.stop_name}`,
        directionLabel: "Inbound / Return",
      };
    }
    return null;
  }, [routeEndpoints, selectedDirection]);

  // Modal Open Handlers
  const handleOpenAddModal = () => {
    if (!selectedDirection) return;
    setEditingSchedule(null);
    setFormData({
      departure_time: "06:30",
      vehicle_id: serviceVehicles[0]?.id || "",
      every_day: true,
    });
    setFormError(null);
    setShowModal(true);
  };

  const handleOpenEditModal = (sched: FleetScheduleItem) => {
    setEditingSchedule(sched);
    setFormData({
      departure_time: sched.departure_time,
      vehicle_id: sched.vehicle_id,
      every_day: sched.every_day,
    });
    setFormError(null);
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingSchedule(null);
    setFormError(null);
  };

  // Save Schedule Handler
  const handleSaveSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDirection) {
      setFormError("Please select a departure depot before creating a schedule.");
      return;
    }
    if (!formData.departure_time) {
      setFormError("Departure time is required.");
      return;
    }
    if (!formData.vehicle_id) {
      setFormError("Please select a vehicle.");
      return;
    }

    try {
      setSubmitting(true);
      setFormError(null);

      if (editingSchedule) {
        await updateFleetSchedule(editingSchedule.id, {
          vehicle_id: formData.vehicle_id,
          direction: selectedDirection,
          departure_time: formData.departure_time,
          every_day: formData.every_day,
        });
      } else {
        await createFleetSchedule({
          service_id: selectedServiceId,
          vehicle_id: formData.vehicle_id,
          direction: selectedDirection,
          departure_time: formData.departure_time,
          every_day: formData.every_day,
        });
      }

      handleCloseModal();
      // Reload current direction schedules
      const refreshed = await getFleetSchedules(selectedServiceId, selectedDirection);
      setSchedules(refreshed || []);
    } catch (err: any) {
      setFormError(err.message || "Failed to save fleet schedule.");
    } finally {
      setSubmitting(false);
    }
  };

  // Delete Schedule Handler
  const handleDeleteSchedule = async (scheduleId: string) => {
    if (
      !window.confirm(
        "Are you sure you want to cancel this recurring departure from the service timetable?"
      )
    ) {
      return;
    }

    try {
      setDeletingId(scheduleId);
      await deleteFleetSchedule(scheduleId);
      if (selectedDirection) {
        const refreshed = await getFleetSchedules(selectedServiceId, selectedDirection);
        setSchedules(refreshed || []);
      }
    } catch (err: any) {
      alert(err.message || "Failed to cancel departure.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="vehicles-page">
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

      {/* Page Header */}
      <div className="page-header" style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "rgba(56, 189, 248, 0.15)",
              color: "#38bdf8",
              border: "1px solid rgba(56, 189, 248, 0.3)",
            }}
          >
            <Clock size={22} />
          </div>
          <div>
            <h1 style={{ fontSize: "1.5rem", fontWeight: 700, margin: 0 }}>Fleet Schedule</h1>
            <p style={{ margin: "2px 0 0 0", color: "#94a3b8", fontSize: "0.875rem" }}>
              Depot-end &amp; direction-scoped recurring service timetables
            </p>
          </div>
        </div>
      </div>

      {/* LAYER 1: SERVICE SELECTION CARD */}
      <div
        className="data-table-card"
        style={{
          marginBottom: "1.25rem",
          padding: "1.25rem",
          overflow: "visible",
          position: "relative",
          zIndex: 30,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "0.85rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Network size={18} color="#38bdf8" />
            <span style={{ fontWeight: 600, fontSize: "0.95rem", color: "#f8fafc" }}>
              1. Select Service
            </span>
          </div>
          {selectedServiceId && (
            <button
              onClick={() => handleServiceChange("")}
              style={{
                background: "transparent",
                border: "none",
                color: "#94a3b8",
                fontSize: "0.8rem",
                cursor: "pointer",
                padding: "2px 6px",
                display: "flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <X size={14} /> Clear Service Selection
            </button>
          )}
        </div>

        {loadingServices ? (
          <div style={{ padding: "0.75rem", color: "#94a3b8", fontSize: "0.875rem" }}>
            Loading available services...
          </div>
        ) : services.length === 0 ? (
          <div
            style={{
              padding: "1rem",
              background: "rgba(239, 68, 68, 0.08)",
              border: "1px solid rgba(239, 68, 68, 0.2)",
              borderRadius: "8px",
              color: "#fca5a5",
              fontSize: "0.875rem",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
          >
            <AlertTriangle size={16} />
            <span>No services available. Create a Service before managing fleet schedules.</span>
          </div>
        ) : (
          <SearchableServiceSelect
            services={services}
            value={selectedServiceId}
            onChange={handleServiceChange}
            placeholder="-- Select Existing Service --"
          />
        )}
      </div>

      {/* LAYER 2: DEPOT / DEPARTURE END SELECTION */}
      {selectedServiceId && (
        <div
          className="data-table-card"
          style={{
            marginBottom: "1.25rem",
            padding: "1.25rem",
            position: "relative",
            zIndex: 20,
            border: "1px solid rgba(56, 189, 248, 0.25)",
            background: "rgba(15, 23, 42, 0.5)",
          }}
        >
          <div style={{ marginBottom: "0.85rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Navigation size={18} color="#38bdf8" />
              <span style={{ fontWeight: 600, fontSize: "0.95rem", color: "#f8fafc" }}>
                2. Select Depot / Departure End
              </span>
            </div>
            <p style={{ margin: "4px 0 0 0", color: "#94a3b8", fontSize: "0.825rem" }}>
              Choose the route end from which departures are scheduled.
            </p>
          </div>

          {loadingEndpoints ? (
            <div
              style={{
                padding: "1.5rem",
                textAlign: "center",
                color: "#94a3b8",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.5rem",
              }}
            >
              <RefreshCw size={16} className="spinning" />
              <span>Resolving route depot endpoints for {currentService?.service_code}...</span>
            </div>
          ) : endpointError ? (
            <div
              style={{
                padding: "1rem",
                background: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                borderRadius: "8px",
                color: "#fca5a5",
                fontSize: "0.875rem",
                display: "flex",
                alignItems: "center",
                gap: "0.6rem",
              }}
            >
              <AlertTriangle size={18} />
              <span>{endpointError}</span>
            </div>
          ) : routeEndpoints ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: "1rem",
              }}
            >
              {/* ENDPOINT 1: FROM START STOP (A_TO_B) */}
              <button
                type="button"
                onClick={() => handleDirectionChange("A_TO_B")}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  textAlign: "left",
                  padding: "1rem 1.25rem",
                  borderRadius: "10px",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  background:
                    selectedDirection === "A_TO_B"
                      ? "rgba(56, 189, 248, 0.15)"
                      : "rgba(30, 41, 59, 0.5)",
                  border:
                    selectedDirection === "A_TO_B"
                      ? "2px solid #38bdf8"
                      : "1px solid rgba(255, 255, 255, 0.1)",
                  boxShadow:
                    selectedDirection === "A_TO_B"
                      ? "0 0 16px rgba(56, 189, 248, 0.25)"
                      : "none",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    width: "100%",
                    marginBottom: "0.4rem",
                  }}
                >
                  <span
                    style={{
                      fontSize: "0.75rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.5px",
                      color: selectedDirection === "A_TO_B" ? "#38bdf8" : "#94a3b8",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.35rem",
                    }}
                  >
                    <MapPin size={13} />
                    Departure Depot End
                  </span>
                  {selectedDirection === "A_TO_B" && (
                    <span
                      style={{
                        background: "#38bdf8",
                        color: "#0f172a",
                        borderRadius: "12px",
                        padding: "1px 8px",
                        fontSize: "0.7rem",
                        fontWeight: 700,
                        display: "flex",
                        alignItems: "center",
                        gap: "3px",
                      }}
                    >
                      <Check size={12} strokeWidth={3} /> ACTIVE
                    </span>
                  )}
                </div>

                <div
                  style={{
                    fontSize: "1.05rem",
                    fontWeight: 700,
                    color: selectedDirection === "A_TO_B" ? "#f8fafc" : "#e2e8f0",
                    marginBottom: "0.35rem",
                  }}
                >
                  FROM {routeEndpoints.startStop.stop_name.toUpperCase()}
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                    fontSize: "0.8rem",
                    color: selectedDirection === "A_TO_B" ? "#bae6fd" : "#94a3b8",
                  }}
                >
                  <span>{routeEndpoints.startStop.stop_name}</span>
                  <ArrowRight size={13} />
                  <span>{routeEndpoints.endStop.stop_name}</span>
                </div>
              </button>

              {/* ENDPOINT 2: FROM END STOP (B_TO_A) */}
              <button
                type="button"
                onClick={() => handleDirectionChange("B_TO_A")}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  textAlign: "left",
                  padding: "1rem 1.25rem",
                  borderRadius: "10px",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  background:
                    selectedDirection === "B_TO_A"
                      ? "rgba(56, 189, 248, 0.15)"
                      : "rgba(30, 41, 59, 0.5)",
                  border:
                    selectedDirection === "B_TO_A"
                      ? "2px solid #38bdf8"
                      : "1px solid rgba(255, 255, 255, 0.1)",
                  boxShadow:
                    selectedDirection === "B_TO_A"
                      ? "0 0 16px rgba(56, 189, 248, 0.25)"
                      : "none",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    width: "100%",
                    marginBottom: "0.4rem",
                  }}
                >
                  <span
                    style={{
                      fontSize: "0.75rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.5px",
                      color: selectedDirection === "B_TO_A" ? "#38bdf8" : "#94a3b8",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.35rem",
                    }}
                  >
                    <MapPin size={13} />
                    Departure Depot End
                  </span>
                  {selectedDirection === "B_TO_A" && (
                    <span
                      style={{
                        background: "#38bdf8",
                        color: "#0f172a",
                        borderRadius: "12px",
                        padding: "1px 8px",
                        fontSize: "0.7rem",
                        fontWeight: 700,
                        display: "flex",
                        alignItems: "center",
                        gap: "3px",
                      }}
                    >
                      <Check size={12} strokeWidth={3} /> ACTIVE
                    </span>
                  )}
                </div>

                <div
                  style={{
                    fontSize: "1.05rem",
                    fontWeight: 700,
                    color: selectedDirection === "B_TO_A" ? "#f8fafc" : "#e2e8f0",
                    marginBottom: "0.35rem",
                  }}
                >
                  FROM {routeEndpoints.endStop.stop_name.toUpperCase()}
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                    fontSize: "0.8rem",
                    color: selectedDirection === "B_TO_A" ? "#bae6fd" : "#94a3b8",
                  }}
                >
                  <span>{routeEndpoints.endStop.stop_name}</span>
                  <ArrowRight size={13} />
                  <span>{routeEndpoints.startStop.stop_name}</span>
                </div>
              </button>
            </div>
          ) : null}
        </div>
      )}

      {/* LAYER 3: SCHEDULE TIMETABLE SECTION */}
      {!selectedServiceId ? (
        <div
          className="data-table-card"
          style={{
            padding: "3.5rem 1.5rem",
            textAlign: "center",
            color: "#64748b",
            position: "relative",
            zIndex: 1,
          }}
        >
          <Clock size={48} style={{ opacity: 0.3, marginBottom: "1rem" }} />
          <h3
            style={{
              fontSize: "1.1rem",
              fontWeight: 600,
              color: "#94a3b8",
              marginBottom: "0.5rem",
            }}
          >
            No Service Selected
          </h3>
          <p style={{ fontSize: "0.875rem", maxWidth: "420px", margin: "0 auto" }}>
            Select an active service above to choose its departure depot and manage its recurring
            timetable.
          </p>
        </div>
      ) : !selectedDirection ? (
        <div
          className="data-table-card"
          style={{
            padding: "3rem 1.5rem",
            textAlign: "center",
            color: "#64748b",
            position: "relative",
            zIndex: 1,
          }}
        >
          <Navigation size={44} style={{ opacity: 0.35, color: "#38bdf8", marginBottom: "1rem" }} />
          <h3
            style={{
              fontSize: "1.1rem",
              fontWeight: 600,
              color: "#94a3b8",
              marginBottom: "0.5rem",
            }}
          >
            Departure Depot Not Selected
          </h3>
          <p style={{ fontSize: "0.875rem", maxWidth: "440px", margin: "0 auto" }}>
            Select one of the two route departure ends above (
            <strong>FROM {routeEndpoints?.startStop.stop_name || "START"}</strong> or{" "}
            <strong>FROM {routeEndpoints?.endStop.stop_name || "END"}</strong>) to view and manage its
            recurring timetable.
          </p>
        </div>
      ) : (
        <div
          className="data-table-card"
          style={{
            padding: "1.5rem",
            position: "relative",
            zIndex: 1,
          }}
        >
          {/* Header Card for Selected Direction Timetable */}
          <div
            style={{
              background: "rgba(15, 23, 42, 0.65)",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              borderRadius: "10px",
              padding: "1.15rem 1.25rem",
              marginBottom: "1.5rem",
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "1rem",
            }}
          >
            <div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.6rem",
                  marginBottom: "0.35rem",
                  flexWrap: "wrap",
                }}
              >
                <span
                  style={{
                    background: "rgba(56, 189, 248, 0.15)",
                    color: "#38bdf8",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    letterSpacing: "0.5px",
                    border: "1px solid rgba(56, 189, 248, 0.3)",
                  }}
                >
                  {currentService?.service_code}
                </span>
                <span style={{ fontWeight: 700, fontSize: "1.15rem", color: "#f8fafc" }}>
                  Fleet Schedule — {currentService?.service_name}
                </span>
              </div>

              {directionalInfo && (
                <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  <div
                    style={{
                      fontSize: "0.95rem",
                      fontWeight: 700,
                      color: "#38bdf8",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                    }}
                  >
                    <MapPin size={15} />
                    <span>FROM {directionalInfo.depotName.toUpperCase()}</span>
                  </div>
                  <div
                    style={{
                      fontSize: "0.85rem",
                      color: "#94a3b8",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                    }}
                  >
                    <RouteIcon size={14} />
                    <span>{directionalInfo.pathDisplay}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Actions: Refresh & Add Schedule */}
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <button
                className="btn-outline"
                onClick={() => {
                  if (selectedServiceId && selectedDirection) {
                    setLoadingSchedules(true);
                    getFleetSchedules(selectedServiceId, selectedDirection)
                      .then((data) => setSchedules(data || []))
                      .catch((err) => console.error(err))
                      .finally(() => setLoadingSchedules(false));
                  }
                }}
                disabled={loadingSchedules}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  padding: "0.55rem 0.85rem",
                  fontSize: "0.85rem",
                }}
              >
                <RefreshCw size={15} className={loadingSchedules ? "spinning" : ""} />
                Refresh
              </button>
              <button
                className="btn-primary"
                onClick={handleOpenAddModal}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.55rem 1rem",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                }}
              >
                <Plus size={16} />
                Add Schedule
              </button>
            </div>
          </div>

          {/* Timetable Subheader & Recurrence Status */}
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "1rem",
              paddingBottom: "0.75rem",
              borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
              gap: "0.75rem",
            }}
          >
            <div>
              <h2 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                Recurring Timetable — FROM {directionalInfo?.depotName}
              </h2>
              <p style={{ margin: "2px 0 0 0", color: "#94a3b8", fontSize: "0.8rem" }}>
                Departures originating from {directionalInfo?.depotName} ({directionalInfo?.pathDisplay})
              </p>
            </div>

            {/* Every Day Setting Badge */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.6rem",
                background: "rgba(34, 197, 94, 0.1)",
                border: "1px solid rgba(34, 197, 94, 0.25)",
                padding: "0.4rem 0.8rem",
                borderRadius: "6px",
              }}
            >
              <div
                style={{
                  width: "16px",
                  height: "16px",
                  borderRadius: "4px",
                  background: "#22c55e",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#0f172a",
                }}
              >
                <Check size={12} strokeWidth={3} />
              </div>
              <div>
                <span style={{ fontWeight: 600, fontSize: "0.85rem", color: "#4ade80" }}>
                  Every Day
                </span>
                <span
                  style={{
                    marginLeft: "6px",
                    fontSize: "0.75rem",
                    color: "#86efac",
                    opacity: 0.85,
                  }}
                >
                  (This timetable repeats every day unless changed)
                </span>
              </div>
            </div>
          </div>

          {/* Schedules Table */}
          {loadingSchedules ? (
            <div style={{ padding: "2.5rem", textAlign: "center", color: "#94a3b8" }}>
              <RefreshCw size={24} className="spinning" style={{ marginBottom: "0.5rem" }} />
              <div>Loading departures from {directionalInfo?.depotName}...</div>
            </div>
          ) : schedules.length === 0 ? (
            <div
              style={{
                padding: "3rem 1.5rem",
                textAlign: "center",
                color: "#64748b",
                background: "rgba(15, 23, 42, 0.3)",
                borderRadius: "8px",
                border: "1px dashed rgba(255, 255, 255, 0.1)",
              }}
            >
              <Calendar size={36} style={{ opacity: 0.3, marginBottom: "0.75rem" }} />
              <h4
                style={{
                  fontSize: "1rem",
                  fontWeight: 600,
                  color: "#94a3b8",
                  marginBottom: "0.35rem",
                }}
              >
                No Departures Scheduled
              </h4>
              <p style={{ fontSize: "0.85rem", maxWidth: "500px", margin: "0 auto 1.25rem auto" }}>
                No departure schedule configured from{" "}
                <strong style={{ color: "#e2e8f0" }}>{directionalInfo?.depotName}</strong> yet. Click
                &ldquo;+ Add Schedule&rdquo; to set up recurring departures.
              </p>
              <button
                className="btn-primary"
                onClick={handleOpenAddModal}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  fontSize: "0.85rem",
                }}
              >
                <Plus size={15} /> Add Schedule
              </button>
            </div>
          ) : (
            <div className="table-responsive" style={{ overflowX: "auto" }}>
              <table className="admin-table" style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr
                    style={{
                      borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
                      textAlign: "left",
                    }}
                  >
                    <th
                      style={{
                        padding: "0.75rem 1rem",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: "#94a3b8",
                        textTransform: "uppercase",
                      }}
                    >
                      Departure Time
                    </th>
                    <th
                      style={{
                        padding: "0.75rem 1rem",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: "#94a3b8",
                        textTransform: "uppercase",
                      }}
                    >
                      Bus
                    </th>
                    <th
                      style={{
                        padding: "0.75rem 1rem",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: "#94a3b8",
                        textTransform: "uppercase",
                      }}
                    >
                      Registration
                    </th>
                    <th
                      style={{
                        padding: "0.75rem 1rem",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: "#94a3b8",
                        textTransform: "uppercase",
                      }}
                    >
                      Type
                    </th>
                    <th
                      style={{
                        padding: "0.75rem 1rem",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: "#94a3b8",
                        textTransform: "uppercase",
                      }}
                    >
                      Status
                    </th>
                    <th
                      style={{
                        padding: "0.75rem 1rem",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: "#94a3b8",
                        textTransform: "uppercase",
                      }}
                    >
                      Driver
                    </th>
                    <th
                      style={{
                        padding: "0.75rem 1rem",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: "#94a3b8",
                        textTransform: "uppercase",
                      }}
                    >
                      Conductor
                    </th>
                    <th
                      style={{
                        padding: "0.75rem 1rem",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: "#94a3b8",
                        textTransform: "uppercase",
                        textAlign: "right",
                      }}
                    >
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((item, index) => (
                    <tr
                      key={item.id}
                      style={{
                        borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
                        background:
                          index % 2 === 0 ? "transparent" : "rgba(255, 255, 255, 0.015)",
                      }}
                    >
                      {/* 1. DEPARTURE TIME */}
                      <td style={{ padding: "0.85rem 1rem", verticalAlign: "middle" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                          <Clock size={16} color="#38bdf8" />
                          <span
                            style={{
                              fontSize: "1.05rem",
                              fontWeight: 700,
                              color: "#f8fafc",
                              fontFamily: "monospace",
                            }}
                          >
                            {item.formatted_departure_time}
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                            ({item.departure_time})
                          </span>
                        </div>
                      </td>

                      {/* 2. BUS */}
                      <td style={{ padding: "0.85rem 1rem", verticalAlign: "middle" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                          <Bus size={15} color="#94a3b8" />
                          <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "#f1f5f9" }}>
                            {item.vehicle_number}
                          </span>
                        </div>
                      </td>

                      {/* 3. REGISTRATION */}
                      <td style={{ padding: "0.85rem 1rem", verticalAlign: "middle" }}>
                        <span style={{ fontSize: "0.85rem", color: "#cbd5e1", fontFamily: "monospace" }}>
                          {item.registration_number || "—"}
                        </span>
                      </td>

                      {/* 4. TYPE */}
                      <td style={{ padding: "0.85rem 1rem", verticalAlign: "middle" }}>
                        <span
                          style={{
                            background: "rgba(255, 255, 255, 0.06)",
                            padding: "2px 7px",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            color: "#94a3b8",
                            border: "1px solid rgba(255, 255, 255, 0.08)",
                          }}
                        >
                          {item.vehicle_type || "Standard"}
                        </span>
                      </td>

                      {/* 5. STATUS */}
                      <td style={{ padding: "0.85rem 1rem", verticalAlign: "middle" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            padding: "2px 7px",
                            borderRadius: "10px",
                            fontSize: "0.72rem",
                            fontWeight: 700,
                            background:
                              item.vehicle_status === "ACTIVE"
                                ? "rgba(34, 197, 94, 0.12)"
                                : "rgba(148, 163, 184, 0.12)",
                            color: item.vehicle_status === "ACTIVE" ? "#4ade80" : "#94a3b8",
                            border:
                              item.vehicle_status === "ACTIVE"
                                ? "1px solid rgba(34, 197, 94, 0.25)"
                                : "1px solid rgba(148, 163, 184, 0.25)",
                          }}
                        >
                          {item.vehicle_status || "ACTIVE"}
                        </span>
                      </td>

                      {/* 6. DRIVER */}
                      <td style={{ padding: "0.85rem 1rem", verticalAlign: "middle" }}>
                        {item.driver ? (
                          <div style={{ fontSize: "0.85rem", color: "#e2e8f0" }}>
                            {item.driver.employee_code && (
                              <span
                                style={{
                                  color: "#38bdf8",
                                  fontWeight: 600,
                                  marginRight: "4px",
                                }}
                              >
                                {item.driver.employee_code}
                              </span>
                            )}
                            <span>{item.driver.name}</span>
                          </div>
                        ) : (
                          <span style={{ fontSize: "0.8rem", color: "#64748b", fontStyle: "italic" }}>
                            Unassigned
                          </span>
                        )}
                      </td>

                      {/* 7. CONDUCTOR */}
                      <td style={{ padding: "0.85rem 1rem", verticalAlign: "middle" }}>
                        {item.conductor ? (
                          <div style={{ fontSize: "0.85rem", color: "#e2e8f0" }}>
                            {item.conductor.employee_code && (
                              <span
                                style={{
                                  color: "#38bdf8",
                                  fontWeight: 600,
                                  marginRight: "4px",
                                }}
                              >
                                {item.conductor.employee_code}
                              </span>
                            )}
                            <span>{item.conductor.name}</span>
                          </div>
                        ) : (
                          <span style={{ fontSize: "0.8rem", color: "#64748b", fontStyle: "italic" }}>
                            Unassigned
                          </span>
                        )}
                      </td>

                      {/* 8. ACTIONS */}
                      <td style={{ padding: "0.85rem 1rem", verticalAlign: "middle", textAlign: "right" }}>
                        <div style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}>
                          <button
                            className="btn-icon"
                            title="Edit Departure"
                            onClick={() => handleOpenEditModal(item)}
                            style={{
                              background: "rgba(255, 255, 255, 0.05)",
                              border: "1px solid rgba(255, 255, 255, 0.1)",
                              padding: "6px",
                              borderRadius: "6px",
                              color: "#94a3b8",
                              cursor: "pointer",
                            }}
                          >
                            <Edit2 size={15} />
                          </button>
                          <button
                            className="btn-icon"
                            title="Cancel Departure"
                            disabled={deletingId === item.id}
                            onClick={() => handleDeleteSchedule(item.id)}
                            style={{
                              background: "rgba(239, 68, 68, 0.1)",
                              border: "1px solid rgba(239, 68, 68, 0.2)",
                              padding: "6px",
                              borderRadius: "6px",
                              color: "#f87171",
                              cursor: "pointer",
                            }}
                          >
                            {deletingId === item.id ? (
                              <RefreshCw size={15} className="spinning" />
                            ) : (
                              <Trash2 size={15} />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Informational Crew Disclaimer */}
              <div
                style={{
                  padding: "0.75rem 1rem",
                  borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  color: "#64748b",
                  fontSize: "0.78rem",
                }}
              >
                <Info size={13} />
                <span>
                  Driver and Conductor information reflects active vehicle and service crew assignments.
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ADD / EDIT SCHEDULE MODAL (VIEWPORT-SAFE WITH FIXED FOOTER) */}
      {showModal && (
        <div
          className="modal-overlay"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "1rem",
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) handleCloseModal();
          }}
        >
          <div
            className="modal-card"
            style={{
              background: "#0f172a",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              borderRadius: "12px",
              width: "100%",
              maxWidth: "520px",
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)",
              overflow: "hidden",
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: "1.25rem",
                borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: "rgba(15, 23, 42, 0.8)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Clock size={20} color="#38bdf8" />
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                  {editingSchedule ? "Edit Departure Schedule" : "Add Departure Schedule"}
                </h3>
              </div>
              <button
                onClick={handleCloseModal}
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

            {/* Modal Body (Scrollable) */}
            <form
              onSubmit={handleSaveSchedule}
              style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}
            >
              <div
                style={{
                  padding: "1.25rem",
                  overflowY: "auto",
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: "1.15rem",
                }}
              >
                {/* FIXED CONTEXT CARD: SERVICE + DEPOT + DIRECTION */}
                <div
                  style={{
                    background: "rgba(56, 189, 248, 0.08)",
                    border: "1px solid rgba(56, 189, 248, 0.25)",
                    borderRadius: "8px",
                    padding: "0.85rem 1rem",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.4rem",
                  }}
                >
                  <div style={{ fontSize: "0.825rem", color: "#94a3b8" }}>
                    Service:{" "}
                    <strong style={{ color: "#38bdf8" }}>{currentService?.service_code}</strong>{" "}
                    ({currentService?.service_name})
                  </div>
                  <div style={{ fontSize: "0.825rem", color: "#94a3b8" }}>
                    Departure From:{" "}
                    <strong style={{ color: "#f8fafc" }}>
                      {directionalInfo?.depotName}
                    </strong>
                  </div>
                  <div style={{ fontSize: "0.825rem", color: "#94a3b8" }}>
                    Direction:{" "}
                    <strong style={{ color: "#38bdf8" }}>
                      {directionalInfo?.pathDisplay}
                    </strong>
                  </div>
                </div>

                {/* Error Banner */}
                {formError && (
                  <div
                    style={{
                      background: "rgba(239, 68, 68, 0.12)",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      borderRadius: "8px",
                      padding: "0.75rem",
                      color: "#fca5a5",
                      fontSize: "0.85rem",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                    }}
                  >
                    <AlertTriangle size={16} />
                    <span>{formError}</span>
                  </div>
                )}

                {/* Field 1: Departure Time */}
                <div>
                  <label
                    htmlFor="departure_time"
                    style={{
                      display: "block",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      color: "#e2e8f0",
                      marginBottom: "0.4rem",
                    }}
                  >
                    Departure Time *
                  </label>
                  <input
                    id="departure_time"
                    type="time"
                    required
                    value={formData.departure_time}
                    onChange={(e) => {
                      setFormData({ ...formData, departure_time: e.target.value });
                      if (formError) setFormError(null);
                    }}
                    style={{
                      width: "100%",
                      padding: "0.65rem 0.85rem",
                      background: "rgba(30, 41, 59, 0.7)",
                      border: "1px solid rgba(255, 255, 255, 0.15)",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "1rem",
                      fontFamily: "monospace",
                      outline: "none",
                    }}
                  />
                  <span
                    style={{
                      display: "block",
                      marginTop: "0.3rem",
                      fontSize: "0.75rem",
                      color: "#94a3b8",
                    }}
                  >
                    Enter departure time in 24-hour format (e.g. 06:30 for 06:30 AM).
                  </span>
                </div>

                {/* Field 2: Bus / Vehicle Selector */}
                <div>
                  <label
                    htmlFor="vehicle_id"
                    style={{
                      display: "block",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      color: "#e2e8f0",
                      marginBottom: "0.4rem",
                    }}
                  >
                    Bus / Vehicle *
                  </label>
                  {serviceVehicles.length === 0 ? (
                    <div
                      style={{
                        padding: "0.85rem",
                        background: "rgba(239, 68, 68, 0.08)",
                        border: "1px solid rgba(239, 68, 68, 0.25)",
                        borderRadius: "6px",
                        color: "#fca5a5",
                        fontSize: "0.85rem",
                      }}
                    >
                      No vehicles available for this service. Add a vehicle in Fleet Management
                      first.
                    </div>
                  ) : (
                    <select
                      id="vehicle_id"
                      required
                      value={formData.vehicle_id}
                      onChange={(e) => {
                        setFormData({ ...formData, vehicle_id: e.target.value });
                        if (formError) setFormError(null);
                      }}
                      style={{
                        width: "100%",
                        padding: "0.65rem 0.85rem",
                        background: "#1e293b",
                        border: "1px solid rgba(255, 255, 255, 0.15)",
                        borderRadius: "6px",
                        color: "#f8fafc",
                        fontSize: "0.95rem",
                        outline: "none",
                        cursor: "pointer",
                      }}
                    >
                      <option value="" disabled>
                        -- Select Assigned Vehicle --
                      </option>
                      {serviceVehicles.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.vehicle_number} {v.vehicle_type ? `(${v.vehicle_type})` : ""}{" "}
                          {v.registration_number ? `• ${v.registration_number}` : ""}
                        </option>
                      ))}
                    </select>
                  )}
                  <span
                    style={{
                      display: "block",
                      marginTop: "0.3rem",
                      fontSize: "0.75rem",
                      color: "#94a3b8",
                    }}
                  >
                    Only vehicles scoped and active for {currentService?.service_code} are eligible.
                  </span>
                </div>

                {/* Field 3: Recurrence Context (Every Day) */}
                <div
                  style={{
                    background: "rgba(34, 197, 94, 0.08)",
                    border: "1px solid rgba(34, 197, 94, 0.25)",
                    borderRadius: "8px",
                    padding: "0.85rem",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "0.6rem",
                  }}
                >
                  <div
                    style={{
                      width: "18px",
                      height: "18px",
                      borderRadius: "4px",
                      background: "#22c55e",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#0f172a",
                      marginTop: "2px",
                      flexShrink: 0,
                    }}
                  >
                    <Check size={14} strokeWidth={3} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "0.875rem", color: "#4ade80" }}>
                      Recurrence Mode: Every Day
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "#86efac", marginTop: "2px" }}>
                      This departure will repeat daily for departures originating from{" "}
                      <strong>{directionalInfo?.depotName}</strong>.
                    </div>
                  </div>
                </div>
              </div>

              {/* Modal Footer (Fixed) */}
              <div
                style={{
                  padding: "1rem 1.25rem",
                  borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "flex-end",
                  gap: "0.75rem",
                  background: "rgba(15, 23, 42, 0.8)",
                }}
              >
                <button
                  type="button"
                  className="btn-outline"
                  onClick={handleCloseModal}
                  disabled={submitting}
                  style={{ padding: "0.55rem 1rem", fontSize: "0.875rem" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={submitting || serviceVehicles.length === 0}
                  style={{
                    padding: "0.55rem 1.25rem",
                    fontSize: "0.875rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.4rem",
                  }}
                >
                  {submitting && <RefreshCw size={15} className="spinning" />}
                  {editingSchedule ? "Update Departure" : "Save Departure"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
