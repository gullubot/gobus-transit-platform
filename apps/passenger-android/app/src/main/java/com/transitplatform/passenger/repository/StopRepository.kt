package com.transitplatform.passenger.repository

import com.transitplatform.passenger.data.model.PassengerStopResponse
import com.transitplatform.passenger.data.remote.PassengerApi

class StopRepository(
    private val api: PassengerApi
) {
    suspend fun getStops(organizationId: String): Result<List<PassengerStopResponse>> {
        return api.getStops(organizationId)
    }
}
