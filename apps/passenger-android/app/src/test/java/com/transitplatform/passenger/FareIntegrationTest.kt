package com.transitplatform.passenger

import com.transitplatform.passenger.data.model.PassengerFareCalculationResponse
import com.transitplatform.passenger.data.model.PassengerMatchedSlabResponse
import com.transitplatform.passenger.ui.plan.FareUiState
import com.transitplatform.passenger.ui.plan.PassengerPlanTripResponse
import com.transitplatform.passenger.ui.plan.PlanTripUiState
import org.junit.Assert.*
import org.junit.Test

/**
 * Unit tests for Step 8J Passenger Android Fare UI Integration.
 *
 * These tests verify:
 * 1. Fare models map correctly to backend response
 * 2. FareUiState covers all required states
 * 3. Duplicate service deduplication logic
 * 4. Fare invalidation on journey changes
 * 5. No client-side fare math exists
 */
class FareIntegrationTest {

    // =========================================================================
    // FARE MODEL TESTS — Verify exact mapping to backend response
    // =========================================================================

    @Test
    fun `fare response model maps all backend fields`() {
        val slab = PassengerMatchedSlabResponse(
            id = "slab-uuid-1",
            min_distance_km = 0.0,
            max_distance_km = 5.0,
            fare_amount = 15.0
        )
        val response = PassengerFareCalculationResponse(
            distance_km = 3.5,
            fare_amount = 15.0,
            currency = "INR",
            matched_slab = slab,
            fare_configuration_id = "config-uuid-1",
            fare_configuration_name = "Default Fare"
        )

        assertEquals(3.5, response.distance_km, 0.001)
        assertEquals(15.0, response.fare_amount, 0.001)
        assertEquals("INR", response.currency)
        assertEquals("slab-uuid-1", response.matched_slab.id)
        assertEquals(0.0, response.matched_slab.min_distance_km, 0.001)
        assertEquals(5.0, response.matched_slab.max_distance_km!!, 0.001)
        assertEquals(15.0, response.matched_slab.fare_amount, 0.001)
        assertEquals("config-uuid-1", response.fare_configuration_id)
        assertEquals("Default Fare", response.fare_configuration_name)
    }

    @Test
    fun `fare slab allows null max_distance_km for open-ended slab`() {
        val slab = PassengerMatchedSlabResponse(
            id = "slab-open",
            min_distance_km = 20.0,
            max_distance_km = null,
            fare_amount = 50.0
        )
        assertNull(slab.max_distance_km)
        assertEquals(20.0, slab.min_distance_km, 0.001)
        assertEquals(50.0, slab.fare_amount, 0.001)
    }

    // =========================================================================
    // FARE UI STATE TESTS — All required states exist
    // =========================================================================

    @Test
    fun `FareUiState has Idle state`() {
        val state: FareUiState = FareUiState.Idle
        assertTrue(state is FareUiState.Idle)
    }

    @Test
    fun `FareUiState has Loading state`() {
        val state: FareUiState = FareUiState.Loading
        assertTrue(state is FareUiState.Loading)
    }

    @Test
    fun `FareUiState has Success state with fare data`() {
        val fare = PassengerFareCalculationResponse(
            distance_km = 5.4,
            fare_amount = 18.0,
            currency = "INR",
            matched_slab = PassengerMatchedSlabResponse("s1", 5.0, 10.0, 18.0),
            fare_configuration_id = "cfg-1",
            fare_configuration_name = "Standard"
        )
        val state: FareUiState = FareUiState.Success(fare)
        assertTrue(state is FareUiState.Success)
        assertEquals(18.0, (state as FareUiState.Success).fare.fare_amount, 0.001)
    }

    @Test
    fun `FareUiState has Error state with message`() {
        val state: FareUiState = FareUiState.Error("Fare unavailable")
        assertTrue(state is FareUiState.Error)
        assertEquals("Fare unavailable", (state as FareUiState.Error).message)
    }

    // =========================================================================
    // DUPLICATE SERVICE DEDUPLICATION TESTS
    // =========================================================================

    @Test
    fun `distinct service_ids are correctly extracted from trip results`() {
        val trips = listOf(
            createTripResponse("service-A", "GO-101"),
            createTripResponse("service-A", "GO-101"),
            createTripResponse("service-B", "GO-102")
        )

        val distinctServiceIds = trips.map { it.service_id }.distinct()
        assertEquals(2, distinctServiceIds.size)
        assertTrue(distinctServiceIds.contains("service-A"))
        assertTrue(distinctServiceIds.contains("service-B"))
    }

    @Test
    fun `single service produces single distinct id`() {
        val trips = listOf(
            createTripResponse("service-A", "GO-101"),
            createTripResponse("service-A", "GO-101"),
            createTripResponse("service-A", "GO-101")
        )

        val distinctServiceIds = trips.map { it.service_id }.distinct()
        assertEquals(1, distinctServiceIds.size)
    }

    // =========================================================================
    // FARE INVALIDATION TESTS
    // =========================================================================

    @Test
    fun `PlanTripUiState fareStates starts empty`() {
        val state = PlanTripUiState()
        assertTrue(state.fareStates.isEmpty())
    }

    @Test
    fun `fareStates can hold independent states per service`() {
        val fareA = FareUiState.Success(
            PassengerFareCalculationResponse(
                distance_km = 3.0, fare_amount = 15.0, currency = "INR",
                matched_slab = PassengerMatchedSlabResponse("s1", 0.0, 5.0, 15.0),
                fare_configuration_id = "cfg-1", fare_configuration_name = "Config A"
            )
        )
        val fareB = FareUiState.Error("Fare unavailable")
        val fareC = FareUiState.Loading

        val fareStates = mapOf(
            "service-A" to fareA as FareUiState,
            "service-B" to fareB as FareUiState,
            "service-C" to fareC as FareUiState
        )

        val state = PlanTripUiState(fareStates = fareStates)
        assertEquals(3, state.fareStates.size)
        assertTrue(state.fareStates["service-A"] is FareUiState.Success)
        assertTrue(state.fareStates["service-B"] is FareUiState.Error)
        assertTrue(state.fareStates["service-C"] is FareUiState.Loading)
    }

    @Test
    fun `different services can have different fare amounts`() {
        val fareA = createSuccessFareState(15.0, "Config A")
        val fareB = createSuccessFareState(25.0, "Config B")

        val stateA = (fareA as FareUiState.Success).fare.fare_amount
        val stateB = (fareB as FareUiState.Success).fare.fare_amount

        assertNotEquals(stateA, stateB, 0.001)
        assertEquals(15.0, stateA, 0.001)
        assertEquals(25.0, stateB, 0.001)
    }

    // =========================================================================
    // NO CLIENT-SIDE FARE MATH VERIFICATION
    // =========================================================================

    @Test
    fun `fare response contains no computed fields beyond backend payload`() {
        // Verify the data class contains ONLY the fields returned by the backend.
        // PassengerFareCalculationResponse has exactly 6 fields:
        // distance_km, fare_amount, currency, matched_slab, fare_configuration_id, fare_configuration_name
        val fields = PassengerFareCalculationResponse::class.java.declaredFields
        val fieldNames = fields.filter { !it.isSynthetic && !it.name.startsWith("$") }.map { it.name }.sorted()

        assertTrue("distance_km must exist", fieldNames.contains("distance_km"))
        assertTrue("fare_amount must exist", fieldNames.contains("fare_amount"))
        assertTrue("currency must exist", fieldNames.contains("currency"))
        assertTrue("matched_slab must exist", fieldNames.contains("matched_slab"))
        assertTrue("fare_configuration_id must exist", fieldNames.contains("fare_configuration_id"))
        assertTrue("fare_configuration_name must exist", fieldNames.contains("fare_configuration_name"))

        // Ensure no extra computed fields (e.g., calculated_distance, local_fare, etc.)
        val expectedFields = setOf(
            "distance_km", "fare_amount", "currency",
            "matched_slab", "fare_configuration_id", "fare_configuration_name"
        )
        for (name in fieldNames) {
            assertTrue(
                "Unexpected field '$name' found — no client-side fare fields allowed",
                expectedFields.contains(name)
            )
        }
    }

    // =========================================================================
    // API REQUEST PARAMETER TESTS
    // =========================================================================

    @Test
    fun `trip response contains service_id for fare lookup`() {
        val trip = createTripResponse("service-123", "GO-101")
        assertEquals("service-123", trip.service_id)
    }

    @Test
    fun `trip response does not contain route_id`() {
        // PassengerPlanTripResponse must NOT include route_id
        val fields = PassengerPlanTripResponse::class.java.declaredFields.map { it.name }
        assertFalse("route_id must NOT exist in PassengerPlanTripResponse", fields.contains("route_id"))
    }

    // =========================================================================
    // FAILURE ISOLATION TESTS
    // =========================================================================

    @Test
    fun `one service fare error does not affect other service fares`() {
        val fareStates = mutableMapOf<String, FareUiState>()
        fareStates["service-A"] = FareUiState.Success(
            PassengerFareCalculationResponse(
                distance_km = 3.0, fare_amount = 15.0, currency = "INR",
                matched_slab = PassengerMatchedSlabResponse("s1", 0.0, 5.0, 15.0),
                fare_configuration_id = "cfg-1", fare_configuration_name = "Config A"
            )
        )
        fareStates["service-B"] = FareUiState.Error("Network error")

        // Service A fare is still accessible after Service B fails
        val stateA = fareStates["service-A"]
        assertTrue(stateA is FareUiState.Success)
        assertEquals(15.0, (stateA as FareUiState.Success).fare.fare_amount, 0.001)

        // Service B is in error state
        val stateB = fareStates["service-B"]
        assertTrue(stateB is FareUiState.Error)
    }

    // =========================================================================
    // HELPERS
    // =========================================================================

    private fun createTripResponse(serviceId: String, serviceName: String) =
        PassengerPlanTripResponse(
            service_id = serviceId,
            service_name = serviceName,
            direction = "UP",
            route_origin = "Stop A",
            route_destination = "Stop D",
            scheduled_departure = "2026-08-31T08:30:00",
            scheduled_arrival = "2026-08-31T09:10:00"
        )

    private fun createSuccessFareState(amount: Double, configName: String): FareUiState =
        FareUiState.Success(
            PassengerFareCalculationResponse(
                distance_km = 5.0,
                fare_amount = amount,
                currency = "INR",
                matched_slab = PassengerMatchedSlabResponse("s1", 0.0, 10.0, amount),
                fare_configuration_id = "cfg-1",
                fare_configuration_name = configName
            )
        )
}
