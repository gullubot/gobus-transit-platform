package com.transitplatform.app.service

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import com.transitplatform.app.MainActivity
import com.transitplatform.app.data.local.AppDatabase
import com.transitplatform.app.data.local.TrackingPacketEntity
import com.transitplatform.app.data.network.ApiClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID
import java.util.concurrent.atomic.AtomicInteger

data class LiveTrackingStatus(
    val isTracking: Boolean = false,
    val sessionId: String? = null,
    val tripId: String? = null,
    val serviceCode: String = "",
    val vehicleNumber: String = "",
    val lastLatitude: Double? = null,
    val lastLongitude: Double? = null,
    val lastAccuracy: Float? = null,
    val lastSpeed: Float? = null,
    val packetsCreated: Int = 0,
    val queuedPacketsCount: Int = 0,
    val lastUploadTime: Long? = null,
    val isOnline: Boolean = true,
    val syncStatus: String = "IDLE", // IDLE, QUEUED, SYNCING, SYNCED
    val gpsStatus: String = "WAITING" // WAITING, OK, UNAVAILABLE
)

class ForegroundTrackingService : Service(), LocationListener {

    private val serviceJob = SupervisorJob()
    private val serviceScope = CoroutineScope(Dispatchers.IO + serviceJob)

    private lateinit var database: AppDatabase
    private val apiClient = ApiClient()

    private var locationManager: LocationManager? = null
    private val sequenceCounter = AtomicInteger(0)

    private var token: String? = null
    private var sessionId: String? = null
    private var tripId: String? = null
    private var serviceCode: String = ""
    private var vehicleNumber: String = ""

    private var syncJob: Job? = null
    private var heartbeatJob: Job? = null

    companion object {
        const val ACTION_START = "com.transitplatform.app.START_TRACKING"
        const val ACTION_STOP = "com.transitplatform.app.STOP_TRACKING"

        const val EXTRA_TOKEN = "extra_token"
        const val EXTRA_SESSION_ID = "extra_session_id"
        const val EXTRA_TRIP_ID = "extra_trip_id"
        const val EXTRA_SERVICE_CODE = "extra_service_code"
        const val EXTRA_VEHICLE_NUMBER = "extra_vehicle_number"
        const val EXTRA_BASE_URL = "extra_base_url"

        private const val NOTIFICATION_CHANNEL_ID = "transit_tracking_channel"
        private const val NOTIFICATION_ID = 9001

        private val _trackingStatus = MutableStateFlow(LiveTrackingStatus())
        val trackingStatus = _trackingStatus.asStateFlow()
    }

    override fun onCreate() {
        super.onCreate()
        database = AppDatabase.getInstance(applicationContext)
        locationManager = getSystemService(Context.LOCATION_SERVICE) as LocationManager
        createNotificationChannel()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                token = intent.getStringExtra(EXTRA_TOKEN)
                sessionId = intent.getStringExtra(EXTRA_SESSION_ID)
                tripId = intent.getStringExtra(EXTRA_TRIP_ID)
                serviceCode = intent.getStringExtra(EXTRA_SERVICE_CODE) ?: "AC4B"
                vehicleNumber = intent.getStringExtra(EXTRA_VEHICLE_NUMBER) ?: "PNB005234"
                val baseUrl = intent.getStringExtra(EXTRA_BASE_URL)
                if (baseUrl != null) {
                    apiClient.setBaseUrl(baseUrl)
                }

                startForegroundServiceInternal()
                startTrackingEngine()
            }
            ACTION_STOP -> {
                stopTrackingEngine()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_STICKY
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "Transit Active Tracking",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows continuous GPS location tracking status for bus trip"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(): Notification {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle("Transit Tracking Active")
            .setContentText("Service $serviceCode · Vehicle $vehicleNumber")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun startForegroundServiceInternal() {
        val notification = buildNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceCompat.startForeground(
                this,
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    @SuppressLint("MissingPermission")
    private fun startTrackingEngine() {
        val currentSession = sessionId ?: return

        serviceScope.launch {
            val maxSeq = database.trackingPacketDao().getMaxSequenceForSession(currentSession) ?: 0
            sequenceCounter.set(maxSeq)

            _trackingStatus.value = LiveTrackingStatus(
                isTracking = true,
                sessionId = currentSession,
                tripId = tripId,
                serviceCode = serviceCode,
                vehicleNumber = vehicleNumber,
                gpsStatus = "ACQUIRING"
            )

            launch(Dispatchers.Main) {
                try {
                    locationManager?.requestLocationUpdates(
                        LocationManager.GPS_PROVIDER,
                        2000L,
                        1f,
                        this@ForegroundTrackingService
                    )
                    // Also register Network provider as fallback
                    if (locationManager?.isProviderEnabled(LocationManager.NETWORK_PROVIDER) == true) {
                        locationManager?.requestLocationUpdates(
                            LocationManager.NETWORK_PROVIDER,
                            3000L,
                            2f,
                            this@ForegroundTrackingService
                        )
                    }
                } catch (e: Exception) {
                    _trackingStatus.value = _trackingStatus.value.copy(gpsStatus = "ERROR: ${e.message}")
                }
            }

            // Start periodic sync worker coroutine
            startSyncLoop()
            // Start periodic heartbeat coroutine
            startHeartbeatLoop()
        }
    }

    private fun stopTrackingEngine() {
        try {
            locationManager?.removeUpdates(this)
        } catch (e: Exception) {
            // Ignore
        }
        syncJob?.cancel()
        heartbeatJob?.cancel()

        // Attempt final batch flush before shutdown and schedule WorkManager durable sync for any remaining backlog
        val currentToken = token
        val currentSession = sessionId
        serviceScope.launch {
            flushPendingPackets()
            if (currentToken != null && currentSession != null) {
                TelemetrySyncWorker.scheduleDurableSync(
                    applicationContext,
                    currentToken,
                    currentSession
                )
            }
            _trackingStatus.value = LiveTrackingStatus(isTracking = false)
        }
    }


    override fun onLocationChanged(location: Location) {
        val currentSession = sessionId ?: return

        val seq = sequenceCounter.incrementAndGet()
        val isoFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val observedAtStr = isoFormat.format(Date(location.time.takeIf { it > 0 } ?: System.currentTimeMillis()))

        val batteryLevel = getBatteryLevel()

        val packet = TrackingPacketEntity(
            packetId = UUID.randomUUID().toString(),
            sessionId = currentSession,
            latitude = location.latitude,
            longitude = location.longitude,
            accuracyM = if (location.hasAccuracy()) location.accuracy else null,
            speedMps = if (location.hasSpeed()) location.speed else null,
            heading = if (location.hasBearing()) location.bearing else null,
            observedAt = observedAtStr,
            deviceSequence = seq,
            batteryLevel = batteryLevel,
            networkType = "CELLULAR",
            gpsStatus = "AVAILABLE"
        )

        serviceScope.launch {
            // Persist to Room local database FIRST (Offline resilience)
            database.trackingPacketDao().insert(packet)
            val pendingCount = database.trackingPacketDao().countPending()

            _trackingStatus.value = _trackingStatus.value.copy(
                lastLatitude = location.latitude,
                lastLongitude = location.longitude,
                lastAccuracy = location.accuracy,
                lastSpeed = location.speed,
                packetsCreated = seq,
                queuedPacketsCount = pendingCount,
                gpsStatus = "OK"
            )
        }
    }

    private fun startSyncLoop() {
        syncJob?.cancel()
        syncJob = serviceScope.launch {
            while (isActive) {
                delay(3000L) // Batch upload check every 3 seconds
                flushPendingPackets()
            }
        }
    }

    private suspend fun flushPendingPackets() {
        val currentToken = token ?: return
        val currentSession = sessionId ?: return

        val pending = database.trackingPacketDao().getPendingPackets(limit = 50)
        if (pending.isEmpty()) {
            val pendingCount = database.trackingPacketDao().countPending()
            _trackingStatus.value = _trackingStatus.value.copy(
                queuedPacketsCount = pendingCount,
                syncStatus = if (pendingCount == 0) "SYNCED" else "QUEUED"
            )
            return
        }

        _trackingStatus.value = _trackingStatus.value.copy(syncStatus = "SYNCING")

        val result = apiClient.uploadBatch(currentToken, currentSession, pending)
        if (result.isSuccess) {
            val ack = result.getOrNull()
            if (ack != null) {
                val toRemove = ack.accepted + ack.duplicates
                if (toRemove.isNotEmpty()) {
                    database.trackingPacketDao().deletePacketsByIds(toRemove)
                }
            }
            val remaining = database.trackingPacketDao().countPending()
            _trackingStatus.value = _trackingStatus.value.copy(
                isOnline = true,
                queuedPacketsCount = remaining,
                lastUploadTime = System.currentTimeMillis(),
                syncStatus = if (remaining == 0) "SYNCED" else "QUEUED"
            )
        } else {
            // Network failure or server offline — retain in Room DB!
            val remaining = database.trackingPacketDao().countPending()
            _trackingStatus.value = _trackingStatus.value.copy(
                isOnline = false,
                queuedPacketsCount = remaining,
                syncStatus = "QUEUED (OFFLINE)"
            )
        }
    }

    private fun startHeartbeatLoop() {
        heartbeatJob?.cancel()
        heartbeatJob = serviceScope.launch {
            while (isActive) {
                delay(30000L) // Heartbeat every 30 seconds
                val currentToken = token ?: continue
                val battery = getBatteryLevel()
                apiClient.sendHeartbeat(
                    token = currentToken,
                    sessionId = sessionId,
                    batteryLevel = battery,
                    networkType = if (_trackingStatus.value.isOnline) "CELLULAR" else "OFFLINE",
                    gpsStatus = _trackingStatus.value.gpsStatus
                )
            }
        }
    }

    private fun getBatteryLevel(): Float? {
        return try {
            val batteryManager = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
            val level = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
            if (level in 0..100) level.toFloat() else null
        } catch (e: Exception) {
            null
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        stopTrackingEngine()
        serviceScope.cancel()
    }

    // Required LocationListener callbacks for older API compatibility
    override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
    override fun onProviderEnabled(provider: String) {}
    override fun onProviderDisabled(provider: String) {}
}
