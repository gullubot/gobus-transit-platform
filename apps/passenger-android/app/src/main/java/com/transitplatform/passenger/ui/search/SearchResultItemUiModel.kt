package com.transitplatform.passenger.ui.search

/**
 * Explicit operational availability mode of a search result.
 */
enum class AvailabilityMode {
    LIVE,
    SCHEDULED,
    UNAVAILABLE
}

/**
 * Explicit semantics of the passenger's boarding departure.
 */
enum class DepartureMode {
    LIVE_DEPARTURE,
    SCHEDULED_DEPARTURE
}

/**
 * Explicit semantics of the destination arrival time.
 */
enum class ArrivalMode {
    LIVE_ETA,
    SCHEDULED_ARRIVAL
}

/**
 * Presentation UI model representing a single service result card
 * on the Passenger Search Results screen.
 *
 * Distinguishes strictly between:
 * - absoluteOrigin / absoluteDestination: The actual terminal endpoints of the service route
 * - searchedOrigin / searchedDestination: The specific boarding and alighting stops searched by the passenger
 */
data class SearchResultItemUiModel(
    val serviceId: String,
    val serviceName: String,
    val serviceCode: String? = null,
    val direction: String,
    val absoluteOrigin: String,
    val absoluteDestination: String,
    val searchedOrigin: String,
    val searchedDestination: String,
    val departureTimeFormatted: String,
    val arrivalTimeFormatted: String,
    val departureLabel: String = "Departure",
    val arrivalLabel: String = "Arrival",
    val departureTimestampMillis: Long? = null,
    val arrivalTimestampMillis: Long? = null,
    val expectedArrivalTimestampMillis: Long? = null,
    val relativeWaitSeconds: Int? = null,
    val relativeMessage: String? = null,
    val availabilityMode: AvailabilityMode = AvailabilityMode.SCHEDULED,
    val departureMode: DepartureMode = DepartureMode.SCHEDULED_DEPARTURE,
    val arrivalMode: ArrivalMode = ArrivalMode.SCHEDULED_ARRIVAL,
    val durationMinutes: Int,
    val journeyDurationSeconds: Int = 0,
    val stopsCount: Int,
    val fareAmount: Double?,
    val currency: String = "₹",
    val isAc: Boolean,
    val isDirect: Boolean,
    val crowdLevel: String?,
    val activeBusesCount: Int,
    val nearestBusEtaSeconds: Int?,
    val nearestBusEtaMinutes: Int?,
    val isBestMatch: Boolean = false,
    val isLowestPrice: Boolean = false,
    val isQuickest: Boolean = false,
    val rankingScore: Double? = null
)

enum class SearchFilter(val label: String) {
    ALL_BUSES("All Buses"),
    AC("AC"),
    NON_AC("Non-AC"),
    DIRECT("Direct")
}

enum class SearchSort(val label: String) {
    BEST_MATCH("Best Match"),
    LOWEST_PRICE("Lowest Price"),
    QUICKEST("Quickest"),
    EARLIEST_DEPARTURE("Earliest Departure")
}

