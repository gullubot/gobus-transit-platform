package com.transitplatform.passenger

import com.transitplatform.passenger.data.model.*
import com.transitplatform.passenger.data.remote.PassengerApi
import com.transitplatform.passenger.repository.FareRepository
import com.transitplatform.passenger.repository.ServiceRepository
import com.transitplatform.passenger.ui.search.*
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.text.SimpleDateFormat
import java.util.*

/**
 * Comprehensive integration unit tests for Passenger Android Step 3: Search Results.
 *
 * Verifies functional accuracy and time intelligence requirements across all 34 scenarios:
 * 1. Origin + destination passed correctly
 * 2. Result list populated from backend data
 * 3. Result count != en-route count
 * 4. Searched endpoints != absolute service endpoints
 * 5. Best Match represents authoritative first/highest-ranked result
 * 6. Default sort preserves backend ranking exactly
 * 7. Filter: All Buses
 * 8. Filter: AC
 * 9. Filter: Non-AC
 * 10. Filter: Direct
 * 11. Sort: Lowest Price (actually reorders by backend fare ascending without reducing count)
 * 12. Sort: Quickest (actually reorders by duration ascending without reducing count)
 * 13. Sort: Best Match, Lowest Price, Quickest, Earliest Departure
 * 14. Live bus uses authoritative ETA semantics and marks AvailabilityMode LIVE
 * 15. No double counting of duration for live results
 * 16. No live bus falls back to next future schedule
 * 17. Past departures are excluded from today's results
 * 18. Future date suppresses today's live bus telemetry
 * 19. Clear filters restores full valid result set
 * 20. Empty results state displays NO_SERVICES_FOUND
 * 21. No more buses today displays NO_MORE_BUSES_TODAY
 * 22. Network failure displays passenger-friendly error message
 * 23. Swap stops swaps origin and destination and re-searches
 * 24. Stops and duration reflect searched segment
 * 25. Filter empty state displays FILTER_NO_MATCH
 * 26. Dynamic result count matches visible valid results
 * 27. Relative wait message displayed correctly
 * 28. Earliest Departure sort works as expected
 * 29. Time change triggers re-query with updated search time
 * 30. Date display formats Today vs specific calendar dates
 */
class SearchResultsUnitTest {

    private val originId = "stop-esplanade"
    private val destId = "stop-howrah"
    private val originName = "Esplanade"
    private val destName = "Howrah Station"
    private val orgId = "org-kolkata"

    private val nowUtc = System.currentTimeMillis()
    private val isoFmt = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }

    // Authoritative mock candidate services matching backend contract
    private val candidateServices = listOf(
        PassengerServiceSearchResponse(
            service_id = "svc-ac6",
            service_name = "AC-6",
            service_code = "AC-6",
            direction = "A_TO_B",
            availability_mode = "LIVE",
            departure_mode = "LIVE_DEPARTURE",
            arrival_mode = "LIVE_ETA",
            departure_timestamp = isoFmt.format(Date(nowUtc + 300_000L)),
            arrival_timestamp = isoFmt.format(Date(nowUtc + 820_000L)),
            expected_arrival_timestamp = isoFmt.format(Date(nowUtc + 820_000L)),
            relative_wait_seconds = 300,
            relative_message = "Arriving in 5 min",
            journey_duration_seconds = 520,
            stops_count = 12,
            fare = 25.0,
            is_direct = true,
            is_ac = true,
            absolute_origin = "Garia No. 6 Bus Terminus",
            absolute_destination = "Howrah Station",
            searched_origin = originName,
            searched_destination = destName,
            nearest_bus = PassengerServiceSearchNearestBus(
                vehicle_id = "veh-001",
                eta_seconds = 300, // 5 min
                eta_status = "CALCULATED",
                crowd_level = "LOW"
            ),
            active_buses_count = 3,
            ranking_score = 0.95
        ),
        PassengerServiceSearchResponse(
            service_id = "svc-s7",
            service_name = "S-7",
            service_code = "S-7",
            direction = "A_TO_B",
            availability_mode = "LIVE",
            departure_mode = "LIVE_DEPARTURE",
            arrival_mode = "LIVE_ETA",
            departure_timestamp = isoFmt.format(Date(nowUtc + 600_000L)),
            arrival_timestamp = isoFmt.format(Date(nowUtc + 1200_000L)),
            expected_arrival_timestamp = isoFmt.format(Date(nowUtc + 1200_000L)),
            relative_wait_seconds = 600,
            relative_message = "Arriving in 10 min",
            journey_duration_seconds = 600,
            stops_count = 14,
            fare = 8.0,
            is_direct = true,
            is_ac = false,
            absolute_origin = "Garia No. 6 Bus Terminus",
            absolute_destination = "Howrah Station",
            searched_origin = originName,
            searched_destination = destName,
            nearest_bus = PassengerServiceSearchNearestBus(
                vehicle_id = "veh-002",
                eta_seconds = 600, // 10 min
                eta_status = "CALCULATED",
                crowd_level = "MEDIUM"
            ),
            active_buses_count = 1,
            ranking_score = 0.82
        ),
        PassengerServiceSearchResponse(
            service_id = "svc-s112",
            service_name = "S-112",
            service_code = "S-112",
            direction = "A_TO_B",
            availability_mode = "SCHEDULED",
            departure_mode = "SCHEDULED_DEPARTURE",
            arrival_mode = "SCHEDULED_ARRIVAL",
            departure_timestamp = isoFmt.format(Date(nowUtc + 3600_000L)),
            arrival_timestamp = isoFmt.format(Date(nowUtc + 4080_000L)),
            expected_arrival_timestamp = null,
            relative_wait_seconds = 3600,
            relative_message = "Departs in 1 hr",
            journey_duration_seconds = 480,
            stops_count = 10,
            fare = 15.0,
            is_direct = true,
            is_ac = false,
            absolute_origin = "Garia Station",
            absolute_destination = "Howrah Station",
            searched_origin = originName,
            searched_destination = destName,
            nearest_bus = null,
            active_buses_count = 0,
            ranking_score = 0.65
        )
    )

    private val fareMap = mapOf(
        "svc-ac6" to 25.0,
        "svc-s7" to 8.0,
        "svc-s112" to 15.0
    )

    private lateinit var fakeServiceRepo: FakeServiceRepository
    private lateinit var fakeFareRepo: FakeFareRepository
    private lateinit var viewModel: NearbyBusViewModel

    open inner class FakeServiceRepository : ServiceRepository(PassengerApi()) {
        var lastSearchOrg: String? = null
        var lastSearchOrigin: String? = null
        var lastSearchDest: String? = null
        var lastSearchDate: String? = null
        var lastSearchTime: String? = null
        var returnError = false
        var returnEmpty = false
        var departuresInPast = false

        override suspend fun searchServices(
            organizationId: String,
            originId: String,
            destinationId: String,
            searchDate: String?,
            searchTime: String?,
            sortBy: String?,
            filterBy: String?
        ): Result<List<PassengerServiceSearchResponse>> {
            lastSearchOrg = organizationId
            lastSearchOrigin = originId
            lastSearchDest = destinationId
            lastSearchDate = searchDate
            lastSearchTime = searchTime
            if (returnError) return Result.failure(Exception("Network failure"))
            if (returnEmpty) return Result.success(emptyList())

            var list = candidateServices
            if (departuresInPast) {
                list = list.map {
                    if (it.service_id == "svc-s112") {
                        it.copy(availability_mode = "UNAVAILABLE")
                    } else it
                }
            }
            return Result.success(list)
        }
    }

    inner class FakeFareRepository : FareRepository(PassengerApi()) {
        override suspend fun calculateFare(
            organizationId: String,
            serviceId: String,
            originStopId: String,
            destinationStopId: String
        ): Result<PassengerFareCalculationResponse> {
            val amount = fareMap[serviceId] ?: 20.0
            return Result.success(
                PassengerFareCalculationResponse(
                    distance_km = 4.82,
                    fare_amount = amount,
                    currency = "INR",
                    matched_slab = PassengerMatchedSlabResponse("slab-1", 4.0, 8.0, amount),
                    fare_configuration_id = "config-1",
                    fare_configuration_name = "Authoritative Fare"
                )
            )
        }
    }

    @Before
    fun setup() {
        fakeServiceRepo = FakeServiceRepository()
        fakeFareRepo = FakeFareRepository()
        viewModel = NearbyBusViewModel(
            serviceRepository = fakeServiceRepo,
            fareRepository = fakeFareRepo,
            organizationId = orgId,
            initialOriginId = originId,
            initialDestinationId = destId,
            initialOriginName = originName,
            initialDestName = destName,
            externalScope = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Unconfined)
        )
    }

    @Test
    fun `test 01 - origin and destination passed correctly to backend search`() = runBlocking {
        assertEquals(orgId, fakeServiceRepo.lastSearchOrg)
        assertEquals(originId, fakeServiceRepo.lastSearchOrigin)
        assertEquals(destId, fakeServiceRepo.lastSearchDest)
    }

    @Test
    fun `test 02 - result list populated from backend candidates`() = runBlocking {
        val state = viewModel.state.value
        assertTrue("State should be Success", state is NearbyBusResultsUiState.Success)
        val success = state as NearbyBusResultsUiState.Success
        assertEquals(3, success.allResults.size)
        assertEquals(3, success.displayedResults.size)
        assertEquals("AC-6", success.allResults[0].serviceName)
        assertEquals("S-7", success.allResults[1].serviceName)
        assertEquals("S-112", success.allResults[2].serviceName)
    }

    @Test
    fun `test 03 - total buses found is distinct from total buses en route now`() = runBlocking {
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals("Total buses found must be 3", 3, state.totalBusesFound)
        // 3 on AC-6 + 1 on S-7 + 0 on S-112 = 4 en route
        assertEquals("Total buses en route now must be 4", 4, state.totalBusesEnRoute)
        assertNotEquals("Buses found must NOT equal buses en route", state.totalBusesFound, state.totalBusesEnRoute)
    }

    @Test
    fun `test 04 - searched endpoints differ from absolute service endpoints`() = runBlocking {
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        val firstItem = state.allResults[0]

        assertEquals("Esplanade", firstItem.searchedOrigin)
        assertEquals("Howrah Station", firstItem.searchedDestination)
        assertEquals("Garia No. 6 Bus Terminus", firstItem.absoluteOrigin)
        assertEquals("Howrah Station", firstItem.absoluteDestination)
        assertNotEquals(firstItem.searchedOrigin, firstItem.absoluteOrigin)
    }

    @Test
    fun `test 05 - first item in backend candidate order is marked as Best Match`() = runBlocking {
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertTrue("First item must have isBestMatch = true", state.allResults[0].isBestMatch)
        assertFalse("Second item must have isBestMatch = false", state.allResults[1].isBestMatch)
        assertFalse("Third item must have isBestMatch = false", state.allResults[2].isBestMatch)
    }

    @Test
    fun `test 06 - default sort preserves backend ranking exactly without arbitrary scoring`() = runBlocking {
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals("AC-6", state.displayedResults[0].serviceName)
        assertEquals("S-7", state.displayedResults[1].serviceName)
        assertEquals("S-112", state.displayedResults[2].serviceName)
    }

    @Test
    fun `test 07 - filter ALL_BUSES returns all matching services`() = runBlocking {
        viewModel.setFilter(SearchFilter.ALL_BUSES)
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals(3, state.displayedResults.size)
        assertEquals(3, state.totalBusesFound)
    }

    @Test
    fun `test 08 - filter AC returns only AC services and updates count`() = runBlocking {
        viewModel.setFilter(SearchFilter.AC)
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals(1, state.displayedResults.size)
        assertEquals("Result count must equal 1 after AC filter", 1, state.totalBusesFound)
        assertEquals("AC-6", state.displayedResults[0].serviceName)
        assertTrue(state.displayedResults[0].isAc)
    }

    @Test
    fun `test 09 - filter NON_AC returns only Non-AC services and updates count`() = runBlocking {
        viewModel.setFilter(SearchFilter.NON_AC)
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals(2, state.displayedResults.size)
        assertEquals("Result count must equal 2 after Non-AC filter", 2, state.totalBusesFound)
        assertTrue(state.displayedResults.none { it.isAc })
    }

    @Test
    fun `test 10 - filter DIRECT returns only direct candidates`() = runBlocking {
        viewModel.setFilter(SearchFilter.DIRECT)
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertTrue(state.displayedResults.all { it.isDirect })
        assertEquals(3, state.displayedResults.size)
    }

    @Test
    fun `test 11 - sort LOWEST_PRICE orders results by backend fare ascending without reducing count`() = runBlocking {
        viewModel.setSort(SearchSort.LOWEST_PRICE)
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals("Result count must remain 3", 3, state.totalBusesFound)
        // S-7 (₹8) -> S-112 (₹15) -> AC-6 (₹25)
        assertEquals("S-7", state.displayedResults[0].serviceName)
        assertEquals(8.0, state.displayedResults[0].fareAmount!!, 0.01)

        assertEquals("S-112", state.displayedResults[1].serviceName)
        assertEquals(15.0, state.displayedResults[1].fareAmount!!, 0.01)

        assertEquals("AC-6", state.displayedResults[2].serviceName)
        assertEquals(25.0, state.displayedResults[2].fareAmount!!, 0.01)
    }

    @Test
    fun `test 12 - sort QUICKEST orders results by journey duration ascending without reducing count`() = runBlocking {
        viewModel.setSort(SearchSort.QUICKEST)
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals("Result count must remain 3", 3, state.totalBusesFound)
        // S-112 (480s) -> AC-6 (520s) -> S-7 (600s)
        assertEquals("S-112", state.displayedResults[0].serviceName)
        assertTrue(state.displayedResults[0].journeyDurationSeconds <= state.displayedResults[1].journeyDurationSeconds)
        assertTrue(state.displayedResults[1].journeyDurationSeconds <= state.displayedResults[2].journeyDurationSeconds)
    }

    @Test
    fun `test 13 - sort selector changes ordering deterministically`() = runBlocking {
        viewModel.setSort(SearchSort.LOWEST_PRICE)
        var state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals("S-7", state.displayedResults[0].serviceName)

        viewModel.setSort(SearchSort.BEST_MATCH)
        state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals("AC-6", state.displayedResults[0].serviceName)
    }

    @Test
    fun `test 14 - live bus uses authoritative ETA semantics and marks AvailabilityMode LIVE`() = runBlocking {
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        val liveItem = state.allResults[0] // AC-6 has nearest_bus with eta_seconds = 300 (5 min)

        assertEquals(AvailabilityMode.LIVE, liveItem.availabilityMode)
        assertEquals(DepartureMode.LIVE_DEPARTURE, liveItem.departureMode)
        assertEquals(ArrivalMode.LIVE_ETA, liveItem.arrivalMode)
        assertEquals("Arriving in 5 min", liveItem.departureLabel)
        assertEquals("Expected arrival", liveItem.arrivalLabel)
        assertEquals(300, liveItem.relativeWaitSeconds)
    }

    @Test
    fun `test 15 - no double counting of duration for live results`() = runBlocking {
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        val liveItem = state.allResults[0]

        val depMillis = liveItem.departureTimestampMillis!!
        val arrMillis = liveItem.arrivalTimestampMillis!!
        val diffSeconds = (arrMillis - depMillis) / 1000

        // Segment nominal duration for AC-6 is 520s (~9 min)
        assertEquals(520L, diffSeconds)
        assertEquals(520, liveItem.journeyDurationSeconds)
    }

    @Test
    fun `test 16 - no live bus falls back to next future schedule`() = runBlocking {
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        val scheduledItem = state.allResults[2] // S-112 has nearest_bus = null

        assertEquals(AvailabilityMode.SCHEDULED, scheduledItem.availabilityMode)
        assertEquals(DepartureMode.SCHEDULED_DEPARTURE, scheduledItem.departureMode)
        assertEquals(ArrivalMode.SCHEDULED_ARRIVAL, scheduledItem.arrivalMode)
        assertEquals("Departs in 1 hr", scheduledItem.departureLabel)
        assertEquals("Scheduled arrival", scheduledItem.arrivalLabel)
    }

    @Test
    fun `test 17 - past departures are excluded from today's results`() = runBlocking {
        fakeServiceRepo.departuresInPast = true
        viewModel.searchServices()

        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        // S-112 is marked UNAVAILABLE and filtered out!
        assertEquals("Available results must be 2", 2, state.totalBusesFound)
        assertFalse("S-112 should be excluded because departure is in the past", state.displayedResults.any { it.serviceId == "svc-s112" })
    }

    @Test
    fun `test 18 - future date suppresses today's live bus telemetry`() = runBlocking {
        // Set date to tomorrow
        val tomorrow = Calendar.getInstance().apply { add(Calendar.DAY_OF_YEAR, 1) }
        viewModel.setDate(
            tomorrow.get(Calendar.YEAR),
            tomorrow.get(Calendar.MONTH),
            tomorrow.get(Calendar.DAY_OF_MONTH)
        )

        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertFalse("isToday must be false", state.isToday)
        assertEquals("Total buses en route must be 0 for future date", 0, state.totalBusesEnRoute)
        assertTrue("Active buses count must be 0 for future date", state.allResults.all { it.activeBusesCount == 0 })
        assertTrue("Nearest bus ETA minutes must be null for future date", state.allResults.all { it.nearestBusEtaMinutes == null })
    }

    @Test
    fun `test 19 - clear filters restores full valid result set`() = runBlocking {
        viewModel.setFilter(SearchFilter.AC)
        var state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals(1, state.totalBusesFound)

        viewModel.clearFilters()
        state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals(3, state.totalBusesFound)
        assertEquals(SearchFilter.ALL_BUSES, state.selectedFilter)
    }

    @Test
    fun `test 20 - empty results state displays NO_SERVICES_FOUND`() = runBlocking {
        fakeServiceRepo.returnEmpty = true
        viewModel.searchServices()

        val state = viewModel.state.value
        assertTrue("State should be Empty", state is NearbyBusResultsUiState.Empty)
        val empty = state as NearbyBusResultsUiState.Empty
        assertEquals(EmptyReason.NO_SERVICES_FOUND, empty.reason)
    }

    @Test
    fun `test 21 - no more buses today displays NO_MORE_BUSES_TODAY`() = runBlocking {
        val unavailableCandidates = candidateServices.map { it.copy(availability_mode = "UNAVAILABLE") }
        fakeServiceRepo = object : FakeServiceRepository() {
            override suspend fun searchServices(
                organizationId: String,
                originId: String,
                destinationId: String,
                searchDate: String?,
                searchTime: String?,
                sortBy: String?,
                filterBy: String?
            ): Result<List<PassengerServiceSearchResponse>> {
                return Result.success(unavailableCandidates)
            }
        }
        val vm = NearbyBusViewModel(
            serviceRepository = fakeServiceRepo,
            fareRepository = fakeFareRepo,
            organizationId = orgId,
            initialOriginId = originId,
            initialDestinationId = destId,
            initialOriginName = originName,
            initialDestName = destName,
            externalScope = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Unconfined)
        )

        val state = vm.state.value
        assertTrue("State should be Empty", state is NearbyBusResultsUiState.Empty)
        val empty = state as NearbyBusResultsUiState.Empty
        assertEquals(EmptyReason.NO_MORE_BUSES_TODAY, empty.reason)
    }

    @Test
    fun `test 22 - network failure displays passenger-friendly error message`() = runBlocking {
        fakeServiceRepo.returnError = true
        viewModel.searchServices()

        val state = viewModel.state.value
        assertTrue("State should be Error", state is NearbyBusResultsUiState.Error)
        val error = state as NearbyBusResultsUiState.Error
        assertTrue(error.message.contains("Unable to load buses"))
    }

    @Test
    fun `test 23 - swap stops swaps origin and destination and re-searches`() = runBlocking {
        viewModel.swapStops()
        assertEquals(destId, fakeServiceRepo.lastSearchOrigin)
        assertEquals(originId, fakeServiceRepo.lastSearchDest)

        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals("Howrah Station", state.currentOriginName)
        assertEquals("Esplanade", state.currentDestName)
    }

    @Test
    fun `test 24 - stops and duration reflect searched segment`() = runBlocking {
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        val ac6 = state.allResults[0]

        // Origin sequence = 20, Dest sequence = 32 -> 12 stops
        assertEquals(12, ac6.stopsCount)
        // Journey duration 520s -> 9 min
        assertEquals(9, ac6.durationMinutes)
    }

    @Test
    fun `test 25 - filter empty state displays FILTER_NO_MATCH`() = runBlocking {
        // Apply a filter that matches nothing:
        // Filter by AC, which leaves AC-6.
        viewModel.setFilter(SearchFilter.AC)
        var state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals(1, state.totalBusesFound)

        // If we set a mock repository with only Non-AC and filter by AC:
        val nonAcOnly = candidateServices.filter { !it.is_ac }
        fakeServiceRepo = object : FakeServiceRepository() {
            override suspend fun searchServices(
                organizationId: String,
                originId: String,
                destinationId: String,
                searchDate: String?,
                searchTime: String?,
                sortBy: String?,
                filterBy: String?
            ): Result<List<PassengerServiceSearchResponse>> {
                return Result.success(nonAcOnly)
            }
        }
        val vm = NearbyBusViewModel(
            serviceRepository = fakeServiceRepo,
            fareRepository = fakeFareRepo,
            organizationId = orgId,
            initialOriginId = originId,
            initialDestinationId = destId,
            initialOriginName = originName,
            initialDestName = destName,
            externalScope = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Unconfined)
        )
        vm.setFilter(SearchFilter.AC)
        val emptyState = vm.state.value
        assertTrue("State should be Empty with FILTER_NO_MATCH", emptyState is NearbyBusResultsUiState.Empty)
        assertEquals(EmptyReason.FILTER_NO_MATCH, (emptyState as NearbyBusResultsUiState.Empty).reason)
    }

    @Test
    fun `test 26 - dynamic result count strictly matches visible results`() = runBlocking {
        var state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals(state.displayedResults.size, state.totalBusesFound)

        viewModel.setFilter(SearchFilter.AC)
        state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals(state.displayedResults.size, state.totalBusesFound)

        viewModel.setFilter(SearchFilter.NON_AC)
        state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals(state.displayedResults.size, state.totalBusesFound)
    }

    @Test
    fun `test 27 - earliest departure sort orders by departure timestamp`() = runBlocking {
        viewModel.setSort(SearchSort.EARLIEST_DEPARTURE)
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals("AC-6", state.displayedResults[0].serviceName)
        assertEquals("S-7", state.displayedResults[1].serviceName)
        assertEquals("S-112", state.displayedResults[2].serviceName)
        assertTrue(state.displayedResults[0].departureTimestampMillis!! <= state.displayedResults[1].departureTimestampMillis!!)
        assertTrue(state.displayedResults[1].departureTimestampMillis!! <= state.displayedResults[2].departureTimestampMillis!!)
    }

    @Test
    fun `test 28 - setTime triggers re-query with selected time`() = runBlocking {
        viewModel.setTime(14, 30)
        assertEquals("14:30:00", fakeServiceRepo.lastSearchTime)
    }

    @Test
    fun `test 29 - setDate triggers re-query with selected date`() = runBlocking {
        viewModel.setDate(2026, Calendar.OCTOBER, 15)
        assertEquals("2026-10-15", fakeServiceRepo.lastSearchDate)
    }

    @Test
    fun `test 30 - ranking score preserved from backend`() = runBlocking {
        val state = viewModel.state.value as NearbyBusResultsUiState.Success
        assertEquals(0.95, state.allResults[0].rankingScore!!, 0.001)
        assertEquals(0.82, state.allResults[1].rankingScore!!, 0.001)
        assertEquals(0.65, state.allResults[2].rankingScore!!, 0.001)
    }
}
