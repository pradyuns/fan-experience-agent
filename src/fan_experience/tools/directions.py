import math

from fan_experience.tools.base import ToolResult


# great-circle distance between two lat/lng points
def _haversine_km(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
) -> float:
    earth_radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# mock directions with simple speed/traffic estimates
async def get_directions(
    origin: tuple[float, float],
    destination: tuple[float, float],
    mode: str,
    _departure_time: str,
) -> ToolResult:
    dist_km = _haversine_km(origin[0], origin[1], destination[0], destination[1])

    if mode == "walking":
        speed_kmh = 4.8
        traffic_factor = 1.0
    elif mode == "driving":
        speed_kmh = 30.0
        traffic_factor = 1.3
    else:
        speed_kmh = 15.0
        traffic_factor = 1.1

    raw_minutes = (dist_km / speed_kmh) * 60
    duration_minutes = round(raw_minutes * traffic_factor, 1)

    data = {
        "duration_minutes": duration_minutes,
        "distance_km": round(dist_km, 2),
        "traffic_factor": traffic_factor,
        "route_summary": f"{mode.capitalize()} via main route, {dist_km:.1f} km",
    }
    return ToolResult(data=data, source="mock_directions_api")
