package com.transitplatform.app.ui

import com.transitplatform.app.data.model.AssignmentResponse
import com.transitplatform.app.data.model.LoginResponse
import com.transitplatform.app.data.model.OperatorTripResponse

enum class ScreenState {
    LOGIN,
    ASSIGNMENT,
    TODAYS_TRIPS,
    TRIP_DETAILS,
    READINESS,
    TRACKING
}

enum class ReadinessGateState {
    NOT_EVALUATED,
    READINESS_REQUIRED,
    READINESS_EVALUATING,
    BLOCKING_FAIL,
    READY_TO_START,
    STARTING,
    ACTIVE_TRACKING
}

data class ReadinessCheckState(
    val hasAuthenticatedSession: Boolean = false,
    val hasTripAssignment: Boolean = false,
    val hasVehicleAssignment: Boolean = false,
    val hasOperatorAssignment: Boolean = false,
    val hasFineLocation: Boolean = false,
    val hasCoarseLocation: Boolean = false,
    val hasNotificationPermission: Boolean = false,
    val isNotificationPermissionRequired: Boolean = true,
    val isGpsEnabled: Boolean = false,
    val isNetworkAvailable: Boolean = false,
    val batteryPercentage: Int = 100
) {
    val hasNotificationCheckPassed: Boolean
        get() = if (isNotificationPermissionRequired) hasNotificationPermission else true

    val hasBlockingLocationPassed: Boolean
        get() = hasFineLocation && isGpsEnabled

    val hasBlockingAssignmentPassed: Boolean
        get() = hasAuthenticatedSession && hasTripAssignment && hasVehicleAssignment && hasOperatorAssignment

    /**
     * Core product rule: Readiness is mandatory.
     * All BLOCKING checks must pass for Start Trip to be enabled.
     * WARNING checks (offline network, battery <= 15%) do NOT block.
     * INFORMATIONAL checks (healthy battery, coarse location) do NOT block.
     */
    val isReadyToTrack: Boolean
        get() = hasBlockingAssignmentPassed && hasBlockingLocationPassed && hasNotificationCheckPassed

    val blockingFailuresCount: Int
        get() {
            var count = 0
            if (!hasAuthenticatedSession) count++
            if (!hasTripAssignment) count++
            if (!hasVehicleAssignment) count++
            if (!hasOperatorAssignment) count++
            if (!hasFineLocation) count++
            if (!isGpsEnabled) count++
            if (!hasNotificationCheckPassed) count++
            return count
        }

    val warningCount: Int
        get() {
            var count = 0
            if (!isNetworkAvailable) count++
            if (batteryPercentage <= 15) count++
            return count
        }
}

enum class OperatorCrowdLevel(
    val levelNumber: Int,
    val displayName: String,
    val backendState: String,
    val confidence: Float,
    val description: String
) {
    NOT_CROWDED(1, "NOT CROWDED", "LOW", 1.0f, "Many empty seats available"),
    MODERATE(2, "MODERATE", "MODERATE", 1.0f, "Some seats available, no standees"),
    CROWDED(3, "CROWDED", "HIGH", 0.8f, "Few seats left, standing room only"),
    VERY_CROWDED(4, "VERY CROWDED", "HIGH", 1.0f, "Packed bus, limited standing room"),
    FULL(5, "FULL", "FULL", 1.0f, "No boarding, at maximum capacity")
}

data class OperatorUiState(
    val currentScreen: ScreenState = ScreenState.LOGIN,
    val baseUrl: String = com.transitplatform.app.BuildConfig.BASE_URL,
    val token: String? = null,
    val userProfile: LoginResponse? = null,
    val assignment: AssignmentResponse? = null,
    val todaysTrips: List<OperatorTripResponse> = emptyList(),
    val selectedTripForDetails: OperatorTripResponse? = null,
    val isTripsLoading: Boolean = false,
    val tripsErrorMessage: String? = null,
    val readiness: ReadinessCheckState = ReadinessCheckState(),
    val readinessGateState: ReadinessGateState = ReadinessGateState.NOT_EVALUATED,
    val previousScreen: ScreenState = ScreenState.ASSIGNMENT,
    val activeTrackingSessionId: String? = null,
    val isLoading: Boolean = false,
    val errorMessage: String? = null,

    // Active Trip Controls (1.0.6)
    val isReportIssueDialogVisible: Boolean = false,
    val isCrowdLevelSheetVisible: Boolean = false,
    val isSubmittingIssue: Boolean = false,
    val isSubmittingCrowd: Boolean = false,
    val issueReportSuccessMessage: String? = null,
    val crowdReportSuccessMessage: String? = null,
    val lastSelectedCrowdLevel: String? = null
)


