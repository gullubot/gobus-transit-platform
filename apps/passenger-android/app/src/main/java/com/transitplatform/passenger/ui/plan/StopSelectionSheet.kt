package com.transitplatform.passenger.ui.plan

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.transitplatform.passenger.data.model.PassengerStopResponse

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StopSelectionSheet(
    viewModel: PlanTripViewModel,
    isOrigin: Boolean = false,
    onDismiss: () -> Unit
) {
    val searchQuery by viewModel.searchQuery.collectAsStateWithLifecycle()
    val filteredStops by viewModel.filteredStops.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .fillMaxHeight(0.9f)
            .padding(16.dp)
    ) {
        // Search Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = searchQuery,
                onValueChange = viewModel::updateSearchQuery,
                modifier = Modifier.weight(1f),
                placeholder = { Text(if (isOrigin) "Search origin..." else "Search destination...") },
                singleLine = true,
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { viewModel.updateSearchQuery("") }) {
                            Icon(Icons.Default.Close, contentDescription = "Clear search")
                        }
                    }
                }
            )
            Spacer(modifier = Modifier.width(8.dp))
            TextButton(onClick = {
                viewModel.updateSearchQuery("")
                onDismiss()
            }) {
                Text("Cancel")
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Results
        if (filteredStops.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = "No stops found",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else {
            LazyColumn {
                items(filteredStops, key = { it.id }) { stop ->
                    StopSelectionItem(
                        stop = stop,
                        onClick = {
                            if (isOrigin) {
                                viewModel.setOrigin(stop)
                            } else {
                                viewModel.setDestination(stop)
                            }
                            viewModel.updateSearchQuery("")
                            onDismiss()
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun StopSelectionItem(
    stop: PassengerStopResponse,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 12.dp, horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = Icons.Default.LocationOn,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(24.dp)
        )
        Spacer(modifier = Modifier.width(16.dp))
        Column {
            Text(
                text = stop.name,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface
            )
            if (stop.stop_code.isNotBlank()) {
                Text(
                    text = "Stop ${stop.stop_code}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
}
