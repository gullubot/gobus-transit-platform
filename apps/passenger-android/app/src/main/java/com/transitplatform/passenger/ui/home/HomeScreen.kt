package com.transitplatform.passenger.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.DirectionsBus
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.transitplatform.passenger.R
import com.transitplatform.passenger.data.model.PassengerStopResponse
import com.transitplatform.passenger.ui.components.DepotIcon
import com.transitplatform.passenger.ui.components.EcoLeafIcon
import com.transitplatform.passenger.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    viewModel: HomeViewModel,
    onLogout: () -> Unit,
    onChangeCity: () -> Unit,
    onSearchNearby: (PassengerStopResponse, PassengerStopResponse) -> Unit,
    onSearchService: () -> Unit,
    onPlanTrip: () -> Unit = {}
) {
    val selectedCityName by viewModel.selectedCityName.collectAsStateWithLifecycle()
    val destinationStop by viewModel.destinationStop.collectAsStateWithLifecycle()
    val originStop by viewModel.originStop.collectAsStateWithLifecycle()
    val depots by viewModel.depots.collectAsStateWithLifecycle()

    var showSearchSheet by remember { mutableStateOf(false) }
    var editingOrigin by remember { mutableStateOf(false) }

    // Location Permission Launcher
    val locationPermissionLauncher = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val granted = permissions.entries.any { it.value }
        if (granted) {
            viewModel.resolveNearestStop()
        } else {
            viewModel.clearOrigin()
        }
    }

    LaunchedEffect(destinationStop) {
        if (destinationStop != null && originStop == null) {
            locationPermissionLauncher.launch(
                arrayOf(
                    android.Manifest.permission.ACCESS_FINE_LOCATION,
                    android.Manifest.permission.ACCESS_COARSE_LOCATION
                )
            )
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BgPage)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
        ) {
            // =================================================================
            // 1 & 2: HEADER + CITY SELECTOR (GoBus Blue container)
            // =================================================================
            // =================================================================
            // 1 & 2: COMPACT HEADER + CITY SELECTOR (GoBus Blue container)
            // =================================================================
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        Brush.verticalGradient(
                            colors = listOf(
                                GoBusBlue,
                                Color(0xFF2563EB)
                            )
                        )
                    )
                    .statusBarsPadding()
                    .padding(start = 18.dp, end = 18.dp, top = 2.dp, bottom = 2.dp)
            ) {
                // Header Bar: "GoBus" + Subtitle + Notification Bell
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "GoBus",
                            style = MaterialTheme.typography.headlineMedium,
                            fontSize = 24.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Spacer(modifier = Modifier.height(1.dp))
                        Text(
                            text = "Your City. Your Ride.",
                            style = MaterialTheme.typography.bodySmall,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Normal,
                            color = Color(0xEEFFFFFF)
                        )
                    }

                    IconButton(
                        onClick = { /* Notification action */ },
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Outlined.Notifications,
                            contentDescription = "Notifications",
                            tint = Color.White,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(4.dp))

                // City Selector Pill: 📍 [City Name] ▼
                Row(
                    modifier = Modifier
                        .clip(RoundedCornerShape(20.dp))
                        .background(Color(0x33FFFFFF))
                        .border(1.dp, Color(0x55FFFFFF), RoundedCornerShape(20.dp))
                        .clickable { onChangeCity() }
                        .padding(horizontal = 12.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.Place,
                        contentDescription = "City Location",
                        tint = Color.White,
                        modifier = Modifier.size(15.dp)
                    )
                    Spacer(modifier = Modifier.width(5.dp))
                    Text(
                        text = selectedCityName ?: "Select City",
                        style = MaterialTheme.typography.labelLarge,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.width(3.dp))
                    Icon(
                        imageVector = Icons.Default.KeyboardArrowDown,
                        contentDescription = "Select City Dropdown",
                        tint = Color.White,
                        modifier = Modifier.size(16.dp)
                    )
                }
            }

            // =================================================================
            // 3: COMPACT HERO ARTWORK (Reference 3 Asset)
            // =================================================================
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(2.05f)
                    .clipToBounds()
                    .background(Color(0xFFBAE6FD))
            ) {
                Image(
                    painter = painterResource(id = R.drawable.hero_city_illustration),
                    contentDescription = "GoBus City Skyline",
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(16f / 9f),
                    contentScale = ContentScale.FillWidth,
                    alignment = Alignment.BottomCenter
                )

                // Eco Tagline: "Better Journeys / A Greener Tomorrow" + leaf (inside hero upper-right)
                Row(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(top = 6.dp, end = 16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            text = "Better Journeys",
                            style = MaterialTheme.typography.labelSmall,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF1E3A8A)
                        )
                        Text(
                            text = "A Greener Tomorrow",
                            style = MaterialTheme.typography.labelSmall,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Normal,
                            color = Color(0xFF1E3A8A).copy(alpha = 0.85f)
                        )
                    }
                    Spacer(modifier = Modifier.width(5.dp))
                    EcoLeafIcon(
                        modifier = Modifier.size(20.dp),
                        tint = EcoGreen
                    )
                }
            }

            // =================================================================
            // 4 & 5: MAIN TRIP SEARCH CARD (Slight bottom-edge overlap)
            // =================================================================
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .offset(y = (-10).dp)
                    .padding(horizontal = 16.dp)
            ) {
                TripSearchCard(
                    origin = originStop,
                    destination = destinationStop,
                    onSwap = viewModel::swapStops,
                    onSearchBuses = {
                        val origin = originStop
                        val destination = destinationStop
                        if (origin != null && destination != null) {
                            onSearchNearby(origin, destination)
                        } else if (destination == null) {
                            editingOrigin = false
                            showSearchSheet = true
                        } else {
                            viewModel.resolveNearestStop()
                            editingOrigin = true
                            showSearchSheet = true
                        }
                    },
                    onEditOrigin = {
                        editingOrigin = true
                        showSearchSheet = true
                    },
                    onEditDestination = {
                        editingOrigin = false
                        showSearchSheet = true
                    }
                )
            }

            Spacer(modifier = Modifier.height(4.dp))

            // =================================================================
            // 6: TWO QUICK ACTION CARDS
            // =================================================================
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // LEFT: Search Bus / Service
                Card(
                    modifier = Modifier
                        .weight(1f)
                        .clickable { onSearchService() },
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    border = BorderStroke(1.dp, BorderLight),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(38.dp)
                                .clip(RoundedCornerShape(10.dp))
                                .background(GoBusBlueLight),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.DirectionsBus,
                                contentDescription = null,
                                tint = GoBusBlue,
                                modifier = Modifier.size(22.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(10.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "Search Bus /",
                                style = MaterialTheme.typography.bodySmall,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary
                            )
                            Text(
                                text = "Service",
                                style = MaterialTheme.typography.bodySmall,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary
                            )
                        }
                        Icon(
                            imageVector = Icons.Default.ChevronRight,
                            contentDescription = null,
                            tint = TextMuted,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }

                // RIGHT: Plan Trip (Date & Time)
                Card(
                    modifier = Modifier
                        .weight(1f)
                        .clickable { onPlanTrip() },
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    border = BorderStroke(1.dp, BorderLight),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(38.dp)
                                .clip(RoundedCornerShape(10.dp))
                                .background(AlertRedLight),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.CalendarToday,
                                contentDescription = null,
                                tint = AlertRed,
                                modifier = Modifier.size(20.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(10.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "Plan Trip",
                                style = MaterialTheme.typography.bodySmall,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary
                            )
                            Text(
                                text = "(Date & Time)",
                                style = MaterialTheme.typography.labelSmall,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium,
                                color = TextSecondary
                            )
                        }
                        Icon(
                            imageVector = Icons.Default.ChevronRight,
                            contentDescription = null,
                            tint = TextMuted,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(18.dp))

            // =================================================================
            // 7: MAJOR DEPOTS (Authoritative Data)
            // =================================================================
            Column(
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Major Depots",
                        style = MaterialTheme.typography.titleMedium,
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                    Text(
                        text = "View All",
                        style = MaterialTheme.typography.labelLarge,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = GoBusBlue,
                        modifier = Modifier.clickable {
                            editingOrigin = false
                            showSearchSheet = true
                        }
                    )
                }

                // Horizontal LazyRow of compact depot cards
                if (depots.isNotEmpty()) {
                    LazyRow(
                        modifier = Modifier.fillMaxWidth(),
                        contentPadding = PaddingValues(horizontal = 16.dp),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(depots) { depot ->
                            Card(
                                modifier = Modifier.clickable {
                                    viewModel.selectDepot(depot)
                                },
                                shape = RoundedCornerShape(14.dp),
                                colors = CardDefaults.cardColors(containerColor = Color.White),
                                border = BorderStroke(1.dp, BorderLight),
                                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .size(38.dp)
                                            .clip(RoundedCornerShape(10.dp))
                                            .background(GoBusBlueLight),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        DepotIcon(
                                            modifier = Modifier.size(20.dp),
                                            tint = GoBusBlue
                                        )
                                    }
                                    Spacer(modifier = Modifier.width(10.dp))
                                    Column {
                                        Text(
                                            text = depot.name,
                                            style = MaterialTheme.typography.bodyMedium,
                                            fontSize = 13.sp,
                                            fontWeight = FontWeight.SemiBold,
                                            color = TextPrimary,
                                            maxLines = 1
                                        )
                                        Text(
                                            text = "${depot.serviceCount} Services",
                                            style = MaterialTheme.typography.bodySmall,
                                            fontSize = 11.sp,
                                            color = TextSecondary
                                        )
                                    }
                                }
                            }
                        }
                    }
                } else {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp)
                            .height(56.dp)
                            .border(1.dp, BorderLight, RoundedCornerShape(14.dp)),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "Loading transit terminals...",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextMuted
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // =================================================================
            // 8: TRAVEL SMART BANNER
            // =================================================================
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
            ) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = EcoGreenBg),
                    border = BorderStroke(1.dp, EcoGreenLight),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        EcoLeafIcon(
                            modifier = Modifier.size(30.dp),
                            tint = EcoGreen
                        )
                        Spacer(modifier = Modifier.width(14.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "Travel Smart",
                                style = MaterialTheme.typography.titleSmall,
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold,
                                color = EcoGreenDark
                            )
                            Text(
                                text = "Choose Public Transport",
                                style = MaterialTheme.typography.bodySmall,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Medium,
                                color = EcoGreenMedium
                            )
                        }
                    }
                }
            }

            // Bottom buffer so fixed navigation does not overlap
            Spacer(modifier = Modifier.height(28.dp))
        }
    }

    // Modal Bottom Sheet for Destination / Origin Search
    if (showSearchSheet) {
        ModalBottomSheet(
            onDismissRequest = { showSearchSheet = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = MaterialTheme.colorScheme.surface
        ) {
            DestinationSearchSheet(
                viewModel = viewModel,
                isOrigin = editingOrigin,
                onDismiss = { showSearchSheet = false }
            )
        }
    }
}
