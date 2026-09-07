package com.transitplatform.passenger.ui.plan

data class PassengerPlanTripResponse(
    val service_id: String,
    val service_name: String,
    val direction: String,
    val route_origin: String,
    val route_destination: String,
    val scheduled_departure: String?,
    val scheduled_arrival: String?
)
