package com.transitplatform.app.ui

import android.app.Application
import android.content.Context
import android.content.Intent
import android.location.LocationManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.transitplatform.app.data.local.AppDatabase
import com.transitplatform.app.data.local.CrowdingReportEntity
import com.transitplatform.app.data.local.SessionStore
import com.transitplatform.app.data.model.AssignmentResponse
import com.transitplatform.app.data.model.OperatorTripResponse
import com.transitplatform.app.data.network.ApiClient
import com.transitplatform.app.data.network.ApiException
import com.transitplatform.app.service.DutyScheduleManager
import com.transitplatform.app.service.ForegroundTrackingService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID

class OperatorViewModel @JvmOverloads constructor(
    application: Application,
    val sessionStore: SessionStore = SessionStore(application)
) : AndroidViewModel(application) {

    private val apiClient = ApiClient()
    private val _uiState = MutableStateFlow(OperatorUiState())
    val uiState = _uiState.asStateFlow()

    private var pendingColdStartTripIdForReadiness: String? = null

    init {
        restoreSessionSynchronously()

        // Collect live tracking status from ForegroundTrackingService
        viewModelScope.launch {
            ForegroundTrackingService.trackingStatus.collect { status ->
                if (status.isTracking && _uiState.value.currentScreen != ScreenState.TRACKING) {
                    _uiState.update { it.copy(currentScreen = ScreenState.TRACKING, activeTrackingSessionId = status.sessionId) }
                } else if (!status.isTracking && _uiState.value.currentScreen == ScreenState.TRACKING) {
                    _uiState.update { it.copy(currentScreen = ScreenState.ASSIGNMENT, activeTrackingSessionId = null) }
                }
            }
        }
    }

    fun restoreSessionSynchronously() {
        val savedSession = sessionStore.getSession()
        if (savedSession != null) {
            _uiState.update {
                it.copy(
                    token = savedSession.access_token,
                    userProfile = savedSession,
                    currentScreen = ScreenState.ASSIGNMENT,
                    isLoading = false,
                    errorMessage = null
                )
            }
            fetchAssignment()
            fetchTodaysTrips()
        }
    }

    fun setPendingColdStartTripForReadiness(tripId: String) {
        pendingColdStartTripIdForReadiness = tripId
    }

    fun getPendingColdStartTripForReadiness(): String? = pendingColdStartTripIdForReadiness

    fun checkUnauthorized(e: Throwable?): Boolean {
        if (e is ApiException && e.statusCode == 401) return true
        val msg = e?.message?.lowercase() ?: ""
        return msg.contains("401") || msg.contains("credentials") || msg.contains("signature has expired")
    }

    fun handleSessionExpired(detailMessage: String? = null) {
        sessionStore.clearSession()
        DutyScheduleManager.cancelAllReminders(getApplication(), _uiState.value.todaysTrips)
        _uiState.update {
            OperatorUiState(
                currentScreen = ScreenState.LOGIN,
                baseUrl = it.baseUrl,
                errorMessage = detailMessage ?: "Session expired. Please log in again."
            )
        }
    }

    fun updateBaseUrl(url: String) {
        apiClient.setBaseUrl(url)
        _uiState.update { it.copy(baseUrl = url) }
    }

    fun login(
        employeeCode: String,
        password: String,
        initialScreen: ScreenState = ScreenState.ASSIGNMENT,
        openDetailsAfter: Boolean = false
    ) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            val result = apiClient.login(employeeCode, password)
            if (result.isSuccess) {
                val loginResp = result.getOrThrow()
                sessionStore.saveSession(loginResp)
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        token = loginResp.access_token,
                        userProfile = loginResp,
                        currentScreen = initialScreen
                    )
                }
                fetchAssignment()
                fetchTodaysTrips(openDetailsAfter = openDetailsAfter)
            } else {
                val err = result.exceptionOrNull()?.message ?: "Login failed"
                _uiState.update { it.copy(isLoading = false, errorMessage = err) }
            }
        }
    }

    fun fetchAssignment() {
        val currentToken = _uiState.value.token ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            val result = apiClient.getAssignment(currentToken)
            if (result.isSuccess) {
                val assignment = result.getOrNull()
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        assignment = assignment,
                        errorMessage = null
                    )
                }
            } else {
                val err = result.exceptionOrNull()
                if (checkUnauthorized(err)) {
                    handleSessionExpired()
                    return@launch
                }
                val msg = err?.message ?: "Couldn't load today's duty. Check your connection and try again."
                _uiState.update { it.copy(isLoading = false, errorMessage = msg) }
            }
        }
    }

    fun navigateToReadiness(previous: ScreenState = _uiState.value.currentScreen) {
        _uiState.update {
            it.copy(
                currentScreen = ScreenState.READINESS,
                previousScreen = previous,
                readinessGateState = ReadinessGateState.READINESS_REQUIRED,
                errorMessage = null
            )
        }
        checkReadiness()
    }

    fun navigateBackFromReadiness() {
        val prev = _uiState.value.previousScreen
        val target = when (prev) {
            ScreenState.TRIP_DETAILS -> ScreenState.TRIP_DETAILS
            ScreenState.TODAYS_TRIPS -> ScreenState.TODAYS_TRIPS
            else -> ScreenState.ASSIGNMENT
        }
        _uiState.update { it.copy(currentScreen = target) }
    }

    fun checkReadiness() {
        _uiState.update { it.copy(readinessGateState = ReadinessGateState.READINESS_EVALUATING) }
        val context = getApplication<Application>()

        // 1. Authenticated Session
        val token = _uiState.value.token
        val hasAuth = !token.isNullOrBlank() && _uiState.value.userProfile != null

        // 2. Assignment Context from Authoritative Backend Model
        val assignment = _uiState.value.assignment
        val hasTrip = assignment != null &&
                assignment.trip_id.isNotBlank() &&
                assignment.trip_status !in listOf("COMPLETED", "CANCELLED", "ABANDONED")

        val hasVehicle = assignment != null &&
                assignment.vehicle_number.isNotBlank() &&
                assignment.vehicle_number != "UNASSIGNED" &&
                assignment.vehicle_number != "UNKNOWN"

        val hasOperator = assignment != null &&
                assignment.assignment_id.isNotBlank() &&
                assignment.operator_role.isNotBlank() &&
                assignment.assignment_status in listOf("ASSIGNED", "ACTIVE")

        // 3. System Hardware & Permissions
        val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val isGpsOn = locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)

        val connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val activeNetwork = connectivityManager.activeNetwork
        val caps = connectivityManager.getNetworkCapabilities(activeNetwork)
        val isNetworkOn = caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true

        val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val batteryPct = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)

        val hasFine = ContextCompat.checkSelfPermission(
            context,
            android.Manifest.permission.ACCESS_FINE_LOCATION
        ) == android.content.pm.PackageManager.PERMISSION_GRANTED

        val hasCoarse = ContextCompat.checkSelfPermission(
            context,
            android.Manifest.permission.ACCESS_COARSE_LOCATION
        ) == android.content.pm.PackageManager.PERMISSION_GRANTED

        val isNotifRequired = android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU
        val hasNotif = if (isNotifRequired) {
            ContextCompat.checkSelfPermission(
                context,
                android.Manifest.permission.POST_NOTIFICATIONS
            ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        } else {
            true
        }

        val updatedReadiness = ReadinessCheckState(
            hasAuthenticatedSession = hasAuth,
            hasTripAssignment = hasTrip,
            hasVehicleAssignment = hasVehicle,
            hasOperatorAssignment = hasOperator,
            hasFineLocation = hasFine,
            hasCoarseLocation = hasCoarse,
            hasNotificationPermission = hasNotif,
            isNotificationPermissionRequired = isNotifRequired,
            isGpsEnabled = isGpsOn,
            isNetworkAvailable = isNetworkOn,
            batteryPercentage = if (batteryPct in 0..100) batteryPct else 100
        )

        val gateState = if (updatedReadiness.isReadyToTrack) {
            ReadinessGateState.READY_TO_START
        } else {
            ReadinessGateState.BLOCKING_FAIL
        }

        _uiState.update {
            it.copy(
                readiness = updatedReadiness,
                readinessGateState = gateState
            )
        }
    }

    fun startTripTracking() {
        val state = _uiState.value
        // Formal local gate: must be READY_TO_START and all blocking checks pass
        if (state.readinessGateState != ReadinessGateState.READY_TO_START || !state.readiness.isReadyToTrack) {
            return
        }
        // Debounce / prevent duplicate taps
        if (state.isLoading || state.readinessGateState == ReadinessGateState.STARTING) {
            return
        }

        val currentToken = state.token ?: return
        val currentAssignment = state.assignment ?: return

        _uiState.update {
            it.copy(
                readinessGateState = ReadinessGateState.STARTING,
                isLoading = true,
                errorMessage = null
            )
        }

        viewModelScope.launch {
            val result = apiClient.startTrip(currentToken, currentAssignment.trip_id)
            if (result.isSuccess) {
                val startResp = result.getOrThrow()
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        readinessGateState = ReadinessGateState.ACTIVE_TRACKING,
                        activeTrackingSessionId = startResp.tracking_session_id,
                        currentScreen = ScreenState.TRACKING
                    )
                }

                // Cache routing hints (NOT authoritative duty)
                sessionStore.saveRoutingHints(
                    currentAssignment.trip_id,
                    currentAssignment.vehicle_id,
                    currentAssignment.service_code
                )

                // Launch Foreground Location Tracking Service
                val context = getApplication<Application>()
                val intent = Intent(context, ForegroundTrackingService::class.java).apply {
                    action = ForegroundTrackingService.ACTION_START
                    putExtra(ForegroundTrackingService.EXTRA_TOKEN, currentToken)
                    putExtra(ForegroundTrackingService.EXTRA_SESSION_ID, startResp.tracking_session_id)
                    putExtra(ForegroundTrackingService.EXTRA_TRIP_ID, currentAssignment.trip_id)
                    putExtra(ForegroundTrackingService.EXTRA_SERVICE_CODE, currentAssignment.service_code)
                    putExtra(ForegroundTrackingService.EXTRA_VEHICLE_NUMBER, currentAssignment.vehicle_number)
                    putExtra(ForegroundTrackingService.EXTRA_BASE_URL, _uiState.value.baseUrl)
                }
                ContextCompat.startForegroundService(context, intent)
            } else {
                val err = result.exceptionOrNull()?.message ?: "Failed to start tracking session"
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        readinessGateState = ReadinessGateState.READY_TO_START,
                        errorMessage = err
                    )
                }
            }
        }
    }

    fun endTripTracking() {
        val currentToken = _uiState.value.token ?: return
        val currentAssignment = _uiState.value.assignment ?: return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }

            sessionStore.saveRoutingHints(null, null, null)

            // Stop Android Foreground Service
            val context = getApplication<Application>()
            val intent = Intent(context, ForegroundTrackingService::class.java).apply {
                action = ForegroundTrackingService.ACTION_STOP
            }
            context.startService(intent)

            // Cancel duty reminders for this completed trip
            DutyScheduleManager.cancelTripReminders(context, currentAssignment.trip_id)

            // Notify server of manual trip end
            apiClient.endTrip(currentToken, currentAssignment.trip_id)

            _uiState.update {
                it.copy(
                    isLoading = false,
                    activeTrackingSessionId = null,
                    currentScreen = ScreenState.ASSIGNMENT,
                    readinessGateState = ReadinessGateState.NOT_EVALUATED
                )
            }
            fetchAssignment()
        }
    }


    fun logout() {
        val context = getApplication<Application>()
        val intent = Intent(context, ForegroundTrackingService::class.java).apply {
            action = ForegroundTrackingService.ACTION_STOP
        }
        context.startService(intent)

        DutyScheduleManager.cancelAllReminders(context, _uiState.value.todaysTrips)
        sessionStore.clearSession()

        _uiState.update {
            OperatorUiState(
                currentScreen = ScreenState.LOGIN,
                baseUrl = it.baseUrl
            )
        }
    }

    fun navigateToTodaysTrips() {
        _uiState.update { it.copy(currentScreen = ScreenState.TODAYS_TRIPS) }
        fetchTodaysTrips()
    }

    fun fetchTodaysTrips(
        openDetailsAfter: Boolean = false,
        targetTripIdForReadiness: String? = null
    ) {
        val currentToken = _uiState.value.token ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isTripsLoading = true, tripsErrorMessage = null) }
            val result = apiClient.getTodaysTrips(currentToken)
            if (result.isSuccess) {
                val trips = result.getOrNull() ?: emptyList()
                val targetTrip = if (openDetailsAfter && trips.isNotEmpty()) {
                    trips.firstOrNull { it.is_next } ?: trips.first()
                } else null
                _uiState.update {
                    it.copy(
                        isTripsLoading = false,
                        todaysTrips = trips,
                        tripsErrorMessage = null,
                        selectedTripForDetails = targetTrip ?: it.selectedTripForDetails,
                        currentScreen = if (targetTrip != null) ScreenState.TRIP_DETAILS else it.currentScreen
                    )
                }

                // Schedule local duty reminders for today's trips
                DutyScheduleManager.scheduleTripReminders(getApplication(), trips)

                // If launched from duty notification with specific trip_id, open Readiness for that trip
                val tripTarget = targetTripIdForReadiness ?: pendingColdStartTripIdForReadiness
                pendingColdStartTripIdForReadiness = null
                if (!tripTarget.isNullOrBlank()) {
                    val resolved = selectTripByIdForReadiness(tripTarget)
                    if (!resolved) {
                        _uiState.update {
                            it.copy(errorMessage = "Assigned trip not found. Please check your schedule.")
                        }
                    }
                }
            } else {
                val err = result.exceptionOrNull()
                if (checkUnauthorized(err)) {
                    handleSessionExpired()
                    return@launch
                }
                val msg = err?.message ?: "Couldn't load today's trips. Check your connection and try again."
                _uiState.update { it.copy(isTripsLoading = false, tripsErrorMessage = msg) }
            }
        }
    }

    fun selectTripByIdForReadiness(tripId: String): Boolean {
        val matchingTrip = _uiState.value.todaysTrips.firstOrNull { it.trip_id == tripId }
        if (matchingTrip != null) {
            selectTripForReadiness(matchingTrip)
            return true
        }
        val currentAssignment = _uiState.value.assignment
        if (currentAssignment != null && currentAssignment.trip_id == tripId) {
            navigateToReadiness()
            return true
        }
        return false
    }

    fun selectTripForReadiness(trip: OperatorTripResponse) {
        val currentAssignment = _uiState.value.assignment
        val prev = _uiState.value.currentScreen
        if (currentAssignment != null && currentAssignment.trip_id == trip.trip_id) {
            navigateToReadiness(previous = prev)
        } else {
            val tempAssignment = AssignmentResponse(
                assignment_id = trip.assignment_id,
                trip_id = trip.trip_id,
                service_id = currentAssignment?.service_id ?: "",
                service_code = trip.service_code,
                service_name = trip.service_name,
                route_id = currentAssignment?.route_id ?: "",
                route_code = trip.route_code,
                route_name = trip.route_name,
                direction = trip.direction,
                vehicle_id = currentAssignment?.vehicle_id ?: "",
                vehicle_number = trip.vehicle_number,
                planned_start_at = trip.planned_start_at,
                trip_status = trip.trip_status,
                operator_role = trip.operator_role,
                assignment_status = trip.assignment_status,
                assigned_device_id = currentAssignment?.assigned_device_id,
                assigned_device_status = currentAssignment?.assigned_device_status,
                active_tracking_session_id = currentAssignment?.active_tracking_session_id,
                tracking_session_status = currentAssignment?.tracking_session_status,
                vehicle_registration = trip.vehicle_registration,
                vehicle_type = trip.vehicle_type,
                origin_stop_name = trip.origin_stop_name,
                destination_stop_name = trip.destination_stop_name,
                route_distance_km = trip.route_distance_km
            )
            _uiState.update { it.copy(assignment = tempAssignment) }
            navigateToReadiness(previous = prev)
        }
    }


    fun selectTripForDetails(trip: OperatorTripResponse) {
        _uiState.update {
            it.copy(
                selectedTripForDetails = trip,
                currentScreen = ScreenState.TRIP_DETAILS
            )
        }
    }

    fun navigateBackToTodaysTrips() {
        _uiState.update {
            it.copy(currentScreen = ScreenState.TODAYS_TRIPS)
        }
    }

    fun navigateBackToAssignment() {
        _uiState.update { it.copy(currentScreen = ScreenState.ASSIGNMENT) }
    }

    // Active Trip Controls (1.0.6)
    fun showReportIssueDialog() {
        _uiState.update { it.copy(isReportIssueDialogVisible = true, errorMessage = null) }
    }

    fun dismissReportIssueDialog() {
        _uiState.update { it.copy(isReportIssueDialogVisible = false) }
    }

    fun showCrowdLevelSheet() {
        _uiState.update { it.copy(isCrowdLevelSheetVisible = true, errorMessage = null) }
    }

    fun dismissCrowdLevelSheet() {
        _uiState.update { it.copy(isCrowdLevelSheetVisible = false) }
    }

    fun openActiveTripScreen() {
        // Pure UI transition: does not start/restart trip, does not call trip-start API, does not create service
        if (_uiState.value.token != null) {
            _uiState.update { it.copy(currentScreen = ScreenState.TRACKING) }
        }
    }

    fun reportIssue(issueType: String, message: String, severity: String = "WARNING") {
        val currentToken = _uiState.value.token ?: return
        val currentAssignment = _uiState.value.assignment ?: return

        viewModelScope.launch {
            _uiState.update { it.copy(isSubmittingIssue = true, errorMessage = null) }
            val result = apiClient.reportOperatorIssue(
                token = currentToken,
                tripId = currentAssignment.trip_id,
                issueType = issueType,
                message = message,
                severity = severity
            )

            if (result.isSuccess) {
                val alert = result.getOrThrow()
                _uiState.update {
                    it.copy(
                        isSubmittingIssue = false,
                        isReportIssueDialogVisible = false,
                        issueReportSuccessMessage = "Issue reported to Dispatch (Alert #${alert.alert_id.take(8)})"
                    )
                }
            } else {
                val err = result.exceptionOrNull()?.message ?: "Failed to report issue"
                _uiState.update {
                    it.copy(
                        isSubmittingIssue = false,
                        errorMessage = err
                    )
                }
            }
        }
    }

    fun submitCrowdLevel(level: OperatorCrowdLevel) {
        val currentToken = _uiState.value.token ?: return
        val currentAssignment = _uiState.value.assignment ?: return
        val vehicleId = currentAssignment.vehicle_id

        viewModelScope.launch {
            _uiState.update { it.copy(isSubmittingCrowd = true, errorMessage = null) }

            val reportId = UUID.randomUUID().toString()
            val nowMillis = System.currentTimeMillis()
            val dateFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
                timeZone = TimeZone.getTimeZone("UTC")
            }
            val observedAtIso = dateFormat.format(Date(nowMillis))

            val result = apiClient.uploadCrowdingReport(
                token = currentToken,
                reportId = reportId,
                vehicleId = vehicleId,
                crowdingState = level.backendState,
                confidence = level.confidence,
                observedAt = observedAtIso
            )

            val database = AppDatabase.getInstance(getApplication())
            if (result.isSuccess) {
                try {
                    database.crowdingDao().insertReport(
                        CrowdingReportEntity(
                            id = reportId,
                            vehicleId = vehicleId,
                            crowdingState = level.backendState,
                            confidence = level.confidence,
                            observedAt = nowMillis,
                            isSynced = true,
                            source = "OPERATOR"
                        )
                    )
                } catch (_: Exception) {}

                _uiState.update {
                    it.copy(
                        isSubmittingCrowd = false,
                        isCrowdLevelSheetVisible = false,
                        lastSelectedCrowdLevel = level.displayName,
                        crowdReportSuccessMessage = "Crowd level updated: ${level.displayName}"
                    )
                }
            } else {
                try {
                    database.crowdingDao().insertReport(
                        CrowdingReportEntity(
                            id = reportId,
                            vehicleId = vehicleId,
                            crowdingState = level.backendState,
                            confidence = level.confidence,
                            observedAt = nowMillis,
                            isSynced = false,
                            source = "OPERATOR"
                        )
                    )
                } catch (_: Exception) {}

                _uiState.update {
                    it.copy(
                        isSubmittingCrowd = false,
                        isCrowdLevelSheetVisible = false,
                        lastSelectedCrowdLevel = level.displayName,
                        crowdReportSuccessMessage = "Saved offline: ${level.displayName} (will sync automatically)"
                    )
                }
            }
        }
    }

    fun clearIssueSuccessMessage() {
        _uiState.update { it.copy(issueReportSuccessMessage = null) }
    }

    fun clearCrowdSuccessMessage() {
        _uiState.update { it.copy(crowdReportSuccessMessage = null) }
    }
}

