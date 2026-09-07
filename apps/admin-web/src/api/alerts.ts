import { apiFetch } from "./api";

export const AlertScope = {
  SERVICE: "SERVICE",
  ROUTE: "ROUTE",
  STOP: "STOP",
  TRIP: "TRIP",
} as const;
export type AlertScope = typeof AlertScope[keyof typeof AlertScope];

export const AlertStatus = {
  OPEN: "OPEN",
  ACKNOWLEDGED: "ACKNOWLEDGED",
  RESOLVED: "RESOLVED",
} as const;
export type AlertStatus = typeof AlertStatus[keyof typeof AlertStatus];

export const AlertSeverity = {
  INFO: "INFO",
  WARNING: "WARNING",
  CRITICAL: "CRITICAL",
} as const;
export type AlertSeverity = typeof AlertSeverity[keyof typeof AlertSeverity];

export interface AlertEntityContext {
  vehicle_id?: string | null;
  vehicle_number?: string | null;
  service_id?: string | null;
  service_code?: string | null;
  service_name?: string | null;
  route_id?: string | null;
  route_code?: string | null;
  route_name?: string | null;
  stop_id?: string | null;
  stop_code?: string | null;
  stop_name?: string | null;
}

export interface SuggestedAction {
  label: string;
  destination: string;
  action_type: string;
  reason: string;
}

export interface SuggestedResolution {
  recommended_action: string;
  reason: string;
  observed: string;
  actions: SuggestedAction[];
}

export interface AlertMetrics {
  active: number;
  critical: number;
  warning: number;
  resolved: number;
  open: number;
  acknowledged: number;
}

export interface ServiceAlert {
  id: string;
  organization_id: string;
  service_id?: string | null;
  route_id?: string | null;
  stop_id?: string | null;
  trip_id?: string | null;
  scope: AlertScope;
  status: AlertStatus;
  type: string;
  incident_fingerprint: string;
  title: string;
  message: string;
  suggested_solution?: string | null;
  severity: AlertSeverity;
  effective_from?: string | null;
  effective_until?: string | null;
  created_by?: string | null;
  acknowledged_by?: string | null;
  acknowledged_at?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;

  // Operational triage & enrichment
  urgency_score: number;
  urgency_rank?: string | null;
  entity_context?: AlertEntityContext | null;
  suggested_resolution?: SuggestedResolution | null;
}

export interface AlertListResponse {
  data: ServiceAlert[];
  total: number;
  metrics: AlertMetrics;
}

export const fetchAlerts = async (params?: {
  status?: AlertStatus;
  severity?: AlertSeverity;
  type?: string;
  search?: string;
  service_id?: string;
  route_id?: string;
  limit?: number;
  offset?: number;
}): Promise<AlertListResponse> => {
  const query = new URLSearchParams();
  if (params?.status) query.append("status", params.status);
  if (params?.severity) query.append("severity", params.severity);
  if (params?.type) query.append("type", params.type);
  if (params?.search && params.search.trim()) query.append("search", params.search.trim());
  if (params?.service_id) query.append("service_id", params.service_id);
  if (params?.route_id) query.append("route_id", params.route_id);
  if (params?.limit) query.append("limit", params.limit.toString());
  if (params?.offset !== undefined) query.append("offset", params.offset.toString());

  return apiFetch(`/admin/alerts?${query.toString()}`);
};

export const fetchAlert = async (id: string): Promise<ServiceAlert> => {
  return apiFetch(`/admin/alerts/${id}`);
};

export const acknowledgeAlert = async (id: string): Promise<ServiceAlert> => {
  return apiFetch(`/admin/alerts/${id}/acknowledge`, { method: "PUT", body: "{}" });
};

export const resolveAlert = async (id: string): Promise<ServiceAlert> => {
  return apiFetch(`/admin/alerts/${id}/resolve`, { method: "PUT", body: "{}" });
};
