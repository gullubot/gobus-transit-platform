package com.transitplatform.passenger.ui.components

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.*
import com.transitplatform.passenger.data.model.PassengerStopResponse

@Composable
fun PassengerMap(
    stops: List<PassengerStopResponse>,
    modifier: Modifier = Modifier
) {
    // Default fallback to center (e.g., Kolkata as fallback if no stops are provided yet)
    // 22.5726, 88.3639 is Kolkata
    val defaultLocation = LatLng(22.5726, 88.3639)
    
    // Determine initial camera position based on available stops
    val initialLocation = remember(stops) {
        if (stops.isNotEmpty()) {
            val firstValid = stops.firstOrNull { it.latitude != null && it.longitude != null }
            if (firstValid != null) {
                LatLng(firstValid.latitude!!, firstValid.longitude!!)
            } else {
                defaultLocation
            }
        } else {
            defaultLocation
        }
    }

    val cameraPositionState = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(initialLocation, 12f)
    }
    
    // If stops load/change dramatically, we could animate camera, but for now just set it once
    // or let user pan freely.
    LaunchedEffect(initialLocation) {
        if (stops.isNotEmpty() && cameraPositionState.position.target == defaultLocation) {
             cameraPositionState.position = CameraPosition.fromLatLngZoom(initialLocation, 12f)
        }
    }

    // Clean passenger map
    val mapProperties by remember {
        mutableStateOf(
            MapProperties(
                isMyLocationEnabled = false, // No background location permission needed
                mapType = MapType.NORMAL
            )
        )
    }

    val mapUiSettings by remember {
        mutableStateOf(
            MapUiSettings(
                zoomControlsEnabled = false,
                compassEnabled = false,
                myLocationButtonEnabled = false,
                mapToolbarEnabled = false
            )
        )
    }

    GoogleMap(
        modifier = modifier.fillMaxSize(),
        cameraPositionState = cameraPositionState,
        properties = mapProperties,
        uiSettings = mapUiSettings
    ) {
        // We are instructed NOT to show every stop permanently unless there is a strong UX reason.
        // So we will leave the map clean for now.
    }
}
