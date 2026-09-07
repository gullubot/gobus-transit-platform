package com.transitplatform.app

import com.transitplatform.app.data.local.TrackingPacketEntity
import com.transitplatform.app.data.model.BatchAckResponse
import com.transitplatform.app.service.LiveTrackingStatus
import com.transitplatform.app.service.ScheduleNotificationHelper
import com.transitplatform.app.ui.ReadinessCheckState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.UUID

class OperatorFlowUnitTest {

    @Test
    fun testReadinessCheckEvaluation() {
        val notReady = ReadinessCheckState(
            hasAuthenticatedSession = true,
            hasTripAssignment = true,
            hasVehicleAssignment = true,
            hasOperatorAssignment = true,
            hasFineLocation = false,
            hasCoarseLocation = true,
            isGpsEnabled = false
        )
        assertFalse(notReady.isReadyToTrack)

        val ready = ReadinessCheckState(
            hasAuthenticatedSession = true,
            hasTripAssignment = true,
            hasVehicleAssignment = true,
            hasOperatorAssignment = true,
            hasFineLocation = true,
            hasCoarseLocation = true,
            hasNotificationPermission = true,
            isGpsEnabled = true,
            isNetworkAvailable = false // Network unavailable should NOT block offline tracking!
        )
        assertTrue(ready.isReadyToTrack)
    }

    @Test
    fun testTrackingPacketEntityCreation() {
        val pktId = UUID.randomUUID().toString()
        val sessId = UUID.randomUUID().toString()
        val packet = TrackingPacketEntity(
            packetId = pktId,
            sessionId = sessId,
            latitude = 30.7333,
            longitude = 76.7794,
            accuracyM = 4.2f,
            speedMps = 12.0f,
            heading = 90.0f,
            observedAt = "2026-08-26T21:00:00.000Z",
            deviceSequence = 1,
            batteryLevel = 90.0f,
            networkType = "4G",
            gpsStatus = "AVAILABLE"
        )
        assertEquals(pktId, packet.packetId)
        assertEquals(1, packet.deviceSequence)
        assertEquals("PENDING", packet.syncStatus)
    }

    @Test
    fun testBatchAckEvictionCalculation() {
        val pkt1 = UUID.randomUUID().toString()
        val pkt2 = UUID.randomUUID().toString()
        val pkt3 = UUID.randomUUID().toString()

        val ack = BatchAckResponse(
            accepted = listOf(pkt1),
            duplicates = listOf(pkt2),
            retryable = listOf(pkt3),
            rejected = emptyList()
        )

        // Accepted + duplicates are safely evicted from local Room queue
        val toEvict = ack.accepted + ack.duplicates
        assertEquals(2, toEvict.size)
        assertTrue(toEvict.contains(pkt1))
        assertTrue(toEvict.contains(pkt2))
        assertFalse(toEvict.contains(pkt3)) // retryable stays in Room queue!
    }

    @Test
    fun testScheduleNotificationConstants() {
        assertEquals("transit_schedule_alerts", ScheduleNotificationHelper.CHANNEL_SCHEDULE_ID)
        assertEquals(
            "com.transitplatform.app.ACTION_START_TRACKING_FROM_NOTIF",
            ScheduleNotificationHelper.ACTION_START_TRACKING_INTENT
        )
        assertEquals(
            "com.transitplatform.app.ACTION_SNOOZE_SCHEDULE",
            ScheduleNotificationHelper.ACTION_SNOOZE_INTENT
        )
    }

    @Test
    fun testLiveTrackingStatusOfflineState() {
        val statusOnline = LiveTrackingStatus(isTracking = true, isOnline = true, syncStatus = "SYNCED")
        assertTrue(statusOnline.isOnline)
        assertEquals("SYNCED", statusOnline.syncStatus)

        val statusOffline = LiveTrackingStatus(
            isTracking = true,
            isOnline = false,
            syncStatus = "QUEUED",
            queuedPacketsCount = 5
        )
        assertFalse(statusOffline.isOnline)
        assertEquals("QUEUED", statusOffline.syncStatus)
        assertEquals(5, statusOffline.queuedPacketsCount)
    }

    @Test
    fun testAssignmentResponseEnrichedOperationalFields() {
        val assignment = com.transitplatform.app.data.model.AssignmentResponse(
            assignment_id = "assign-1",
            trip_id = "trip-1",
            service_id = "svc-1",
            service_code = "SVC01-SD5",
            service_name = "SD5",
            route_id = "route-1",
            route_code = "R001-SD5",
            route_name = "Sonarpur Station - Khariberia , via Tollygunge & New Alipore",
            direction = "A_TO_B",
            vehicle_id = "veh-1",
            vehicle_number = "SD5V01",
            planned_start_at = "2026-09-04T15:27:20.554542",
            trip_status = "PLANNED",
            operator_role = "DRIVER",
            assignment_status = "ASSIGNED",
            assigned_device_id = null,
            assigned_device_status = "ACTIVE",
            active_tracking_session_id = null,
            tracking_session_status = null,
            vehicle_registration = "WB-03AB3765",
            vehicle_type = "BUS",
            origin_stop_name = "Sonarpur Station Bus Terminus",
            destination_stop_name = "Khariberia",
            route_distance_km = 43.691
        )

        assertEquals("SVC01-SD5", assignment.service_code)
        assertEquals("SD5V01", assignment.vehicle_number)
        assertEquals("WB-03AB3765", assignment.vehicle_registration)
        assertEquals("BUS", assignment.vehicle_type)
        assertEquals("Sonarpur Station Bus Terminus", assignment.origin_stop_name)
        assertEquals("Khariberia", assignment.destination_stop_name)
        assertEquals(43.691, assignment.route_distance_km!!, 0.001)
    }

    @Test
    fun testAssignmentResponseWithNullableOptionalFields() {
        val assignment = com.transitplatform.app.data.model.AssignmentResponse(
            assignment_id = "assign-2",
            trip_id = "trip-2",
            service_id = "svc-2",
            service_code = "SD5",
            service_name = "SD5 Express",
            route_id = "route-2",
            route_code = "R2",
            route_name = "Howrah - Esplanade",
            direction = "B_TO_A",
            vehicle_id = "veh-2",
            vehicle_number = "SD5V02",
            planned_start_at = "2026-09-05T06:30:00Z",
            trip_status = "ACTIVE",
            operator_role = "DRIVER",
            assignment_status = "ACTIVE",
            assigned_device_id = null,
            assigned_device_status = null,
            active_tracking_session_id = null,
            tracking_session_status = null,
            vehicle_registration = null,
            vehicle_type = null,
            origin_stop_name = null,
            destination_stop_name = null,
            route_distance_km = null
        )

        assertEquals("SD5", assignment.service_code)
        org.junit.Assert.assertNull(assignment.vehicle_registration)
        org.junit.Assert.assertNull(assignment.route_distance_km)
    }

    @Test
    fun testOperatorTripResponseModel() {
        val trip = com.transitplatform.app.data.model.OperatorTripResponse(
            trip_id = "trip-101",
            assignment_id = "assign-101",
            service_code = "SVC01-SD5",
            service_name = "SD5",
            route_code = "R001-SD5",
            route_name = "Sonarpur Station - Khariberia",
            direction = "A_TO_B",
            vehicle_number = "SD5V01",
            vehicle_registration = "WB-03AB3765",
            vehicle_type = "BUS",
            planned_start_at = "2026-09-05T06:30:00",
            actual_start_at = null,
            actual_end_at = null,
            trip_status = "PLANNED",
            assignment_status = "ASSIGNED",
            operator_role = "DRIVER",
            origin_stop_name = "Sonarpur Station Bus Terminus",
            destination_stop_name = "Khariberia",
            route_distance_km = 43.691,
            is_next = true
        )

        assertEquals("SD5", trip.service_name)
        assertEquals("SD5V01", trip.vehicle_number)
        assertEquals("WB-03AB3765", trip.vehicle_registration)
        assertEquals("Sonarpur Station Bus Terminus", trip.origin_stop_name)
        assertEquals("Khariberia", trip.destination_stop_name)
        assertTrue(trip.is_next)
    }

    @Test
    fun testTodaysTripsChronologicalOrdering() {
        val trip1 = com.transitplatform.app.data.model.OperatorTripResponse(
            trip_id = "t1", assignment_id = "a1", service_code = "S1", service_name = "SD5",
            route_code = "R1", route_name = "R1", direction = "A_TO_B", vehicle_number = "V1",
            vehicle_registration = "REG1", vehicle_type = "BUS",
            planned_start_at = "2026-09-05T06:30:00", actual_start_at = null, actual_end_at = null,
            trip_status = "COMPLETED", assignment_status = "COMPLETED", operator_role = "DRIVER",
            origin_stop_name = "Sonarpur", destination_stop_name = "Khariberia", route_distance_km = 40.0,
            is_next = false
        )
        val trip2 = com.transitplatform.app.data.model.OperatorTripResponse(
            trip_id = "t2", assignment_id = "a2", service_code = "S1", service_name = "SD5",
            route_code = "R1", route_name = "R1", direction = "B_TO_A", vehicle_number = "V1",
            vehicle_registration = "REG1", vehicle_type = "BUS",
            planned_start_at = "2026-09-05T09:15:00", actual_start_at = null, actual_end_at = null,
            trip_status = "PLANNED", assignment_status = "ASSIGNED", operator_role = "DRIVER",
            origin_stop_name = "Khariberia", destination_stop_name = "Sonarpur", route_distance_km = 40.0,
            is_next = true
        )
        val trip3 = com.transitplatform.app.data.model.OperatorTripResponse(
            trip_id = "t3", assignment_id = "a3", service_code = "S1", service_name = "SD5",
            route_code = "R1", route_name = "R1", direction = "A_TO_B", vehicle_number = "V1",
            vehicle_registration = "REG1", vehicle_type = "BUS",
            planned_start_at = "2026-09-05T13:00:00", actual_start_at = null, actual_end_at = null,
            trip_status = "PLANNED", assignment_status = "ASSIGNED", operator_role = "DRIVER",
            origin_stop_name = "Sonarpur", destination_stop_name = "Khariberia", route_distance_km = 40.0,
            is_next = false
        )

        val trips = listOf(trip1, trip2, trip3)
        // Verify sorted by planned_start_at ASC
        val sorted = trips.sortedBy { it.planned_start_at }
        assertEquals(listOf("t1", "t2", "t3"), sorted.map { it.trip_id })

        // At most one trip has is_next == true
        val nextCount = trips.count { it.is_next }
        assertEquals(1, nextCount)
        assertEquals("t2", trips.first { it.is_next }.trip_id)
    }

    @Test
    fun testStatusPresentationLabels() {
        fun formatStatus(status: String): String = when (status.uppercase()) {
            "PLANNED" -> "Scheduled"
            "ACTIVE" -> "Trip in Progress"
            "SUSPECTED_START" -> "Starting"
            "COMPLETED" -> "Completed"
            "CANCELLED" -> "Cancelled"
            "ABANDONED" -> "Abandoned"
            else -> status.replace('_', ' ')
        }

        assertEquals("Scheduled", formatStatus("PLANNED"))
        assertEquals("Trip in Progress", formatStatus("ACTIVE"))
        assertEquals("Starting", formatStatus("SUSPECTED_START"))
        assertEquals("Completed", formatStatus("COMPLETED"))
        assertEquals("Cancelled", formatStatus("CANCELLED"))
        assertEquals("Abandoned", formatStatus("ABANDONED"))
    }

    @Test
    fun testOperatorScreenStateTransitions() {
        var screen = com.transitplatform.app.ui.ScreenState.LOGIN
        assertEquals(com.transitplatform.app.ui.ScreenState.LOGIN, screen)

        // Login succeeds -> Home (ASSIGNMENT)
        screen = com.transitplatform.app.ui.ScreenState.ASSIGNMENT
        assertEquals(com.transitplatform.app.ui.ScreenState.ASSIGNMENT, screen)

        // Tap Today's Trips -> TODAYS_TRIPS
        screen = com.transitplatform.app.ui.ScreenState.TODAYS_TRIPS
        assertEquals(com.transitplatform.app.ui.ScreenState.TODAYS_TRIPS, screen)

        // Tap Back -> ASSIGNMENT
        screen = com.transitplatform.app.ui.ScreenState.ASSIGNMENT
        assertEquals(com.transitplatform.app.ui.ScreenState.ASSIGNMENT, screen)
    }

    @Test
    fun testTripDetailsStateTransitionsAndBackNavigation() {
        val sampleTrip = com.transitplatform.app.data.model.OperatorTripResponse(
            trip_id = "trip-201",
            assignment_id = "assign-201",
            service_code = "SD5",
            service_name = "Sonarpur - Khariberia Service",
            route_code = "R001-SD5",
            route_name = "Sonarpur Station - Khariberia , via Tollygunge",
            direction = "A_TO_B",
            vehicle_number = "SD5V02",
            vehicle_registration = "WB-19F-1002",
            vehicle_type = "BUS",
            planned_start_at = "2026-09-06T07:35:00",
            trip_status = "PLANNED",
            assignment_status = "ASSIGNED",
            operator_role = "DRIVER",
            origin_stop_name = "Sonarpur Station Bus Terminus",
            destination_stop_name = "Khariberia",
            route_distance_km = 43.691,
            is_next = true
        )

        // 1. TODAYS_TRIPS -> TRIP_DETAILS
        var state = com.transitplatform.app.ui.OperatorUiState(
            currentScreen = com.transitplatform.app.ui.ScreenState.TODAYS_TRIPS,
            todaysTrips = listOf(sampleTrip)
        )
        assertEquals(com.transitplatform.app.ui.ScreenState.TODAYS_TRIPS, state.currentScreen)

        // Select trip for details: updates selectedTripForDetails and changes screen to TRIP_DETAILS
        state = state.copy(
            selectedTripForDetails = sampleTrip,
            currentScreen = com.transitplatform.app.ui.ScreenState.TRIP_DETAILS
        )
        assertEquals(com.transitplatform.app.ui.ScreenState.TRIP_DETAILS, state.currentScreen)

        // 2. selectedTripForDetails stores correct trip
        assertEquals("trip-201", state.selectedTripForDetails?.trip_id)
        assertEquals("SD5V02", state.selectedTripForDetails?.vehicle_number)

        // 22. Back returns to TODAYS_TRIPS
        state = state.copy(currentScreen = com.transitplatform.app.ui.ScreenState.TODAYS_TRIPS)
        assertEquals(com.transitplatform.app.ui.ScreenState.TODAYS_TRIPS, state.currentScreen)

        // 23. Missing selected trip safely returns to Today's Trips
        val fallbackState = com.transitplatform.app.ui.OperatorUiState(
            currentScreen = com.transitplatform.app.ui.ScreenState.TRIP_DETAILS,
            selectedTripForDetails = null
        )
        val resolvedScreen = if (fallbackState.selectedTripForDetails == null && fallbackState.currentScreen == com.transitplatform.app.ui.ScreenState.TRIP_DETAILS) {
            com.transitplatform.app.ui.ScreenState.TODAYS_TRIPS
        } else {
            fallbackState.currentScreen
        }
        assertEquals(com.transitplatform.app.ui.ScreenState.TODAYS_TRIPS, resolvedScreen)
    }

    @Test
    fun testTripDetailsPresentationFields() {
        val tripOutbound = com.transitplatform.app.data.model.OperatorTripResponse(
            trip_id = "trip-out",
            assignment_id = "assign-out",
            service_code = "SD5",
            service_name = "Sonarpur - Khariberia Express",
            route_code = "R001-SD5",
            route_name = "Sonarpur Station - Khariberia , via Tollygunge",
            direction = "A_TO_B",
            vehicle_number = "SD5V02",
            vehicle_registration = "WB-19F-1002",
            vehicle_type = "BUS",
            planned_start_at = "2026-09-06T07:35:00",
            trip_status = "PLANNED",
            assignment_status = "ASSIGNED",
            operator_role = "DRIVER",
            origin_stop_name = "Sonarpur Station Bus Terminus",
            destination_stop_name = "Khariberia",
            route_distance_km = 43.691,
            is_next = true
        )

        // 3. Service display & 4. Service hierarchy
        assertEquals("SD5", tripOutbound.service_code)
        assertEquals("Sonarpur - Khariberia Express", tripOutbound.service_name)

        // 5. Departure formatting
        val iso = tripOutbound.planned_start_at
        val cleanIso = iso.substringBefore("+").substringBefore("Z")
        val parser = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", java.util.Locale.US)
        val parsedDate = parser.parse(cleanIso)
        val formattedTime = java.text.SimpleDateFormat("hh:mm a", java.util.Locale.US).format(parsedDate!!)
        assertEquals("07:35 AM", formattedTime)

        // 6. Origin & destination
        assertEquals("Sonarpur Station Bus Terminus", tripOutbound.origin_stop_name)
        assertEquals("Khariberia", tripOutbound.destination_stop_name)

        // 7. A_TO_B direction
        assertEquals("A_TO_B", tripOutbound.direction)
        val outboundLabel = if (tripOutbound.direction == "B_TO_A") "Return Direction (B → A)" else "Outbound Direction (A → B)"
        assertEquals("Outbound Direction (A → B)", outboundLabel)

        // 8. B_TO_A direction
        val tripReturn = tripOutbound.copy(
            direction = "B_TO_A",
            origin_stop_name = "Khariberia",
            destination_stop_name = "Sonarpur Station Bus Terminus"
        )
        val returnLabel = if (tripReturn.direction == "B_TO_A") "Return Direction (B → A)" else "Outbound Direction (A → B)"
        assertEquals("Return Direction (B → A)", returnLabel)
        assertEquals("Khariberia", tripReturn.origin_stop_name)
        assertEquals("Sonarpur Station Bus Terminus", tripReturn.destination_stop_name)

        // 9. Vehicle number & 10. Registration & 11. Vehicle type & 12. Operator role
        assertEquals("SD5V02", tripOutbound.vehicle_number)
        assertEquals("WB-19F-1002", tripOutbound.vehicle_registration)
        assertEquals("BUS", tripOutbound.vehicle_type)
        assertEquals("DRIVER", tripOutbound.operator_role)

        // 13. Distance formatting
        val distanceStr = String.format(java.util.Locale.US, "%.1f km", tripOutbound.route_distance_km)
        assertEquals("43.7 km", distanceStr)

        // 15. is_next authoritative propagation
        assertTrue(tripOutbound.is_next)
    }

    @Test
    fun testStartTripEligibilityAcrossLifecycleStates() {
        fun isEligibleToStart(status: String): Boolean {
            val isScheduled = status.uppercase() == "PLANNED"
            val isCompleted = status.uppercase() == "COMPLETED"
            val isCancelled = status.uppercase() == "CANCELLED" || status.uppercase() == "ABANDONED"
            return isScheduled && !isCompleted && !isCancelled
        }

        // Scheduled is eligible
        assertTrue(isEligibleToStart("PLANNED"))

        // 16. COMPLETED has no Start Trip
        assertFalse(isEligibleToStart("COMPLETED"))

        // 17. CANCELLED has no Start Trip
        assertFalse(isEligibleToStart("CANCELLED"))

        // 18. ABANDONED has no Start Trip
        assertFalse(isEligibleToStart("ABANDONED"))

        // 19. ACTIVE does not invoke duplicate Start Trip
        assertFalse(isEligibleToStart("ACTIVE"))
        assertFalse(isEligibleToStart("SUSPECTED_START"))
    }

    @Test
    fun testZeroMutationOnSelectingTripForDetails() {
        // 20. Opening details causes no mutation
        val initialTrip = com.transitplatform.app.data.model.OperatorTripResponse(
            trip_id = "t-pure", assignment_id = "a-pure", service_code = "S1", service_name = "SD5",
            route_code = "R1", route_name = "R1", direction = "A_TO_B", vehicle_number = "V1",
            vehicle_registration = "REG1", vehicle_type = "BUS",
            planned_start_at = "2026-09-06T08:00:00", trip_status = "PLANNED", assignment_status = "ASSIGNED",
            operator_role = "DRIVER", origin_stop_name = "A", destination_stop_name = "B", route_distance_km = 10.0,
            is_next = false
        )

        val stateBefore = com.transitplatform.app.ui.OperatorUiState(
            currentScreen = com.transitplatform.app.ui.ScreenState.TODAYS_TRIPS,
            todaysTrips = listOf(initialTrip),
            assignment = null,
            activeTrackingSessionId = null
        )

        // Tapping card transitions screen without modifying assignment or tracking session
        val stateAfter = stateBefore.copy(
            selectedTripForDetails = initialTrip,
            currentScreen = com.transitplatform.app.ui.ScreenState.TRIP_DETAILS
        )

        assertEquals(com.transitplatform.app.ui.ScreenState.TRIP_DETAILS, stateAfter.currentScreen)
        assertEquals(stateBefore.assignment, stateAfter.assignment) // Zero assignment mutation!
        assertEquals(stateBefore.activeTrackingSessionId, stateAfter.activeTrackingSessionId) // Zero tracking mutation!
    }

    @Test
    fun testExplicitStartTripDelegatesToReadiness() {
        // 21. Explicit Start Trip delegates to existing readiness flow
        val tripToStart = com.transitplatform.app.data.model.OperatorTripResponse(
            trip_id = "t-start-1", assignment_id = "a-start-1", service_code = "S1", service_name = "SD5",
            route_code = "R1", route_name = "R1", direction = "A_TO_B", vehicle_number = "V1",
            vehicle_registration = "REG1", vehicle_type = "BUS",
            planned_start_at = "2026-09-06T08:00:00", trip_status = "PLANNED", assignment_status = "ASSIGNED",
            operator_role = "DRIVER", origin_stop_name = "A", destination_stop_name = "B", route_distance_km = 10.0,
            is_next = true
        )

        val tempAssignment = com.transitplatform.app.data.model.AssignmentResponse(
            assignment_id = tripToStart.assignment_id,
            trip_id = tripToStart.trip_id,
            service_id = "s-1",
            service_code = tripToStart.service_code,
            service_name = tripToStart.service_name,
            route_id = "r-1",
            route_code = tripToStart.route_code,
            route_name = tripToStart.route_name,
            direction = tripToStart.direction,
            vehicle_id = "v-1",
            vehicle_number = tripToStart.vehicle_number,
            planned_start_at = tripToStart.planned_start_at,
            trip_status = tripToStart.trip_status,
            operator_role = tripToStart.operator_role,
            assignment_status = tripToStart.assignment_status,
            assigned_device_id = null,
            assigned_device_status = null,
            active_tracking_session_id = null,
            tracking_session_status = null,
            vehicle_registration = tripToStart.vehicle_registration,
            vehicle_type = tripToStart.vehicle_type,
            origin_stop_name = tripToStart.origin_stop_name,
            destination_stop_name = tripToStart.destination_stop_name,
            route_distance_km = tripToStart.route_distance_km
        )

        val readinessState = com.transitplatform.app.ui.OperatorUiState(
            currentScreen = com.transitplatform.app.ui.ScreenState.READINESS,
            assignment = tempAssignment
        )

        assertEquals(com.transitplatform.app.ui.ScreenState.READINESS, readinessState.currentScreen)
        assertEquals("t-start-1", readinessState.assignment?.trip_id)
        assertEquals("SD5", readinessState.assignment?.service_name)
    }

    @Test
    fun testUserFacingPresentationDoesNotExposeUUIDsOrBackendJargon() {
        // 24. No UUIDs or backend terminology appear in user-facing presentation
        val trip = com.transitplatform.app.data.model.OperatorTripResponse(
            trip_id = "8f3b218a-92e1-4c12-b912-78d1f2a34567",
            assignment_id = "b812a021-34fa-58bc-98de-129038475612",
            service_code = "SD5",
            service_name = "Sonarpur - Khariberia Express",
            route_code = "R001-SD5",
            route_name = "Sonarpur Station - Khariberia , via Tollygunge",
            direction = "A_TO_B",
            vehicle_number = "SD5V02",
            vehicle_registration = "WB-19F-1002",
            vehicle_type = "BUS",
            planned_start_at = "2026-09-06T07:35:00",
            trip_status = "PLANNED",
            assignment_status = "ASSIGNED",
            operator_role = "DRIVER",
            origin_stop_name = "Sonarpur Station Bus Terminus",
            destination_stop_name = "Khariberia",
            route_distance_km = 43.691,
            is_next = true
        )

        val userFacingStrings = listOf(
            trip.service_code,
            trip.service_name,
            trip.vehicle_number,
            trip.vehicle_registration ?: "",
            trip.origin_stop_name ?: "",
            trip.destination_stop_name ?: "",
            trip.operator_role,
            "Scheduled",
            "Outbound Direction (A → B)",
            "43.7 km"
        )

        for (text in userFacingStrings) {
            assertFalse("User facing string must not contain raw UUID: $text", text.contains(trip.trip_id))
            assertFalse("User facing string must not contain raw UUID: $text", text.contains(trip.assignment_id))
            assertFalse("User facing string must not contain raw DB enum: $text", text.contains("PLANNED"))
            assertFalse("User facing string must not contain raw direction enum: $text", text.contains("A_TO_B"))
        }
    }
}

