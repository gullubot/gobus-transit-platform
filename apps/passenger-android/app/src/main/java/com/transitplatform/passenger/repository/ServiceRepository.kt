package com.transitplatform.passenger.repository

import com.transitplatform.passenger.data.model.PassengerServiceSearchResponse
import com.transitplatform.passenger.data.remote.PassengerApi

import com.transitplatform.passenger.data.model.PassengerServiceSummaryResponse
import com.transitplatform.passenger.data.model.PassengerDepartureResponse
import com.transitplatform.passenger.data.model.PassengerServiceDetailResponse

open class ServiceRepository(
    private val api: PassengerApi
) {
    open suspend fun searchServices(
        organizationId: String,
        originId: String,
        destinationId: String,
        searchDate: String? = null,
        searchTime: String? = null,
        sortBy: String? = "BEST_MATCH",
        filterBy: String? = "ALL"
    ): Result<List<PassengerServiceSearchResponse>> {
        return api.searchServices(organizationId, originId, destinationId, searchDate, searchTime, sortBy, filterBy)
    }

    open suspend fun getServices(
        organizationId: String
    ): Result<List<PassengerServiceSummaryResponse>> {
        return api.getServices(organizationId)
    }

    open suspend fun getServiceDetails(
        serviceId: String
    ): Result<PassengerServiceDetailResponse> {
        return api.getServiceDetails(serviceId)
    }

    open suspend fun getStopDepartures(
        stopId: String,
        serviceId: String,
        direction: String
    ): Result<List<PassengerDepartureResponse>> {
        return api.getStopDepartures(stopId, serviceId, direction)
    }

    open suspend fun planTrip(
        organizationId: String,
        originId: String,
        destinationId: String,
        date: String,
        time: String
    ): Result<List<com.transitplatform.passenger.ui.plan.PassengerPlanTripResponse>> {
        return api.planTrip(organizationId, originId, destinationId, date, time)
    }
}
