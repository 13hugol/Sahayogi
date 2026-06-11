from __future__ import annotations
import math
import re

NEPAL_CITIES = {
    'kathmandu': (27.7172, 85.3240),
    'pokhara': (28.2096, 83.9856),
    'lalitpur': (27.6744, 85.3240),
    'patan': (27.6744, 85.3240),
    'bhaktapur': (27.6710, 85.4298),
    'biratnagar': (26.4525, 87.2718),
    'bharatpur': (27.6833, 84.4333),
    'janakpur': (26.7270, 85.9231),
    'hetauda': (27.4277, 85.0305),
    'nepalgunj': (28.0500, 81.6167),
    'butwal': (27.7006, 83.4484),
    'dharan': (26.8126, 87.2831),
    'itahari': (26.6639, 87.2717),
    'dhangadhi': (28.6853, 80.6083),
    'birendranagar': (28.5985, 81.6322),
    'surkhet': (28.5985, 81.6322),
    'siddharthanagar': (27.5081, 83.4502),
    'bhairahawa': (27.5081, 83.4502),
}

def parse_coordinates(location_str: str | None) -> tuple[float, float] | None:
    if not location_str:
        return None
    cleaned = location_str.strip()
    if not cleaned:
        return None
    match = re.match(r'^([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)$', cleaned)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except ValueError:
            pass
    city_key = cleaned.lower()
    if city_key in NEPAL_CITIES:
        return NEPAL_CITIES[city_key]
    return None

def haversine_distance(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c
