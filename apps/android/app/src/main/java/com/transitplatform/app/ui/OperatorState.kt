package com.transitplatform.app.ui

import com.transitplatform.app.data.model.AssignmentResponse
import com.transitplatform.app.data.model.LoginResponse

enum class ScreenState {
    LOGIN,
    ASSIGNMENT,
    READINESS,
    TRACKING
}

data class ReadinessCheckState(
    val hasFineLocation: Boolean = false,
    val hasCoarseLocation: Boolean = false,
    val hasNotificationPermission: Boolean = false,
    val isGpsEnabled: Boolean = false,
    val isNetworkAvailable: Boolean = false,
    val batteryPercentage: Int = 100
) {
    val isReadyToTrack: Boolean
        get() = hasFineLocation && hasCoarseLocation && isGpsEnabled
}

data class OperatorUiState(
    val currentScreen: ScreenState = ScreenState.LOGIN,
    val baseUrl: String = "http://10.0.2.2:8000",
    val token: String? = null,
    val userProfile: LoginResponse? = null,
    val assignment: AssignmentResponse? = null,
    val readiness: ReadinessCheckState = ReadinessCheckState(),
    val activeTrackingSessionId: String? = null,
    val isLoading: Boolean = false,
    val errorMessage: String? = null
)
