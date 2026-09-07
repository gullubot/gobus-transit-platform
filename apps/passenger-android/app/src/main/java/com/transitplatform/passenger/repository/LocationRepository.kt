package com.transitplatform.passenger.repository

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.transitplatform.passenger.data.model.PassengerStopResponse
import kotlinx.coroutines.tasks.await
import kotlin.math.*

class LocationRepository(context: Context) {
    private val fusedLocationClient = LocationServices.getFusedLocationProviderClient(context)

    @SuppressLint("MissingPermission")
    suspend fun getCurrentLocation(): Location? {
        return try {
            // Using Priority.PRIORITY_BALANCED_POWER_ACCURACY to not force GPS if network is available
            fusedLocationClient.getCurrentLocation(Priority.PRIORITY_BALANCED_POWER_ACCURACY, null).await()
        } catch (e: Exception) {
            null
        }
    }

    fun calculateNearestStop(
        currentLocation: Location,
        stops: List<PassengerStopResponse>
    ): PassengerStopResponse? {
        if (stops.isEmpty()) return null

        var nearestStop: PassengerStopResponse? = null
        var minDistance = Float.MAX_VALUE

        for (stop in stops) {
            if (stop.latitude != null && stop.longitude != null) {
                val results = FloatArray(1)
                Location.distanceBetween(
                    currentLocation.latitude, currentLocation.longitude,
                    stop.latitude, stop.longitude,
                    results
                )
                val distance = results[0]
                if (distance < minDistance) {
                    minDistance = distance
                    nearestStop = stop
                }
            }
        }
        return nearestStop
    }
}
