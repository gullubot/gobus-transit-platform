package com.transitplatform.passenger.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.transitplatform.passenger.data.model.PassengerStopResponse
import com.transitplatform.passenger.ui.components.SwapArrowsIcon
import com.transitplatform.passenger.ui.theme.BorderLight
import com.transitplatform.passenger.ui.theme.GoBusBlue
import com.transitplatform.passenger.ui.theme.GoBusBlueLight
import com.transitplatform.passenger.ui.theme.TextMuted
import com.transitplatform.passenger.ui.theme.TextPrimary
import com.transitplatform.passenger.ui.theme.TextSecondary

@Composable
fun TripSearchCard(
    origin: PassengerStopResponse?,
    destination: PassengerStopResponse?,
    onSwap: () -> Unit,
    onSearchBuses: () -> Unit,
    onEditOrigin: () -> Unit,
    onEditDestination: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .shadow(
                elevation = 6.dp,
                shape = RoundedCornerShape(20.dp),
                spotColor = Color(0x1A000000),
                ambientColor = Color(0x10000000)
            ),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 18.dp)
        ) {
            // 1. Search Prompt Bar ("Where do you want to go?")
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp)
                    .border(1.dp, BorderLight, RoundedCornerShape(12.dp))
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color.White)
                    .clickable { onEditDestination() }
                    .padding(horizontal = 14.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Search,
                    contentDescription = null,
                    tint = Color(0xFF6B7280),
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(10.dp))
                Text(
                    text = "Where do you want to go?",
                    style = MaterialTheme.typography.bodyMedium,
                    fontSize = 15.sp,
                    color = Color(0xFF6B7280),
                    modifier = Modifier.weight(1f)
                )
                VerticalDivider(
                    modifier = Modifier.height(20.dp),
                    color = BorderLight
                )
                Spacer(modifier = Modifier.width(10.dp))
                Icon(
                    imageVector = Icons.Default.Mic,
                    contentDescription = "Voice Search",
                    tint = GoBusBlue,
                    modifier = Modifier.size(20.dp)
                )
            }

            Spacer(modifier = Modifier.height(18.dp))

            // 2. From / To Routing Block with Connector and Swap Button
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Left Route Visual Indicator (Solid Dot -> Line -> Hollow Dot)
                Column(
                    modifier = Modifier.width(16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    // Origin Dot (Solid Blue)
                    Box(
                        modifier = Modifier
                            .size(12.dp)
                            .clip(CircleShape)
                            .background(GoBusBlue)
                    )
                    // Vertical Connector
                    Box(
                        modifier = Modifier
                            .width(2.dp)
                            .height(38.dp)
                            .background(Color(0xFFCBD5E1))
                    )
                    // Destination Dot (Hollow Circle)
                    Box(
                        modifier = Modifier
                            .size(12.dp)
                            .border(2.5.dp, GoBusBlue, CircleShape)
                    )
                }

                Spacer(modifier = Modifier.width(12.dp))

                // Middle Text Columns (From / To)
                Column(
                    modifier = Modifier.weight(1f)
                ) {
                    // FROM Section
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onEditOrigin() }
                            .padding(vertical = 2.dp)
                    ) {
                        Text(
                            text = "From",
                            style = MaterialTheme.typography.labelMedium,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium,
                            color = TextSecondary
                        )
                        Text(
                            text = origin?.name ?: "Your Location",
                            style = MaterialTheme.typography.titleMedium,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = TextPrimary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text(
                            text = if (origin != null) (if (origin.stop_code.isNotBlank()) "Code: ${origin.stop_code}" else "Selected stop") else "Nearest stop or area",
                            style = MaterialTheme.typography.bodySmall,
                            fontSize = 11.sp,
                            color = TextMuted,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    // TO Section
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onEditDestination() }
                            .padding(vertical = 2.dp)
                    ) {
                        Text(
                            text = "To",
                            style = MaterialTheme.typography.labelMedium,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium,
                            color = TextSecondary
                        )
                        Text(
                            text = destination?.name ?: "Select Destination",
                            style = MaterialTheme.typography.titleMedium,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = TextPrimary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text(
                            text = if (destination != null) (if (destination.stop_code.isNotBlank()) "Code: ${destination.stop_code}" else "Selected stop") else "Bus stop, area or landmark",
                            style = MaterialTheme.typography.bodySmall,
                            fontSize = 11.sp,
                            color = TextMuted,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }

                Spacer(modifier = Modifier.width(10.dp))

                // Right Swap Button
                IconButton(
                    onClick = onSwap,
                    modifier = Modifier
                        .size(42.dp)
                        .clip(CircleShape)
                        .background(GoBusBlueLight)
                ) {
                    SwapArrowsIcon(
                        modifier = Modifier.size(20.dp),
                        tint = GoBusBlue
                    )
                }
            }

            Spacer(modifier = Modifier.height(18.dp))

            // 3. "Search Buses" CTA Button
            Button(
                onClick = onSearchBuses,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(50.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = GoBusBlue,
                    contentColor = Color.White
                ),
                elevation = ButtonDefaults.buttonElevation(defaultElevation = 2.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Search,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                    tint = Color.White
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Search Buses",
                    style = MaterialTheme.typography.titleMedium,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
            }
        }
    }
}
