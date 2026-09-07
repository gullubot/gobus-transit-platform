package com.transitplatform.app.service

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import com.transitplatform.app.data.model.OperatorTripResponse
import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.util.Locale

/**
 * Manages local background duty reminder scheduling for today's scheduled operator trips.
 *
 * Responsibilities:
 * - Deterministic alarm identity based on trip_id + reminder type.
 * - Idempotent scheduling (repeated refreshes never spawn duplicate alarms).
 * - Exact-alarm permission check (API 31+) with graceful fallback to inexact alarms.
 * - Filtering out completed, cancelled, abandoned, and past trips.
 * - Snooze scheduling (+5 minutes).
 * - Safe cancellation when trips are completed, cancelled, or operator logs out.
 */
object DutyScheduleManager {

    private const val TAG = "DutyScheduleManager"

    // 10 minutes prior to departure
    const val T10_OFFSET_MS = 10 * 60 * 1000L
    // 5 minutes snooze duration
    const val SNOOZE_DURATION_MS = 5 * 60 * 1000L

    enum class ReminderType {
        T10,
        DEPARTURE,
        SNOOZE
    }

    data class ScheduleSummary(
        val scheduledCount: Int,
        val cancelledCount: Int,
        val skippedPastCount: Int,
        val ineligibleCount: Int
    )

    /**
     * Deterministic alarm request code based on trip_id and reminder type.
     * Guaranteed to produce the same non-negative integer for identical inputs,
     * preventing duplicate alarms on repeated schedule calls.
     */
    fun getAlarmRequestCode(tripId: String, reminderType: ReminderType): Int {
        val hash = tripId.hashCode() * 31 + reminderType.name.hashCode()
        return hash and 0x7FFFFFFF
    }

    /**
     * Deterministic notification ID corresponding to the alarm request code.
     */
    fun getNotificationId(tripId: String, reminderType: ReminderType): Int {
        return getAlarmRequestCode(tripId, reminderType)
    }

    /**
     * Parses planned_start_at string into epoch milliseconds.
     * Supports ISO-8601 UTC ("Z"), offset ("+05:30"), and local datetime strings.
     */
    fun parseDepartureMillis(plannedStartAt: String?): Long? {
        if (plannedStartAt.isNullOrBlank()) return null
        return try {
            Instant.parse(plannedStartAt).toEpochMilli()
        } catch (e1: Exception) {
            try {
                OffsetDateTime.parse(plannedStartAt).toInstant().toEpochMilli()
            } catch (e2: Exception) {
                try {
                    LocalDateTime.parse(plannedStartAt)
                        .atZone(ZoneId.systemDefault())
                        .toInstant()
                        .toEpochMilli()
                } catch (e3: Exception) {
                    Log.w(TAG, "Failed to parse departure timestamp: $plannedStartAt", e3)
                    null
                }
            }
        }
    }

    /**
     * Formats planned departure time into HH:mm for operator-friendly display.
     */
    fun formatDepartureTime(plannedStartAt: String?, epochMillis: Long?): String {
        if (epochMillis != null && epochMillis > 0) {
            try {
                val localTime = Instant.ofEpochMilli(epochMillis)
                    .atZone(ZoneId.systemDefault())
                    .toLocalTime()
                return String.format(Locale.US, "%02d:%02d", localTime.hour, localTime.minute)
            } catch (e: Exception) {
                // fallback to string extraction
            }
        }
        if (!plannedStartAt.isNullOrBlank() && plannedStartAt.contains("T")) {
            val timePart = plannedStartAt.substringAfter("T").take(5)
            if (timePart.length == 5 && timePart.contains(":")) {
                return timePart
            }
        }
        return "--:--"
    }

    /**
     * Determines whether a trip is valid and eligible for duty reminders.
     * Excludes COMPLETED, CANCELLED, and ABANDONED trips.
     */
    fun isTripEligible(trip: OperatorTripResponse): Boolean {
        val status = trip.trip_status.trim().uppercase(Locale.US)
        if (status in listOf("COMPLETED", "CANCELLED", "ABANDONED")) {
            return false
        }
        return true
    }

    /**
     * Schedules duty reminders for today's trips.
     *
     * For each valid trip:
     * - T-10 alarm: 10 minutes before planned departure.
     * - DEPARTURE alarm: At planned departure.
     *
     * Ineligible trips (completed/cancelled) will have any existing alarms cancelled.
     */
    fun scheduleTripReminders(
        context: Context,
        trips: List<OperatorTripResponse>,
        nowMillis: Long = System.currentTimeMillis()
    ): ScheduleSummary {
        var scheduled = 0
        var cancelled = 0
        var skippedPast = 0
        var ineligible = 0

        for (trip in trips) {
            if (!isTripEligible(trip)) {
                cancelTripReminders(context, trip.trip_id)
                ineligible++
                cancelled++
                continue
            }

            val departureMillis = parseDepartureMillis(trip.planned_start_at)
            if (departureMillis == null) {
                Log.w(TAG, "Skipping trip ${trip.trip_id}: invalid planned_start_at=${trip.planned_start_at}")
                continue
            }

            val formattedTime = formatDepartureTime(trip.planned_start_at, departureMillis)

            // 1. T-10 Minutes Alarm
            val t10Millis = departureMillis - T10_OFFSET_MS
            if (t10Millis > nowMillis) {
                val ok = scheduleAlarm(
                    context = context,
                    triggerMillis = t10Millis,
                    trip = trip,
                    reminderType = ReminderType.T10,
                    formattedDepartureTime = formattedTime
                )
                if (ok) scheduled++
            } else {
                skippedPast++
            }

            // 2. Scheduled Departure Alarm (T-0)
            if (departureMillis > nowMillis) {
                val ok = scheduleAlarm(
                    context = context,
                    triggerMillis = departureMillis,
                    trip = trip,
                    reminderType = ReminderType.DEPARTURE,
                    formattedDepartureTime = formattedTime
                )
                if (ok) scheduled++
            } else {
                skippedPast++
            }
        }

        Log.i(TAG, "Duty schedule result: scheduled=$scheduled, cancelled=$cancelled, skippedPast=$skippedPast, ineligible=$ineligible")
        return ScheduleSummary(scheduled, cancelled, skippedPast, ineligible)
    }

    /**
     * Schedules a single alarm with AlarmManager using exact alarm where permitted,
     * falling back safely to inexact alarms.
     */
    fun scheduleAlarm(
        context: Context,
        triggerMillis: Long,
        trip: OperatorTripResponse,
        reminderType: ReminderType,
        formattedDepartureTime: String
    ): Boolean {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return false
        val requestCode = getAlarmRequestCode(trip.trip_id, reminderType)

        val intent = Intent(context, DutyAlarmReceiver::class.java).apply {
            action = ScheduleNotificationHelper.ACTION_DUTY_REMINDER
            putExtra(ScheduleNotificationHelper.EXTRA_TRIP_ID, trip.trip_id)
            putExtra(ScheduleNotificationHelper.EXTRA_SERVICE_CODE, trip.service_code)
            putExtra(ScheduleNotificationHelper.EXTRA_VEHICLE_NUMBER, trip.vehicle_number)
            putExtra(ScheduleNotificationHelper.EXTRA_ROUTE_CODE, trip.route_code)
            putExtra(ScheduleNotificationHelper.EXTRA_DIRECTION, trip.direction)
            putExtra(ScheduleNotificationHelper.EXTRA_DEPARTURE_TIME, formattedDepartureTime)
            putExtra(ScheduleNotificationHelper.EXTRA_REMINDER_TYPE, reminderType.name)
            putExtra(ScheduleNotificationHelper.EXTRA_NOTIFICATION_ID, requestCode)
        }

        val pendingIntent = PendingIntent.getBroadcast(
            context,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                if (alarmManager.canScheduleExactAlarms()) {
                    alarmManager.setExactAndAllowWhileIdle(
                        AlarmManager.RTC_WAKEUP,
                        triggerMillis,
                        pendingIntent
                    )
                } else {
                    Log.w(TAG, "Exact alarm permission not granted. Falling back to setAndAllowWhileIdle.")
                    alarmManager.setAndAllowWhileIdle(
                        AlarmManager.RTC_WAKEUP,
                        triggerMillis,
                        pendingIntent
                    )
                }
            } else {
                alarmManager.setExactAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP,
                    triggerMillis,
                    pendingIntent
                )
            }
            true
        } catch (e: SecurityException) {
            Log.w(TAG, "SecurityException on setExactAndAllowWhileIdle; falling back to inexact.", e)
            try {
                alarmManager.setAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP,
                    triggerMillis,
                    pendingIntent
                )
                true
            } catch (fallbackEx: Exception) {
                Log.e(TAG, "Failed fallback inexact alarm scheduling", fallbackEx)
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to schedule alarm for trip=${trip.trip_id}, type=$reminderType", e)
            false
        }
    }

    /**
     * Schedules a Snooze alarm (+5 minutes from now).
     * Does NOT alter trip data, trip status, backend state, or admin alerts.
     */
    fun scheduleSnooze(
        context: Context,
        tripId: String,
        serviceCode: String,
        vehicleNumber: String,
        routeCode: String,
        direction: String,
        departureTime: String,
        snoozeDurationMs: Long = SNOOZE_DURATION_MS,
        nowMillis: Long = System.currentTimeMillis()
    ): Boolean {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return false
        val triggerMillis = nowMillis + snoozeDurationMs
        val requestCode = getAlarmRequestCode(tripId, ReminderType.SNOOZE)

        val intent = Intent(context, DutyAlarmReceiver::class.java).apply {
            action = ScheduleNotificationHelper.ACTION_DUTY_REMINDER
            putExtra(ScheduleNotificationHelper.EXTRA_TRIP_ID, tripId)
            putExtra(ScheduleNotificationHelper.EXTRA_SERVICE_CODE, serviceCode)
            putExtra(ScheduleNotificationHelper.EXTRA_VEHICLE_NUMBER, vehicleNumber)
            putExtra(ScheduleNotificationHelper.EXTRA_ROUTE_CODE, routeCode)
            putExtra(ScheduleNotificationHelper.EXTRA_DIRECTION, direction)
            putExtra(ScheduleNotificationHelper.EXTRA_DEPARTURE_TIME, departureTime)
            putExtra(ScheduleNotificationHelper.EXTRA_REMINDER_TYPE, ReminderType.SNOOZE.name)
            putExtra(ScheduleNotificationHelper.EXTRA_NOTIFICATION_ID, requestCode)
        }

        val pendingIntent = PendingIntent.getBroadcast(
            context,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                if (alarmManager.canScheduleExactAlarms()) {
                    alarmManager.setExactAndAllowWhileIdle(
                        AlarmManager.RTC_WAKEUP,
                        triggerMillis,
                        pendingIntent
                    )
                } else {
                    alarmManager.setAndAllowWhileIdle(
                        AlarmManager.RTC_WAKEUP,
                        triggerMillis,
                        pendingIntent
                    )
                }
            } else {
                alarmManager.setExactAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP,
                    triggerMillis,
                    pendingIntent
                )
            }
            Log.i(TAG, "Snooze alarm scheduled for trip=$tripId in ${snoozeDurationMs / 1000}s")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to schedule snooze alarm for trip=$tripId", e)
            false
        }
    }

    /**
     * Cancels all pending duty alarms (T10, DEPARTURE, SNOOZE) for a given trip.
     */
    fun cancelTripReminders(context: Context, tripId: String) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
        for (type in ReminderType.values()) {
            val requestCode = getAlarmRequestCode(tripId, type)
            val intent = Intent(context, DutyAlarmReceiver::class.java).apply {
                action = ScheduleNotificationHelper.ACTION_DUTY_REMINDER
            }
            val pendingIntent = PendingIntent.getBroadcast(
                context,
                requestCode,
                intent,
                PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE
            )
            if (pendingIntent != null) {
                alarmManager.cancel(pendingIntent)
                pendingIntent.cancel()
            }
        }
    }

    /**
     * Cancels alarms for all provided trips (e.g. upon operator logout).
     */
    fun cancelAllReminders(context: Context, trips: List<OperatorTripResponse>) {
        for (trip in trips) {
            cancelTripReminders(context, trip.trip_id)
        }
    }

    /**
     * Boot completed hook.
     * Note: Session persistence (encrypted storage) is not yet implemented in 1.0.5.
     * In accordance with requirements, this fails safely without attempting insecure
     * plaintext credential storage.
     */
    fun handleBootCompleted(context: Context) {
        Log.i(TAG, "handleBootCompleted: Cold-start session limitation active. Awaiting operator login to reschedule duty reminders.")
    }
}
