package com.transitplatform.app

import com.transitplatform.app.data.model.AssignmentResponse
import com.transitplatform.app.data.model.LoginResponse
import com.transitplatform.app.data.model.OperatorTripResponse
import com.transitplatform.app.ui.OperatorUiState
import com.transitplatform.app.ui.ReadinessCheckState
import com.transitplatform.app.ui.ReadinessGateState
import com.transitplatform.app.ui.ScreenState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ReadinessCheckUnitTest {

    private fun createBaseReadyState() = ReadinessCheckState(
        hasAuthenticatedSession = true,
        hasTripAssignment = true,
        hasVehicleAssignment = true,
        hasOperatorAssignment = true,
        hasFineLocation = true,
        hasCoarseLocation = true,
        hasNotificationPermission = true,
        isNotificationPermissionRequired = true,
        isGpsEnabled = true,
        isNetworkAvailable = true,
        batteryPercentage = 85
    )

    // ── 1. BLOCKING CHECKS EVALUATION ──

    @Test
    fun testAllBlockingChecksPass_ReadyToStart() {
        val state = createBaseReadyState()
        assertTrue("All blocking checks pass; readiness must be true", state.isReadyToTrack)
        assertEquals(0, state.blockingFailuresCount)
        assertEquals(0, state.warningCount)
    }

    @Test
    fun testMissingFineLocation_Blocked() {
        val state = createBaseReadyState().copy(hasFineLocation = false)
        assertFalse("Missing Fine Location must block start", state.isReadyToTrack)
        assertEquals(1, state.blockingFailuresCount)
    }

    @Test
    fun testGpsDisabled_Blocked() {
        val state = createBaseReadyState().copy(isGpsEnabled = false)
        assertFalse("Disabled hardware GPS must block start", state.isReadyToTrack)
        assertEquals(1, state.blockingFailuresCount)
    }

    @Test
    fun testMissingNotificationPermission_WhenRequired_Blocked() {
        val state = createBaseReadyState().copy(
            hasNotificationPermission = false,
            isNotificationPermissionRequired = true
        )
        assertFalse("Missing notification permission on API 33+ must block start", state.isReadyToTrack)
        assertEquals(1, state.blockingFailuresCount)
    }

    @Test
    fun testNotificationPermissionNotRequired_OnOlderApi_NotBlocked() {
        val state = createBaseReadyState().copy(
            hasNotificationPermission = false,
            isNotificationPermissionRequired = false // Android 12 or lower
        )
        assertTrue("On API < 33 notification permission is not a runtime blocker", state.isReadyToTrack)
        assertEquals(0, state.blockingFailuresCount)
    }

    @Test
    fun testMissingTripAssignment_Blocked() {
        val state = createBaseReadyState().copy(hasTripAssignment = false)
        assertFalse("Missing trip assignment must block start", state.isReadyToTrack)
        assertEquals(1, state.blockingFailuresCount)
    }

    @Test
    fun testMissingVehicleAssignment_Blocked() {
        val state = createBaseReadyState().copy(hasVehicleAssignment = false)
        assertFalse("Missing vehicle assignment must block start", state.isReadyToTrack)
        assertEquals(1, state.blockingFailuresCount)
    }

    @Test
    fun testMissingOperatorAssignment_Blocked() {
        val state = createBaseReadyState().copy(hasOperatorAssignment = false)
        assertFalse("Missing operator assignment must block start", state.isReadyToTrack)
        assertEquals(1, state.blockingFailuresCount)
    }

    @Test
    fun testMissingAuthenticatedSession_Blocked() {
        val state = createBaseReadyState().copy(hasAuthenticatedSession = false)
        assertFalse("Missing authenticated session must block start", state.isReadyToTrack)
        assertEquals(1, state.blockingFailuresCount)
    }

    // ── 2. WARNING CHECKS (NON-BLOCKING) ──

    @Test
    fun testOfflineNetwork_WarningOnly_NotBlocked() {
        val state = createBaseReadyState().copy(isNetworkAvailable = false)
        assertTrue("Offline network must NOT block tracking due to store-and-forward", state.isReadyToTrack)
        assertEquals(0, state.blockingFailuresCount)
        assertEquals(1, state.warningCount)
    }

    @Test
    fun testLowBattery_WarningOnly_NotBlocked() {
        val state = createBaseReadyState().copy(batteryPercentage = 12)
        assertTrue("Battery <= 15% is a warning and must NOT block tracking", state.isReadyToTrack)
        assertEquals(0, state.blockingFailuresCount)
        assertEquals(1, state.warningCount)
    }

    @Test
    fun testOfflineNetworkAndLowBattery_BothWarnings_NotBlocked() {
        val state = createBaseReadyState().copy(
            isNetworkAvailable = false,
            batteryPercentage = 8
        )
        assertTrue("Multiple warnings must NOT prevent trip start", state.isReadyToTrack)
        assertEquals(0, state.blockingFailuresCount)
        assertEquals(2, state.warningCount)
    }

    // ── 3. INFORMATIONAL CHECKS (NON-BLOCKING) ──

    @Test
    fun testHealthyBattery_Info_NotBlocked() {
        val state = createBaseReadyState().copy(batteryPercentage = 95)
        assertTrue(state.isReadyToTrack)
        assertEquals(0, state.blockingFailuresCount)
        assertEquals(0, state.warningCount)
    }

    @Test
    fun testCoarseLocation_Informational_NotBlocked() {
        val state = createBaseReadyState().copy(hasCoarseLocation = false)
        // Fine location alone satisfies precise tracking
        assertTrue(state.isReadyToTrack)
    }

    // ── 4. MULTIPLE BLOCKING FAILURES ──

    @Test
    fun testMultipleBlockingFailures_CountAccurate() {
        val state = ReadinessCheckState(
            hasAuthenticatedSession = false,
            hasTripAssignment = false,
            hasVehicleAssignment = false,
            hasOperatorAssignment = false,
            hasFineLocation = false,
            isGpsEnabled = false,
            hasNotificationPermission = false,
            isNotificationPermissionRequired = true
        )
        assertFalse(state.isReadyToTrack)
        assertEquals(7, state.blockingFailuresCount)
    }

    // ── 5. FORMAL LOCAL START GATE TESTS ──

    @Test
    fun testGateCannotStart_WhenBlockingChecksFail() {
        val blockedReadiness = createBaseReadyState().copy(hasFineLocation = false)
        val uiState = OperatorUiState(
            readiness = blockedReadiness,
            readinessGateState = ReadinessGateState.BLOCKING_FAIL
        )

        // Verify that start cannot be triggered
        val canStart = uiState.readiness.isReadyToTrack &&
                uiState.readinessGateState == ReadinessGateState.READY_TO_START &&
                !uiState.isLoading

        assertFalse("Gate must disable start when blocking fail exists", canStart)
    }

    @Test
    fun testGateAllowsStart_WhenReadyToStart() {
        val readyReadiness = createBaseReadyState()
        val uiState = OperatorUiState(
            readiness = readyReadiness,
            readinessGateState = ReadinessGateState.READY_TO_START,
            isLoading = false
        )

        val canStart = uiState.readiness.isReadyToTrack &&
                uiState.readinessGateState == ReadinessGateState.READY_TO_START &&
                !uiState.isLoading

        assertTrue("Gate must allow start when all blocking checks pass and status is READY_TO_START", canStart)
    }

    @Test
    fun testGatePreventsDuplicateTaps_WhenStarting() {
        val readyReadiness = createBaseReadyState()
        val uiState = OperatorUiState(
            readiness = readyReadiness,
            readinessGateState = ReadinessGateState.STARTING,
            isLoading = true
        )

        val canStart = uiState.readiness.isReadyToTrack &&
                uiState.readinessGateState == ReadinessGateState.READY_TO_START &&
                !uiState.isLoading

        assertFalse("Gate must prevent duplicate taps while in STARTING state", canStart)
    }

    @Test
    fun testGatePreservesNavigationContext() {
        val uiStateFromDetails = OperatorUiState(
            currentScreen = ScreenState.READINESS,
            previousScreen = ScreenState.TRIP_DETAILS
        )
        assertEquals(ScreenState.TRIP_DETAILS, uiStateFromDetails.previousScreen)

        val uiStateFromTrips = OperatorUiState(
            currentScreen = ScreenState.READINESS,
            previousScreen = ScreenState.TODAYS_TRIPS
        )
        assertEquals(ScreenState.TODAYS_TRIPS, uiStateFromTrips.previousScreen)

        val uiStateFromHome = OperatorUiState(
            currentScreen = ScreenState.READINESS,
            previousScreen = ScreenState.ASSIGNMENT
        )
        assertEquals(ScreenState.ASSIGNMENT, uiStateFromHome.previousScreen)
    }
}
