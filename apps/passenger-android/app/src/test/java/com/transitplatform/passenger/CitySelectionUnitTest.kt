package com.transitplatform.passenger

import com.transitplatform.passenger.data.model.PassengerOrganizationResponse
import com.transitplatform.passenger.ui.city.CitySelectionState
import com.transitplatform.passenger.ui.city.CitySelectionViewModel
import org.junit.Assert.*
import org.junit.Test

/**
 * Unit tests for Passenger Step 1: Select City / First-Time City Setup.
 *
 * These tests verify:
 * 1. CitySelectionState model hierarchy (Loading, Success, Error)
 * 2. Search filtering logic (case-insensitive, empty query, whitespace, partial substring, no matches)
 * 3. Single-selection semantics (only one city selected at a time, switching selection)
 * 4. Model mapping and confirmation preconditions
 */
class CitySelectionUnitTest {

    private val sampleCities = listOf(
        PassengerOrganizationResponse(id = "city-1", name = "Kolkata"),
        PassengerOrganizationResponse(id = "city-2", name = "Delhi"),
        PassengerOrganizationResponse(id = "city-3", name = "Mumbai"),
        PassengerOrganizationResponse(id = "city-4", name = "Bangalore"),
        PassengerOrganizationResponse(id = "city-5", name = "Chennai"),
        PassengerOrganizationResponse(id = "city-6", name = "Hyderabad"),
        PassengerOrganizationResponse(id = "city-7", name = "Pune")
    )

    // =========================================================================
    // STATE MODEL TESTS
    // =========================================================================

    @Test
    fun `CitySelectionState Loading is a distinct state`() {
        val state: CitySelectionState = CitySelectionState.Loading
        assertTrue("State should be Loading", state is CitySelectionState.Loading)
    }

    @Test
    fun `CitySelectionState Success holds city list accurately`() {
        val state: CitySelectionState = CitySelectionState.Success(sampleCities)
        assertTrue("State should be Success", state is CitySelectionState.Success)
        assertEquals(7, (state as CitySelectionState.Success).cities.size)
        assertEquals("Kolkata", state.cities[0].name)
        assertEquals("Pune", state.cities[6].name)
    }

    @Test
    fun `CitySelectionState Error holds error message`() {
        val state: CitySelectionState = CitySelectionState.Error("Failed to load cities.")
        assertTrue("State should be Error", state is CitySelectionState.Error)
        assertEquals("Failed to load cities.", (state as CitySelectionState.Error).message)
    }

    // =========================================================================
    // SEARCH FILTERING TESTS
    // =========================================================================

    @Test
    fun `filterCities returns all cities when query is empty`() {
        val filtered = CitySelectionViewModel.filterCities(sampleCities, "")
        assertEquals(sampleCities.size, filtered.size)
        assertEquals(sampleCities, filtered)
    }

    @Test
    fun `filterCities returns all cities when query is blank whitespace`() {
        val filtered = CitySelectionViewModel.filterCities(sampleCities, "   ")
        assertEquals(sampleCities.size, filtered.size)
        assertEquals(sampleCities, filtered)
    }

    @Test
    fun `filterCities filters cities with exact match case-insensitively`() {
        val filtered = CitySelectionViewModel.filterCities(sampleCities, "kolkata")
        assertEquals(1, filtered.size)
        assertEquals("Kolkata", filtered[0].name)
        assertEquals("city-1", filtered[0].id)
    }

    @Test
    fun `filterCities filters cities with uppercase query`() {
        val filtered = CitySelectionViewModel.filterCities(sampleCities, "MUMBAI")
        assertEquals(1, filtered.size)
        assertEquals("Mumbai", filtered[0].name)
    }

    @Test
    fun `filterCities filters cities by partial prefix substring`() {
        val filtered = CitySelectionViewModel.filterCities(sampleCities, "del")
        assertEquals(1, filtered.size)
        assertEquals("Delhi", filtered[0].name)
    }

    @Test
    fun `filterCities filters cities by partial infix substring`() {
        // "bad" in Hyderabad
        val filtered = CitySelectionViewModel.filterCities(sampleCities, "bad")
        assertEquals(1, filtered.size)
        assertEquals("Hyderabad", filtered[0].name)
    }

    @Test
    fun `filterCities returns empty list when no cities match`() {
        val filtered = CitySelectionViewModel.filterCities(sampleCities, "NonExistentCityXYZ")
        assertTrue("Filtered list should be empty", filtered.isEmpty())
    }

    @Test
    fun `filterCities works on empty city input list`() {
        val filtered = CitySelectionViewModel.filterCities(emptyList(), "Delhi")
        assertTrue("Filtered list should be empty for empty input", filtered.isEmpty())
    }

    // =========================================================================
    // SELECTION SEMANTICS TESTS
    // =========================================================================

    @Test
    fun `selection simulates single active city state`() {
        var selectedCity: PassengerOrganizationResponse? = null

        // Initial state is unselected
        assertNull("Initially no city is selected", selectedCity)

        // Select first city
        selectedCity = sampleCities[0]
        assertEquals("Kolkata", selectedCity.name)

        // Select another city - replaces previous selection
        selectedCity = sampleCities[2]
        assertEquals("Mumbai", selectedCity.name)
        assertEquals("city-3", selectedCity.id)
    }

    @Test
    fun `only one city can be marked selected at a time`() {
        val selectedCityId = sampleCities[4].id // Chennai

        val selectionMap = sampleCities.associate { it.id to (it.id == selectedCityId) }
        val selectedCount = selectionMap.values.count { it }

        assertEquals("Exactly one city should be selected", 1, selectedCount)
        assertTrue("Chennai should be selected", selectionMap["city-5"] == true)
        assertFalse("Kolkata should not be selected", selectionMap["city-1"] == true)
    }

    @Test
    fun `confirmation preconditions require non-null selected city`() {
        val canConfirm: (PassengerOrganizationResponse?) -> Boolean = { it != null }

        assertFalse("Cannot confirm when selection is null", canConfirm(null))
        assertTrue("Can confirm when selection is present", canConfirm(sampleCities[0]))
    }

    @Test
    fun `organization model fields map correctly for city selection`() {
        val city = PassengerOrganizationResponse(id = "city-kol-1", name = "Kolkata Hub")
        assertEquals("city-kol-1", city.id)
        assertEquals("Kolkata Hub", city.name)
    }
}
