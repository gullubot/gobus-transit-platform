package com.transitplatform.passenger.ui.search

import android.app.DatePickerDialog
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.ConfirmationNumber
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.transitplatform.passenger.ui.theme.*
import java.util.*

@Composable
fun NearbyBusResultsScreen(
    viewModel: NearbyBusViewModel,
    onBack: () -> Unit,
    onNavigateTab: (String) -> Unit = {},
    onServiceTap: (String) -> Unit
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current

    val calendar = remember { Calendar.getInstance() }
    val datePickerDialog = remember {
        DatePickerDialog(
            context,
            { _, year, month, dayOfMonth ->
                viewModel.setDate(year, month, dayOfMonth)
            },
            calendar.get(Calendar.YEAR),
            calendar.get(Calendar.MONTH),
            calendar.get(Calendar.DAY_OF_MONTH)
        )
    }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = {
            SearchResultsBottomBar(
                onTabClick = { route ->
                    if (route == "home_tab") {
                        onBack()
                    } else {
                        onNavigateTab(route)
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFFF8FAFC))
                .padding(bottom = paddingValues.calculateBottomPadding())
        ) {
            // =================================================================
            // 1. TOP GOBUS HEADER
            // =================================================================
            TopHeader(
                onBack = onBack
            )

            // =================================================================
            // 2. CONTENT STATES
            // =================================================================
            when (val currentState = state) {
                is NearbyBusResultsUiState.Loading -> {
                    SearchResultsSkeleton()
                }
                is NearbyBusResultsUiState.Error -> {
                    SearchResultsError(
                        message = currentState.message,
                        onRetry = viewModel::searchServices
                    )
                }
                is NearbyBusResultsUiState.Empty -> {
                    SearchResultsEmptyContent(
                        state = currentState,
                        onSwap = viewModel::swapStops,
                        onChangeDate = { datePickerDialog.show() },
                        onClearFilters = viewModel::clearFilters
                    )
                }
                is NearbyBusResultsUiState.Success -> {
                    SearchResultsContent(
                        state = currentState,
                        onSwap = viewModel::swapStops,
                        onChangeDate = { datePickerDialog.show() },
                        onFilterSelect = viewModel::setFilter,
                        onSortSelect = viewModel::setSort,
                        onServiceTap = onServiceTap,
                        onClearFilters = viewModel::clearFilters
                    )
                }
            }
        }
    }
}

// =============================================================================
// HEADER COMPONENT
// =============================================================================
@Composable
private fun TopHeader(onBack: () -> Unit) {
    Row(
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
            .padding(horizontal = 8.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        IconButton(onClick = onBack) {
            Icon(
                imageVector = Icons.Default.ArrowBack,
                contentDescription = "Back",
                tint = Color.White
            )
        }

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = "GoBus",
                style = MaterialTheme.typography.titleLarge,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
            Text(
                text = "Your City. Your Ride.",
                style = MaterialTheme.typography.bodySmall,
                fontSize = 11.sp,
                fontWeight = FontWeight.Normal,
                color = Color(0xEEFFFFFF)
            )
        }

        IconButton(onClick = { /* Notifications */ }) {
            Icon(
                imageVector = Icons.Outlined.Notifications,
                contentDescription = "Notifications",
                tint = Color.White
            )
        }
    }
}

// =============================================================================
// SEARCH RESULTS MAIN CONTENT
// =============================================================================
@Composable
private fun SearchResultsContent(
    state: NearbyBusResultsUiState.Success,
    onSwap: () -> Unit,
    onChangeDate: () -> Unit,
    onFilterSelect: (SearchFilter) -> Unit,
    onSortSelect: (SearchSort) -> Unit,
    onServiceTap: (String) -> Unit,
    onClearFilters: () -> Unit
) {
    var sortMenuExpanded by remember { mutableStateOf(false) }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // A. SEARCHED JOURNEY BANNER
        item {
            SearchedJourneyBanner(
                originName = state.currentOriginName,
                destName = state.currentDestName,
                onSwap = onSwap
            )
        }

        // B. DATE CONTROL
        item {
            DateControlRow(
                dateDisplay = state.searchDateDisplay,
                onChangeDate = onChangeDate
            )
        }

        // C. FILTER CHIPS
        item {
            FilterChipsRow(
                selectedFilter = state.selectedFilter,
                onFilterSelect = onFilterSelect
            )
        }

        // D. RESULTS COUNT & SORT DROPDOWN
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 2.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "${state.totalBusesFound} Buses Found",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF0F172A)
                )

                Box {
                    Row(
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .border(1.dp, BorderLight, RoundedCornerShape(8.dp))
                            .background(Color.White)
                            .clickable { sortMenuExpanded = true }
                            .padding(horizontal = 10.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.Sort,
                            contentDescription = "Sort",
                            tint = Color(0xFF334155),
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = state.selectedSort.label,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium,
                            color = Color(0xFF334155)
                        )
                        Spacer(modifier = Modifier.width(2.dp))
                        Icon(
                            imageVector = Icons.Default.KeyboardArrowDown,
                            contentDescription = "Sort Menu",
                            tint = Color(0xFF64748B),
                            modifier = Modifier.size(16.dp)
                        )
                    }

                    DropdownMenu(
                        expanded = sortMenuExpanded,
                        onDismissRequest = { sortMenuExpanded = false },
                        modifier = Modifier.background(Color.White)
                    ) {
                        SearchSort.values().forEach { sortOption ->
                            DropdownMenuItem(
                                text = {
                                    Text(
                                        text = sortOption.label,
                                        fontWeight = if (state.selectedSort == sortOption) FontWeight.Bold else FontWeight.Normal,
                                        color = if (state.selectedSort == sortOption) GoBusBlue else Color(0xFF1E293B)
                                    )
                                },
                                onClick = {
                                    onSortSelect(sortOption)
                                    sortMenuExpanded = false
                                }
                            )
                        }
                    }
                }
            }
        }

        // E. LIVE EN-ROUTE BANNER
        item {
            LiveEnRouteBanner(
                totalEnRoute = state.totalBusesEnRoute,
                isToday = state.isToday,
                searchDate = state.searchDateDisplay
            )
        }

        // F. RESULTS LIST
        items(
            items = state.displayedResults,
            key = { it.serviceId }
        ) { resultItem ->
            Box(modifier = Modifier.padding(horizontal = 16.dp)) {
                SearchResultCard(
                    item = resultItem,
                    onClick = { onServiceTap(resultItem.serviceId) }
                )
            }
        }
    }
}

// =============================================================================
// SEARCH RESULTS EMPTY STATE CONTENT
// =============================================================================
@Composable
private fun SearchResultsEmptyContent(
    state: NearbyBusResultsUiState.Empty,
    onSwap: () -> Unit,
    onChangeDate: () -> Unit,
    onClearFilters: () -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            SearchedJourneyBanner(
                originName = state.currentOriginName,
                destName = state.currentDestName,
                onSwap = onSwap
            )
        }

        item {
            DateControlRow(
                dateDisplay = state.searchDateDisplay,
                onChangeDate = onChangeDate
            )
        }

        item {
            val titleText = when (state.reason) {
                EmptyReason.NO_SERVICES_FOUND -> "No buses found for this journey."
                EmptyReason.NO_MORE_BUSES_TODAY -> "No more buses scheduled today."
                EmptyReason.FILTER_NO_MATCH -> "No buses match these filters."
            }
            val subText = when (state.reason) {
                EmptyReason.NO_SERVICES_FOUND -> "Try searching for a different origin or destination stop."
                EmptyReason.NO_MORE_BUSES_TODAY -> "All scheduled trips for today have concluded. Try selecting tomorrow or another date."
                EmptyReason.FILTER_NO_MATCH -> "No active buses match your filter criteria. Try adjusting or clearing filters."
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp, vertical = 40.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Box(
                        modifier = Modifier
                            .size(64.dp)
                            .clip(CircleShape)
                            .background(Color(0xFFEFF6FF)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.DirectionsBus,
                            contentDescription = null,
                            tint = GoBusBlue,
                            modifier = Modifier.size(32.dp)
                        )
                    }
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = titleText,
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF0F172A),
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = subText,
                        fontSize = 13.sp,
                        color = Color(0xFF64748B),
                        textAlign = TextAlign.Center
                    )

                    if (state.reason == EmptyReason.FILTER_NO_MATCH) {
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(
                            onClick = onClearFilters,
                            colors = ButtonDefaults.buttonColors(containerColor = GoBusBlue),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("Clear Filters", color = Color.White, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }
    }
}

// =============================================================================
// SEARCHED JOURNEY BANNER
// =============================================================================
@Composable
private fun SearchedJourneyBanner(
    originName: String,
    destName: String,
    onSwap: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 6.dp),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(1.dp, BorderLight),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Origin info
            Row(
                modifier = Modifier.weight(1f),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(14.dp)
                        .background(Color(0xFFDBEAFE), CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    Box(
                        modifier = Modifier
                            .size(7.dp)
                            .background(GoBusBlue, CircleShape)
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                Column {
                    Text(
                        text = "From",
                        fontSize = 11.sp,
                        color = Color(0xFF64748B),
                        fontWeight = FontWeight.Medium
                    )
                    Text(
                        text = originName,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF0F172A),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        text = "Kolkata",
                        fontSize = 11.sp,
                        color = Color(0xFF94A3B8)
                    )
                }
            }

            // Arrow forward
            Icon(
                imageVector = Icons.Default.ArrowForward,
                contentDescription = "To",
                tint = GoBusBlue,
                modifier = Modifier
                    .size(20.dp)
                    .padding(horizontal = 2.dp)
            )

            // Destination info
            Row(
                modifier = Modifier.weight(1f),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Spacer(modifier = Modifier.width(6.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "To",
                        fontSize = 11.sp,
                        color = Color(0xFF64748B),
                        fontWeight = FontWeight.Medium
                    )
                    Text(
                        text = destName,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF0F172A),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        text = "Kolkata",
                        fontSize = 11.sp,
                        color = Color(0xFF94A3B8)
                    )
                }
            }

            // Swap Button
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(Color(0xFFEFF6FF))
                    .border(1.dp, Color(0xFFBFDBFE), CircleShape)
                    .clickable { onSwap() },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.SwapVert,
                    contentDescription = "Swap Endpoints",
                    tint = GoBusBlue,
                    modifier = Modifier.size(20.dp)
                )
            }
        }
    }
}

// =============================================================================
// DATE CONTROL ROW
// =============================================================================
@Composable
private fun DateControlRow(
    dateDisplay: String,
    onChangeDate: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(
            modifier = Modifier
                .clip(RoundedCornerShape(8.dp))
                .border(1.dp, BorderLight, RoundedCornerShape(8.dp))
                .background(Color.White)
                .clickable { onChangeDate() }
                .padding(horizontal = 12.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icons.Default.DateRange,
                contentDescription = "Calendar",
                tint = Color(0xFF2563EB),
                modifier = Modifier.size(16.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = dateDisplay,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                color = Color(0xFF1E293B)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Icon(
                imageVector = Icons.Default.KeyboardArrowDown,
                contentDescription = "Select Date",
                tint = Color(0xFF64748B),
                modifier = Modifier.size(16.dp)
            )
        }

        Text(
            text = "Change Date",
            fontSize = 12.sp,
            fontWeight = FontWeight.SemiBold,
            color = GoBusBlue,
            modifier = Modifier
                .clip(RoundedCornerShape(6.dp))
                .clickable { onChangeDate() }
                .padding(horizontal = 8.dp, vertical = 4.dp)
        )
    }
}

// =============================================================================
// FILTER CHIPS ROW
// =============================================================================
@Composable
private fun FilterChipsRow(
    selectedFilter: SearchFilter,
    onFilterSelect: (SearchFilter) -> Unit
) {
    val scrollState = rememberScrollState()

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(scrollState)
            .padding(horizontal = 16.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        SearchFilter.values().forEach { filter ->
            val isSelected = selectedFilter == filter

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(20.dp))
                    .background(if (isSelected) GoBusBlue else Color.White)
                    .border(
                        width = 1.dp,
                        color = if (isSelected) Color.Transparent else BorderLight,
                        shape = RoundedCornerShape(20.dp)
                    )
                    .clickable { onFilterSelect(filter) }
                    .padding(horizontal = 14.dp, vertical = 7.dp)
            ) {
                Text(
                    text = filter.label,
                    fontSize = 12.sp,
                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                    color = if (isSelected) Color.White else Color(0xFF334155)
                )
            }
        }
    }
}

// =============================================================================
// LIVE EN-ROUTE BANNER
// =============================================================================
@Composable
private fun LiveEnRouteBanner(
    totalEnRoute: Int,
    isToday: Boolean,
    searchDate: String
) {
    val containerBg = if (isToday) Color(0xFFECFDF5) else Color(0xFFF1F5F9)
    val borderCol = if (isToday) Color(0xFFA7F3D0) else Color(0xFFCBD5E1)
    val iconTint = if (isToday) Color(0xFF059669) else GoBusBlue
    val primaryText = if (isToday) "$totalEnRoute buses enroute now" else "Scheduled Timetable"
    val secondaryText = if (isToday) {
        if (totalEnRoute > 0) "Live location available" else "Scheduled services running"
    } else {
        "Showing services for $searchDate"
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 2.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = containerBg),
        border = BorderStroke(1.dp, borderCol),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icons.Default.DirectionsBus,
                contentDescription = null,
                tint = iconTint,
                modifier = Modifier.size(24.dp)
            )

            Spacer(modifier = Modifier.width(10.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = primaryText,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (isToday) Color(0xFF065F46) else Color(0xFF1E293B)
                )
                Text(
                    text = secondaryText,
                    fontSize = 11.sp,
                    color = if (isToday) Color(0xFF047857) else Color(0xFF64748B)
                )
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Default.Nature,
                    contentDescription = null,
                    tint = Color(0xFF10B981),
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = "Travel Smart",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF065F46)
                    )
                    Text(
                        text = "Choose Public Transport",
                        fontSize = 9.sp,
                        color = Color(0xFF047857)
                    )
                }
            }
        }
    }
}

// =============================================================================
// SEARCH RESULT CARD
// =============================================================================
@Composable
private fun SearchResultCard(
    item: SearchResultItemUiModel,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(
            width = if (item.isBestMatch) 1.5.dp else 1.dp,
            color = if (item.isBestMatch) Color(0xFF93C5FD) else BorderLight
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp)
        ) {
            // 1. TOP ROW: Bus Icon + Service Name + Absolute Endpoints + Fare + Best Match Ribbon
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.Top
            ) {
                // Bus Icon badge
                val busIconBg = if (item.isAc) Color(0xFFDBEAFE) else Color(0xFFFEF3C7)
                val busIconTint = if (item.isAc) GoBusBlue else Color(0xFFD97706)

                Box(
                    modifier = Modifier
                        .size(38.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(busIconBg),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.DirectionsBus,
                        contentDescription = null,
                        tint = busIconTint,
                        modifier = Modifier.size(22.dp)
                    )
                }

                Spacer(modifier = Modifier.width(10.dp))

                // Service Name & Absolute Endpoints
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = item.serviceName,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF0F172A)
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = "${item.absoluteOrigin} → ${item.absoluteDestination}",
                        fontSize = 12.sp,
                        color = GoBusBlue,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )

                    Spacer(modifier = Modifier.height(6.dp))

                    // Badges Row: LIVE/Scheduled, AC/Non-AC, Direct, Ranking tag
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // LIVE badge
                        if (item.availabilityMode == AvailabilityMode.LIVE) {
                            BadgePill(text = "LIVE", bgColor = Color(0xFFDCFCE7), textColor = Color(0xFF16A34A))
                        }

                        // AC / Non-AC
                        val acBg = if (item.isAc) Color(0xFFE0F2FE) else Color(0xFFF1F5F9)
                        val acText = if (item.isAc) Color(0xFF0284C7) else Color(0xFF475569)
                        BadgePill(text = if (item.isAc) "AC" else "Non-AC", bgColor = acBg, textColor = acText)

                        // Direct
                        if (item.isDirect) {
                            BadgePill(text = "Direct", bgColor = Color(0xFFDCFCE7), textColor = Color(0xFF16A34A))
                        }

                        // Ranking tags: Best Match, Lowest Price, Quickest
                        if (item.isBestMatch) {
                            BadgePill(text = "Best Match", bgColor = Color(0xFFDCFCE7), textColor = Color(0xFF16A34A))
                        } else if (item.isLowestPrice) {
                            BadgePill(text = "Lowest Price", bgColor = Color(0xFFF3E8FF), textColor = Color(0xFF9333EA))
                        } else if (item.isQuickest) {
                            BadgePill(text = "Quickest", bgColor = Color(0xFFFFEDD5), textColor = Color(0xFFEA580C))
                        }
                    }
                }

                // Fare & Best Match Ribbon
                Column(horizontalAlignment = Alignment.End) {
                    if (item.isBestMatch) {
                        Row(
                            modifier = Modifier
                                .clip(RoundedCornerShape(6.dp))
                                .background(Color(0xFF059669))
                                .padding(horizontal = 6.dp, vertical = 2.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.Star,
                                contentDescription = null,
                                tint = Color.White,
                                modifier = Modifier.size(11.dp)
                            )
                            Spacer(modifier = Modifier.width(3.dp))
                            Text(
                                text = "Best Match",
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                        Spacer(modifier = Modifier.height(4.dp))
                    }

                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(top = 4.dp)
                    ) {
                        val fareText = if (item.fareAmount != null) "₹${item.fareAmount.toInt()}" else "--"
                        Text(
                            text = fareText,
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Bold,
                            color = GoBusBlue
                        )
                        Icon(
                            imageVector = Icons.Default.ChevronRight,
                            contentDescription = "Details",
                            tint = Color(0xFF94A3B8),
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // 2. MIDDLE ROW: DEPARTURE - DURATION / STOPS - ARRIVAL
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Departure
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = item.departureLabel,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        color = if (item.availabilityMode == AvailabilityMode.LIVE) Color(0xFF16A34A) else Color(0xFF64748B)
                    )
                    Text(
                        text = item.departureTimeFormatted,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF0F172A)
                    )
                    Text(
                        text = item.searchedOrigin,
                        fontSize = 11.sp,
                        color = Color(0xFF64748B),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                // Dotted timeline
                Column(
                    modifier = Modifier.weight(1.2f),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "${item.durationMinutes} min",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        color = Color(0xFF64748B)
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .background(GoBusBlue, CircleShape)
                        )
                        HorizontalDivider(
                            modifier = Modifier.weight(1f),
                            thickness = 1.5.dp,
                            color = Color(0xFFCBD5E1)
                        )
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .background(GoBusBlue, CircleShape)
                        )
                    }
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = "${item.stopsCount} stops",
                        fontSize = 10.sp,
                        color = Color(0xFF94A3B8)
                    )
                }

                // Arrival
                Column(
                    modifier = Modifier.weight(1f),
                    horizontalAlignment = Alignment.End
                ) {
                    Text(
                        text = item.arrivalLabel,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        color = Color(0xFF64748B)
                    )
                    Text(
                        text = item.arrivalTimeFormatted,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF0F172A)
                    )
                    Text(
                        text = item.searchedDestination,
                        fontSize = 11.sp,
                        color = Color(0xFF64748B),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 3. BOTTOM SPLIT STATUS BOX: CROWD & EN ROUTE INFO
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(Color(0xFFF8FAFC))
                    .border(1.dp, Color(0xFFF1F5F9), RoundedCornerShape(10.dp))
                    .padding(horizontal = 10.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Left: Crowd
                val crowdColor = when (item.crowdLevel) {
                    "Low Crowd" -> Color(0xFF10B981)
                    "Medium Crowd" -> Color(0xFFF59E0B)
                    "High Crowd" -> Color(0xFFEF4444)
                    else -> Color(0xFF10B981)
                }

                Row(
                    modifier = Modifier.weight(1f),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.People,
                        contentDescription = null,
                        tint = crowdColor,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = item.crowdLevel ?: "Low Crowd",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = Color(0xFF1E293B)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Icon(
                                imageVector = Icons.Default.Info,
                                contentDescription = "Crowd Info",
                                tint = Color(0xFF94A3B8),
                                modifier = Modifier.size(12.dp)
                            )
                        }
                        Text(
                            text = "Based on live data",
                            fontSize = 9.sp,
                            color = Color(0xFF64748B)
                        )
                    }
                }

                // Vertical Divider
                Box(
                    modifier = Modifier
                        .height(26.dp)
                        .width(1.dp)
                        .background(Color(0xFFE2E8F0))
                )

                // Right: En Route & Next ETA
                Row(
                    modifier = Modifier
                        .weight(1f)
                        .padding(start = 10.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = Icons.Default.DirectionsBus,
                        contentDescription = null,
                        tint = GoBusBlue,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "${item.activeBusesCount} buses enroute",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = Color(0xFF1E293B)
                        )
                        Text(
                            text = item.relativeMessage ?: if (item.nearestBusEtaMinutes != null) "Next in ${item.nearestBusEtaMinutes} min" else "Scheduled service",
                            fontSize = 9.sp,
                            color = Color(0xFF64748B)
                        )
                    }
                    Icon(
                        imageVector = Icons.Default.ChevronRight,
                        contentDescription = null,
                        tint = Color(0xFF94A3B8),
                        modifier = Modifier.size(16.dp)
                    )
                }
            }
        }
    }
}

// =============================================================================
// BADGE PILL HELPER
// =============================================================================
@Composable
private fun BadgePill(
    text: String,
    bgColor: Color,
    textColor: Color
) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(6.dp))
            .background(bgColor)
            .padding(horizontal = 7.dp, vertical = 2.dp)
    ) {
        Text(
            text = text,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            color = textColor
        )
    }
}

// =============================================================================
// FIXED BOTTOM NAVIGATION BAR
// =============================================================================
@Composable
private fun SearchResultsBottomBar(
    onTabClick: (String) -> Unit
) {
    NavigationBar(
        containerColor = Color.White,
        tonalElevation = 8.dp,
        modifier = Modifier.border(width = 1.dp, color = BorderLight)
    ) {
        NavigationBarItem(
            icon = {
                Icon(
                    imageVector = Icons.Filled.Home,
                    contentDescription = "Home",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = {
                Text(
                    text = "Home",
                    style = MaterialTheme.typography.labelSmall,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold
                )
            },
            selected = true,
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = GoBusBlue,
                selectedTextColor = GoBusBlue,
                indicatorColor = GoBusBlueLight,
                unselectedIconColor = TextMuted,
                unselectedTextColor = TextMuted
            ),
            onClick = { onTabClick("home_tab") }
        )

        NavigationBarItem(
            icon = {
                Icon(
                    imageVector = Icons.Outlined.Schedule,
                    contentDescription = "History",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = {
                Text(
                    text = "History",
                    style = MaterialTheme.typography.labelSmall,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium
                )
            },
            selected = false,
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = GoBusBlue,
                selectedTextColor = GoBusBlue,
                indicatorColor = GoBusBlueLight,
                unselectedIconColor = TextMuted,
                unselectedTextColor = TextMuted
            ),
            onClick = { onTabClick("history_tab") }
        )

        NavigationBarItem(
            icon = {
                Icon(
                    imageVector = Icons.Outlined.ConfirmationNumber,
                    contentDescription = "My Trips",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = {
                Text(
                    text = "My Trips",
                    style = MaterialTheme.typography.labelSmall,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium
                )
            },
            selected = false,
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = GoBusBlue,
                selectedTextColor = GoBusBlue,
                indicatorColor = GoBusBlueLight,
                unselectedIconColor = TextMuted,
                unselectedTextColor = TextMuted
            ),
            onClick = { onTabClick("my_trips_tab") }
        )

        NavigationBarItem(
            icon = {
                Icon(
                    imageVector = Icons.Default.Menu,
                    contentDescription = "More",
                    modifier = Modifier.size(24.dp)
                )
            },
            label = {
                Text(
                    text = "More",
                    style = MaterialTheme.typography.labelSmall,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium
                )
            },
            selected = false,
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = GoBusBlue,
                selectedTextColor = GoBusBlue,
                indicatorColor = GoBusBlueLight,
                unselectedIconColor = TextMuted,
                unselectedTextColor = TextMuted
            ),
            onClick = { onTabClick("more_tab") }
        )
    }
}

// =============================================================================
// SKELETON LOADING STATE
// =============================================================================
@Composable
private fun SearchResultsSkeleton() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        CircularProgressIndicator(
            color = GoBusBlue,
            strokeWidth = 3.dp,
            modifier = Modifier.size(36.dp)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Searching available buses...",
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium,
            color = Color(0xFF64748B)
        )
    }
}

// =============================================================================
// ERROR STATE
// =============================================================================
@Composable
private fun SearchResultsError(
    message: String,
    onRetry: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                imageVector = Icons.Default.Warning,
                contentDescription = null,
                tint = Color(0xFFDC2626),
                modifier = Modifier.size(40.dp)
            )
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = message,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium,
                color = Color(0xFF1E293B),
                modifier = Modifier.padding(horizontal = 16.dp)
            )
            Spacer(modifier = Modifier.height(16.dp))
            Button(
                onClick = onRetry,
                colors = ButtonDefaults.buttonColors(containerColor = GoBusBlue)
            ) {
                Text("Retry")
            }
        }
    }
}
