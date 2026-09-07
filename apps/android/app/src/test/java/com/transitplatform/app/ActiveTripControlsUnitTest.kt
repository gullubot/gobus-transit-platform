package com.transitplatform.app

import com.transitplatform.app.data.local.CrowdingReportEntity
import com.transitplatform.app.data.model.OperatorIssueResponse
import com.transitplatform.app.service.ForegroundTrackingService
import com.transitplatform.app.ui.OPERATOR_ISSUE_TYPES
import com.transitplatform.app.ui.OperatorCrowdLevel
import com.transitplatform.app.ui.OperatorUiState
import com.transitplatform.app.ui.ScreenState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ActiveTripControlsUnitTest {

    @Test
    fun testCrowdLevelPresentsExactlyFiveOptions() {
        val levels = OperatorCrowdLevel.values()
        assertEquals("Crowd Level selector must present exactly 5 options", 5, levels.size)

        // Verify order and display names
        assertEquals("1. NOT CROWDED", 1, levels[0].levelNumber)
        assertEquals("NOT CROWDED", levels[0].displayName)

        assertEquals("2. MODERATE", 2, levels[1].levelNumber)
        assertEquals("MODERATE", levels[1].displayName)

        assertEquals("3. CROWDED", 3, levels[2].levelNumber)
        assertEquals("CROWDED", levels[2].displayName)

        assertEquals("4. VERY CROWDED", 4, levels[3].levelNumber)
        assertEquals("VERY CROWDED", levels[3].displayName)

        assertEquals("5. FULL", 5, levels[4].levelNumber)
        assertEquals("FULL", levels[4].displayName)
    }

    @Test
    fun testCrowdLevelBackendMappingAndConfidence() {
        // NOT CROWDED -> LOW (1.0)
        assertEquals("LOW", OperatorCrowdLevel.NOT_CROWDED.backendState)
        assertEquals(1.0f, OperatorCrowdLevel.NOT_CROWDED.confidence, 0.001f)

        // MODERATE -> MODERATE (1.0)
        assertEquals("MODERATE", OperatorCrowdLevel.MODERATE.backendState)
        assertEquals(1.0f, OperatorCrowdLevel.MODERATE.confidence, 0.001f)

        // CROWDED -> HIGH (0.8 confidence differentiator)
        assertEquals("HIGH", OperatorCrowdLevel.CROWDED.backendState)
        assertEquals(0.8f, OperatorCrowdLevel.CROWDED.confidence, 0.001f)

        // VERY CROWDED -> HIGH (1.0 higher confidence)
        assertEquals("HIGH", OperatorCrowdLevel.VERY_CROWDED.backendState)
        assertEquals(1.0f, OperatorCrowdLevel.VERY_CROWDED.confidence, 0.001f)

        // FULL -> FULL (1.0)
        assertEquals("FULL", OperatorCrowdLevel.FULL.backendState)
        assertEquals(1.0f, OperatorCrowdLevel.FULL.confidence, 0.001f)

        // Verify all mapped states belong to backend CrowdingState enum without schema mutation
        val validBackendStates = setOf("LOW", "MODERATE", "HIGH", "FULL")
        for (level in OperatorCrowdLevel.values()) {
            assertTrue(
                "Level ${level.displayName} maps to valid backend state ${level.backendState}",
                validBackendStates.contains(level.backendState)
            )
        }
    }

    @Test
    fun testNotificationActionConstantsAndChannel() {
        assertEquals("com.transitplatform.app.ACTION_OPEN_TRIP", ForegroundTrackingService.ACTION_OPEN_TRIP)
        assertEquals("com.transitplatform.app.ACTION_REPORT_ISSUE", ForegroundTrackingService.ACTION_REPORT_ISSUE)
        assertEquals("com.transitplatform.app.ACTION_CROWD_LEVEL", ForegroundTrackingService.ACTION_CROWD_LEVEL)

        assertEquals("extra_open_action", ForegroundTrackingService.EXTRA_OPEN_ACTION)
        assertEquals("OPEN_TRIP", ForegroundTrackingService.ACTION_NAME_OPEN_TRIP)
        assertEquals("REPORT_ISSUE", ForegroundTrackingService.ACTION_NAME_REPORT_ISSUE)
        assertEquals("CROWD_LEVEL", ForegroundTrackingService.ACTION_NAME_CROWD_LEVEL)

        assertEquals("transit_tracking_channel", ForegroundTrackingService.NOTIFICATION_CHANNEL_ID)
    }

    @Test
    fun testOperatorIssueTypesContainExpectedCategories() {
        val typeCodes = OPERATOR_ISSUE_TYPES.map { it.code }
        assertTrue(typeCodes.contains("BREAKDOWN"))
        assertTrue(typeCodes.contains("TRAFFIC_DELAY"))
        assertTrue(typeCodes.contains("ACCIDENT"))
        assertTrue(typeCodes.contains("MECHANICAL_ISSUE"))
        assertTrue(typeCodes.contains("PASSENGER_INCIDENT"))
        assertTrue(typeCodes.contains("MEDICAL_EMERGENCY"))
        assertTrue(typeCodes.contains("OTHER"))
    }

    @Test
    fun testOperatorIssueResponseDataClass() {
        val resp = OperatorIssueResponse(
            alert_id = "alert-123",
            trip_id = "trip-456",
            service_id = "serv-789",
            route_id = "rt-001",
            scope = "TRIP",
            status = "OPEN",
            type = "OPERATOR_REPORTED_ISSUE",
            severity = "CRITICAL",
            title = "Operator Report: Breakdown",
            message = "Engine stalled",
            created_at = "2026-09-06T12:00:00Z",
            created_by = "usr-1"
        )
        assertEquals("alert-123", resp.alert_id)
        assertEquals("trip-456", resp.trip_id)
        assertEquals("TRIP", resp.scope)
        assertEquals("OPEN", resp.status)
        assertEquals("OPERATOR_REPORTED_ISSUE", resp.type)
        assertEquals("CRITICAL", resp.severity)
    }

    @Test
    fun testUiStateActiveTripControlsDefaults() {
        val state = OperatorUiState()
        assertFalse(state.isReportIssueDialogVisible)
        assertFalse(state.isCrowdLevelSheetVisible)
        assertFalse(state.isSubmittingIssue)
        assertFalse(state.isSubmittingCrowd)
        assertNull(state.issueReportSuccessMessage)
        assertNull(state.crowdReportSuccessMessage)
        assertNull(state.lastSelectedCrowdLevel)
    }

    @Test
    fun testUiStateDialogTogglesAndSuccessMessages() {
        var state = OperatorUiState()

        // Open Report Issue dialog
        state = state.copy(isReportIssueDialogVisible = true)
        assertTrue(state.isReportIssueDialogVisible)

        // Submit issue completes
        state = state.copy(
            isReportIssueDialogVisible = false,
            issueReportSuccessMessage = "Issue reported to Dispatch (Alert #alert-12)"
        )
        assertFalse(state.isReportIssueDialogVisible)
        assertNotNull(state.issueReportSuccessMessage)

        // Clear issue success
        state = state.copy(issueReportSuccessMessage = null)
        assertNull(state.issueReportSuccessMessage)

        // Open Crowd Level sheet
        state = state.copy(isCrowdLevelSheetVisible = true)
        assertTrue(state.isCrowdLevelSheetVisible)

        // Select VERY CROWDED
        state = state.copy(
            isCrowdLevelSheetVisible = false,
            lastSelectedCrowdLevel = OperatorCrowdLevel.VERY_CROWDED.displayName,
            crowdReportSuccessMessage = "Crowd level updated: VERY CROWDED"
        )
        assertFalse(state.isCrowdLevelSheetVisible)
        assertEquals("VERY CROWDED", state.lastSelectedCrowdLevel)
        assertEquals("Crowd level updated: VERY CROWDED", state.crowdReportSuccessMessage)
    }

    @Test
    fun testCrowdReportEntitySourceIsOperator() {
        val entity = CrowdingReportEntity(
            vehicleId = "veh_999",
            crowdingState = OperatorCrowdLevel.CROWDED.backendState,
            confidence = OperatorCrowdLevel.CROWDED.confidence,
            observedAt = 123456789L,
            isSynced = false,
            source = "OPERATOR"
        )
        assertEquals("HIGH", entity.crowdingState)
        assertEquals(0.8f, entity.confidence, 0.001f)
        assertEquals("OPERATOR", entity.source)
        assertFalse(entity.isSynced)
    }
}
