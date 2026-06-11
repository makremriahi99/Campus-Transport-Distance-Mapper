#!/usr/bin/env python3
"""
Test: distanza università → piazza principale della città via Overpass.
Strategia: dentro il confine comunale cerca prima il duomo/cattedrale,
poi la piazza principale (place=square), poi cade sul centroide admin.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import math, time
import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS      = {"User-Agent": "UniversityTest/2.0 (educational project)"}

TEST_SEDI = [
    ("Bari",     41.10949, 16.88169),
    ("Venezia",  45.43450, 12.32645),
    ("Milano",   45.46011,  9.19532),
    ("Napoli",   40.84776, 14.25660),
    ("Bologna",  44.49829, 11.35446),
    ("Roma",     41.89332, 12.48293),
    ("Firenze",  43.77814, 11.26041),
    ("Torino",   45.07338,  7.69944),
    ("Palermo",  38.11740, 13.37000),
    ("Pisa",     43.71831, 10.39692),
]


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def overpass_query(ql: str) -> list[dict]:
    for attempt in range(3):
        try:
            r = requests.post(OVERPASS_URL, data={"data": ql}, headers=HEADERS, timeout=35)
            if r.status_code == 200:
                return r.json().get("elements", [])
            elif r.status_code == 429:
                time.sleep(15)
        except requests.RequestException as e:
            print(f"  [errore] {e}")
            time.sleep(3)
    return []


def get_element_coords(el: dict) -> tuple[float, float] | None:
    if el["type"] == "node":
        return el.get("lat"), el.get("lon")
    c = el.get("center", {})
    if c:
        return c.get("lat"), c.get("lon")
    return None


def piazza_principale(city: str, uni_lat: float, uni_lon: float) -> tuple[float, float, str] | None:
    """
    Cerca nell'ordine:
      1. Cattedrale / duomo (building=cathedral o historic=cathedral)
      2. Piazza principale (place=square) — quella più vicina al centroide admin
      3. Centroide del comune (fallback)
    Restituisce (lat, lon, metodo_usato).
    """

    # ── 1. Cattedrale ────────────────────────────────────────────────────────
    ql_duomo = f"""
[out:json][timeout:30];
area["admin_level"="8"]["name"="{city}"]->.a;
(
  node["building"="cathedral"](area.a);
  way["building"="cathedral"](area.a);
  node["historic"="cathedral"](area.a);
  way["historic"="cathedral"](area.a);
  node["amenity"="place_of_worship"]["building"="cathedral"](area.a);
  way["amenity"="place_of_worship"]["building"="cathedral"](area.a);
);
out center;
"""
    els = overpass_query(ql_duomo)
    time.sleep(1.5)
    if els:
        # Prendi quello più vicino all'università
        best, best_d = None, float("inf")
        for el in els:
            coords = get_element_coords(el)
            if coords and coords[0]:
                d = haversine_m(uni_lat, uni_lon, *coords)
                if d < best_d:
                    best_d, best = d, coords
        if best:
            return best[0], best[1], "cattedrale/duomo"

    # ── 2. Place=square ───────────────────────────────────────────────────────
    ql_piazza = f"""
[out:json][timeout:30];
area["admin_level"="8"]["name"="{city}"]->.a;
(
  node["place"="square"](area.a);
  way["place"="square"](area.a);
);
out center;
"""
    els = overpass_query(ql_piazza)
    time.sleep(1.5)
    if els:
        # Prima cerca una con nome che contiene "principale", "grande", "maggiore", "duomo"
        keywords = ["principale", "grande", "maggiore", "duomo", "municipio", "libertà", "italia"]
        for kw in keywords:
            for el in els:
                name = el.get("tags", {}).get("name", "").lower()
                if kw in name:
                    coords = get_element_coords(el)
                    if coords and coords[0]:
                        return coords[0], coords[1], f"piazza '{el['tags'].get('name', '')}'"
        # Altrimenti prendi quella più vicina all'università
        best, best_d = None, float("inf")
        for el in els:
            coords = get_element_coords(el)
            if coords and coords[0]:
                d = haversine_m(uni_lat, uni_lon, *coords)
                if d < best_d:
                    best_d, best = d, (coords, el.get("tags", {}).get("name", "?"))
        if best:
            return best[0][0], best[0][1], f"piazza '{best[1]}' (più vicina)"

    # ── 3. Fallback: centroide admin ──────────────────────────────────────────
    ql_admin = f"""
[out:json][timeout:30];
relation["admin_level"="8"]["name"="{city}"]["boundary"="administrative"];
out center;
"""
    els = overpass_query(ql_admin)
    time.sleep(1.5)
    if els:
        c = els[0].get("center", {})
        if c:
            return c["lat"], c["lon"], "centroide amministrativo (fallback)"

    return None


print(f"{'Città':<10} {'Distanza':>10}  Punto di riferimento")
print("-" * 65)

for city, uni_lat, uni_lon in TEST_SEDI:
    result = piazza_principale(city, uni_lat, uni_lon)
    if result:
        lat, lon, metodo = result
        dist = haversine_m(uni_lat, uni_lon, lat, lon)
        print(f"{city:<10} {dist:>8.0f}m  → {metodo}")
        print(f"           coords: {lat:.5f}, {lon:.5f}")
    else:
        print(f"{city:<10}         —  nessun risultato")
    print()
