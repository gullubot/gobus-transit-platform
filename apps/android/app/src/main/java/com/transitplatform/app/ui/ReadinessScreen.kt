package com.transitplatform.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.BatteryChargingFull
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.GpsFixed
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReadinessScreen(
    uiState: OperatorUiState,
    onRequestPermissions: () -> Unit,
    onConfirmStart: () -> Unit,
    onBack: () -> Unit
) {
    val readiness = uiState.readiness

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Tracking Readiness",
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Bold
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = "System check before starting GPS duty session:",
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                Spacer(modifier = Modifier.height(20.dp))

                // Readiness Checklist Cards
                ReadinessItem(
                    icon = Icons.Default.LocationOn,
                    title = "Location Permission",
                    subtitle = if (readiness.hasFineLocation) "Precise GPS granted" else "Permission required",
                    isPass = readiness.hasFineLocation
                )

                Spacer(modifier = Modifier.height(12.dp))

                ReadinessItem(
                    icon = Icons.Default.GpsFixed,
                    title = "GPS Location Hardware",
                    subtitle = if (readiness.isGpsEnabled) "Hardware GPS active" else "Please enable GPS in Settings",
                    isPass = readiness.isGpsEnabled
                )

                Spacer(modifier = Modifier.height(12.dp))

                ReadinessItem(
                    icon = Icons.Default.Notifications,
                    title = "Foreground Notification",
                    subtitle = if (readiness.hasNotificationPermission) "Notification permission ready" else "Required for persistent duty banner",
                    isPass = readiness.hasNotificationPermission
                )

                Spacer(modifier = Modifier.height(12.dp))

                ReadinessItem(
                    icon = Icons.Default.Wifi,
                    title = "Network Connection",
                    subtitle = if (readiness.isNetworkAvailable) "Online — live sync active" else "Offline — location stored locally & synced later",
                    isPass = true, // Network is NOT a blocker! Offline storage is fully supported
                    isWarning = !readiness.isNetworkAvailable
                )

                Spacer(modifier = Modifier.height(12.dp))

                ReadinessItem(
                    icon = Icons.Default.BatteryChargingFull,
                    title = "Device Battery",
                    subtitle = "${readiness.batteryPercentage}% battery remaining",
                    isPass = readiness.batteryPercentage > 15,
                    isWarning = readiness.batteryPercentage <= 15
                )
            }

            // Bottom action button
            Column {
                if (!readiness.hasFineLocation || !readiness.hasNotificationPermission) {
                    Button(
                        onClick = onRequestPermissions,
                        modifier = Modifier.fillMaxWidth().height(56.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.secondary)
                    ) {
                        Text("GRANT REQUIRED PERMISSIONS", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                    }
                } else {
                    Button(
                        onClick = onConfirmStart,
                        enabled = readiness.isGpsEnabled && !uiState.isLoading,
                        modifier = Modifier.fillMaxWidth().height(58.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                    ) {
                        if (uiState.isLoading) {
                            CircularProgressIndicator(color = MaterialTheme.colorScheme.onPrimary, modifier = Modifier.size(24.dp))
                        } else {
                            Text("CONFIRM & BEGIN TRACKING", fontSize = 17.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ReadinessItem(
    icon: ImageVector,
    title: String,
    subtitle: String,
    isPass: Boolean,
    isWarning: Boolean = false
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Row(
            modifier = Modifier.padding(16.dp).fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(28.dp)
                )
                Spacer(modifier = Modifier.width(16.dp))
                Column {
                    Text(text = title, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                    Text(text = subtitle, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            Box(
                modifier = Modifier
                    .size(28.dp)
                    .background(
                        color = when {
                            isWarning -> Color(0xFFFFA000)
                            isPass -> Color(0xFF2E7D32)
                            else -> Color(0xFFC62828)
                        },
                        shape = CircleShape
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = if (isPass || isWarning) Icons.Default.Check else Icons.Default.Close,
                    contentDescription = null,
                    tint = Color.White,
                    modifier = Modifier.size(18.dp)
                )
            }
        }
    }
}
