package com.transitplatform.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.AltRoute
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.transitplatform.app.data.model.AssignmentResponse
import java.util.Calendar

@Composable
fun AssignmentScreen(
    uiState: OperatorUiState,
    onRefresh: () -> Unit,
    onStartTrackingClicked: () -> Unit,
    onLogout: () -> Unit,
    onNavigateToTodaysTrips: () -> Unit = {}
) {
    val assignment = uiState.assignment
    val user = uiState.userProfile
    val scrollState = rememberScrollState()

    var activeQuickActionDialog by remember { mutableStateOf<String?>(null) }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .verticalScroll(scrollState)
                .padding(horizontal = 20.dp, vertical = 16.dp)
        ) {
            // ── TOP BAR / OPERATOR IDENTITY ──
            OperatorHeader(
                operatorName = user?.name,
                organizationName = user?.organization_name,
                onRefresh = onRefresh,
                onLogout = onLogout,
                isLoading = uiState.isLoading
            )

            Spacer(modifier = Modifier.height(20.dp))

            // ── ERROR BANNER ──
            if (uiState.errorMessage != null) {
                ErrorBanner(
                    message = uiState.errorMessage,
                    onRetry = onRefresh
                )
                Spacer(modifier = Modifier.height(16.dp))
            }

            // ── LOADING STATE ──
            if (uiState.isLoading && assignment == null) {
                LoadingDutyCard()
            } else if (assignment != null) {
                // ── TODAY'S DUTY (HERO CARD) ──
                TodaysDutyCard(
                    assignment = assignment,
                    onStartTrip = onStartTrackingClicked,
                    isStarting = uiState.isLoading
                )

                Spacer(modifier = Modifier.height(20.dp))

                // ── NEXT DEPARTURE ──
                NextDepartureCard(assignment = assignment)

                Spacer(modifier = Modifier.height(20.dp))

                // ── MY VEHICLE ──
                MyVehicleCard(assignment = assignment)

                Spacer(modifier = Modifier.height(20.dp))

                // ── QUICK ACTIONS ──
                Text(
                    text = "QUICK ACTIONS",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    letterSpacing = 1.sp
                )
                Spacer(modifier = Modifier.height(10.dp))
                QuickActionsRow(
                    onActionClick = { action ->
                        if (action == "trips") {
                            onNavigateToTodaysTrips()
                        } else {
                            activeQuickActionDialog = action
                        }
                    }
                )
            } else {
                // ── NO DUTY ASSIGNED STATE ──
                NoDutyCard(onCheckDuty = onRefresh, isLoading = uiState.isLoading)
            }

            Spacer(modifier = Modifier.height(32.dp))
        }
    }

    // Quick Action Information Dialogs
    if (activeQuickActionDialog != null && assignment != null) {
        QuickActionDialog(
            actionType = activeQuickActionDialog!!,
            assignment = assignment,
            onDismiss = { activeQuickActionDialog = null }
        )
    }
}

/**
 * Clean operator greeting header with contextual time of day and actions.
 */
@Composable
private fun OperatorHeader(
    operatorName: String?,
    organizationName: String?,
    onRefresh: () -> Unit,
    onLogout: () -> Unit,
    isLoading: Boolean
) {
    val firstName = operatorName?.trim()?.split(" ")?.firstOrNull() ?: "Operator"
    val greeting = remember(operatorName) {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        when (hour) {
            in 4..11 -> "Good morning"
            in 12..16 -> "Good afternoon"
            else -> "Good evening"
        }
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = "$greeting, $firstName 👋",
                fontSize = 22.sp,
                fontWeight = FontWeight.ExtraBold,
                color = MaterialTheme.colorScheme.onBackground
            )
            Text(
                text = if (!organizationName.isNullOrBlank()) organizationName else "GoBus Operations",
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(
                onClick = onRefresh,
                enabled = !isLoading,
                modifier = Modifier
                    .size(44.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.primary
                    )
                } else {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = "Refresh Duty",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Spacer(modifier = Modifier.width(8.dp))

            IconButton(
                onClick = onLogout,
                modifier = Modifier
                    .size(44.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.4f))
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ExitToApp,
                    contentDescription = "Logout",
                    tint = MaterialTheme.colorScheme.error
                )
            }
        }
    }
}

/**
 * Primary Hero card presenting today's operational duty clearly with zero jargon.
 */
@Composable
private fun TodaysDutyCard(
    assignment: AssignmentResponse,
    onStartTrip: () -> Unit,
    isStarting: Boolean
) {
    val displayServiceCode = remember(assignment.service_code, assignment.service_name) {
        when {
            assignment.service_code.contains("-") -> assignment.service_code.substringAfter("-")
            assignment.service_name.isNotBlank() && assignment.service_name.length <= 6 -> assignment.service_name
            else -> assignment.service_code
        }
    }

    val (statusLabel, statusColor, statusBg) = remember(assignment.assignment_status, assignment.trip_status) {
        when {
            assignment.trip_status == "ACTIVE" || assignment.assignment_status == "ACTIVE" ->
                Triple("Trip in Progress", Color(0xFF059669), Color(0xFFD1FAE5))
            assignment.assignment_status == "ASSIGNED" ->
                Triple("Ready for Duty", Color(0xFF2563EB), Color(0xFFDBEAFE))
            assignment.trip_status == "PLANNED" ->
                Triple("Scheduled", Color(0xFFD97706), Color(0xFFFEF3C7))
            else ->
                Triple("Assigned", Color(0xFF4B5563), Color(0xFFF3F4F6))
        }
    }

    val (originName, destinationName, viaText) = remember(assignment) {
        resolveRouteStops(assignment)
    }

    val departureTimeFormatted = remember(assignment.planned_start_at) {
        formatTimeOfDay(assignment.planned_start_at)
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f),
                shape = RoundedCornerShape(22.dp)
            ),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(22.dp)
        ) {
            // Header Row: Service Badge & Status Pill
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
                                shape = RoundedCornerShape(12.dp)
                            )
                            .padding(horizontal = 14.dp, vertical = 6.dp)
                    ) {
                        Text(
                            text = displayServiceCode,
                            fontSize = 24.sp,
                            fontWeight = FontWeight.Black,
                            color = MaterialTheme.colorScheme.onPrimary
                        )
                    }
                    if (assignment.service_name.isNotBlank() && assignment.service_name != displayServiceCode) {
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = assignment.service_name,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                    }
                }

                // Status Pill
                Surface(
                    color = statusBg,
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(statusColor)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = statusLabel,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = statusColor
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Route Endpoint Visualizer
            RouteEndpointsView(
                origin = originName,
                destination = destinationName,
                via = viaText
            )

            Spacer(modifier = Modifier.height(20.dp))

            HorizontalDivider(
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f),
                thickness = 1.dp
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Key Duty Metrics (Vehicle, Departure, Distance)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                DutyMetricItem(
                    icon = Icons.Default.DirectionsBus,
                    label = "VEHICLE",
                    value = assignment.vehicle_number,
                    subtext = assignment.vehicle_registration ?: assignment.vehicle_type ?: "Bus"
                )

                DutyMetricItem(
                    icon = Icons.Default.Schedule,
                    label = "NEXT DEPARTURE",
                    value = departureTimeFormatted,
                    subtext = "Scheduled"
                )

                if (assignment.route_distance_km != null && assignment.route_distance_km > 0) {
                    DutyMetricItem(
                        icon = Icons.AutoMirrored.Filled.AltRoute,
                        label = "DISTANCE",
                        value = String.format("%.1f km", assignment.route_distance_km),
                        subtext = "One Way"
                    )
                }
            }

            Spacer(modifier = Modifier.height(22.dp))

            // Primary Touch-Friendly Action Button: START TRIP
            Button(
                onClick = onStartTrip,
                enabled = !isStarting,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(58.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary
                ),
                elevation = ButtonDefaults.buttonElevation(defaultElevation = 3.dp)
            ) {
                if (isStarting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                } else {
                    Icon(
                        imageVector = Icons.Default.PlayArrow,
                        contentDescription = null,
                        modifier = Modifier.size(28.dp)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = if (assignment.assignment_status == "ACTIVE" || assignment.trip_status == "ACTIVE") "RESUME TRIP TRACKING" else "START TRIP",
                        fontSize = 17.sp,
                        fontWeight = FontWeight.ExtraBold,
                        letterSpacing = 0.5.sp
                    )
                }
            }
        }
    }
}

/**
 * Visual route layout showing origin stop, directional path, and destination terminal.
 */
@Composable
private fun RouteEndpointsView(
    origin: String,
    destination: String,
    via: String?
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        // Origin Stop
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(16.dp)
                    .clip(CircleShape)
                    .background(Color(0xFF10B981)),
                contentAlignment = Alignment.Center
            ) {
                Box(
                    modifier = Modifier
                        .size(6.dp)
                        .clip(CircleShape)
                        .background(Color.White)
                )
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Text(
                    text = origin,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = "Origin Terminal",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        // Connector Arrow & Via text
        Row(
            modifier = Modifier.padding(start = 7.dp, top = 2.dp, bottom = 2.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .width(2.dp)
                    .height(26.dp)
                    .background(MaterialTheme.colorScheme.outlineVariant)
            )
            Spacer(modifier = Modifier.width(19.dp))
            if (!via.isNullOrBlank()) {
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text(
                        text = via,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            } else {
                Icon(
                    imageVector = Icons.Default.ArrowDownward,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                    modifier = Modifier.size(14.dp)
                )
            }
        }

        // Destination Stop
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(16.dp)
                    .clip(CircleShape)
                    .background(Color(0xFFEF4444)),
                contentAlignment = Alignment.Center
            ) {
                Box(
                    modifier = Modifier
                        .size(6.dp)
                        .clip(CircleShape)
                        .background(Color.White)
                )
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Text(
                    text = destination,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = "Destination Terminal",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

/**
 * Single duty metric cell (Vehicle / Next Departure / Distance).
 */
@Composable
private fun DutyMetricItem(
    icon: ImageVector,
    label: String,
    value: String,
    subtext: String
) {
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(14.dp)
            )
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                text = label,
                fontSize = 10.sp,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                letterSpacing = 0.5.sp
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = value,
            fontSize = 16.sp,
            fontWeight = FontWeight.ExtraBold,
            color = MaterialTheme.colorScheme.onSurface
        )
        Text(
            text = subtext,
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

/**
 * Dedicated Next Departure preview card.
 */
@Composable
private fun NextDepartureCard(assignment: AssignmentResponse) {
    val departureTime = remember(assignment.planned_start_at) {
        formatTimeOfDay(assignment.planned_start_at)
    }
    val (originName, destinationName, _) = remember(assignment) {
        resolveRouteStops(assignment)
    }
    val serviceCode = remember(assignment.service_code) {
        if (assignment.service_code.contains("-")) assignment.service_code.substringAfter("-")
        else assignment.service_code
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        border = CardDefaults.outlinedCardBorder()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Clock time block
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(12.dp))
                    .background(MaterialTheme.colorScheme.primaryContainer)
                    .padding(horizontal = 14.dp, vertical = 10.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = departureTime,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Black,
                    color = MaterialTheme.colorScheme.onPrimaryContainer
                )
            }

            Spacer(modifier = Modifier.width(16.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "NEXT DEPARTURE",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    letterSpacing = 0.5.sp
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = "$serviceCode · $originName → $destinationName",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = "Vehicle ${assignment.vehicle_number}",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

/**
 * Clear vehicle identity card showing assigned vehicle number, bus type, and registration.
 */
@Composable
private fun MyVehicleCard(assignment: AssignmentResponse) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        border = CardDefaults.outlinedCardBorder()
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.secondaryContainer),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.DirectionsBus,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSecondaryContainer,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = "MY VEHICLE",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface,
                        letterSpacing = 0.5.sp
                    )
                }

                // Ready status badge
                Surface(
                    color = Color(0xFFD1FAE5),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = Color(0xFF059669),
                            modifier = Modifier.size(12.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "Tracking Ready",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF059669)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = assignment.vehicle_number,
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Black,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        text = (assignment.vehicle_type ?: "Bus").lowercase().replaceFirstChar { it.uppercase() },
                        fontSize = 13.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                if (!assignment.vehicle_registration.isNullOrBlank()) {
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = RoundedCornerShape(8.dp),
                        border = CardDefaults.outlinedCardBorder()
                    ) {
                        Text(
                            text = assignment.vehicle_registration,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }
    }
}

/**
 * 3 Touch-friendly quick action cards for high-frequency operational tasks.
 */
@Composable
private fun QuickActionsRow(
    onActionClick: (String) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        QuickActionButton(
            modifier = Modifier.weight(1f),
            title = "Today's Trips",
            icon = Icons.Default.Schedule,
            onClick = { onActionClick("trips") }
        )
        QuickActionButton(
            modifier = Modifier.weight(1f),
            title = "My Route",
            icon = Icons.AutoMirrored.Filled.AltRoute,
            onClick = { onActionClick("route") }
        )
        QuickActionButton(
            modifier = Modifier.weight(1f),
            title = "My Vehicle",
            icon = Icons.Default.DirectionsBus,
            onClick = { onActionClick("vehicle") }
        )
    }
}

@Composable
private fun QuickActionButton(
    modifier: Modifier = Modifier,
    title: String,
    icon: ImageVector,
    onClick: () -> Unit
) {
    Card(
        modifier = modifier
            .height(72.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        border = CardDefaults.outlinedCardBorder()
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(22.dp)
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = title,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

/**
 * Clean, human-friendly empty state when operator has no duty scheduled.
 */
@Composable
private fun NoDutyCard(
    onCheckDuty: () -> Unit,
    isLoading: Boolean
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
        ),
        border = CardDefaults.outlinedCardBorder()
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                modifier = Modifier
                    .size(64.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.surfaceVariant),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.EventBusy,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(32.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "NO DUTY ASSIGNED",
                fontSize = 18.sp,
                fontWeight = FontWeight.ExtraBold,
                color = MaterialTheme.colorScheme.onSurface
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "You have no scheduled operating duty for today.",
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 8.dp),
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )

            Spacer(modifier = Modifier.height(24.dp))

            Button(
                onClick = onCheckDuty,
                enabled = !isLoading,
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primary
                )
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(18.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                } else {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Check for Assignments",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

/**
 * Mobile loading state card.
 */
@Composable
private fun LoadingDutyCard() {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(180.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
        )
    ) {
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            CircularProgressIndicator(
                modifier = Modifier.size(36.dp),
                strokeWidth = 3.dp,
                color = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Loading today's duty...",
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

/**
 * Friendly error banner with retry action.
 */
@Composable
private fun ErrorBanner(
    message: String,
    onRetry: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                modifier = Modifier.weight(1f),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onErrorContainer,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(10.dp))
                Text(
                    text = if (message.contains("Failed") || message.contains("connection")) "Couldn't load today's duty. Check your connection." else message,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium
                )
            }
            TextButton(
                onClick = onRetry,
                colors = ButtonDefaults.textButtonColors(
                    contentColor = MaterialTheme.colorScheme.onErrorContainer
                )
            ) {
                Text("Retry", fontWeight = FontWeight.Bold)
            }
        }
    }
}

/**
 * Informational dialog for quick action cards.
 */
@Composable
private fun QuickActionDialog(
    actionType: String,
    assignment: AssignmentResponse,
    onDismiss: () -> Unit
) {
    val (title, icon) = when (actionType) {
        "trips" -> "Today's Trips" to Icons.Default.Schedule
        "route" -> "My Route" to Icons.AutoMirrored.Filled.AltRoute
        else -> "My Vehicle" to Icons.Default.DirectionsBus
    }

    val (originName, destinationName, viaText) = remember(assignment) {
        resolveRouteStops(assignment)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        icon = {
            Icon(imageVector = icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
        },
        title = {
            Text(text = title, fontWeight = FontWeight.Bold)
        },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                when (actionType) {
                    "trips" -> {
                        DetailItem(label = "Assigned Service", value = "${assignment.service_code} (${assignment.service_name})")
                        DetailItem(label = "Planned Departure", value = formatTimeOfDay(assignment.planned_start_at))
                        DetailItem(label = "Duty Status", value = assignment.assignment_status)
                        DetailItem(label = "Direction", value = if (assignment.direction == "A_TO_B") "Outbound (A → B)" else "Inbound (B → A)")
                    }
                    "route" -> {
                        DetailItem(label = "Route Code", value = assignment.route_code)
                        DetailItem(label = "Origin Terminal", value = originName)
                        DetailItem(label = "Destination", value = destinationName)
                        if (!viaText.isNullOrBlank()) {
                            DetailItem(label = "Corridor", value = viaText)
                        }
                        if (assignment.route_distance_km != null) {
                            DetailItem(label = "Total Distance", value = "${assignment.route_distance_km} km")
                        }
                    }
                    else -> {
                        DetailItem(label = "Vehicle Number", value = assignment.vehicle_number)
                        DetailItem(label = "Registration", value = assignment.vehicle_registration ?: "Standard Fleet")
                        DetailItem(label = "Vehicle Type", value = assignment.vehicle_type ?: "City Transit Bus")
                        DetailItem(label = "Tracking Status", value = assignment.assigned_device_status ?: "Device Active")
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("Close", fontWeight = FontWeight.Bold)
            }
        }
    )
}

@Composable
private fun DetailItem(label: String, value: String) {
    Column(modifier = Modifier.padding(vertical = 4.dp)) {
        Text(text = label, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(text = value, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
    }
}

/**
 * Resolves clean origin, destination, and via corridor from assignment data.
 */
private fun resolveRouteStops(assignment: AssignmentResponse): Triple<String, String, String?> {
    // 1. If backend returned explicit terminal stop names, use them!
    if (!assignment.origin_stop_name.isNullOrBlank() && !assignment.destination_stop_name.isNullOrBlank()) {
        val via = if (assignment.route_name.contains("via", ignoreCase = true)) {
            assignment.route_name.substringAfter("via", "").trim().let { if (it.isNotBlank()) "via $it" else null }
        } else null
        return Triple(assignment.origin_stop_name.trim(), assignment.destination_stop_name.trim(), via)
    }

    // 2. Fallback parsing from route_name (e.g. "Sonarpur Station - Khariberia , via Tollygunge")
    val rawName = assignment.route_name
    val viaText = if (rawName.contains("via", ignoreCase = true)) {
        rawName.substringAfter("via", "").trim().let { if (it.isNotBlank()) "via $it" else null }
    } else null

    val endpointsPortion = rawName.substringBefore(", via").substringBefore("via").trim()
    return if (endpointsPortion.contains(" - ")) {
        val parts = endpointsPortion.split(" - ")
        val origin = parts.getOrNull(0)?.trim() ?: endpointsPortion
        val dest = parts.getOrNull(1)?.trim() ?: "Destination"
        Triple(origin, dest, viaText)
    } else {
        Triple(endpointsPortion, "Terminal", viaText)
    }
}

/**
 * Formats an ISO-8601 timestamp into a clean, human-readable 12-hour time (e.g. "06:30 AM").
 */
private fun formatTimeOfDay(isoString: String?): String {
    if (isoString.isNullOrBlank()) return "--:--"
    return try {
        if (isoString.contains("T")) {
            val timePart = isoString.substringAfter("T").substringBefore("Z").substringBefore("+").substringBefore(".")
            val parts = timePart.split(":")
            val hours = parts.getOrNull(0)?.toIntOrNull() ?: 0
            val minutes = parts.getOrNull(1)?.toIntOrNull() ?: 0
            val ampm = if (hours >= 12) "PM" else "AM"
            val displayHour = when {
                hours == 0 -> 12
                hours > 12 -> hours - 12
                else -> hours
            }
            String.format("%02d:%02d %s", displayHour, minutes, ampm)
        } else {
            isoString
        }
    } catch (e: Exception) {
        "--:--"
    }
}
