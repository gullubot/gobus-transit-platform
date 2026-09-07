package com.transitplatform.passenger.ui.live

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.DirectionsBus
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.transitplatform.passenger.data.model.PassengerLiveBusResponse
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

@Composable
fun SelectedBusBottomSheet(
    bus: PassengerLiveBusResponse,
    onClose: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 8.dp,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(24.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.DirectionsBus, 
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(28.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = "Bus ${bus.vehicle_id.take(4).uppercase()}",
                        style = MaterialTheme.typography.headlineSmall,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
                
                IconButton(onClick = onClose) {
                    Icon(Icons.Default.Close, contentDescription = "Close")
                }
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            val etaText = when (val seconds = bus.eta_seconds) {
                null -> "ETA unavailable"
                in 0..60 -> "Arriving now"
                else -> "Arriving in ${seconds / 60} min"
            }
            
            Text(
                text = etaText,
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            val crowdDisplay = bus.crowd_level.lowercase().replaceFirstChar { it.uppercase() }
            Text(
                text = "● $crowdDisplay crowding",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))
            Spacer(modifier = Modifier.height(16.dp))
            
            val statusText = when (bus.state) {
                "IN_TRANSIT" -> "On the way"
                "DWELLING" -> "At stop"
                else -> bus.state.lowercase().replaceFirstChar { it.uppercase() }
            }
            
            Text(
                text = statusText,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
            
            val freshness = calculateFreshness(bus.last_updated_at)
            Text(
                text = freshness,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            
            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

private fun calculateFreshness(timestampStr: String?): String {
    if (timestampStr == null) return "Updated recently"
    try {
        // e.g. "2026-08-30T19:00:00Z"
        val format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        format.timeZone = TimeZone.getTimeZone("UTC")
        val date = format.parse(timestampStr) ?: return "Updated recently"
        
        val diffSeconds = (System.currentTimeMillis() - date.time) / 1000
        
        return when {
            diffSeconds < 15 -> "Updated just now"
            diffSeconds < 60 -> "Updated $diffSeconds sec ago"
            diffSeconds < 3600 -> "Updated ${diffSeconds / 60} min ago"
            else -> "Updated recently"
        }
    } catch (e: Exception) {
        return "Updated recently"
    }
}
