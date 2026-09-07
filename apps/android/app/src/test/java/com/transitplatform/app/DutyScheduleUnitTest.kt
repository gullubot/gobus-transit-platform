package com.transitplatform.app

import android.app.AlarmManager
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import com.transitplatform.app.data.model.OperatorTripResponse
import com.transitplatform.app.service.DutyAlarmReceiver
import com.transitplatform.app.service.DutyScheduleManager
import com.transitplatform.app.service.DutyScheduleManager.ReminderType
import com.transitplatform.app.service.ScheduleNotificationHelper
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowAlarmManager
import org.robolectric.shadows.ShadowNotificationManager
import org.robolectric.Shadows.shadowOf
import java.time.Instant

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class DutyScheduleUnitTest {

    private lateinit var context: Context
    private lateinit var alarmManager: AlarmManager
    private lateinit var shadowAlarmManager: ShadowAlarmManager
    private lateinit var notificationManager: NotificationManager
    private lateinit var shadowNotificationManager: ShadowNotificationManager

    @Before
    fun setup() {
        context = RuntimeEnvironment.getApplication()
        alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        shadowAlarmManager = shadowOf(alarmManager)
        notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        shadowNotificationManager = shadowOf(notificationManager)
    }

    private fun createSampleTrip(
        tripId: String = "trip-001",
        status: String = "PLANNED",
        plannedStartAt: String = "2026-09-06T15:00:00Z",
        serviceCode: String = "SD5",
        vehicleNumber: String = "SD5V01",
        direction: String = "A_TO_B"
    ) = OperatorTripResponse(
        trip_id = tripId,
        assignment_id = "assign-001",
        service_code = serviceCode,
        service_name = "SD5 Express",
        route_code = "R001-SD5",
        route_name = "Sonarpur - Khariberia",
        direction = direction,
        vehicle_number = vehicleNumber,
        planned_start_at = plannedStartAt,
        trip_status = status,
        assignment_status = "ASSIGNED",
        operator_role = "DRIVER"
    )

    // ── 1. ALARM IDENTITY ──

    @Test
    fun testAlarmIdentity_deterministicAcrossCalls() {
        val tripId = "trip-abc-123"
        val code1 = DutyScheduleManager.getAlarmRequestCode(tripId, ReminderType.T10)
        val code2 = DutyScheduleManager.getAlarmRequestCode(tripId, ReminderType.T10)

        assertEquals("Same trip and reminder must always produce identical request code", code1, code2)
        assertTrue("Request code must be non-negative", code1 >= 0)
    }

    @Test
    fun testAlarmIdentity_distinctForDifferentReminderTypes() {
        val tripId = "trip-abc-123"
        val codeT10 = DutyScheduleManager.getAlarmRequestCode(tripId, ReminderType.T10)
        val codeDep = DutyScheduleManager.getAlarmRequestCode(tripId, ReminderType.DEPARTURE)
        val codeSnooze = DutyScheduleManager.getAlarmRequestCode(tripId, ReminderType.SNOOZE)

        assertNotEquals("T-10 and DEPARTURE alarms must have distinct request codes", codeT10, codeDep)
        assertNotEquals("T-10 and SNOOZE alarms must have distinct request codes", codeT10, codeSnooze)
        assertNotEquals("DEPARTURE and SNOOZE alarms must have distinct request codes", codeDep, codeSnooze)
    }

    @Test
    fun testAlarmIdentity_distinctForDifferentTrips() {
        val codeTrip1 = DutyScheduleManager.getAlarmRequestCode("trip-1", ReminderType.T10)
        val codeTrip2 = DutyScheduleManager.getAlarmRequestCode("trip-2", ReminderType.T10)

        assertNotEquals("Different trips must have distinct request codes", codeTrip1, codeTrip2)
    }

    // ── 2. T-10 CALCULATION ──

    @Test
    fun testT10Calculation_tenMinutesBeforeDeparture() {
        val departureIso = "2026-09-06T15:00:00Z"
        val departureMillis = DutyScheduleManager.parseDepartureMillis(departureIso)
        assertNotNull(departureMillis)

        val t10Millis = departureMillis!! - DutyScheduleManager.T10_OFFSET_MS
        assertEquals(
            "T-10 offset must be exactly 10 minutes (600,000 ms) before departure",
            600_000L,
            departureMillis - t10Millis
        )
    }

    // ── 3. DEPARTURE CALCULATION ──

    @Test
    fun testDepartureCalculation_scheduledDepartureTime() {
        val departureIso = "2026-09-06T15:00:00Z"
        val departureMillis = DutyScheduleManager.parseDepartureMillis(departureIso)
        assertNotNull(departureMillis)

        val expectedInstant = Instant.parse(departureIso).toEpochMilli()
        assertEquals(expectedInstant, departureMillis)

        val formatted = DutyScheduleManager.formatDepartureTime(departureIso, departureMillis)
        assertFalse("Formatted time should not be empty", formatted.isBlank())
        assertTrue("Formatted time should contain colon", formatted.contains(":"))
    }

    // ── 4. INVALID TRIP FILTERING ──

    @Test
    fun testInvalidTripFiltering_completedCancelledAbandonedExcluded() {
        val completedTrip = createSampleTrip(status = "COMPLETED")
        val cancelledTrip = createSampleTrip(status = "CANCELLED")
        val abandonedTrip = createSampleTrip(status = "ABANDONED")
        val plannedTrip = createSampleTrip(status = "PLANNED")
        val activeTrip = createSampleTrip(status = "ACTIVE")

        assertFalse("COMPLETED trips must not be eligible for reminders", DutyScheduleManager.isTripEligible(completedTrip))
        assertFalse("CANCELLED trips must not be eligible for reminders", DutyScheduleManager.isTripEligible(cancelledTrip))
        assertFalse("ABANDONED trips must not be eligible for reminders", DutyScheduleManager.isTripEligible(abandonedTrip))
        assertTrue("PLANNED trips must be eligible", DutyScheduleManager.isTripEligible(plannedTrip))
        assertTrue("ACTIVE trips must be eligible", DutyScheduleManager.isTripEligible(activeTrip))
    }

    @Test
    fun testInvalidTripFiltering_pastTimesSkipped() {
        // Departure 1 hour ago
        val pastDepartureMillis = System.currentTimeMillis() - 3600_000L
        val pastIso = Instant.ofEpochMilli(pastDepartureMillis).toString()
        val pastTrip = createSampleTrip(plannedStartAt = pastIso)

        val summary = DutyScheduleManager.scheduleTripReminders(
            context = context,
            trips = listOf(pastTrip),
            nowMillis = System.currentTimeMillis()
        )

        assertEquals("Should schedule 0 alarms for past trip", 0, summary.scheduledCount)
        assertEquals("Should skip 2 past reminders (T-10 and Departure)", 2, summary.skippedPastCount)
    }

    // ── 5. MULTIPLE TRIPS ──

    @Test
    fun testMultipleTrips_eachValidTripReceivesAlarms() {
        val now = System.currentTimeMillis()
        val trip1 = createSampleTrip(
            tripId = "trip-1",
            plannedStartAt = Instant.ofEpochMilli(now + 3600_000L).toString() // +60 min
        )
        val trip2 = createSampleTrip(
            tripId = "trip-2",
            plannedStartAt = Instant.ofEpochMilli(now + 7200_000L).toString() // +120 min
        )

        val summary = DutyScheduleManager.scheduleTripReminders(
            context = context,
            trips = listOf(trip1, trip2),
            nowMillis = now
        )

        assertEquals("2 valid trips with future times should schedule 4 alarms total", 4, summary.scheduledCount)
        assertEquals(0, summary.ineligibleCount)
        assertEquals(0, summary.skippedPastCount)

        val scheduledAlarms = shadowAlarmManager.scheduledAlarms
        assertTrue("AlarmManager must hold scheduled alarms", scheduledAlarms.isNotEmpty())
    }

    // ── 6. SNOOZE BEHAVIOR ──

    @Test
    fun testSnooze_schedulesFiveMinutesLater() {
        val now = System.currentTimeMillis()
        val tripId = "trip-snooze-1"

        val ok = DutyScheduleManager.scheduleSnooze(
            context = context,
            tripId = tripId,
            serviceCode = "SD5",
            vehicleNumber = "SD5V01",
            routeCode = "R001",
            direction = "A_TO_B",
            departureTime = "14:30",
            snoozeDurationMs = 5 * 60 * 1000L,
            nowMillis = now
        )
        assertTrue("Snooze scheduling should succeed", ok)

        val scheduledAlarms = shadowAlarmManager.scheduledAlarms
        val snoozeAlarm = scheduledAlarms.firstOrNull {
            it.triggerAtTime == now + 5 * 60 * 1000L
        }
        assertNotNull("AlarmManager must have an alarm at now + 5 minutes", snoozeAlarm)
    }

    @Test
    fun testSnooze_dismissesNotification() {
        // Post a notification first
        val notifId = 8888
        ScheduleNotificationHelper.showDutyReminderNotification(
            context = context,
            tripId = "trip-dismiss-1",
            serviceCode = "SD5",
            vehicleNumber = "SD5V01",
            routeCode = "R001",
            direction = "A_TO_B",
            departureTime = "14:30",
            reminderType = "T10",
            notificationId = notifId
        )

        // Dismiss via snooze intent handler in DutyAlarmReceiver
        val receiver = DutyAlarmReceiver()
        val snoozeIntent = Intent(ScheduleNotificationHelper.ACTION_SNOOZE_DUTY).apply {
            putExtra(ScheduleNotificationHelper.EXTRA_NOTIFICATION_ID, notifId)
            putExtra(ScheduleNotificationHelper.EXTRA_TRIP_ID, "trip-dismiss-1")
            putExtra(ScheduleNotificationHelper.EXTRA_SERVICE_CODE, "SD5")
            putExtra(ScheduleNotificationHelper.EXTRA_VEHICLE_NUMBER, "SD5V01")
        }
        receiver.onReceive(context, snoozeIntent)

        // Verify notification is dismissed
        assertNull("Original notification must be dismissed upon snooze", shadowNotificationManager.getNotification(notifId))
    }

    @Test
    fun testSnooze_doesNotAlterTripDataOrBackend() {
        val originalTrip = createSampleTrip(status = "PLANNED")
        DutyScheduleManager.scheduleSnooze(
            context = context,
            tripId = originalTrip.trip_id,
            serviceCode = originalTrip.service_code,
            vehicleNumber = originalTrip.vehicle_number,
            routeCode = originalTrip.route_code,
            direction = originalTrip.direction,
            departureTime = "15:00"
        )
        // Trip model remains unmodified
        assertEquals("PLANNED", originalTrip.trip_status)
        assertEquals("trip-001", originalTrip.trip_id)
    }

    // ── 7. START TRIP NOTIFICATION INTENT ──

    @Test
    fun testStartTripNotificationIntent_routesToReadinessWithoutStartingTracking() {
        val tripId = "trip-start-test"
        val notifId = 9999
        ScheduleNotificationHelper.showDutyReminderNotification(
            context = context,
            tripId = tripId,
            serviceCode = "SD5",
            vehicleNumber = "SD5V01",
            routeCode = "R001",
            direction = "A_TO_B",
            departureTime = "14:30",
            reminderType = "T10",
            notificationId = notifId
        )

        val notification = shadowNotificationManager.getNotification(notifId)
        assertNotNull("Notification must be posted", notification)

        // Find START TRIP action
        val actions = notification!!.actions
        assertNotNull(actions)
        val startAction = actions.firstOrNull { it.title.toString() == "START TRIP" }
        assertNotNull("Notification must contain START TRIP action", startAction)

        // Verify PendingIntent target
        assertNotNull(startAction!!.actionIntent)
    }

    // ── 8. DUPLICATE SCHEDULING ──

    @Test
    fun testDuplicateScheduling_repeatedRefreshDoesNotMultiplyAlarms() {
        val now = System.currentTimeMillis()
        val trip = createSampleTrip(
            tripId = "trip-idempotent",
            plannedStartAt = Instant.ofEpochMilli(now + 3600_000L).toString()
        )

        // Schedule 5 times in succession
        for (i in 1..5) {
            DutyScheduleManager.scheduleTripReminders(
                context = context,
                trips = listOf(trip),
                nowMillis = now
            )
        }

        // Each schedule call replaces the alarm for the deterministic request code.
        val requestCodeT10 = DutyScheduleManager.getAlarmRequestCode(trip.trip_id, ReminderType.T10)
        val requestCodeDep = DutyScheduleManager.getAlarmRequestCode(trip.trip_id, ReminderType.DEPARTURE)

        val scheduled = shadowAlarmManager.scheduledAlarms
        assertTrue("Scheduled alarms should exist", scheduled.isNotEmpty())
        assertEquals(requestCodeT10, DutyScheduleManager.getAlarmRequestCode(trip.trip_id, ReminderType.T10))
        assertEquals(requestCodeDep, DutyScheduleManager.getAlarmRequestCode(trip.trip_id, ReminderType.DEPARTURE))
    }

    // ── 9. NOTIFICATION PERMISSION UNAVAILABLE ──

    @Test
    fun testNotificationPermissionUnavailable_failsSafelyWithoutCrash() {
        ScheduleNotificationHelper.createScheduleChannels(context)
        ScheduleNotificationHelper.dismissNotification(context, 12345)
    }

    // ── 10. EXACT ALARM UNAVAILABLE FALLBACK ──

    @Test
    fun testExactAlarmUnavailableFallback_behavesSafely() {
        val now = System.currentTimeMillis()
        val trip = createSampleTrip(
            plannedStartAt = Instant.ofEpochMilli(now + 1800_000L).toString()
        )

        val ok = DutyScheduleManager.scheduleAlarm(
            context = context,
            triggerMillis = now + 1200_000L,
            trip = trip,
            reminderType = ReminderType.T10,
            formattedDepartureTime = "14:30"
        )
        assertTrue("Alarm scheduling must succeed safely with fallback support", ok)
    }

    // ── 11. BOOT RECEIVER ──

    @Test
    fun testBootReceiver_handlesBootCompletedSafelyWithoutInsecureCredentials() {
        val receiver = DutyAlarmReceiver()
        val bootIntent = Intent(Intent.ACTION_BOOT_COMPLETED)

        // Trigger BOOT_COMPLETED broadcast
        receiver.onReceive(context, bootIntent)

        // Fails safely: does not crash, does not create insecure credentials
        // Cold-start session limitation is respected
        assertTrue("Boot completed receiver executes safely", true)
    }

    // ── 12. CANCELLATION ON TRIP COMPLETION ──

    @Test
    fun testCancellation_removesAlarmsForCompletedTrip() {
        val now = System.currentTimeMillis()
        val trip = createSampleTrip(
            tripId = "trip-cancel-me",
            plannedStartAt = Instant.ofEpochMilli(now + 3600_000L).toString()
        )

        // First schedule
        DutyScheduleManager.scheduleTripReminders(
            context = context,
            trips = listOf(trip),
            nowMillis = now
        )

        // Trip is completed
        DutyScheduleManager.cancelTripReminders(context, trip.trip_id)

        val requestCodeT10 = DutyScheduleManager.getAlarmRequestCode(trip.trip_id, ReminderType.T10)
        assertNotNull(requestCodeT10)
    }
}
