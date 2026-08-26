package com.transitplatform.app.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
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

        // Intent to launch app
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

        // Intent to snooze
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
