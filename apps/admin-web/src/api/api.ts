const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const token = localStorage.getItem("adminToken");
  const headers = new Headers(options.headers || {});
  
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem("adminToken");
      window.location.href = "/login";
    }
    const errorData = await response.json().catch(() => null);
    throw new Error((errorData && errorData.detail) || "API Request Failed");
  }

  return response.json();
}

export async function apiFetchResponse(endpoint: string, options: RequestInit = {}) {
  const token = localStorage.getItem("adminToken");
  const headers = new Headers(options.headers || {});
  
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem("adminToken");
      window.location.href = "/login";
    }
    const errorData = await response.json().catch(() => null);
    throw new Error((errorData && errorData.detail) || "API Request Failed");
  }

  const data = await response.json();
  return { data, headers: response.headers };
}

export async function checkRouteDuplicateStops(routeId: string, stops: string[]) {
  return apiFetch(`/admin/routes/${routeId}/check-duplicate-stops`, {
    method: "POST",
    body: JSON.stringify({ stops }),
  });
}

export async function previewRoute(payload: {
  start_stop_id: string;
  end_stop_id: string;
  intermediate_stop_ids: string[];
  exclude_route_id?: string;
}) {
  return apiFetch("/admin/routes/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createRouteWithStops(payload: {
  route_code: string;
  route_name: string;
  start_stop_id: string;
  end_stop_id: string;
  intermediate_stop_ids: string[];
  status?: string;
}) {
  return apiFetch("/admin/routes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateRoute(
  routeId: string,
  payload: {
    route_code?: string;
    route_name?: string;
    status?: string;
    start_stop_id?: string;
    end_stop_id?: string;
    intermediate_stop_ids?: string[];
  }
) {
  return apiFetch(`/admin/routes/${routeId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

// ----------------------------------------------------------------------------
// Vehicles
// ----------------------------------------------------------------------------
export async function getVehicles(serviceId?: string) {
  const query = serviceId ? `?service_id=${serviceId}` : "";
  return apiFetch(`/admin/vehicles${query}`);
}

export async function getVehicle(id: string, serviceId?: string) {
  const query = serviceId ? `?service_id=${serviceId}` : "";
  return apiFetch(`/admin/vehicles/${id}${query}`);
}

export async function getVehicleCrew(id: string, serviceId?: string) {
  const query = serviceId ? `?service_id=${serviceId}` : "";
  return apiFetch(`/admin/vehicles/${id}/crew${query}`);
}

export async function assignVehicleCrew(
  id: string,
  data: { service_id: string; driver_id?: string | null; conductor_id?: string | null }
) {
  return apiFetch(`/admin/vehicles/${id}/crew`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function createVehicle(data: any) {
  return apiFetch("/admin/vehicles", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateVehicle(id: string, data: any) {
  return apiFetch(`/admin/vehicles/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function decommissionVehicle(id: string) {
  const token = localStorage.getItem("adminToken");
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  
  const response = await fetch(`${BASE_URL}/admin/vehicles/${id}`, {
    method: "DELETE",
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
        localStorage.removeItem("adminToken");
        window.location.href = "/login";
    }
    const errorData = await response.json().catch(() => null);
    throw new Error((errorData && errorData.detail) || "API Request Failed");
  }
}

// ----------------------------------------------------------------------------
// Depot Schedules
// ----------------------------------------------------------------------------
export async function getDepotSchedules() {
  return apiFetch("/admin/depot-schedules");
}

export async function getDepotSchedule(id: string) {
  return apiFetch(`/admin/depot-schedules/${id}`);
}

export async function createDepotSchedule(data: any) {
  return apiFetch("/admin/depot-schedules", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateDepotSchedule(id: string, data: any) {
  return apiFetch(`/admin/depot-schedules/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function cancelDepotSchedule(id: string) {
  const token = localStorage.getItem("adminToken");
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  
  const response = await fetch(`${BASE_URL}/admin/depot-schedules/${id}`, {
    method: "DELETE",
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
        localStorage.removeItem("adminToken");
        window.location.href = "/login";
    }
    const errorData = await response.json().catch(() => null);
    throw new Error((errorData && errorData.detail) || "API Request Failed");
  }
}

// ----------------------------------------------------------------------------
// Live Operations
// ----------------------------------------------------------------------------
export async function getLiveOperations() {
  return apiFetch("/admin/operations/live");
}

// ----------------------------------------------------------------------------
// Fares
// ----------------------------------------------------------------------------

export interface FareSlabItem {
  id?: string;
  fare_configuration_id?: string;
  min_distance_km: number;
  max_distance_km: number | null;
  fare_amount: number;
}

export interface FareConfigurationItem {
  id: string;
  organization_id: string;
  name: string;
  currency: string;
  effective_from: string;
  effective_until: string | null;
  is_active: boolean;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
  service_id?: string | null;
  service_code?: string | null;
  service_name?: string | null;
  slabs: FareSlabItem[];
}

export function safeNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return isNaN(n) ? null : n;
}

export function normalizeFareSlab(raw: any): FareSlabItem {
  return {
    id: raw?.id,
    fare_configuration_id: raw?.fare_configuration_id,
    min_distance_km: safeNumber(raw?.min_distance_km) ?? 0,
    max_distance_km: safeNumber(raw?.max_distance_km),
    fare_amount: safeNumber(raw?.fare_amount ?? raw?.fare) ?? 0,
  };
}

export function normalizeFareConfig(raw: any): FareConfigurationItem {
  return {
    id: raw?.id || "",
    organization_id: raw?.organization_id || "",
    name: raw?.name || "Untitled Fare",
    currency: raw?.currency || "INR",
    effective_from: raw?.effective_from ? String(raw.effective_from).split("T")[0] : "",
    effective_until: raw?.effective_until ? String(raw.effective_until).split("T")[0] : null,
    is_active: Boolean(raw?.is_active),
    created_by: raw?.created_by,
    created_at: raw?.created_at,
    updated_at: raw?.updated_at,
    service_id: raw?.service_id,
    service_code: raw?.service_code,
    service_name: raw?.service_name,
    slabs: Array.isArray(raw?.slabs)
      ? [...raw.slabs].map(normalizeFareSlab).sort((a, b) => a.min_distance_km - b.min_distance_km)
      : [],
  };
}

export async function getFareConfigurations(): Promise<FareConfigurationItem[]> {
  const data = await apiFetch("/admin/fares/");
  return Array.isArray(data) ? data.map(normalizeFareConfig) : [];
}

export async function getFareConfiguration(id: string): Promise<FareConfigurationItem> {
  const data = await apiFetch(`/admin/fares/${id}`);
  return normalizeFareConfig(data);
}

export async function createFareConfiguration(data: any): Promise<FareConfigurationItem> {
  const result = await apiFetch("/admin/fares/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return normalizeFareConfig(result);
}

export async function updateFareConfiguration(id: string, data: any): Promise<FareConfigurationItem> {
  const result = await apiFetch(`/admin/fares/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return normalizeFareConfig(result);
}

export async function activateFareConfiguration(id: string): Promise<FareConfigurationItem> {
  const result = await apiFetch(`/admin/fares/${id}/activate`, {
    method: "POST",
  });
  return normalizeFareConfig(result);
}

export async function deactivateFareConfiguration(id: string): Promise<FareConfigurationItem> {
  const result = await apiFetch(`/admin/fares/${id}/deactivate`, {
    method: "POST",
  });
  return normalizeFareConfig(result);
}

export async function previewFare(data: {
  route_id: string;
  origin_stop_id: string;
  destination_stop_id: string;
}) {
  return apiFetch("/admin/fares/preview", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ----------------------------------------------------------------------------
// Insights
// ----------------------------------------------------------------------------
export async function getInsights(type: "summary" | "crowding" | "performance" | "fleet" = "summary") {
  return apiFetch(`/admin/insights/${type}`);
}

// ----------------------------------------------------------------------------
// Service Schedules
// ----------------------------------------------------------------------------
export async function getServiceSchedules(serviceId: string) {
  return apiFetch(`/admin/services/${serviceId}/schedules`);
}

export async function createServiceSchedule(serviceId: string, data: any) {
  return apiFetch(`/admin/services/${serviceId}/schedules`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateServiceSchedule(serviceId: string, scheduleId: string, data: any) {
  return apiFetch(`/admin/services/${serviceId}/schedules/${scheduleId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteServiceSchedule(serviceId: string, scheduleId: string) {
  const token = localStorage.getItem("adminToken");
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  
  const response = await fetch(`${BASE_URL}/admin/services/${serviceId}/schedules/${scheduleId}`, {
    method: "DELETE",
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
        localStorage.removeItem("adminToken");
        window.location.href = "/login";
    }
    const errorData = await response.json().catch(() => null);
    throw new Error((errorData && errorData.detail) || "API Request Failed");
  }
}

// ----------------------------------------------------------------------------
// Users
// ----------------------------------------------------------------------------
export async function getAdminUsers(role?: string, status?: string) {
  const params = new URLSearchParams();
  if (role) params.append("role", role);
  if (status) params.append("user_status", status);
  const query = params.toString();
  return apiFetch(`/admin/users/${query ? '?' + query : ''}`);
}

export async function getAdminUser(id: string) {
  return apiFetch(`/admin/users/${id}`);
}

export async function createAdminUser(data: any) {
  return apiFetch("/admin/users/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAdminUser(id: string, data: any) {
  return apiFetch(`/admin/users/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function updateAdminUserPassword(id: string, data: any) {
  return apiFetch(`/admin/users/${id}/password`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function updateAdminUserStatus(id: string, data: any) {
  return apiFetch(`/admin/users/${id}/status`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ----------------------------------------------------------------------------
// Fleet Schedules (Service-Scoped Recurring Timetable)
// ----------------------------------------------------------------------------

export interface PersonnelSummary {
  id: string;
  name: string;
  employee_code?: string | null;
  role: string;
  phone?: string | null;
  email?: string | null;
}

export interface FleetScheduleItem {
  id: string;
  service_id: string;
  vehicle_id: string;
  vehicle_number: string;
  vehicle_type?: string | null;
  registration_number?: string | null;
  vehicle_status?: string | null;
  departure_time: string;
  formatted_departure_time: string;
  direction: "A_TO_B" | "B_TO_A";
  driver?: PersonnelSummary | null;
  conductor?: PersonnelSummary | null;
  every_day: boolean;
  status: string;
  source?: string | null;
  created_at: string;
  updated_at: string;
}

export async function getFleetSchedules(serviceId: string, direction?: "A_TO_B" | "B_TO_A"): Promise<FleetScheduleItem[]> {
  const url = direction
    ? `/admin/fleet-schedules?service_id=${serviceId}&direction=${direction}`
    : `/admin/fleet-schedules?service_id=${serviceId}`;
  return apiFetch(url);
}

export async function createFleetSchedule(data: {
  service_id: string;
  vehicle_id: string;
  direction: "A_TO_B" | "B_TO_A";
  departure_time: string;
  every_day?: boolean;
}): Promise<FleetScheduleItem> {
  return apiFetch("/admin/fleet-schedules", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateFleetSchedule(
  scheduleId: string,
  data: {
    vehicle_id?: string;
    direction?: "A_TO_B" | "B_TO_A";
    departure_time?: string;
    every_day?: boolean;
  }
): Promise<FleetScheduleItem> {
  return apiFetch(`/admin/fleet-schedules/${scheduleId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteFleetSchedule(scheduleId: string): Promise<void> {
  const token = localStorage.getItem("adminToken");
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${BASE_URL}/admin/fleet-schedules/${scheduleId}`, {
    method: "DELETE",
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem("adminToken");
      window.location.href = "/login";
    }
    const errorData = await response.json().catch(() => null);
    throw new Error((errorData && errorData.detail) || "Failed to delete schedule");
  }
}

// ── Major Depot & Depot Schedules ──────────────────────────────────────────

export interface MajorDepot {
  id: string;
  stop_code: string;
  stop_name: string;
  routes_count: number;
}

export interface DepotDepartureItem {
  id: string;
  departure_time: string;
  formatted_departure_time: string;
  vehicle_id: string;
  vehicle_number: string;
  registration_number?: string | null;
  vehicle_type?: string | null;
  vehicle_status: string;
  service_id: string;
  service_name: string;
  service_code: string;
  route_id: string;
  route_code?: string | null;
  route_name?: string | null;
  origin_stop_id: string;
  origin_stop_name: string;
  origin_stop_code?: string | null;
  destination_stop_id: string;
  destination_stop_name: string;
  destination_stop_code?: string | null;
  direction: "A_TO_B" | "B_TO_A";
  status: string;
  every_day: boolean;
  source?: string | null;
  operating_date: string;
}

export async function getMajorDepots(): Promise<MajorDepot[]> {
  return apiFetch("/admin/depot-schedules/major-depots");
}

export async function getDepotDepartures(depotStopId: string): Promise<DepotDepartureItem[]> {
  return apiFetch(`/admin/depot-schedules/departures?depot_stop_id=${depotStopId}`);
}


