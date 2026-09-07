package com.transitplatform.passenger.data.model

data class PassengerStopResponse(
    val id: String,
    val organization_id: String,
    val stop_code: String,
    val name: String,
    val latitude: Double?,
    val longitude: Double?,
    val aliases: List<String> = emptyList()
)
