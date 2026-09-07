package com.transitplatform.app.ui

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.CloudDone
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.GpsFixed
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.transitplatform.app.service.ForegroundTrackingService
import com.transitplatform.app.service.LiveTrackingStatus

@Composable
fun ActiveTrackingScreen(
    uiState: OperatorUiState,
    onEndTripClicked: () -> Unit,
    onShowReportIssue: () -> Unit = {},
    onShowCrowdLevel: () -> Unit = {},
    onReportIssue: (String, String, String) -> Unit = { _, _, _ -> },
    onSelectCrowdLevel: (OperatorCrowdLevel) -> Unit = {},
    onDismissIssueDialog: () -> Unit = {},
    onDismissCrowdSheet: () -> Unit = {},
    onClearIssueSuccess: () -> Unit = {},
    onClearCrowdSuccess: () -> Unit = {}
) {
    val liveStatus by ForegroundTrackingService.trackingStatus.collectAsState()
    val assignment = uiState.assignment

    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "alpha"
    )

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
            Column(
                modifier = Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState())
            ) {
                // Tracking Active Header
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF1B5E20))
                ) {
                    Row(
                        modifier = Modifier.padding(18.dp).fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(16.dp)
                                    .clip(CircleShape)
                                    .background(Color(0xFF69F0AE).copy(alpha = alpha))
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = "TRACKING ACTIVE",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.ExtraBold,
                                color = Color.White
                            )
                        }

                        Surface(
                            color = Color.White.copy(alpha = 0.2f),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text(
                                text = liveStatus.serviceCode.ifEmpty { assignment?.service_code ?: "AC4B" },
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Vehicle and Duty Info
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp).fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column {
                            Text(text = "Bus Registration", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(
                                text = liveStatus.vehicleNumber.ifEmpty { assignment?.vehicle_number ?: "PNB005234" },
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text(text = "Direction", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(
                                text = assignment?.direction ?: "A → B",
                                fontSize = 16.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Offline Notice Banner (Dynamic)
                if (!liveStatus.isOnline) {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF3E0))
                    ) {
                        Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.CloudOff, contentDescription = null, tint = Color(0xFFE65100))
                            Spacer(modifier = Modifier.width(10.dp))
                            Text(
                                text = "Offline Mode — Location points are safely stored locally in Room queue & will sync automatically when network returns.",
                                fontSize = 12.sp,
                                color = Color(0xFFE65100)
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(16.dp))
                }

                // Telemetry Metrics Grid
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    MetricCard(
                        modifier = Modifier.weight(1f),
                        title = "GPS Status",
                        value = liveStatus.gpsStatus,
                        icon = Icons.Default.GpsFixed,
                        valueColor = if (liveStatus.gpsStatus == "OK") Color(0xFF2E7D32) else Color(0xFFE65100)
                    )
                    MetricCard(
                        modifier = Modifier.weight(1f),
                        title = "Network Sync",
                        value = if (liveStatus.isOnline) liveStatus.syncStatus else "OFFLINE",
                        icon = if (liveStatus.isOnline) Icons.Default.CloudDone else Icons.Default.CloudOff,
                        valueColor = if (liveStatus.isOnline) Color(0xFF2E7D32) else Color(0xFFC62828)
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    MetricCard(
                        modifier = Modifier.weight(1f),
                        title = "Packets Recorded",
                        value = "${liveStatus.packetsCreated}",
                        icon = null,
                        subtitle = "Total observations"
                    )
                    MetricCard(
                        modifier = Modifier.weight(1f),
                        title = "Local Buffer",
                        value = "${liveStatus.queuedPacketsCount}",
                        icon = null,
                        subtitle = if (liveStatus.queuedPacketsCount == 0) "All synced" else "Queued in Room"
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                // GPS Coordinate Box
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Text(text = "Latest Coordinate Fix", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(modifier = Modifier.height(4.dp))
                        if (liveStatus.lastLatitude != null && liveStatus.lastLongitude != null) {
                            Text(
                                text = "%.5f° N,  %.5f° E".format(liveStatus.lastLatitude, liveStatus.lastLongitude),
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = "Accuracy: ±%.1fm  ·  Speed: %.1f m/s".format(
                                    liveStatus.lastAccuracy ?: 0f,
                                    liveStatus.lastSpeed ?: 0f
                                ),
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        } else {
                            Text(text = "Acquiring satellite fix...", fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                // Success Banners
                if (uiState.issueReportSuccessMessage != null) {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = CardDefaults.cardColors(containerColor = Color(0xFFE8F5E9))
                    ) {
                        Row(
                            modifier = Modifier.padding(10.dp).fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                                Icon(Icons.Default.CheckCircle, contentDescription = null, tint = Color(0xFF2E7D32), modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(text = uiState.issueReportSuccessMessage, fontSize = 12.sp, color = Color(0xFF1B5E20), fontWeight = FontWeight.Medium)
                            }
                            TextButton(onClick = onClearIssueSuccess) {
                                Text("Dismiss", fontSize = 11.sp, color = Color(0xFF2E7D32))
                            }
                        }
                    }
                }

                if (uiState.crowdReportSuccessMessage != null) {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = CardDefaults.cardColors(containerColor = Color(0xFFE3F2FD))
                    ) {
                        Row(
                            modifier = Modifier.padding(10.dp).fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                                Icon(Icons.Default.CheckCircle, contentDescription = null, tint = Color(0xFF0277BD), modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(text = uiState.crowdReportSuccessMessage, fontSize = 12.sp, color = Color(0xFF01579B), fontWeight = FontWeight.Medium)
                            }
                            TextButton(onClick = onClearCrowdSuccess) {
                                Text("Dismiss", fontSize = 11.sp, color = Color(0xFF0277BD))
                            }
                        }
                    }
                }

                // In-App Action Buttons: [ REPORT ISSUE ] [ CROWD LEVEL ]
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Button(
                        onClick = onShowReportIssue,
                        modifier = Modifier
                            .weight(1f)
                            .height(50.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFE65100))
                    ) {
                        Icon(Icons.Default.Warning, contentDescription = null, modifier = Modifier.size(18.dp), tint = Color.White)
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "REPORT ISSUE",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }

                    Button(
                        onClick = onShowCrowdLevel,
                        modifier = Modifier
                            .weight(1f)
                            .height(50.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0277BD))
                    ) {
                        Icon(Icons.Default.Groups, contentDescription = null, modifier = Modifier.size(18.dp), tint = Color.White)
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "CROWD LEVEL",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }
                }

                // End Tracking Button
                Button(
                    onClick = onEndTripClicked,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(54.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) {
                    Icon(Icons.Default.Stop, contentDescription = null, modifier = Modifier.size(26.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "END TRIP TRACKING",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                }
            }
        }
    }

    // Overlays: Report Issue Dialog & Crowd Level Sheet
    if (uiState.isReportIssueDialogVisible) {
        ReportIssueDialog(
            isSubmitting = uiState.isSubmittingIssue,
            errorMessage = uiState.errorMessage,
            onSubmit = onReportIssue,
            onDismiss = onDismissIssueDialog
        )
    }

    if (uiState.isCrowdLevelSheetVisible) {
        CrowdLevelSheet(
            isSubmitting = uiState.isSubmittingCrowd,
            currentSelection = uiState.lastSelectedCrowdLevel,
            onSelectCrowdLevel = onSelectCrowdLevel,
            onDismiss = onDismissCrowdSheet
        )
    }
}

@Composable
private fun MetricCard(
    modifier: Modifier = Modifier,
    title: String,
    value: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector?,
    subtitle: String? = null,
    valueColor: Color = MaterialTheme.colorScheme.onSurfaceVariant
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(text = title, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(modifier = Modifier.height(4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (icon != null) {
                    Icon(icon, contentDescription = null, tint = valueColor, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                }
                Text(text = value, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = valueColor)
            }
            if (subtitle != null) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(text = subtitle, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f))
            }
        }
    }
}
