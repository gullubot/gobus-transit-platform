import math
import datetime
from typing import List, Dict, Any, Tuple

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0 # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360
    return compass_bearing

class RoutePhysics:
    def __init__(self, route_stops: List[Dict[str, Any]]):
        self.stops = sorted(route_stops, key=lambda x: x.get('sequence_number', 0))
        self.segments = []
        self.total_distance_km = 0.0
        
        for i in range(len(self.stops) - 1):
            s1 = self.stops[i]
            s2 = self.stops[i+1]
            dist = haversine(s1['latitude'], s1['longitude'], s2['latitude'], s2['longitude'])
            bearing = calculate_bearing(s1['latitude'], s1['longitude'], s2['latitude'], s2['longitude'])
            self.segments.append({
                'start_idx': i,
                'end_idx': i+1,
                'distance_km': dist,
                'bearing': bearing,
                'start_lat': s1['latitude'],
                'start_lon': s1['longitude'],
                'end_lat': s2['latitude'],
                'end_lon': s2['longitude']
            })
            self.total_distance_km += dist
            
        self.current_distance_km = 0.0
        self.current_segment_idx = 0

    def move(self, distance_km: float) -> Tuple[float, float, float]:
        """Moves the bus by distance_km along the polyline. Returns (lat, lon, bearing)."""
        self.current_distance_km += distance_km
        
        if self.current_distance_km >= self.total_distance_km:
            # End of route
            last_stop = self.stops[-1]
            return last_stop['latitude'], last_stop['longitude'], 0.0

        # Find current segment
        accumulated = 0.0
        for idx, seg in enumerate(self.segments):
            if accumulated + seg['distance_km'] >= self.current_distance_km:
                self.current_segment_idx = idx
                # Interpolate within segment
                segment_progress_km = self.current_distance_km - accumulated
                if seg['distance_km'] > 0:
                    fraction = segment_progress_km / seg['distance_km']
                else:
                    fraction = 1.0
                
                lat = seg['start_lat'] + (seg['end_lat'] - seg['start_lat']) * fraction
                lon = seg['start_lon'] + (seg['end_lon'] - seg['start_lon']) * fraction
                return lat, lon, seg['bearing']
            accumulated += seg['distance_km']
            
        # Fallback
        last_stop = self.stops[-1]
        return last_stop['latitude'], last_stop['longitude'], 0.0

    def is_complete(self) -> bool:
        return self.current_distance_km >= self.total_distance_km

class SimulationClock:
    def __init__(self, multiplier: float, duration_seconds: float):
        self.multiplier = multiplier
        # Start in the past so that we finish around NOW
        self.start_real_time = datetime.datetime.now(datetime.timezone.utc)
        self.start_sim_time = self.start_real_time - datetime.timedelta(seconds=(duration_seconds))
        self.current_sim_time = self.start_sim_time

    def tick(self, real_delta_seconds: float) -> datetime.datetime:
        sim_delta = real_delta_seconds * self.multiplier
        self.current_sim_time += datetime.timedelta(seconds=sim_delta)
        # Ensure we don't accidentally drift into the future past backend server time
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.current_sim_time > now:
            self.current_sim_time = now
        return self.current_sim_time
