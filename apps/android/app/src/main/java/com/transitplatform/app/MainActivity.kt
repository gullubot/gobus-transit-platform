package com.transitplatform.app

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import com.transitplatform.app.service.ForegroundTrackingService
import com.transitplatform.app.service.ScheduleNotificationHelper
import com.transitplatform.app.ui.ActiveTrackingScreen
import com.transitplatform.app.ui.AssignmentScreen
import com.transitplatform.app.ui.LoginScreen
import com.transitplatform.app.ui.OperatorViewModel
import com.transitplatform.app.ui.ReadinessScreen
import com.transitplatform.app.ui.ScreenState
import com.transitplatform.app.ui.TodaysTripsScreen
import com.transitplatform.app.ui.TripDetailsScreen
import com.transitplatform.app.ui.theme.TransitPlatformTheme

class MainActivity : ComponentActivity() {

    companion object {
        const val EXTRA_INTENT_CONSUMED = "com.transitplatform.app.EXTRA_INTENT_CONSUMED"
    }

    private val viewModel: OperatorViewModel by viewModels()
    private var lastProcessedIntentSignature: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        handleNotificationIntent(intent)
        enableEdgeToEdge()
        setContent {
            TransitPlatformTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    OperatorAppRoot(
                        viewModel = viewModel,
                        modifier = Modifier.padding(innerPadding)
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleNotificationIntent(intent)
    }

    private fun handleNotificationIntent(intent: Intent?) {
        if (intent == null) return

        // 1. Idempotency Guard: prevent duplicate execution across recreation / recomposition
        if (intent.getBooleanExtra(EXTRA_INTENT_CONSUMED, false)) {
            return
        }

        val action = intent.getStringExtra("action") ?: intent.action
        val openAction = intent.getStringExtra(ForegroundTrackingService.EXTRA_OPEN_ACTION)
        val tripId = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_TRIP_ID)
            ?: intent.getStringExtra("trip_id")

        val intentSignature = "$action|$openAction|$tripId|${intent.flags}"
        if (intentSignature == lastProcessedIntentSignature) {
            return
        }

        intent.putExtra(EXTRA_INTENT_CONSUMED, true)
        lastProcessedIntentSignature = intentSignature

        // 2. Authentication Gate: No notification action may bypass authentication
        val hasAuth = viewModel.uiState.value.token != null || viewModel.sessionStore.hasSession()

        if (action == ScheduleNotificationHelper.ACTION_START_TRACKING_INTENT) {
            if (hasAuth) {
                if (viewModel.uiState.value.token == null) {
                    viewModel.restoreSessionSynchronously()
                }
                if (!tripId.isNullOrBlank()) {
                    val handled = viewModel.selectTripByIdForReadiness(tripId)
                    if (!handled) {
                        viewModel.setPendingColdStartTripForReadiness(tripId)
                        viewModel.fetchTodaysTrips(targetTripIdForReadiness = tripId)
                    }
                } else if (viewModel.uiState.value.assignment != null) {
                    viewModel.navigateToReadiness()
                }
            }
        } else if (action == ScheduleNotificationHelper.ACTION_SNOOZE_INTENT) {
            ScheduleNotificationHelper.dismissNotification(
                this,
                ScheduleNotificationHelper.NOTIF_UPCOMING_TRIP_ID
            )
        }

        // Active Trip Controls Notification Actions (1.0.6 & 1.0.7)
        if (hasAuth) {
            if (viewModel.uiState.value.token == null) {
                viewModel.restoreSessionSynchronously()
            }
            if (openAction == ForegroundTrackingService.ACTION_NAME_OPEN_TRIP ||
                openAction == ForegroundTrackingService.ACTION_OPEN_TRIP
            ) {
                viewModel.openActiveTripScreen()
            } else if (openAction == ForegroundTrackingService.ACTION_NAME_REPORT_ISSUE ||
                openAction == ForegroundTrackingService.ACTION_REPORT_ISSUE
            ) {
                viewModel.openActiveTripScreen()
                viewModel.showReportIssueDialog()
            } else if (openAction == ForegroundTrackingService.ACTION_NAME_CROWD_LEVEL ||
                openAction == ForegroundTrackingService.ACTION_CROWD_LEVEL
            ) {
                viewModel.openActiveTripScreen()
                viewModel.showCrowdLevelSheet()
            }
        }

        val customUrl = intent?.getStringExtra("base_url")
        if (!customUrl.isNullOrBlank()) {
            viewModel.updateBaseUrl(customUrl)
        }

        val autoCode = intent?.getStringExtra("employee_code")
        val autoPwd = intent?.getStringExtra("password") ?: "operator123"
        val openTrips = (intent?.getBooleanExtra("open_todays_trips", false) ?: false) ||
                intent?.getStringExtra("open_todays_trips") == "true"
        val openTripDetails = (intent?.getBooleanExtra("open_trip_details", false) ?: false) ||
                intent?.getStringExtra("open_trip_details") == "true"
        val navigateBack = (intent?.getBooleanExtra("navigate_back", false) ?: false) ||
                intent?.getStringExtra("navigate_back") == "true"

        if (navigateBack) {
            if (viewModel.uiState.value.currentScreen == ScreenState.TRIP_DETAILS) {
                viewModel.navigateBackToTodaysTrips()
            } else if (viewModel.uiState.value.currentScreen == ScreenState.TODAYS_TRIPS) {
                viewModel.navigateBackToAssignment()
            }
        } else if (openTripDetails && viewModel.uiState.value.token != null) {
            val trips = viewModel.uiState.value.todaysTrips
            if (trips.isNotEmpty()) {
                val trip = trips.firstOrNull { it.is_next } ?: trips.first()
                viewModel.selectTripForDetails(trip)
            } else {
                viewModel.fetchTodaysTrips(openDetailsAfter = true)
            }
        } else if (openTrips && viewModel.uiState.value.token != null) {
            viewModel.navigateToTodaysTrips()
        } else if (!autoCode.isNullOrBlank()) {
            val targetScreen = if (openTripDetails || openTrips) ScreenState.TODAYS_TRIPS else ScreenState.ASSIGNMENT
            viewModel.login(
                autoCode,
                autoPwd,
                initialScreen = targetScreen,
                openDetailsAfter = openTripDetails
            )
        }
    }
}

@Composable
fun OperatorAppRoot(
    viewModel: OperatorViewModel,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsState()

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) {
        viewModel.checkReadiness()
    }

    fun requestPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        permissionLauncher.launch(permissions.toTypedArray())
    }

    when (uiState.currentScreen) {
        ScreenState.LOGIN -> {
            LoginScreen(
                uiState = uiState,
                onLogin = { code, pwd -> viewModel.login(code, pwd) },
                onUpdateBaseUrl = { url -> viewModel.updateBaseUrl(url) }
            )
        }
        ScreenState.ASSIGNMENT -> {
            AssignmentScreen(
                uiState = uiState,
                onRefresh = { viewModel.fetchAssignment() },
                onStartTrackingClicked = { viewModel.navigateToReadiness() },
                onNavigateToTodaysTrips = { viewModel.navigateToTodaysTrips() },
                onLogout = { viewModel.logout() }
            )
        }
        ScreenState.TODAYS_TRIPS -> {
            TodaysTripsScreen(
                uiState = uiState,
                onBack = { viewModel.navigateBackToAssignment() },
                onRefresh = { viewModel.fetchTodaysTrips() },
                onStartTrip = { trip -> viewModel.selectTripForReadiness(trip) },
                onSelectTrip = { trip -> viewModel.selectTripForDetails(trip) }
            )
        }
        ScreenState.TRIP_DETAILS -> {
            val trip = uiState.selectedTripForDetails
            if (trip != null) {
                TripDetailsScreen(
                    trip = trip,
                    onBack = { viewModel.navigateBackToTodaysTrips() },
                    onStartTrip = { t -> viewModel.selectTripForReadiness(t) }
                )
            } else {
                viewModel.navigateBackToTodaysTrips()
            }
        }
        ScreenState.READINESS -> {
            ReadinessScreen(
                uiState = uiState,
                onRequestPermissions = { requestPermissions() },
                onConfirmStart = { viewModel.startTripTracking() },
                onBack = { viewModel.navigateBackFromReadiness() },
                onRecheckReadiness = { viewModel.checkReadiness() }
            )
        }
        ScreenState.TRACKING -> {
            ActiveTrackingScreen(
                uiState = uiState,
                onEndTripClicked = { viewModel.endTripTracking() },
                onShowReportIssue = { viewModel.showReportIssueDialog() },
                onShowCrowdLevel = { viewModel.showCrowdLevelSheet() },
                onReportIssue = { type, msg, sev -> viewModel.reportIssue(type, msg, sev) },
                onSelectCrowdLevel = { level -> viewModel.submitCrowdLevel(level) },
                onDismissIssueDialog = { viewModel.dismissReportIssueDialog() },
                onDismissCrowdSheet = { viewModel.dismissCrowdLevelSheet() },
                onClearIssueSuccess = { viewModel.clearIssueSuccessMessage() },
                onClearCrowdSuccess = { viewModel.clearCrowdSuccessMessage() }
            )
        }
    }
}
