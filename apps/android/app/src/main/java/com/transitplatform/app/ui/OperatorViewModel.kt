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
import com.transitplatform.app.data.network.ApiClient
import com.transitplatform.app.service.ForegroundTrackingService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class OperatorViewModel(application: Application) : AndroidViewModel(application) {

    private val apiClient = ApiClient()
    private val _uiState = MutableStateFlow(OperatorUiState())
    val uiState = _uiState.asStateFlow()

    init {
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

    fun updateBaseUrl(url: String) {
        apiClient.setBaseUrl(url)
        _uiState.update { it.copy(baseUrl = url) }
    }

    fun login(employeeCode: String, password: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            val result = apiClient.login(employeeCode, password)
            if (result.isSuccess) {
                val loginResp = result.getOrThrow()
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        token = loginResp.access_token,
                        userProfile = loginResp,
                        currentScreen = ScreenState.ASSIGNMENT
                    )
                }
                fetchAssignment()
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
                val assignment = result.getOrThrow()
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        assignment = assignment
                    )
                }
            } else {
                val err = result.exceptionOrNull()?.message ?: "Failed to load duty assignment"
                _uiState.update { it.copy(isLoading = false, errorMessage = err) }
            }
        }
    }

    fun navigateToReadiness() {
        checkReadiness()
        _uiState.update { it.copy(currentScreen = ScreenState.READINESS) }
    }

    fun checkReadiness() {
        val context = getApplication<Application>()
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

        val hasNotif = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                context,
                android.Manifest.permission.POST_NOTIFICATIONS
            ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        } else {
            true
        }

        _uiState.update {
            it.copy(
                readiness = ReadinessCheckState(
                    hasFineLocation = hasFine,
                    hasCoarseLocation = hasCoarse,
                    hasNotificationPermission = hasNotif,
                    isGpsEnabled = isGpsOn,
                    isNetworkAvailable = isNetworkOn,
                    batteryPercentage = if (batteryPct in 0..100) batteryPct else 100
                )
            )
        }
    }

    fun startTripTracking() {
        val currentToken = _uiState.value.token ?: return
        val currentAssignment = _uiState.value.assignment ?: return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            val result = apiClient.startTrip(currentToken, currentAssignment.trip_id)
            if (result.isSuccess) {
                val startResp = result.getOrThrow()
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        activeTrackingSessionId = startResp.tracking_session_id,
                        currentScreen = ScreenState.TRACKING
                    )
                }

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
                _uiState.update { it.copy(isLoading = false, errorMessage = err) }
            }
        }
    }

    fun endTripTracking() {
        val currentToken = _uiState.value.token ?: return
        val currentAssignment = _uiState.value.assignment ?: return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }

            // Stop Android Foreground Service
            val context = getApplication<Application>()
            val intent = Intent(context, ForegroundTrackingService::class.java).apply {
                action = ForegroundTrackingService.ACTION_STOP
            }
            context.startService(intent)

            // Notify server of manual trip end
            apiClient.endTrip(currentToken, currentAssignment.trip_id)

            _uiState.update {
                it.copy(
                    isLoading = false,
                    activeTrackingSessionId = null,
                    currentScreen = ScreenState.ASSIGNMENT
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

        _uiState.update {
            OperatorUiState(
                currentScreen = ScreenState.LOGIN,
                baseUrl = it.baseUrl
            )
        }
    }

    fun navigateBackToAssignment() {
        _uiState.update { it.copy(currentScreen = ScreenState.ASSIGNMENT) }
    }
}
