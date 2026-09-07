package com.transitplatform.passenger.ui.components

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.platform.LocalContext
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.*
import com.google.maps.android.compose.*
import com.transitplatform.passenger.data.model.PassengerLiveBusResponse
import com.transitplatform.passenger.data.model.RouteStopDetail
import com.transitplatform.passenger.ui.live.BusMarkerIcon
import org.json.JSONObject

@Composable
fun PassengerLiveMap(
    routeGeometry: String?,
    stops: List<RouteStopDetail>,
    buses: List<PassengerLiveBusResponse>,
    selectedVehicleId: String?,
    onBusSelected: (String) -> Unit,
    onMapClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    
    // Bounds calculation
    val bounds = remember(routeGeometry, stops) {
        val builder = LatLngBounds.builder()
        var hasPoints = false

        stops.forEach { stop ->
            if (stop.latitude != null && stop.longitude != null) {
                builder.include(LatLng(stop.latitude, stop.longitude))
                hasPoints = true
            }
        }

        if (hasPoints) builder.build() else null
    }

    val cameraPositionState = rememberCameraPositionState()
    
    // Initial camera zoom
    LaunchedEffect(bounds) {
        if (bounds != null) {
            cameraPositionState.animate(CameraUpdateFactory.newLatLngBounds(bounds, 100))
        } else if (stops.isNotEmpty()) {
            val first = stops.firstOrNull { it.latitude != null && it.longitude != null }
            if (first != null) {
                cameraPositionState.animate(CameraUpdateFactory.newLatLngZoom(LatLng(first.latitude!!, first.longitude!!), 12f))
            }
        }
    }

    val polylinePoints = remember(routeGeometry) {
        val points = mutableListOf<LatLng>()
        if (routeGeometry != null) {
            try {
                val json = JSONObject(routeGeometry)
                if (json.has("coordinates")) {
                    val coords = json.getJSONArray("coordinates")
                    for (i in 0 until coords.length()) {
                        val pt = coords.getJSONArray(i)
                        // GeoJSON is [longitude, latitude]
                        val lng = pt.getDouble(0)
                        val lat = pt.getDouble(1)
                        points.add(LatLng(lat, lng))
                    }
                }
            } catch (e: Exception) {
                // Ignore parse errors, fallback to empty line
            }
        }
        points
    }

    GoogleMap(
        modifier = modifier.fillMaxSize(),
        cameraPositionState = cameraPositionState,
        properties = MapProperties(
            isMyLocationEnabled = false,
            mapType = MapType.NORMAL
        ),
        uiSettings = MapUiSettings(
            zoomControlsEnabled = false,
            myLocationButtonEnabled = false
        ),
        onMapClick = { onMapClick() }
    ) {
        // Route Line
        if (polylinePoints.isNotEmpty()) {
            Polyline(
                points = polylinePoints,
                color = androidx.compose.ui.graphics.Color(0xFF0D47A1), // GoBus Blue approx
                width = 12f,
                zIndex = 1f
            )
        }

        // Stops
        stops.forEach { stop ->
            if (stop.latitude != null && stop.longitude != null) {
                Marker(
                    state = MarkerState(position = LatLng(stop.latitude, stop.longitude)),
                    title = stop.stop_name,
                    icon = BitmapDescriptorFactory.defaultMarker(BitmapDescriptorFactory.HUE_AZURE),
                    alpha = 0.6f,
                    zIndex = 2f
                )
            }
        }

        // Active Buses
        buses.forEach { bus ->
            if (bus.latitude != null && bus.longitude != null) {
                val isSelected = bus.vehicle_id == selectedVehicleId
                val bitmapDescriptor = remember(isSelected) {
                    createBusMarkerBitmap(context, isSelected)
                }
                
                Marker(
                    state = MarkerState(position = LatLng(bus.latitude, bus.longitude)),
                    title = "Bus ${bus.vehicle_id}",
                    snippet = bus.eta_status,
                    icon = bitmapDescriptor,
                    zIndex = if (isSelected) 4f else 3f,
                    onClick = {
                        onBusSelected(bus.vehicle_id)
                        true // consume click
                    }
                )
            }
        }
    }
}

// Convert compose view to BitmapDescriptor
private fun createBusMarkerBitmap(context: Context, isSelected: Boolean): BitmapDescriptor {
    val composeView = ComposeView(context).apply {
        setContent {
            BusMarkerIcon(isSelected = isSelected)
        }
    }
    
    // Measure and layout
    composeView.measure(
        View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED),
        View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
    )
    composeView.layout(0, 0, composeView.measuredWidth, composeView.measuredHeight)
    
    val bitmap = Bitmap.createBitmap(
        composeView.measuredWidth,
        composeView.measuredHeight,
        Bitmap.Config.ARGB_8888
    )
    val canvas = Canvas(bitmap)
    composeView.draw(canvas)
    
    return BitmapDescriptorFactory.fromBitmap(bitmap)
}
