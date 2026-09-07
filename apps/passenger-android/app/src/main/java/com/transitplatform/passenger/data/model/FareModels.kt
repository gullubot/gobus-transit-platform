package com.transitplatform.passenger.data.model

/**
 * Passenger-safe fare response models.
 * Mapped exactly to the backend GET /api/passenger/fares/calculate response.
 * Android performs ZERO fare calculation — these are display-only containers.
 */

data class PassengerMatchedSlabResponse(
    val id: String,
    val min_distance_km: Double,
    val max_distance_km: Double?,
    val fare_amount: Double
)

data class PassengerFareCalculationResponse(
    val distance_km: Double,
    val fare_amount: Double,
    val currency: String,
    val matched_slab: PassengerMatchedSlabResponse,
    val fare_configuration_id: String,
    val fare_configuration_name: String
)
