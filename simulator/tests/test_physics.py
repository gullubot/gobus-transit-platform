import math
from src.physics import haversine, calculate_bearing, RoutePhysics

def test_haversine():
    dist = haversine(22.5726, 88.3639, 22.5736, 88.3649)
    assert dist > 0.0

def test_route_physics_move():
    stops = [
        {"sequence_number": 1, "latitude": 22.5726, "longitude": 88.3639},
        {"sequence_number": 2, "latitude": 22.5736, "longitude": 88.3649}
    ]
    physics = RoutePhysics(stops)
    assert physics.total_distance_km > 0.0
    assert not physics.is_complete()
    
    lat, lon, bearing = physics.move(0.001)
    assert 22.5726 <= lat <= 22.5736
    assert 88.3639 <= lon <= 88.3649
    
    # Move past the end
    lat, lon, bearing = physics.move(physics.total_distance_km + 1.0)
    assert physics.is_complete()
    assert math.isclose(lat, 22.5736, rel_tol=1e-5)
    assert math.isclose(lon, 88.3649, rel_tol=1e-5)
