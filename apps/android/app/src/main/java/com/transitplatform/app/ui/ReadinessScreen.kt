package com.transitplatform.app.ui

import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.BatteryChargingFull
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.DirectionsBus
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.GpsFixed
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Route
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner

enum class ReadinessItemStatus {
    PASS,
    BLOCKING,
    WARNING,
    INFO
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReadinessScreen(
    uiState: OperatorUiState,
    onRequestPermissions: () -> Unit,
    onConfirmStart: () -> Unit,
    onBack: () -> Unit,
    onRecheckReadiness: () -> Unit = {}
) {
    val readiness = uiState.readiness
    val assignment = uiState.assignment
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scrollState = rememberScrollState()

    // Automatically re-evaluate readiness whenever returning from settings or permissions dialog
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                onRecheckReadiness()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 20.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Column(
                modifier = Modifier
                    .weight(1f)
                    .verticalScroll(scrollState)
            ) {
                // Top Header Row
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Column {
                        Text(
                            text = "Trip Readiness Check",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onBackground
                        )
                        Text(
                            text = "Mandatory operational verification before departure",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // Duty / Trip Context Card
                if (assignment != null) {
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(
                                width = 1.dp,
                                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f),
                                shape = RoundedCornerShape(16.dp)
                            ),
                        shape = RoundedCornerShape(16.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                        )
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Box(
                                        modifier = Modifier
                                            .background(
                                                color = MaterialTheme.colorScheme.primary,
                                                shape = RoundedCornerShape(8.dp)
                                            )
                                            .padding(horizontal = 10.dp, vertical = 4.dp)
                                    ) {
                                        Text(
                                            text = assignment.service_code.ifBlank { "TRIP" },
                                            fontSize = 16.sp,
                                            fontWeight = FontWeight.Black,
                                            color = MaterialTheme.colorScheme.onPrimary
                                        )
                                    }
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        text = assignment.route_name.ifBlank { assignment.service_name.ifBlank { "Scheduled Duty" } },
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.onSurface
                                    )
                                }
                                Box(
                                    modifier = Modifier
                                        .background(
                                            color = MaterialTheme.colorScheme.secondaryContainer,
                                            shape = RoundedCornerShape(8.dp)
                                        )
                                        .padding(horizontal = 8.dp, vertical = 3.dp)
                                ) {
                                    Text(
                                        text = assignment.trip_status,
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.onSecondaryContainer
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.height(8.dp))
                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f))
                            Spacer(modifier = Modifier.height(8.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = "Vehicle: ${assignment.vehicle_number.ifBlank { "UNASSIGNED" }}",
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Text(
                                    text = "Role: ${assignment.operator_role.ifBlank { "DRIVER" }}",
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))
                }

                // Overall Readiness Summary Pill
                val isReady = readiness.isReadyToTrack
                val gateState = uiState.readinessGateState
                val readyToStart = isReady && (gateState == ReadinessGateState.READY_TO_START || gateState == ReadinessGateState.STARTING || gateState == ReadinessGateState.READINESS_EVALUATING)

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = if (readyToStart) Color(0xFFE8F5E9) else Color(0xFFFFEBEE)
                    ),
                    border = CardDefaults.outlinedCardBorder().copy(
                        brush = androidx.compose.ui.graphics.SolidColor(
                            if (readyToStart) Color(0xFF2E7D32) else Color(0xFFC62828)
                        )
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = if (readyToStart) Icons.Default.CheckCircle else Icons.Default.Warning,
                            contentDescription = null,
                            tint = if (readyToStart) Color(0xFF2E7D32) else Color(0xFFC62828),
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                text = if (readyToStart) "READY TO START DUTY" else "${readiness.blockingFailuresCount} BLOCKING CHECK(S) REMAINING",
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Black,
                                color = if (readyToStart) Color(0xFF1B5E20) else Color(0xFFB71C1C)
                            )
                            val summarySubtext = when {
                                readyToStart && readiness.warningCount > 0 -> "All blocking items pass (${readiness.warningCount} non-blocking warning active)"
                                readyToStart -> "All blocking system requirements satisfied"
                                else -> "Mandatory items must pass before departure tracking is allowed"
                            }
                            Text(
                                text = summarySubtext,
                                fontSize = 11.sp,
                                color = if (readyToStart) Color(0xFF2E7D32) else Color(0xFFC62828)
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = "READINESS CHECKLIST",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Black,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    letterSpacing = 1.sp
                )

                Spacer(modifier = Modifier.height(10.dp))

                // ── 1. Authenticated Session ──
                ReadinessCheckCard(
                    icon = Icons.Default.Person,
                    title = "Authenticated Session",
                    subtitle = if (readiness.hasAuthenticatedSession) {
                        "Operator session active: ${uiState.userProfile?.name ?: "Verified"}"
                    } else {
                        "Valid operator login required (BLOCKING)"
                    },
                    status = if (readiness.hasAuthenticatedSession) ReadinessItemStatus.PASS else ReadinessItemStatus.BLOCKING
                )

                Spacer(modifier = Modifier.height(8.dp))

                // ── 2. Trip Assignment ──
                ReadinessCheckCard(
                    icon = Icons.Default.Route,
                    title = "Trip Assignment",
                    subtitle = if (readiness.hasTripAssignment) {
                        "Scheduled duty verified: ${assignment?.service_code ?: ""}"
                    } else {
                        "No eligible active trip assigned for this duty (BLOCKING)"
                    },
                    status = if (readiness.hasTripAssignment) ReadinessItemStatus.PASS else ReadinessItemStatus.BLOCKING
                )

                Spacer(modifier = Modifier.height(8.dp))

                // ── 3. Vehicle Assignment ──
                ReadinessCheckCard(
                    icon = Icons.Default.DirectionsBus,
                    title = "Vehicle Assignment",
                    subtitle = if (readiness.hasVehicleAssignment) {
                        "Bus ${assignment?.vehicle_number} scoped & assigned"
                    } else {
                        "No vehicle assigned to this trip (BLOCKING)"
                    },
                    status = if (readiness.hasVehicleAssignment) ReadinessItemStatus.PASS else ReadinessItemStatus.BLOCKING
                )

                Spacer(modifier = Modifier.height(8.dp))

                // ── 4. Operator Assignment ──
                ReadinessCheckCard(
                    icon = Icons.Default.Person,
                    title = "Operator Duty Assignment",
                    subtitle = if (readiness.hasOperatorAssignment) {
                        "${assignment?.operator_role ?: "Driver"} duty confirmed (${assignment?.assignment_status ?: "ASSIGNED"})"
                    } else {
                        "Operator assignment inactive or unassigned (BLOCKING)"
                    },
                    status = if (readiness.hasOperatorAssignment) ReadinessItemStatus.PASS else ReadinessItemStatus.BLOCKING
                )

                Spacer(modifier = Modifier.height(8.dp))

                // ── 5. Location Permission ──
                ReadinessCheckCard(
                    icon = Icons.Default.LocationOn,
                    title = "Location Permission",
                    subtitle = if (readiness.hasFineLocation) {
                        "Precise GPS location permission granted"
                    } else {
                        "Precise location permission required for tracking (BLOCKING)"
                    },
                    status = if (readiness.hasFineLocation) ReadinessItemStatus.PASS else ReadinessItemStatus.BLOCKING,
                    actionText = if (!readiness.hasFineLocation) "GRANT PERMISSION" else null,
                    onAction = onRequestPermissions
                )

                Spacer(modifier = Modifier.height(8.dp))

                // ── 6. GPS Hardware Switch ──
                ReadinessCheckCard(
                    icon = Icons.Default.GpsFixed,
                    title = "GPS Location Hardware",
                    subtitle = if (readiness.isGpsEnabled) {
                        "Device GPS provider enabled"
                    } else {
                        "GPS is turned off in Android system settings (BLOCKING)"
                    },
                    status = if (readiness.isGpsEnabled) ReadinessItemStatus.PASS else ReadinessItemStatus.BLOCKING,
                    actionText = if (!readiness.isGpsEnabled) "OPEN LOCATION SETTINGS" else null,
                    onAction = {
                        val intent = Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
                        context.startActivity(intent)
                    }
                )

                Spacer(modifier = Modifier.height(8.dp))

                // ── 7. Foreground Duty Notifications ──
                val notifPass = readiness.hasNotificationCheckPassed
                ReadinessCheckCard(
                    icon = Icons.Default.Notifications,
                    title = "Foreground Notification",
                    subtitle = when {
                        notifPass && readiness.isNotificationPermissionRequired -> "Persistent duty banner permission granted"
                        notifPass -> "Notification enabled by system platform"
                        else -> "Notification permission required for active duty banner (BLOCKING)"
                    },
                    status = if (notifPass) ReadinessItemStatus.PASS else ReadinessItemStatus.BLOCKING,
                    actionText = if (!notifPass && readiness.isNotificationPermissionRequired) "ENABLE NOTIFICATIONS" else null,
                    onAction = onRequestPermissions
                )

                Spacer(modifier = Modifier.height(8.dp))

                // ── 8. Network Connectivity (WARNING ONLY) ──
                ReadinessCheckCard(
                    icon = Icons.Default.Wifi,
                    title = "Network Connection",
                    subtitle = if (readiness.isNetworkAvailable) {
                        "Online — live cloud telemetry sync active"
                    } else {
                        "Offline — store-and-forward active; telemetry queues locally in Room"
                    },
                    status = if (readiness.isNetworkAvailable) ReadinessItemStatus.PASS else ReadinessItemStatus.WARNING
                )

                Spacer(modifier = Modifier.height(8.dp))

                // ── 9. Device Battery ──
                val isBatteryLow = readiness.batteryPercentage <= 15
                ReadinessCheckCard(
                    icon = Icons.Default.BatteryChargingFull,
                    title = "Device Battery",
                    subtitle = if (isBatteryLow) {
                        "${readiness.batteryPercentage}% battery remaining — Connect vehicle charger soon"
                    } else {
                        "${readiness.batteryPercentage}% battery remaining — Sufficient charge"
                    },
                    status = if (isBatteryLow) ReadinessItemStatus.WARNING else ReadinessItemStatus.INFO
                )

                Spacer(modifier = Modifier.height(16.dp))
            }

            // Bottom Action Area & Gate Enforcement
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp)
            ) {
                // Display error message if start failed
                if (uiState.errorMessage != null) {
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 10.dp),
                        shape = RoundedCornerShape(10.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.ErrorOutline,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.error,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = uiState.errorMessage,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.onErrorContainer
                            )
                        }
                    }
                }

                val canStart = readiness.isReadyToTrack &&
                        (uiState.readinessGateState == ReadinessGateState.READY_TO_START || uiState.readinessGateState == ReadinessGateState.READINESS_EVALUATING) &&
                        !uiState.isLoading

                Button(
                    onClick = onConfirmStart,
                    enabled = canStart,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (canStart) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant,
                        contentColor = if (canStart) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant
                    )
                ) {
                    if (uiState.isLoading || uiState.readinessGateState == ReadinessGateState.STARTING) {
                        CircularProgressIndicator(
                            color = MaterialTheme.colorScheme.onPrimary,
                            modifier = Modifier.size(22.dp),
                            strokeWidth = 2.5.dp
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = "STARTING TRIP...",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 0.5.sp
                        )
                    } else if (canStart) {
                        Icon(
                            imageVector = Icons.Default.PlayArrow,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "CONFIRM & BEGIN TRACKING",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 0.5.sp
                        )
                    } else {
                        Text(
                            text = "RESOLVE ${readiness.blockingFailuresCount} BLOCKING REQUIREMENT(S)",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 0.5.sp
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ReadinessCheckCard(
    icon: ImageVector,
    title: String,
    subtitle: String,
    status: ReadinessItemStatus,
    actionText: String? = null,
    onAction: (() -> Unit)? = null
) {
    val (statusLabel, badgeColor, textColor) = when (status) {
        ReadinessItemStatus.PASS -> Triple("PASS", Color(0xFFE8F5E9), Color(0xFF2E7D32))
        ReadinessItemStatus.BLOCKING -> Triple("BLOCKING", Color(0xFFFFEBEE), Color(0xFFC62828))
        ReadinessItemStatus.WARNING -> Triple("WARNING", Color(0xFFFFF3E0), Color(0xFFE65100))
        ReadinessItemStatus.INFO -> Triple("INFO", Color(0xFFE3F2FD), Color(0xFF1565C0))
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = androidx.compose.ui.graphics.SolidColor(
                when (status) {
                    ReadinessItemStatus.BLOCKING -> Color(0xFFEF9A9A)
                    ReadinessItemStatus.WARNING -> Color(0xFFFFCC80)
                    else -> MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f)
                }
            )
        )
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.weight(1f)
                ) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(badgeColor),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = when (status) {
                                ReadinessItemStatus.PASS -> Icons.Default.Check
                                ReadinessItemStatus.BLOCKING -> Icons.Default.Close
                                ReadinessItemStatus.WARNING -> Icons.Default.Warning
                                ReadinessItemStatus.INFO -> Icons.Default.Info
                            },
                            contentDescription = null,
                            tint = textColor,
                            modifier = Modifier.size(20.dp)
                        )
                    }

                    Spacer(modifier = Modifier.width(12.dp))

                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = title,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(badgeColor)
                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                            ) {
                                Text(
                                    text = statusLabel,
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Black,
                                    color = textColor
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = subtitle,
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }

            // In-Card Action Shortcut
            if (actionText != null && onAction != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Button(
                    onClick = onAction,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(36.dp),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (status == ReadinessItemStatus.BLOCKING) Color(0xFFC62828) else MaterialTheme.colorScheme.secondary
                    ),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 0.dp)
                ) {
                    Text(
                        text = actionText,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 0.5.sp
                    )
                }
            }
        }
    }
}
