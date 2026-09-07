package com.transitplatform.passenger.ui.live

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.transitplatform.passenger.ui.components.PassengerLiveMap

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ServiceLiveScreen(
    viewModel: ServiceLiveViewModel,
    onBack: () -> Unit
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val lifecycleOwner = LocalLifecycleOwner.current

    // Handle lifecycle for polling
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_PAUSE || event == Lifecycle.Event.ON_STOP) {
                viewModel.pausePolling()
            } else if (event == Lifecycle.Event.ON_RESUME) {
                viewModel.resumePolling()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            viewModel.pausePolling()
        }
    }

    Scaffold(
        topBar = {
            val titleText = when (val s = state) {
                is ServiceLiveState.Success -> s.service.service_name
                else -> "Live Map"
            }
            TopAppBar(
                title = { Text(titleText) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    navigationIconContentColor = MaterialTheme.colorScheme.onPrimary
                )
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            when (val currentState = state) {
                is ServiceLiveState.Loading -> {
                    Column(
                        modifier = Modifier.fillMaxSize().padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        CircularProgressIndicator()
                        Spacer(modifier = Modifier.height(16.dp))
                        Text("Finding buses...", style = MaterialTheme.typography.bodyLarge)
                    }
                }
                is ServiceLiveState.Error -> {
                    Column(
                        modifier = Modifier.fillMaxSize().padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Text(currentState.message, color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = { viewModel.loadInitialData() }) {
                            Text("Retry")
                        }
                    }
                }
                is ServiceLiveState.Success -> {
                    val isBusSelected = currentState.selectedVehicleId != null

                    // Base map is always shown if we have success
                    PassengerLiveMap(
                        routeGeometry = currentState.service.route_geometry,
                        stops = currentState.service.stops,
                        buses = currentState.buses,
                        selectedVehicleId = currentState.selectedVehicleId,
                        onBusSelected = { viewModel.selectBus(it) },
                        onMapClick = { viewModel.clearSelection() },
                        modifier = Modifier.fillMaxSize()
                    )

                    // Offline Banner overlay
                    if (currentState.isOffline) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(MaterialTheme.colorScheme.errorContainer)
                                .padding(8.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                "You're offline — live updates paused.",
                                color = MaterialTheme.colorScheme.onErrorContainer,
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }

                    if (isBusSelected) {
                        // Selected Bus State
                        val selectedBus = currentState.buses.find { it.vehicle_id == currentState.selectedVehicleId }
                        if (selectedBus != null) {
                            Box(modifier = Modifier.align(Alignment.BottomCenter)) {
                                SelectedBusBottomSheet(
                                    bus = selectedBus,
                                    onClose = { viewModel.clearSelection() }
                                )
                            }
                        } else {
                            // If selected bus disappeared, we could show a snackbar or just clear selection.
                            // The viewmodel clears it if not in list, but in case of race condition:
                            LaunchedEffect(currentState.selectedVehicleId) {
                                viewModel.clearSelection()
                            }
                        }
                    } else {
                        // List State (Half overlay or full overlay? The prompt says: "When no bus is selected: show the active bus list.")
                        // We will overlay it from the bottom in a bottom sheet style, or split screen. Let's make it a bottom sheet overlay.
                        Surface(
                            modifier = Modifier
                                .align(Alignment.BottomCenter)
                                .fillMaxWidth()
                                .fillMaxHeight(0.5f), // Take bottom 50%
                            color = MaterialTheme.colorScheme.surface,
                            tonalElevation = 8.dp,
                            shadowElevation = 8.dp
                        ) {
                            LiveBusList(
                                buses = currentState.buses,
                                onBusSelected = { viewModel.selectBus(it) }
                            )
                        }
                    }
                }
            }
        }
    }
}
