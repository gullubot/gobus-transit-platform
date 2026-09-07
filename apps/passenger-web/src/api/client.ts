const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * GoBus Passenger API Client.
 *
 * Centralized fetch wrapper that handles:
 * - Base URL configuration
 * - Authentication headers (JWT)
 * - Organization/city scoping
 * - JSON parsing
 * - Error handling
 */

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  // Attach auth token if present
  const token = localStorage.getItem('gobus_access_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(response.status, detail);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * Append city or organization_id to query params if a city is selected.
 */
function withCity(path: string, extraParams?: Record<string, string>): string {
  const cityName = localStorage.getItem('gobus_city_name');
  const cityId = localStorage.getItem('gobus_city_id');
  const params = new URLSearchParams();
  if (cityName) {
    params.set('city', cityName);
  } else if (cityId) {
    params.set('city', cityId);
  }
  if (extraParams) {
    for (const [k, v] of Object.entries(extraParams)) {
      params.set(k, v);
    }
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

// ── Public API ──────────────────────────────────────────────────────

export const api = {
  // Auth
  login(phone: string, name: string) {
    return request<{
      access_token: string;
      token_type: string;
      user_id: string;
      name: string;
      role: string;
      phone: string;
    }>('/api/auth/passenger/login', {
      method: 'POST',
      body: JSON.stringify({ phone, name }),
    });
  },

  // Cities
  getCities() {
    return request<Array<{ id: string; name: string }>>('/api/passenger/cities');
  },

  // Organizations (kept for backward compatibility)
  getOrganizations() {
    return request<Array<{ id: string; name: string }>>('/api/passenger/organizations');
  },

  // Stops
  getStops(search?: string) {
    return request<Array<{
      id: string;
      organization_id: string;
      stop_code: string;
      name: string;
      latitude: number | null;
      longitude: number | null;
      aliases?: string[];
    }>>(withCity('/api/passenger/stops', search ? { search } : undefined));
  },

  // Services
  getServices() {
    return request<Array<{
      id: string;
      organization_id: string;
      service_code: string;
      service_name: string;
      route_id: string;
    }>>(withCity('/api/passenger/services'));
  },

  // Service detail
  getServiceDetail(serviceId: string) {
    return request<{
      id: string;
      organization_id: string;
      service_code: string;
      service_name: string;
      route_id: string;
      route_code: string;
      route_name: string;
      route_geometry: { type: string, coordinates: number[][] } | null;
      stops: Array<{
        stop_id: string;
        stop_name: string;
        sequence_number: number;
        latitude: number | null;
        longitude: number | null;
        distance_from_start: number | null;
        nominal_travel_time_seconds: number | null;
      }>;
      schedules: Array<{
        direction: string;
        start_time: string;
        end_time: string;
        typical_interval_minutes: number;
        days_of_week: number[] | null;
      }>;
    }>(withCity(`/api/passenger/services/${serviceId}`));
  },

  // Service search
  searchServices(originId: string, destinationId: string) {
    return request<Array<{
      service_id: string;
      service_name: string;
      direction: string;
      nearest_bus: {
        bus_id: string;
        status: string;
        eta_seconds: number | null;
        crowd_level: string;
      } | null;
      active_buses_count: number;
    }>>(withCity('/api/passenger/services/search', {
      origin_id: originId,
      destination_id: destinationId,
    }));
  },

  // Get nearest bus
  getNearestBus(serviceId: string, originId: string, destinationId: string) {
    return request<{
      bus_id: string;
      status: string;
      eta_seconds: number | null;
      crowd_level: string;
    }>(withCity(`/api/passenger/services/${serviceId}/nearest-bus`, {
      origin_id: originId,
      destination_id: destinationId,
    }));
  },

  // Live buses for service
  getServiceLive(serviceId: string) {
    return request<Array<{
      vehicle_id: string;
      latitude: number | null;
      longitude: number | null;
      direction: string | null;
      current_stop_id: string | null;
      next_stop_id: string | null;
      eta_seconds: number | null;
      eta_status: string | null;
      crowd_level: string;
      state: string;
      last_updated_at: string | null;
    }>>(withCity(`/api/passenger/services/${serviceId}/live`));
  },

  // Departures for stop
  getStopDepartures(stopId: string, serviceId?: string, direction?: string) {
    const params: Record<string, string> = {};
    if (serviceId) params.service_id = serviceId;
    if (direction) params.direction = direction;
    
    return request<Array<{
      service_id: string;
      service_name: string;
      direction: string;
      route_origin: string;
      route_destination: string;
      scheduled_time: string | null;
      expected_time: string | null;
      status: string;
    }>>(withCity(`/api/passenger/stops/${stopId}/departures`, Object.keys(params).length > 0 ? params : undefined));
  },

  // Plan trip
  planTrip(originId: string, destinationId: string, date: string, time: string) {
    return request<Array<{
      service_id: string;
      service_name: string;
      direction: string;
      route_origin: string;
      route_destination: string;
      scheduled_departure: string | null;
      scheduled_arrival: string | null;
    }>>(withCity('/api/passenger/plan', {
      origin_id: originId,
      destination_id: destinationId,
      date,
      time,
    }));
  },
};

export { ApiError };
