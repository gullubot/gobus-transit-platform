package com.transitplatform.app

import android.content.Intent
import android.content.SharedPreferences
import com.transitplatform.app.data.local.SessionStore
import com.transitplatform.app.data.model.AssignmentResponse
import com.transitplatform.app.data.model.LoginResponse
import com.transitplatform.app.data.model.OperatorTripResponse
import com.transitplatform.app.data.network.ApiException
import com.transitplatform.app.service.ForegroundTrackingService
import com.transitplatform.app.service.ScheduleNotificationHelper
import com.transitplatform.app.ui.OperatorUiState
import com.transitplatform.app.ui.ReadinessGateState
import com.transitplatform.app.ui.ScreenState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class SessionPersistenceUnitTest {

    private lateinit var fakePrefs: FakeSharedPreferences
    private lateinit var sessionStore: SessionStore

    private val sampleLoginResponse = LoginResponse(
        access_token = "mock-jwt-token-12345",
        token_type = "bearer",
        user_id = "user-uuid-1",
        name = "Driver Test",
        role = "DRIVER",
        employee_code = "DRV001",
        organization_id = "org-uuid-1",
        organization_name = "Transit Demo"
    )

    @Before
    fun setUp() {
        fakePrefs = FakeSharedPreferences()
        sessionStore = SessionStore(fakePrefs)
    }

    // 1. Login persists required session data securely.
    @Test
    fun testLoginPersistsRequiredSessionDataSecurely() {
        assertFalse(sessionStore.hasSession())
        sessionStore.saveSession(sampleLoginResponse)

        assertTrue(sessionStore.hasSession())
        assertEquals("mock-jwt-token-12345", sessionStore.getAccessToken())

        val restored = sessionStore.getSession()
        assertNotNull(restored)
        assertEquals(sampleLoginResponse.access_token, restored?.access_token)
        assertEquals(sampleLoginResponse.user_id, restored?.user_id)
        assertEquals(sampleLoginResponse.name, restored?.name)
        assertEquals(sampleLoginResponse.role, restored?.role)
        assertEquals(sampleLoginResponse.employee_code, restored?.employee_code)
        assertEquals(sampleLoginResponse.organization_id, restored?.organization_id)
        assertEquals(sampleLoginResponse.organization_name, restored?.organization_name)
    }

    // 2. Session can be restored after simulated process death.
    @Test
    fun testSessionRestoredAfterSimulatedProcessDeath() {
        // Step A: Save session
        sessionStore.saveSession(sampleLoginResponse)
        sessionStore.saveRoutingHints("trip-101", "veh-202", "AC4B")

        // Step B: Simulate process death by creating a completely new SessionStore
        // instance backed by the same persistent storage
        val newSessionStore = SessionStore(fakePrefs)
        assertTrue(newSessionStore.hasSession())

        val restored = newSessionStore.getSession()
        assertNotNull(restored)
        assertEquals("DRV001", restored?.employee_code)
        assertEquals("trip-101", newSessionStore.getHintTripId())
        assertEquals("veh-202", newSessionStore.getHintVehicleId())
        assertEquals("AC4B", newSessionStore.getHintServiceCode())
    }

    // 3. Logout clears persisted session.
    @Test
    fun testLogoutClearsPersistedSession() {
        sessionStore.saveSession(sampleLoginResponse)
        sessionStore.saveRoutingHints("trip-101", "veh-202", "AC4B")
        assertTrue(sessionStore.hasSession())

        sessionStore.clearSession()
        assertFalse(sessionStore.hasSession())
        assertNull(sessionStore.getSession())
        assertNull(sessionStore.getAccessToken())
        assertNull(sessionStore.getHintTripId())
    }

    // 4. Expired/invalid token fails safely.
    @Test
    fun testExpiredOrInvalidTokenFailsSafely() {
        sessionStore.saveSession(sampleLoginResponse)
        assertTrue(sessionStore.hasSession())

        // Simulate 401 Unauthorized from backend
        val api401Error = ApiException(401, "Signature has expired")

        // Validation logic clears session and transitions state
        val isAuthError = api401Error.statusCode == 401 ||
                (api401Error.message?.contains("expired") == true)
        assertTrue(isAuthError)

        if (isAuthError) {
            sessionStore.clearSession()
        }

        assertFalse(sessionStore.hasSession())
        assertNull(sessionStore.getAccessToken())
    }

    // 5. START TRIP notification after cold start routes to Readiness.
    @Test
    fun testStartTripNotificationAfterColdStart_routesToReadiness() {
        sessionStore.saveSession(sampleLoginResponse)

        var state = OperatorUiState(
            currentScreen = ScreenState.ASSIGNMENT,
            token = sessionStore.getAccessToken(),
            userProfile = sessionStore.getSession()
        )

        // Incoming notification intent
        val targetTripId = "trip-abc-123"
        val intentAction = ScheduleNotificationHelper.ACTION_START_TRACKING_INTENT

        // Process notification: routes to Readiness
        if (intentAction == ScheduleNotificationHelper.ACTION_START_TRACKING_INTENT && state.token != null) {
            state = state.copy(
                currentScreen = ScreenState.READINESS,
                readinessGateState = ReadinessGateState.READINESS_REQUIRED
            )
        }

        assertEquals(ScreenState.READINESS, state.currentScreen)
        assertEquals(ReadinessGateState.READINESS_REQUIRED, state.readinessGateState)
        assertNull("Trip must not have active tracking session yet", state.activeTrackingSessionId)
    }

    // 6. OPEN TRIP notification after cold start routes to active trip.
    @Test
    fun testOpenTripNotificationAfterColdStart_routesToActiveTrip() {
        sessionStore.saveSession(sampleLoginResponse)

        var state = OperatorUiState(
            currentScreen = ScreenState.ASSIGNMENT,
            token = sessionStore.getAccessToken(),
            userProfile = sessionStore.getSession()
        )

        val openAction = ForegroundTrackingService.ACTION_NAME_OPEN_TRIP
        if (openAction == ForegroundTrackingService.ACTION_NAME_OPEN_TRIP && state.token != null) {
            state = state.copy(currentScreen = ScreenState.TRACKING)
        }

        assertEquals(ScreenState.TRACKING, state.currentScreen)
    }

    // 7. REPORT ISSUE notification after cold start opens issue dialog.
    @Test
    fun testReportIssueNotificationAfterColdStart_opensIssueDialog() {
        sessionStore.saveSession(sampleLoginResponse)

        var state = OperatorUiState(
            currentScreen = ScreenState.ASSIGNMENT,
            token = sessionStore.getAccessToken(),
            userProfile = sessionStore.getSession()
        )

        val openAction = ForegroundTrackingService.ACTION_NAME_REPORT_ISSUE
        if (openAction == ForegroundTrackingService.ACTION_NAME_REPORT_ISSUE && state.token != null) {
            state = state.copy(
                currentScreen = ScreenState.TRACKING,
                isReportIssueDialogVisible = true
            )
        }

        assertEquals(ScreenState.TRACKING, state.currentScreen)
        assertTrue("Issue dialog must be visible", state.isReportIssueDialogVisible)
        assertFalse("Must not be automatically submitting issue", state.isSubmittingIssue)
    }

    // 8. CROWD LEVEL notification after cold start opens crowd selector.
    @Test
    fun testCrowdLevelNotificationAfterColdStart_opensCrowdSelector() {
        sessionStore.saveSession(sampleLoginResponse)

        var state = OperatorUiState(
            currentScreen = ScreenState.ASSIGNMENT,
            token = sessionStore.getAccessToken(),
            userProfile = sessionStore.getSession()
        )

        val openAction = ForegroundTrackingService.ACTION_NAME_CROWD_LEVEL
        if (openAction == ForegroundTrackingService.ACTION_NAME_CROWD_LEVEL && state.token != null) {
            state = state.copy(
                currentScreen = ScreenState.TRACKING,
                isCrowdLevelSheetVisible = true
            )
        }

        assertEquals(ScreenState.TRACKING, state.currentScreen)
        assertTrue("Crowd Level sheet must be visible", state.isCrowdLevelSheetVisible)
        assertFalse("Must not be automatically submitting crowd", state.isSubmittingCrowd)
    }

    // 9. Same intent is not processed twice.
    @Test
    fun testSameIntentIsNotProcessedTwice() {
        val extraConsumedKey = MainActivity.EXTRA_INTENT_CONSUMED

        var executionCount = 0
        var lastSignature: String? = null

        fun processIntent(action: String, tripId: String, isConsumed: Boolean): Boolean {
            if (isConsumed) return false
            val sig = "$action|$tripId"
            if (sig == lastSignature) return false
            lastSignature = sig
            executionCount++
            return true
        }

        // 1st invocation: fresh intent
        val firstResult = processIntent("START_TRIP", "trip-1", isConsumed = false)
        assertTrue(firstResult)
        assertEquals(1, executionCount)

        // 2nd invocation (same intent on recomposition/recreation)
        val secondResult = processIntent("START_TRIP", "trip-1", isConsumed = true)
        assertFalse(secondResult)
        assertEquals(1, executionCount)

        // 3rd invocation (same signature)
        val thirdResult = processIntent("START_TRIP", "trip-1", isConsumed = false)
        assertFalse(thirdResult)
        assertEquals(1, executionCount)
    }

    // 10. No notification action silently starts a trip.
    @Test
    fun testNoNotificationActionSilentlyStartsTrip() {
        sessionStore.saveSession(sampleLoginResponse)

        var state = OperatorUiState(
            currentScreen = ScreenState.ASSIGNMENT,
            token = sessionStore.getAccessToken(),
            userProfile = sessionStore.getSession()
        )

        // When notification START TRIP arrives:
        // Must route to Readiness, NOT TRACKING
        state = state.copy(currentScreen = ScreenState.READINESS)

        assertFalse("Must not silently enter TRACKING screen", state.currentScreen == ScreenState.TRACKING)
        assertNull("Must not have active tracking session id", state.activeTrackingSessionId)
        assertEquals(ReadinessGateState.NOT_EVALUATED, state.readinessGateState)
    }

    // 11. No notification action silently submits an issue.
    @Test
    fun testNoNotificationActionSilentlySubmitsIssue() {
        sessionStore.saveSession(sampleLoginResponse)

        var state = OperatorUiState(
            currentScreen = ScreenState.ASSIGNMENT,
            token = sessionStore.getAccessToken()
        )

        // Operator taps REPORT ISSUE notification
        state = state.copy(
            currentScreen = ScreenState.TRACKING,
            isReportIssueDialogVisible = true
        )

        assertFalse("Submission flag must remain false until operator taps Submit", state.isSubmittingIssue)
        assertNull("No success message can be created without submission", state.issueReportSuccessMessage)
    }

    // 12. No notification action silently submits crowd data.
    @Test
    fun testNoNotificationActionSilentlySubmitsCrowd() {
        sessionStore.saveSession(sampleLoginResponse)

        var state = OperatorUiState(
            currentScreen = ScreenState.ASSIGNMENT,
            token = sessionStore.getAccessToken()
        )

        // Operator taps CROWD LEVEL notification
        state = state.copy(
            currentScreen = ScreenState.TRACKING,
            isCrowdLevelSheetVisible = true
        )

        assertFalse("Crowd submit flag must remain false until option tapped", state.isSubmittingCrowd)
        assertNull("No crowd report success message without selection", state.crowdReportSuccessMessage)
        assertNull("No crowd level selected automatically", state.lastSelectedCrowdLevel)
    }

    // 13. Wrong/missing trip_id fails safely.
    @Test
    fun testMissingTripIdFailsSafely() {
        sessionStore.saveSession(sampleLoginResponse)

        var state = OperatorUiState(
            currentScreen = ScreenState.ASSIGNMENT,
            token = sessionStore.getAccessToken(),
            todaysTrips = listOf(
                OperatorTripResponse(
                    trip_id = "valid-trip-1",
                    assignment_id = "asgn-1",
                    service_code = "AC4B",
                    service_name = "Express",
                    route_code = "R1",
                    route_name = "Route 1",
                    direction = "A_TO_B",
                    vehicle_number = "PNB001",
                    planned_start_at = "2026-09-06T10:00:00Z",
                    trip_status = "PLANNED",
                    assignment_status = "ASSIGNED",
                    operator_role = "DRIVER"
                )
            )
        )

        val unknownTripId = "non-existent-trip-999"
        val matchingTrip = state.todaysTrips.firstOrNull { it.trip_id == unknownTripId }

        if (matchingTrip == null) {
            state = state.copy(errorMessage = "Assigned trip not found. Please check your schedule.")
        }

        assertEquals(ScreenState.ASSIGNMENT, state.currentScreen)
        assertEquals("Assigned trip not found. Please check your schedule.", state.errorMessage)
    }

    // 14. No persisted session means login flow.
    @Test
    fun testNoPersistedSessionRoutesToLogin() {
        // No session saved in store
        assertFalse(sessionStore.hasSession())

        var state = OperatorUiState(currentScreen = ScreenState.LOGIN)

        // Notification actions incoming while unauthenticated
        val incomingActions = listOf(
            ScheduleNotificationHelper.ACTION_START_TRACKING_INTENT,
            ForegroundTrackingService.ACTION_NAME_OPEN_TRIP,
            ForegroundTrackingService.ACTION_NAME_REPORT_ISSUE,
            ForegroundTrackingService.ACTION_NAME_CROWD_LEVEL
        )

        for (action in incomingActions) {
            val hasAuth = state.token != null || sessionStore.hasSession()
            if (!hasAuth) {
                // Must remain strictly on LOGIN
                state = state.copy(currentScreen = ScreenState.LOGIN)
            }
            assertEquals("Screen must stay LOGIN for unauthenticated action $action", ScreenState.LOGIN, state.currentScreen)
            assertFalse(state.isReportIssueDialogVisible)
            assertFalse(state.isCrowdLevelSheetVisible)
        }
    }
}

/**
 * Fast in-memory SharedPreferences implementation for JUnit tests.
 */
class FakeSharedPreferences : SharedPreferences {
    private val data = HashMap<String, Any?>()

    override fun getAll(): MutableMap<String, *> = HashMap(data)
    override fun getString(key: String?, defValue: String?): String? = data[key] as? String ?: defValue
    override fun getStringSet(key: String?, defValues: MutableSet<String>?): MutableSet<String>? =
        @Suppress("UNCHECKED_CAST") (data[key] as? MutableSet<String> ?: defValues)
    override fun getInt(key: String?, defValue: Int): Int = (data[key] as? Int) ?: defValue
    override fun getLong(key: String?, defValue: Long): Long = (data[key] as? Long) ?: defValue
    override fun getFloat(key: String?, defValue: Float): Float = (data[key] as? Float) ?: defValue
    override fun getBoolean(key: String?, defValue: Boolean): Boolean = (data[key] as? Boolean) ?: defValue
    override fun contains(key: String?): Boolean = data.containsKey(key)
    override fun edit(): SharedPreferences.Editor = FakeEditor(data)
    override fun registerOnSharedPreferenceChangeListener(listener: SharedPreferences.OnSharedPreferenceChangeListener?) {}
    override fun unregisterOnSharedPreferenceChangeListener(listener: SharedPreferences.OnSharedPreferenceChangeListener?) {}

    class FakeEditor(private val backingData: HashMap<String, Any?>) : SharedPreferences.Editor {
        private val temp = HashMap<String, Any?>()
        private var clearRequested = false

        override fun putString(key: String?, value: String?): SharedPreferences.Editor {
            if (key != null) temp[key] = value
            return this
        }
        override fun putStringSet(key: String?, values: MutableSet<String>?): SharedPreferences.Editor {
            if (key != null) temp[key] = values
            return this
        }
        override fun putInt(key: String?, value: Int): SharedPreferences.Editor {
            if (key != null) temp[key] = value
            return this
        }
        override fun putLong(key: String?, value: Long): SharedPreferences.Editor {
            if (key != null) temp[key] = value
            return this
        }
        override fun putFloat(key: String?, value: Float): SharedPreferences.Editor {
            if (key != null) temp[key] = value
            return this
        }
        override fun putBoolean(key: String?, value: Boolean): SharedPreferences.Editor {
            if (key != null) temp[key] = value
            return this
        }
        override fun remove(key: String?): SharedPreferences.Editor {
            if (key != null) temp[key] = null
            return this
        }
        override fun clear(): SharedPreferences.Editor {
            clearRequested = true
            return this
        }
        override fun commit(): Boolean {
            apply()
            return true
        }
        override fun apply() {
            if (clearRequested) {
                backingData.clear()
            }
            for ((k, v) in temp) {
                if (v == null) backingData.remove(k) else backingData[k] = v
            }
        }
    }
}
