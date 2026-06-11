#!/usr/bin/env python3
"""Test: distanza università → centroide amministrativo città via Overpass (max 10 sedi)."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json, math, time
import requests

OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS       = {"User-Agent": "UniversityTest/1.0 (educational project)"}

# 10 sedi di test prese dal checkpoint esistente
TEST_SEDI = [
    ("Bari",           41.10949, 16.88169),
    ("Venezia",        45.43450, 12.32645),
    ("Messina",        38.22964, 15.55110),
    ("Milano",         45.46011,  9.19532),
    ("Napoli",         40.84776, 14.25660),
    ("Bologna",        44.49829, 11.35446),
    ("Roma",           41.89332, 12.48293),
    ("Firenze",        43.77814, 11.26041),
    ("Torino",         45.07338,  7.69944),
    ("Palermo",        38.11740, 13.37000),
]


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def centroide_overpass(city: str) -> tuple[float, float] | None:
    """Cerca il centroide del comune (admin_level=8) via Overpass."""
    query = f"""
[out:json][timeout:30];
relation["admin_level"="8"]["name"="{city}"]["boundary"="administrative"];
out center;
"""
    try:
        r = requests.post(OVERPASS_URL, data={"data": query}, headers=HEADERS, timeout=35)
        if r.status_code == 200:
            elements = r.json().get("elements", [])
            if elements:
                el = elements[0]
                c = el.get("center", {})
                if c:
                    return c["lat"], c["lon"]
    except requests.RequestException as e:
        print(f"  [Overpass errore] {e}")
    return None


def centroide_nominatim_vecchio(city: str) -> tuple[float, float] | None:
    """Vecchio metodo: cerca 'piazza principale / centro storico' via Nominatim."""
    queries = [
        f"piazza principale, {city}, Italy",
        f"centro storico, {city}, Italy",
        f"{city}, Italy",
    ]
    for q in queries:
        try:
            r = requests.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "limit": 1},
                headers=HEADERS, timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"])
        except requests.RequestException:
            pass
        time.sleep(1)
    return None


print(f"{'Città':<12} {'Overpass (m)':>14} {'Nominatim (m)':>14}  Diff")
print("-" * 55)

for city, uni_lat, uni_lon in TEST_SEDI:
    # Metodo 1: centroide Overpass
    coords_op = centroide_overpass(city)
    time.sleep(2)

    # Metodo 2: vecchio Nominatim
    coords_nom = centroide_nominatim_vecchio(city)
    time.sleep(1)

    dist_op  = round(haversine_m(uni_lat, uni_lon, *coords_op), 0)  if coords_op  else None
    dist_nom = round(haversine_m(uni_lat, uni_lon, *coords_nom), 0) if coords_nom else None

    op_str  = f"{dist_op:.0f}m"  if dist_op  is not None else "—"
    nom_str = f"{dist_nom:.0f}m" if dist_nom is not None else "—"

    if dist_op and dist_nom:
        diff = f"Δ {abs(dist_op - dist_nom):.0f}m"
    else:
        diff = ""

    print(f"{city:<12} {op_str:>14} {nom_str:>14}  {diff}")

    if coords_op:
        print(f"  Overpass centro: {coords_op[0]:.5f}, {coords_op[1]:.5f}")
    if coords_nom:
        print(f"  Nominatim centro: {coords_nom[0]:.5f}, {coords_nom[1]:.5f}")
    print()
