package com.transitplatform.passenger.ui.city

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.transitplatform.passenger.R
import com.transitplatform.passenger.data.model.PassengerOrganizationResponse

// ─── Brand Colors ────────────────────────────────────────────────────────
private val GoBusPrimaryBlue = Color(0xFF0B63E5)
private val GoBusDisabledBlue = Color(0xFFB4D0F8)
private val TextPrimary = Color(0xFF111827)
private val TextSecondary = Color(0xFF6B7280)
private val SelectedRowBg = Color(0xFFEFF6FF)
private val DividerColor = Color(0xFFF3F4F6)

// ─── Main Screen ────────────────────────────────────────────────────────

@Composable
fun CitySelectionScreen(
    viewModel: CitySelectionViewModel,
    onCitySelected: () -> Unit
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val searchQuery by viewModel.searchQuery.collectAsStateWithLifecycle()
    val selectedCity by viewModel.selectedCity.collectAsStateWithLifecycle()
    val filteredCities by viewModel.filteredCities.collectAsStateWithLifecycle()
    val focusManager = LocalFocusManager.current

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.White)
    ) {
        val screenHeight = maxHeight
        // Allocate approximately 38% of screen height to hero illustration (bounded for extreme screen sizes)
        val heroHeight = (screenHeight * 0.38f).coerceIn(250.dp, 360.dp)

        Column(modifier = Modifier.fillMaxSize()) {

            // ── Scrollable content (Hero + Welcome/Title + Search + Popular Cities) ──
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentPadding = PaddingValues(bottom = 8.dp)
            ) {

                // 1. High-Resolution Hero Illustration from Reference Asset
                item {
                    HeroIllustrationSection(height = heroHeight)
                }

                // 2. Welcome to GoBus + Select Your City + Subtitle
                item {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 10.dp, bottom = 4.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "Welcome to",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Medium,
                            color = TextSecondary
                        )
                        Text(
                            text = "GoBus",
                            fontSize = 26.sp,
                            fontWeight = FontWeight.Bold,
                            color = GoBusPrimaryBlue
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "Select Your City",
                            fontSize = 23.sp,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = "To get started",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Normal,
                            color = TextSecondary
                        )
                    }
                }

                // 3. Search Field
                item {
                    OutlinedTextField(
                        value = searchQuery,
                        onValueChange = viewModel::updateSearchQuery,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 20.dp, vertical = 12.dp),
                        placeholder = {
                            Text(
                                text = "Search City",
                                color = Color(0xFF9CA3AF),
                                fontSize = 14.sp
                            )
                        },
                        leadingIcon = {
                            Icon(
                                imageVector = Icons.Default.Search,
                                contentDescription = "Search",
                                tint = Color(0xFF9CA3AF),
                                modifier = Modifier.size(20.dp)
                            )
                        },
                        singleLine = true,
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = GoBusPrimaryBlue,
                            unfocusedBorderColor = Color(0xFFE5E7EB),
                            focusedContainerColor = Color.White,
                            unfocusedContainerColor = Color.White,
                            cursorColor = GoBusPrimaryBlue
                        ),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(
                            onDone = { focusManager.clearFocus() }
                        ),
                        textStyle = LocalTextStyle.current.copy(
                            fontSize = 14.sp,
                            color = TextPrimary
                        )
                    )
                }

                // 4. "Popular Cities" section label
                item {
                    Text(
                        text = "Popular Cities",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color(0xFF4B5563),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(start = 20.dp, end = 20.dp, top = 4.dp, bottom = 6.dp)
                    )
                }

                // 5. City list / states
                when (val currentState = state) {
                    is CitySelectionState.Loading -> {
                        item {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(100.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                CircularProgressIndicator(
                                    color = GoBusPrimaryBlue,
                                    strokeWidth = 2.dp,
                                    modifier = Modifier.size(28.dp)
                                )
                            }
                        }
                    }
                    is CitySelectionState.Error -> {
                        item {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 20.dp, vertical = 20.dp),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Text(
                                    text = currentState.message,
                                    color = Color(0xFFDC2626),
                                    fontSize = 14.sp
                                )
                                Spacer(modifier = Modifier.height(10.dp))
                                OutlinedButton(
                                    onClick = viewModel::loadCities,
                                    shape = RoundedCornerShape(8.dp),
                                    colors = ButtonDefaults.outlinedButtonColors(
                                        contentColor = GoBusPrimaryBlue
                                    )
                                ) {
                                    Text("Retry", fontSize = 14.sp)
                                }
                            }
                        }
                    }
                    is CitySelectionState.Success -> {
                        if (filteredCities.isEmpty() && searchQuery.isNotBlank()) {
                            item {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(70.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "No cities match \"$searchQuery\"",
                                        fontSize = 14.sp,
                                        color = TextSecondary
                                    )
                                }
                            }
                        } else {
                            items(
                                items = filteredCities,
                                key = { it.id }
                            ) { city ->
                                CityRow(
                                    city = city,
                                    isSelected = selectedCity?.id == city.id,
                                    onClick = { viewModel.selectCity(city) }
                                )
                            }
                        }
                    }
                }
            }

            // ── Bottom: Continue button ─────────────────────────────────────
            ContinueButton(
                enabled = selectedCity != null,
                onClick = { viewModel.confirmSelection(onCitySelected) }
            )
        }
    }
}

// ─── Hero Illustration Section ──────────────────────────────────────────

@Composable
private fun HeroIllustrationSection(
    height: androidx.compose.ui.unit.Dp
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(height)
    ) {
        // High-resolution hero illustration image asset
        Image(
            painter = painterResource(id = R.drawable.hero_city_illustration),
            contentDescription = "GoBus City Skyline Illustration",
            contentScale = ContentScale.Crop,
            alignment = Alignment.Center,
            modifier = Modifier.fillMaxSize()
        )

        // Subtle gradient overlay at the bottom so the roadway smoothly dissolves into pure white
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(48.dp)
                .align(Alignment.BottomCenter)
                .background(
                    Brush.verticalGradient(
                        colors = listOf(
                            Color.Transparent,
                            Color(0x33FFFFFF),
                            Color(0xBBFFFFFF),
                            Color.White
                        )
                    )
                )
        )
    }
}

// ─── City Row ───────────────────────────────────────────────────────────

@Composable
private fun CityRow(
    city: PassengerOrganizationResponse,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp, vertical = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(8.dp))
                .background(if (isSelected) SelectedRowBg else Color.Transparent)
                .clickable(onClick = onClick)
                .padding(horizontal = 14.dp, vertical = 12.dp)
                .semantics {
                    role = Role.RadioButton
                    selected = isSelected
                    contentDescription = if (isSelected) "${city.name}, selected" else city.name
                },
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = city.name,
                fontSize = 15.sp,
                fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                color = TextPrimary,
                modifier = Modifier.weight(1f)
            )
            if (isSelected) {
                // Blue circular badge with white checkmark matching Reference Image 1
                Box(
                    modifier = Modifier
                        .size(20.dp)
                        .background(GoBusPrimaryBlue, CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Check,
                        contentDescription = "Selected",
                        tint = Color.White,
                        modifier = Modifier.size(13.dp)
                    )
                }
            }
        }
        // Subtle divider below row (only when unselected to preserve pill aesthetic)
        if (!isSelected) {
            HorizontalDivider(
                modifier = Modifier.padding(horizontal = 8.dp),
                thickness = 0.5.dp,
                color = DividerColor
            )
        }
    }
}

// ─── Continue Button ────────────────────────────────────────────────────

@Composable
private fun ContinueButton(
    enabled: Boolean,
    onClick: () -> Unit
) {
    Surface(
        color = Color.White,
        shadowElevation = 2.dp
    ) {
        Button(
            onClick = onClick,
            enabled = enabled,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 12.dp)
                .navigationBarsPadding()
                .height(52.dp),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = GoBusPrimaryBlue,
                contentColor = Color.White,
                disabledContainerColor = GoBusDisabledBlue,
                disabledContentColor = Color.White
            ),
            elevation = ButtonDefaults.buttonElevation(
                defaultElevation = 0.dp,
                pressedElevation = 0.dp,
                disabledElevation = 0.dp
            )
        ) {
            Text(
                text = "Continue",
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold
            )
        }
    }
}
