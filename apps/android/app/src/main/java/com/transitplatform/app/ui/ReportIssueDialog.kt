package com.transitplatform.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog

data class IssueTypeOption(
    val code: String,
    val label: String
)

val OPERATOR_ISSUE_TYPES = listOf(
    IssueTypeOption("BREAKDOWN", "Breakdown"),
    IssueTypeOption("TRAFFIC_DELAY", "Traffic Delay"),
    IssueTypeOption("ACCIDENT", "Accident"),
    IssueTypeOption("MECHANICAL_ISSUE", "Mechanical Issue"),
    IssueTypeOption("PASSENGER_INCIDENT", "Passenger Incident"),
    IssueTypeOption("MEDICAL_EMERGENCY", "Medical Emergency"),
    IssueTypeOption("OTHER", "Other")
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReportIssueDialog(
    isSubmitting: Boolean,
    errorMessage: String? = null,
    onSubmit: (issueType: String, message: String, severity: String) -> Unit,
    onDismiss: () -> Unit
) {
    var selectedType by remember { mutableStateOf(OPERATOR_ISSUE_TYPES.first().code) }
    var selectedSeverity by remember { mutableStateOf("WARNING") }
    var messageText by remember { mutableStateOf("") }
    var validationError by remember { mutableStateOf<String?>(null) }

    Dialog(onDismissRequest = { if (!isSubmitting) onDismiss() }) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .wrapContentHeight(),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
        ) {
            Column(
                modifier = Modifier
                    .padding(20.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                // Header
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = null,
                        tint = Color(0xFFD32F2F),
                        modifier = Modifier.size(28.dp)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text(
                            text = "Report Issue",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Creates an incident alert for Admin triage",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Issue Type Selector
                Text(
                    text = "Issue Category",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(6.dp))

                // Chips for Issue Type
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    OPERATOR_ISSUE_TYPES.chunked(2).forEach { rowItems ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            rowItems.forEach { option ->
                                val isSelected = selectedType == option.code
                                FilterChip(
                                    selected = isSelected,
                                    onClick = { selectedType = option.code },
                                    label = {
                                        Text(
                                            text = option.label,
                                            fontSize = 12.sp,
                                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                                        )
                                    },
                                    modifier = Modifier.weight(1f),
                                    colors = FilterChipDefaults.filterChipColors(
                                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
                                        selectedLabelColor = MaterialTheme.colorScheme.onPrimaryContainer
                                    )
                                )
                            }
                            if (rowItems.size == 1) {
                                Spacer(modifier = Modifier.weight(1f))
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // Severity Selector
                Text(
                    text = "Severity",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    listOf(
                        "INFO" to "Info",
                        "WARNING" to "Warning",
                        "CRITICAL" to "Critical"
                    ).forEach { (sevCode, sevLabel) ->
                        val isSelected = selectedSeverity == sevCode
                        val color = when (sevCode) {
                            "CRITICAL" -> Color(0xFFC62828)
                            "WARNING" -> Color(0xFFE65100)
                            else -> Color(0xFF0277BD)
                        }
                        FilterChip(
                            selected = isSelected,
                            onClick = { selectedSeverity = sevCode },
                            label = {
                                Text(
                                    text = sevLabel,
                                    fontSize = 12.sp,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                    color = if (isSelected) color else MaterialTheme.colorScheme.onSurface
                                )
                            },
                            modifier = Modifier.weight(1f)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // Description Field
                Text(
                    text = "Description / Details",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(6.dp))
                OutlinedTextField(
                    value = messageText,
                    onValueChange = {
                        messageText = it
                        if (validationError != null) validationError = null
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(100.dp),
                    placeholder = { Text("Describe the situation briefly...", fontSize = 13.sp) },
                    enabled = !isSubmitting,
                    shape = RoundedCornerShape(10.dp)
                )

                if (validationError != null) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = validationError ?: "",
                        color = MaterialTheme.colorScheme.error,
                        fontSize = 12.sp
                    )
                }

                if (errorMessage != null) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = errorMessage,
                        color = MaterialTheme.colorScheme.error,
                        fontSize = 12.sp
                    )
                }

                Spacer(modifier = Modifier.height(20.dp))

                // Action Buttons
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f),
                        enabled = !isSubmitting,
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Text("Cancel")
                    }

                    Button(
                        onClick = {
                            val trimmed = messageText.trim()
                            if (trimmed.isEmpty()) {
                                validationError = "Please provide a short description"
                            } else {
                                onSubmit(selectedType, trimmed, selectedSeverity)
                            }
                        },
                        modifier = Modifier.weight(1f),
                        enabled = !isSubmitting,
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (selectedSeverity == "CRITICAL") Color(0xFFC62828) else Color(0xFFE65100)
                        )
                    ) {
                        if (isSubmitting) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                color = Color.White,
                                strokeWidth = 2.dp
                            )
                        } else {
                            Text("Submit", fontWeight = FontWeight.Bold, color = Color.White)
                        }
                    }
                }
            }
        }
    }
}
