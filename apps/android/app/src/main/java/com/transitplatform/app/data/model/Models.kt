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
    val tracking_session_status: String?
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
    val status: String,
    val received_at: String,
    val device_status: String,
    val session_status: String?
)
