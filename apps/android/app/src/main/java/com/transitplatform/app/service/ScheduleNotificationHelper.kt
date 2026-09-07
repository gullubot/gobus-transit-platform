package com.transitplatform.app.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.transitplatform.app.MainActivity

object ScheduleNotificationHelper {

    const val CHANNEL_SCHEDULE_ID = "transit_schedule_alerts"
    const val CHANNEL_SCHEDULE_NAME = "Upcoming Duty & Schedule Alerts"

    const val NOTIF_UPCOMING_TRIP_ID = 8001
    const val NOTIF_REMINDER_ID = 8002
    const val NOTIF_ALERT_GPS_ID = 8003
    const val NOTIF_ALERT_NET_ID = 8004

    const val ACTION_START_TRACKING_INTENT = "com.transitplatform.app.ACTION_START_TRACKING_FROM_NOTIF"
    const val ACTION_SNOOZE_INTENT = "com.transitplatform.app.ACTION_SNOOZE_SCHEDULE"

    const val ACTION_DUTY_REMINDER = "com.transitplatform.app.ACTION_DUTY_REMINDER"
    const val ACTION_SNOOZE_DUTY = "com.transitplatform.app.ACTION_SNOOZE_DUTY"

    const val EXTRA_TRIP_ID = "extra_trip_id"
    const val EXTRA_SERVICE_CODE = "extra_service_code"
    const val EXTRA_VEHICLE_NUMBER = "extra_vehicle_number"
    const val EXTRA_ROUTE_CODE = "extra_route_code"
    const val EXTRA_DIRECTION = "extra_direction"
    const val EXTRA_DEPARTURE_TIME = "extra_departure_time"
    const val EXTRA_REMINDER_TYPE = "extra_reminder_type"
    const val EXTRA_NOTIFICATION_ID = "extra_notification_id"
    const val EXTRA_DESTINATION = "extra_destination"

    fun createScheduleChannels(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_SCHEDULE_ID,
                CHANNEL_SCHEDULE_NAME,
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Alerts and reminders for scheduled bus departure duties."
                enableVibration(true)
            }
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }

    /**
     * Shows a pre-trip duty notification (T-10m, Departure T-0m, or Snooze) with:
     * - [START TRIP] action that launches MainActivity targeting the Readiness screen.
     * - [SNOOZE] action that dismisses the alert and reschedules in 5 minutes.
     *
     * Tapping START TRIP will NEVER automatically start tracking or call the trip-start API.
     */
    fun showDutyReminderNotification(
        context: Context,
        tripId: String,
        serviceCode: String,
        vehicleNumber: String,
        routeCode: String,
        direction: String,
        departureTime: String,
        reminderType: String,
        notificationId: Int
    ) {
        // Safe handling for missing notification permission
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
            return
        }

        createScheduleChannels(context)

        val title = when (reminderType.uppercase()) {
            "T10" -> "Your trip starts in 10 minutes"
            "DEPARTURE" -> "Your scheduled trip is ready to start"
            "SNOOZE" -> "Duty Reminder: Service $serviceCode"
            else -> "Upcoming Duty: Service $serviceCode"
        }

        val formattedDirection = when (direction.uppercase()) {
            "A_TO_B" -> "A → B"
            "B_TO_A" -> "B → A"
            else -> direction
        }

        val contentText = "$serviceCode • Vehicle $vehicleNumber • Dep $departureTime"
        val bigText = buildString {
            append("Service: ").append(serviceCode)
            if (routeCode.isNotBlank()) append(" (").append(routeCode).append(")")
            append("\nVehicle: ").append(vehicleNumber)
            append("\nDeparture: ").append(departureTime)
            if (formattedDirection.isNotBlank()) append("\nDirection: ").append(formattedDirection)
        }

        // START TRIP Action -> Launches MainActivity with trip_id and destination READINESS
        val launchIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("action", ACTION_START_TRACKING_INTENT)
            putExtra(EXTRA_TRIP_ID, tripId)
            putExtra("trip_id", tripId)
            putExtra(EXTRA_DESTINATION, "READINESS")
            putExtra("destination", "READINESS")
        }
        val pendingLaunch = PendingIntent.getActivity(
            context,
            notificationId,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // SNOOZE Action -> Sends broadcast to DutyAlarmReceiver to snooze by 5 min
        val snoozeIntent = Intent(context, DutyAlarmReceiver::class.java).apply {
            action = ACTION_SNOOZE_DUTY
            putExtra(EXTRA_TRIP_ID, tripId)
            putExtra(EXTRA_SERVICE_CODE, serviceCode)
            putExtra(EXTRA_VEHICLE_NUMBER, vehicleNumber)
            putExtra(EXTRA_ROUTE_CODE, routeCode)
            putExtra(EXTRA_DIRECTION, direction)
            putExtra(EXTRA_DEPARTURE_TIME, departureTime)
            putExtra(EXTRA_NOTIFICATION_ID, notificationId)
        }
        val pendingSnooze = PendingIntent.getBroadcast(
            context,
            notificationId + 500000,
            snoozeIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, CHANNEL_SCHEDULE_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(contentText)
            .setStyle(NotificationCompat.BigTextStyle().bigText(bigText))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pendingLaunch)
            .addAction(android.R.drawable.ic_media_play, "START TRIP", pendingLaunch)
            .addAction(android.R.drawable.ic_lock_idle_alarm, "SNOOZE", pendingSnooze)
            .build()

        try {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.notify(notificationId, notification)
        } catch (e: Exception) {
            // Fail safely without crash
        }
    }

    /**
     * Posts an upcoming trip notification with [START TRACKING] and [SNOOZE] actions.
     */
    fun showUpcomingTripNotification(
        context: Context,
        serviceCode: String,
        routeCode: String,
        departureTime: String,
        vehicleNumber: String
    ) {
        createScheduleChannels(context)

        val launchIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("action", ACTION_START_TRACKING_INTENT)
        }
        val pendingLaunch = PendingIntent.getActivity(
            context,
            0,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val snoozeIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("action", ACTION_SNOOZE_INTENT)
        }
        val pendingSnooze = PendingIntent.getActivity(
            context,
            1,
            snoozeIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, CHANNEL_SCHEDULE_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Upcoming Duty: Service $serviceCode")
            .setContentText("Bus $vehicleNumber scheduled to depart at $departureTime (Route $routeCode).")
            .setStyle(
                NotificationCompat.BigTextStyle().bigText(
                    "Service $serviceCode ($routeCode) with vehicle $vehicleNumber is scheduled for departure at $departureTime. Please confirm readiness and begin tracking."
                )
            )
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pendingLaunch)
            .addAction(android.R.drawable.ic_media_play, "START TRACKING", pendingLaunch)
            .addAction(android.R.drawable.ic_lock_idle_alarm, "SNOOZE", pendingSnooze)
            .build()

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIF_UPCOMING_TRIP_ID, notification)
    }

    /**
     * Posts tracking not started reminder if departure time is near.
     */
    fun showTrackingReminder(context: Context, serviceCode: String) {
        createScheduleChannels(context)

        val launchIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingLaunch = PendingIntent.getActivity(
            context,
            2,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, CHANNEL_SCHEDULE_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("Tracking Reminder: Service $serviceCode")
            .setContentText("Departure is approaching. Ensure tracking is active before departure.")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pendingLaunch)
            .addAction(android.R.drawable.ic_media_play, "START NOW", pendingLaunch)
            .build()

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIF_REMINDER_ID, notification)
    }

    fun dismissNotification(context: Context, notificationId: Int) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.cancel(notificationId)
    }
}
