package com.transitplatform.passenger.repository

import com.transitplatform.passenger.data.model.PassengerLiveBusResponse
import com.transitplatform.passenger.data.model.PassengerServiceDetailResponse
import com.transitplatform.passenger.data.remote.PassengerApi

class LiveServiceRepository(
    private val api: PassengerApi
) {
    suspend fun getServiceDetails(serviceId: String): Result<PassengerServiceDetailResponse> {
        return api.getServiceDetails(serviceId)
    }

    suspend fun getLiveBuses(serviceId: String): Result<List<PassengerLiveBusResponse>> {
        return api.getLiveBuses(serviceId)
    }
}
