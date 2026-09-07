package com.transitplatform.passenger.ui.home

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
fun DestinationSearchSheet(
    viewModel: HomeViewModel,
    isOrigin: Boolean = false,
    onDismiss: () -> Unit
) {
    val searchQuery by viewModel.searchQuery.collectAsStateWithLifecycle()
    val searchState by viewModel.stopSearchState.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .fillMaxHeight(0.9f) // Take up 90% of screen height
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
                placeholder = { Text("Search destination...") },
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
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Search Results
        when (val state = searchState) {
            is StopSearchState.Idle -> {
                // Before search starts, maybe show recent searches in the future.
                // For now, if empty, it just shows list of all stops if cached
                val allStops = viewModel.getAllStops()
                if (allStops.isNotEmpty()) {
                    StopList(stops = allStops, onStopSelected = { 
                        if (isOrigin) {
                            viewModel.selectOrigin(it)
                        } else {
                            viewModel.selectDestination(it)
                        }
                        onDismiss()
                    })
                }
            }
            is StopSearchState.Loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }
            is StopSearchState.Error -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(text = state.message, color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(8.dp))
                        if (state.message.contains("Try again")) {
                            Button(onClick = viewModel::retryLoadStops) {
                                Text("Retry")
                            }
                        }
                    }
                }
            }
            is StopSearchState.Success -> {
                StopList(stops = state.stops, onStopSelected = { 
                    if (isOrigin) {
                        viewModel.selectOrigin(it)
                    } else {
                        viewModel.selectDestination(it)
                    }
                    onDismiss()
                })
            }
        }
    }
}

@Composable
private fun StopList(
    stops: List<PassengerStopResponse>,
    onStopSelected: (PassengerStopResponse) -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(stops) { stop ->
            StopSearchResultItem(stop = stop, onClick = { onStopSelected(stop) })
        }
    }
}

@Composable
private fun StopSearchResultItem(stop: PassengerStopResponse, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
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
            Text(text = stop.name, style = MaterialTheme.typography.bodyLarge)
            if (stop.stop_code.isNotEmpty()) {
                Text(
                    text = "Stop Code: ${stop.stop_code}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
