package com.transitplatform.passenger.ui.plan

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.SwapVert
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlanTripScreen(
    viewModel: PlanTripViewModel,
    onBack: () -> Unit,
    onNavigateToResults: () -> Unit
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current

    var showSearchSheet by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }
    var editingOrigin by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }

    val canSearch = state.origin != null && state.destination != null
    
    // Automatically navigate to results when data is ready
    LaunchedEffect(state.results, state.error) {
        if (state.results != null || state.error != null) {
            onNavigateToResults()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Plan Trip") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    navigationIconContentColor = MaterialTheme.colorScheme.onPrimary
                )
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp)
        ) {
            // Stops
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    // Origin
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                editingOrigin = true
                                showSearchSheet = true
                            }
                            .padding(vertical = 8.dp)
                    ) {
                        Icon(Icons.Default.LocationOn, contentDescription = "Origin", tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.width(16.dp))
                        Text(
                            text = state.origin?.name ?: "Select Origin",
                            style = MaterialTheme.typography.titleMedium,
                            color = if (state.origin == null) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        HorizontalDivider(modifier = Modifier.weight(1f).padding(start = 40.dp, end = 16.dp))
                        IconButton(onClick = { viewModel.swapStops() }) {
                            Icon(Icons.Default.SwapVert, contentDescription = "Swap")
                        }
                    }

                    // Destination
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                editingOrigin = false
                                showSearchSheet = true
                            }
                            .padding(vertical = 8.dp)
                    ) {
                        Icon(Icons.Default.LocationOn, contentDescription = "Destination", tint = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.width(16.dp))
                        Text(
                            text = state.destination?.name ?: "Select Destination",
                            style = MaterialTheme.typography.titleMedium,
                            color = if (state.destination == null) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface
                        )
                    }
                }
            }
            
            Spacer(modifier = Modifier.height(24.dp))

            // Date and Time
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                // Date Picker
                val dateFormat = SimpleDateFormat("MMM dd, yyyy", Locale.US)
                val dateDisplay = dateFormat.format(state.selectedDate)
                
                Card(
                    modifier = Modifier.weight(1f).clickable {
                        val cal = Calendar.getInstance()
                        cal.time = state.selectedDate
                        DatePickerDialog(
                            context,
                            { _, year, month, dayOfMonth ->
                                val selectedCal = Calendar.getInstance()
                                selectedCal.set(year, month, dayOfMonth)
                                viewModel.setDate(selectedCal.time)
                            },
                            cal.get(Calendar.YEAR),
                            cal.get(Calendar.MONTH),
                            cal.get(Calendar.DAY_OF_MONTH)
                        ).apply {
                            datePicker.minDate = System.currentTimeMillis() - 1000
                        }.show()
                    },
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.CalendarToday, contentDescription = "Date", tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(text = dateDisplay, style = MaterialTheme.typography.bodyLarge)
                    }
                }

                // Time Picker
                Card(
                    modifier = Modifier.weight(1f).clickable {
                        val parts = state.selectedTime.split(":")
                        val currentHour = parts.getOrNull(0)?.toIntOrNull() ?: 12
                        val currentMinute = parts.getOrNull(1)?.toIntOrNull() ?: 0

                        TimePickerDialog(
                            context,
                            { _, hourOfDay, minute ->
                                viewModel.setTime(hourOfDay, minute)
                            },
                            currentHour,
                            currentMinute,
                            false
                        ).show()
                    },
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Schedule, contentDescription = "Time", tint = MaterialTheme.colorScheme.primary)
                        Spacer(modifier = Modifier.width(12.dp))
                        
                        // Format display time for UI (AM/PM)
                        val parts = state.selectedTime.split(":")
                        val displayHour = parts.getOrNull(0)?.toIntOrNull() ?: 12
                        val displayMin = parts.getOrNull(1)?.toIntOrNull() ?: 0
                        
                        val cal = Calendar.getInstance()
                        cal.set(Calendar.HOUR_OF_DAY, displayHour)
                        cal.set(Calendar.MINUTE, displayMin)
                        val timeDisplayFormat = SimpleDateFormat("hh:mm a", Locale.US)
                        
                        Text(text = timeDisplayFormat.format(cal.time), style = MaterialTheme.typography.bodyLarge)
                    }
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            if (state.error != null) {
                Text(
                    text = state.error!!,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.align(Alignment.CenterHorizontally).padding(bottom = 16.dp)
                )
            }

            Button(
                onClick = { viewModel.planTrip() },
                enabled = canSearch && !state.isLoading,
                modifier = Modifier.fillMaxWidth().height(56.dp),
                shape = RoundedCornerShape(16.dp)
            ) {
                if (state.isLoading) {
                    CircularProgressIndicator(modifier = Modifier.size(24.dp), color = MaterialTheme.colorScheme.onPrimary)
                } else {
                    Text("Find Trips", style = MaterialTheme.typography.titleMedium)
                }
            }
        }
    }

    if (showSearchSheet) {
        ModalBottomSheet(
            onDismissRequest = { showSearchSheet = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = MaterialTheme.colorScheme.surface
        ) {
            StopSelectionSheet(
                viewModel = viewModel,
                isOrigin = editingOrigin,
                onDismiss = { showSearchSheet = false }
            )
        }
    }
}
