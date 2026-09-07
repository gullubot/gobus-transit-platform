package com.transitplatform.passenger.ui.service

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun DepartureBoard(
    state: ServiceDetailsUiState,
    onRetry: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Text("Departures", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(bottom = 16.dp))

        if (state.departuresLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else if (state.departuresError != null) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(state.departuresError, color = MaterialTheme.colorScheme.error)
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(onClick = onRetry) {
                        Text("Try again")
                    }
                }
            }
        } else if (state.departures.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No upcoming departures.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(state.departures) { departure ->
                    Card(
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                // Priority ETA / Expected time
                                val timeText = departure.expected_time ?: departure.scheduled_time ?: "Time unknown"
                                // Time conversion is ideally done safely, but assuming backend provides string like "10:35 PM" or "5 min"
                                // The prompt says: "If expected_time is available, show it... If unavailable, fall back to scheduled time... Do not invent a new ETA algorithm."
                                
                                Text(
                                    text = timeText,
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold
                                )

                                val statusColor = when (departure.status) {
                                    "ON_TIME", "ARRIVING" -> MaterialTheme.colorScheme.primary
                                    "DELAYED" -> MaterialTheme.colorScheme.error
                                    else -> MaterialTheme.colorScheme.secondary
                                }

                                Text(
                                    text = departure.status.replace("_", " "),
                                    style = MaterialTheme.typography.labelMedium,
                                    color = statusColor
                                )
                            }
                            
                            if (departure.expected_time != null && departure.scheduled_time != null) {
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = "Scheduled: ${departure.scheduled_time}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
