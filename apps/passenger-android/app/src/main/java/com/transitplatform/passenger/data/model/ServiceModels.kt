package com.transitplatform.passenger.data.model

data class PassengerServiceSearchNearestBus(
    val vehicle_id: String,
    val eta_seconds: Int?,
    val eta_status: String?,
    val crowd_level: String
)

data class PassengerServiceSearchResponse(
    val service_id: String,
    val service_name: String,
    val service_code: String? = null,
    val route_id: String? = null,
    val direction: String,
    val availability_mode: String = "SCHEDULED",
    val departure_mode: String = "SCHEDULED_DEPARTURE",
    val arrival_mode: String = "SCHEDULED_ARRIVAL",
    val departure_timestamp: String? = null,
    val arrival_timestamp: String? = null,
    val expected_arrival_timestamp: String? = null,
    val relative_wait_seconds: Int? = null,
    val relative_message: String? = null,
    val journey_duration_seconds: Int? = null,
    val fare: Double? = null,
    val is_direct: Boolean = true,
    val is_ac: Boolean = false,
    val service_type: String = "REGULAR",
    val absolute_origin: String? = null,
    val absolute_destination: String? = null,
    val searched_origin: String? = null,
    val searched_destination: String? = null,
    val stops_count: Int = 0,
    val active_buses_count: Int = 0,
    val nearest_bus: PassengerServiceSearchNearestBus? = null,
    val ranking_score: Double? = null
)

data class PassengerServiceSummaryResponse(
    val id: String,
    val organization_id: String,
    val service_code: String,
    val service_name: String,
    val route_id: String
)

data class PassengerDepartureResponse(
    val service_id: String,
    val service_name: String,
    val direction: String,
    val route_origin: String,
    val route_destination: String,
    val scheduled_time: String?,
    val expected_time: String?,
    val status: String
)
