package com.transitplatform.app.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * BroadcastReceiver responsible for receiving AlarmManager duty reminder alarms,
 * handling snooze actions, and reacting to device reboot (BOOT_COMPLETED).
 */
class DutyAlarmReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        Log.d(TAG, "DutyAlarmReceiver received action: $action")

        when (action) {
            ScheduleNotificationHelper.ACTION_DUTY_REMINDER -> {
                handleDutyReminder(context, intent)
            }
            ScheduleNotificationHelper.ACTION_SNOOZE_DUTY -> {
                handleSnooze(context, intent)
            }
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED -> {
                handleBootCompleted(context)
            }
            else -> {
                Log.w(TAG, "Unhandled action in DutyAlarmReceiver: $action")
            }
        }
    }

    private fun handleDutyReminder(context: Context, intent: Intent) {
        val tripId = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_TRIP_ID) ?: return
        val serviceCode = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_SERVICE_CODE) ?: "Transit"
        val vehicleNumber = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_VEHICLE_NUMBER) ?: "Assigned Bus"
        val routeCode = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_ROUTE_CODE) ?: ""
        val direction = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_DIRECTION) ?: "A_TO_B"
        val departureTime = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_DEPARTURE_TIME) ?: ""
        val reminderType = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_REMINDER_TYPE) ?: "T10"
        val notificationId = intent.getIntExtra(
            ScheduleNotificationHelper.EXTRA_NOTIFICATION_ID,
            ScheduleNotificationHelper.NOTIF_UPCOMING_TRIP_ID
        )

        Log.i(TAG, "Triggering duty reminder notification: tripId=$tripId, type=$reminderType, notifId=$notificationId")
        ScheduleNotificationHelper.showDutyReminderNotification(
            context = context,
            tripId = tripId,
            serviceCode = serviceCode,
            vehicleNumber = vehicleNumber,
            routeCode = routeCode,
            direction = direction,
            departureTime = departureTime,
            reminderType = reminderType,
            notificationId = notificationId
        )
    }

    private fun handleSnooze(context: Context, intent: Intent) {
        val notificationId = intent.getIntExtra(
            ScheduleNotificationHelper.EXTRA_NOTIFICATION_ID,
            ScheduleNotificationHelper.NOTIF_UPCOMING_TRIP_ID
        )
        // 1. Dismiss the current notification
        ScheduleNotificationHelper.dismissNotification(context, notificationId)

        val tripId = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_TRIP_ID) ?: return
        val serviceCode = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_SERVICE_CODE) ?: "Transit"
        val vehicleNumber = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_VEHICLE_NUMBER) ?: "Assigned Bus"
        val routeCode = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_ROUTE_CODE) ?: ""
        val direction = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_DIRECTION) ?: "A_TO_B"
        val departureTime = intent.getStringExtra(ScheduleNotificationHelper.EXTRA_DEPARTURE_TIME) ?: ""

        Log.i(TAG, "Snoozing duty reminder for tripId=$tripId (+5 min). Notification dismissed.")
        // 2. Schedule next reminder ~5 minutes later
        DutyScheduleManager.scheduleSnooze(
            context = context,
            tripId = tripId,
            serviceCode = serviceCode,
            vehicleNumber = vehicleNumber,
            routeCode = routeCode,
            direction = direction,
            departureTime = departureTime
        )
    }

    private fun handleBootCompleted(context: Context) {
        Log.i(TAG, "Received BOOT_COMPLETED. Checking for local duty schedule...")
        DutyScheduleManager.handleBootCompleted(context)
    }

    companion object {
        private const val TAG = "DutyAlarmReceiver"
    }
}
