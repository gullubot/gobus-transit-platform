package com.transitplatform.passenger.ui.service

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.SwapVert
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.transitplatform.passenger.data.model.RouteStopDetail

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ServiceDetailsScreen(
    viewModel: ServiceDetailsViewModel,
    onBack: () -> Unit,
    onViewLiveBuses: (String) -> Unit
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(state.service?.service_name ?: "Service Details") },
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
        Box(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
            if (state.loading) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else if (state.error != null) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(state.error!!, color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = viewModel::loadServiceDetails) {
                            Text("Try again")
                        }
                    }
                }
            } else if (state.service != null) {
                Column(modifier = Modifier.fillMaxSize()) {
                    // Header
                    ServiceHeader(
                        serviceName = state.service!!.service_name,
                        routeName = state.service!!.route_name,
                        activeDirection = state.activeDirection,
                        onDirectionToggle = {
                            val newDir = if (state.activeDirection == "A_TO_B") "B_TO_A" else "A_TO_B"
                            viewModel.setDirection(newDir)
                        },
                        onLiveBusesClick = { onViewLiveBuses(state.service!!.id) }
                    )

                    HorizontalDivider()

                    // Main Content Split
                    Row(modifier = Modifier.fillMaxSize()) {
                        // Left: Stop List
                        Box(modifier = Modifier.weight(1f).fillMaxHeight()) {
                            StopList(
                                stops = state.displayedStops,
                                selectedStopId = state.selectedStopId,
                                onStopSelect = viewModel::selectStop
                            )
                        }

                        // Right: Departure Board (only if stop selected)
                        if (state.selectedStopId != null) {
                            VerticalDivider()
                            Box(modifier = Modifier.weight(1f).fillMaxHeight().padding(8.dp)) {
                                DepartureBoard(state = state, onRetry = viewModel::retryDepartures)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ServiceHeader(
    serviceName: String,
    routeName: String,
    activeDirection: String,
    onDirectionToggle: () -> Unit,
    onLiveBusesClick: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(serviceName, style = MaterialTheme.typography.titleLarge)
                Text(routeName, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Button(onClick = onLiveBusesClick, shape = RoundedCornerShape(16.dp)) {
                Text("Live Buses")
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Direction Toggle
        Card(
            modifier = Modifier.fillMaxWidth().clickable { onDirectionToggle() },
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
            shape = RoundedCornerShape(16.dp)
        ) {
            Row(
                modifier = Modifier.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center
            ) {
                Icon(Icons.Default.SwapVert, contentDescription = "Toggle Direction", tint = MaterialTheme.colorScheme.onSecondaryContainer)
                Spacer(modifier = Modifier.width(8.dp))
                val dirText = if (activeDirection == "A_TO_B") "Direction: A → B" else "Direction: B → A"
                Text(dirText, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSecondaryContainer)
            }
        }
    }
}

@Composable
fun StopList(
    stops: List<RouteStopDetail>,
    selectedStopId: String?,
    onStopSelect: (String) -> Unit
) {
    LazyColumn(
        contentPadding = PaddingValues(vertical = 16.dp, horizontal = 8.dp),
        modifier = Modifier.fillMaxSize()
    ) {
        itemsIndexed(stops) { index, stop ->
            val isFirst = index == 0
            val isLast = index == stops.size - 1
            val isSelected = stop.stop_id == selectedStopId

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onStopSelect(stop.stop_id) }
                    .background(if (isSelected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f) else MaterialTheme.colorScheme.surface)
                    .padding(vertical = 8.dp, horizontal = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Visual route line
                Box(
                    modifier = Modifier.width(24.dp).height(48.dp),
                    contentAlignment = Alignment.Center
                ) {
                    if (!isFirst) {
                        Box(modifier = Modifier.align(Alignment.TopCenter).width(4.dp).height(24.dp).background(MaterialTheme.colorScheme.primary))
                    }
                    if (!isLast) {
                        Box(modifier = Modifier.align(Alignment.BottomCenter).width(4.dp).height(24.dp).background(MaterialTheme.colorScheme.primary))
                    }
                    val circleSize = if (isFirst || isLast || isSelected) 16.dp else 12.dp
                    val circleColor = if (isSelected) MaterialTheme.colorScheme.primary else if (isFirst || isLast) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.surfaceVariant
                    Box(modifier = Modifier.size(circleSize).clip(CircleShape).background(circleColor))
                }
                
                Spacer(modifier = Modifier.width(12.dp))
                
                Text(
                    text = stop.stop_name,
                    style = if (isSelected) MaterialTheme.typography.titleMedium else MaterialTheme.typography.bodyMedium,
                    color = if (isSelected) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurface
                )
            }
        }
    }
}
