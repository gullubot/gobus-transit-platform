package com.transitplatform.passenger.data.local

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.transitplatform.passenger.ui.history.HistoryItem
import com.transitplatform.passenger.data.model.PassengerStopResponse
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import org.json.JSONArray
import org.json.JSONObject

private val Context.historyDataStore by preferencesDataStore(name = "passenger_history")

class HistoryStore(private val context: Context) {
    
    // Keyed by organization_id
    private fun getCityKey(organizationId: String) = stringPreferencesKey("history_$organizationId")

    fun getHistoryFlow(organizationId: String): Flow<List<HistoryItem>> {
        return context.historyDataStore.data.map { preferences ->
            val jsonString = preferences[getCityKey(organizationId)] ?: "[]"
            parseHistory(jsonString)
        }
    }

    suspend fun addTrip(organizationId: String, origin: PassengerStopResponse, destination: PassengerStopResponse) {
        context.historyDataStore.edit { preferences ->
            val key = getCityKey(organizationId)
            val jsonString = preferences[key] ?: "[]"
            val currentList = parseHistory(jsonString).toMutableList()

            // De-duplicate: remove if exists
            currentList.removeAll { it.origin.id == origin.id && it.destination.id == destination.id }

            // Add to top
            currentList.add(0, HistoryItem(origin, destination, System.currentTimeMillis()))

            // Enforce max 10
            val limitedList = currentList.take(10)

            // Save back
            preferences[key] = serializeHistory(limitedList)
        }
    }

    private fun parseHistory(jsonString: String): List<HistoryItem> {
        val list = mutableListOf<HistoryItem>()
        try {
            val jsonArray = JSONArray(jsonString)
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                val originObj = obj.getJSONObject("origin")
                val destObj = obj.getJSONObject("destination")
                
                val origin = PassengerStopResponse(
                    id = originObj.getString("id"),
                    organization_id = originObj.getString("organization_id"),
                    name = originObj.getString("name"),
                    latitude = originObj.getDouble("latitude"),
                    longitude = originObj.getDouble("longitude"),
                    stop_code = originObj.optString("stop_code", "")
                )
                
                val dest = PassengerStopResponse(
                    id = destObj.getString("id"),
                    organization_id = destObj.getString("organization_id"),
                    name = destObj.getString("name"),
                    latitude = destObj.getDouble("latitude"),
                    longitude = destObj.getDouble("longitude"),
                    stop_code = destObj.optString("stop_code", "")
                )
                
                val timestamp = obj.getLong("timestamp")
                list.add(HistoryItem(origin, dest, timestamp))
            }
        } catch (e: Exception) {
            // Ignore parse errors, just return whatever is parsed so far
        }
        return list
    }

    private fun serializeHistory(list: List<HistoryItem>): String {
        val jsonArray = JSONArray()
        list.forEach { item ->
            val obj = JSONObject()
            
            val originObj = JSONObject().apply {
                put("id", item.origin.id)
                put("organization_id", item.origin.organization_id)
                put("name", item.origin.name)
                put("latitude", item.origin.latitude)
                put("longitude", item.origin.longitude)
                put("stop_code", item.origin.stop_code)
            }
            
            val destObj = JSONObject().apply {
                put("id", item.destination.id)
                put("organization_id", item.destination.organization_id)
                put("name", item.destination.name)
                put("latitude", item.destination.latitude)
                put("longitude", item.destination.longitude)
                put("stop_code", item.destination.stop_code)
            }
            
            obj.put("origin", originObj)
            obj.put("destination", destObj)
            obj.put("timestamp", item.timestamp)
            
            jsonArray.put(obj)
        }
        return jsonArray.toString()
    }
}
