package com.transitplatform.passenger.repository

import com.transitplatform.passenger.data.model.PassengerFareCalculationResponse
import com.transitplatform.passenger.data.remote.PassengerApi

/**
 * Repository for fare calculation.
 * Delegates entirely to the backend — performs ZERO local fare math,
 * distance calculation, slab selection, or rounding.
 */
open class FareRepository(
    private val api: PassengerApi
) {
    open suspend fun calculateFare(
        organizationId: String,
        serviceId: String,
        originStopId: String,
        destinationStopId: String
    ): Result<PassengerFareCalculationResponse> {
        return api.calculateFare(organizationId, serviceId, originStopId, destinationStopId)
    }
}
