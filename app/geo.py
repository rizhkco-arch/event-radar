import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bounding_box(lat: float, lon: float, radius_km: float):
    lat_delta = radius_km / 111.32
    lon_delta = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    return lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta


def in_radius(lat1, lon1, lat2, lon2, radius_km) -> bool:
    return haversine_km(lat1, lon1, lat2, lon2) <= radius_km
