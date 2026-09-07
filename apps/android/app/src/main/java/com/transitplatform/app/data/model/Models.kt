package com.transitplatform.app.data.model

data class LoginResponse(
    val access_token: String,
    val token_type: String,
    val user_id: String,
    val name: String,
    val role: String,
    val employee_code: String,
    val organization_id: String,
    val organization_name: String
)

data class AssignmentResponse(
    val assignment_id: String,
    val trip_id: String,
    val service_id: String,
    val service_code: String,
    val service_name: String,
    val route_id: String,
    val route_code: String,
    val route_name: String,
    val direction: String,
    val vehicle_id: String,
    val vehicle_number: String,
    val planned_start_at: String,
    val trip_status: String,
    val operator_role: String,
    val assignment_status: String,
    val assigned_device_id: String?,
    val assigned_device_status: String?,
    val active_tracking_session_id: String?,
    val tracking_session_status: String?,
    val vehicle_registration: String? = null,
    val vehicle_type: String? = null,
    val origin_stop_name: String? = null,
    val destination_stop_name: String? = null,
    val route_distance_km: Double? = null
)

data class TripStartResponse(
    val tracking_session_id: String,
    val trip_id: String,
    val device_id: String,
    val status: String,
    val started_at: String
)

data class TripEndResponse(
    val tracking_session_id: String,
    val trip_id: String,
    val status: String,
    val ended_at: String
)

data class BatchAckResponse(
    val accepted: List<String>,
    val duplicates: List<String>,
    val retryable: List<String>,
    val rejected: List<Map<String, Any>>
)

data class HeartbeatResponse(
    val device_id: String = "",
    val status: String,
    val received_at: String,
    val device_status: String,
    val session_status: String?
)

data class OperatorTripResponse(
    val trip_id: String,
    val assignment_id: String,
    val service_code: String,
    val service_name: String,
    val route_code: String,
    val route_name: String,
    val direction: String,
    val vehicle_number: String,
    val vehicle_registration: String? = null,
    val vehicle_type: String? = null,
    val planned_start_at: String,
    val actual_start_at: String? = null,
    val actual_end_at: String? = null,
    val trip_status: String,
    val assignment_status: String,
    val operator_role: String,
    val origin_stop_name: String? = null,
    val destination_stop_name: String? = null,
    val route_distance_km: Double? = null,
    val is_next: Boolean = false
)

data class OperatorIssueResponse(
    val alert_id: String,
    val trip_id: String,
    val service_id: String? = null,
    val route_id: String? = null,
    val scope: String,
    val status: String,
    val type: String,
    val severity: String,
    val title: String,
    val message: String,
    val created_at: String,
    val created_by: String? = null
)

