package com.transitplatform.passenger.data.model

data class RouteStopDetail(
    val stop_id: String,
    val stop_name: String,
    val sequence_number: Int,
    val latitude: Double?,
    val longitude: Double?,
    val nominal_travel_time_seconds: Int? = null
)

data class PassengerServiceDetailResponse(
    val id: String,
    val service_name: String,
    val route_name: String,
    val route_geometry: String?, // We'll keep it as String for the GeoJSON parsing or parse JSON
    val stops: List<RouteStopDetail>
)

data class PassengerLiveBusResponse(
    val vehicle_id: String,
    val latitude: Double?,
    val longitude: Double?,
    val direction: String?,
    val current_stop_id: String?,
    val next_stop_id: String?,
    val eta_seconds: Int?,
    val eta_status: String?,
    val crowd_level: String,
    val state: String,
    val last_updated_at: String?
)
