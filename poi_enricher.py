#!/usr/bin/env python3
"""
Arricchisce dataset universitario con dati di prossimità urbana via Overpass API.
Geocoding tramite Nominatim (OpenStreetMap) — nessuna API key necessaria.
"""
import math
import time
import sys

import pandas as pd
import requests

INPUT_FILE  = r"C:\Users\Utente\Downloads\dataset_universita_ARRICCHITO.xlsx"
OUTPUT_FILE = r"C:\Users\Utente\Desktop\DISTANZA\dataset_universita_POI.xlsx"
RADIUS_M    = 2000

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"

HEADERS = {"User-Agent": "UniversityPOIEnricher/1.0 (educational project)"}

# -------------------------------------------------------------------
# Categorie POI: nome → lista di tag OSM (AND logic dentro ogni dict,
#                OR logic tra dict diversi nello stesso gruppo)
# -------------------------------------------------------------------
POI_CATEGORIES = {
    "cinema": [
        {"amenity": "cinema"},
    ],
    "palestre": [
        {"leisure": "fitness_centre"},
        {"leisure": "sports_centre"},
    ],
    "bar": [
        {"amenity": "bar"},
        {"amenity": "cafe"},
    ],
    "ristoranti": [
        {"amenity": "restaurant"},
        {"amenity": "fast_food"},
    ],
    "mense": [
        {"amenity": "canteen"},
        {"amenity": "university", "canteen": "yes"},
    ],
}


# -------------------------------------------------------------------
# Haversine distance in metri
# -------------------------------------------------------------------
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# -------------------------------------------------------------------
# Geocoding con Nominatim
# -------------------------------------------------------------------
def geocode(city: str, province: str, retries: int = 3) -> tuple[float, float] | None:
    queries = [
        f"{city}, {province}, Italy",
        f"{city}, Italy",
    ]
    for q in queries:
        for attempt in range(retries):
            try:
                r = requests.get(
                    NOMINATIM_URL,
                    params={"q": q, "format": "json", "limit": 1},
                    headers=HEADERS,
                    timeout=10,
                )
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        return float(data[0]["lat"]), float(data[0]["lon"])
                elif r.status_code == 429:
                    print(f"      [Nominatim 429] attendo 10s…")
                    time.sleep(10)
                    continue
            except requests.RequestException as e:
                print(f"      [Nominatim errore] {e}")
                time.sleep(2)
            time.sleep(1)
    return None


# -------------------------------------------------------------------
# Costruzione query Overpass per una categoria
# -------------------------------------------------------------------
def build_overpass_query(lat: float, lon: float, radius: int, tag_groups: list[dict]) -> str:
    union_parts = []
    for tags in tag_groups:
        for node_type in ("node", "way", "relation"):
            filters = "".join(f'["{k}"="{v}"]' for k, v in tags.items())
            union_parts.append(f'  {node_type}(around:{radius},{lat},{lon}){filters};')
    body = "\n".join(union_parts)
    return f"[out:json][timeout:25];\n(\n{body}\n);\nout center;"


# -------------------------------------------------------------------
# Query Overpass con retry su 429
# -------------------------------------------------------------------
def query_overpass(lat: float, lon: float, radius: int, tag_groups: list[dict],
                   retries: int = 3) -> list[dict]:
    ql = build_overpass_query(lat, lon, radius, tag_groups)
    for attempt in range(retries):
        try:
            r = requests.post(OVERPASS_URL, data={"data": ql}, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json().get("elements", [])
            elif r.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"      [Overpass 429] attendo {wait}s…")
                time.sleep(wait)
            elif r.status_code in (504, 502, 503):
                wait = 8 * (attempt + 1)
                print(f"      [Overpass {r.status_code}] attendo {wait}s…")
                time.sleep(wait)
            else:
                print(f"      [Overpass {r.status_code}]")
                time.sleep(3)
        except requests.RequestException as e:
            print(f"      [Overpass errore] {e}")
            time.sleep(3)
    return []


# -------------------------------------------------------------------
# Estrae coordinate centro da un elemento OSM
# -------------------------------------------------------------------
def get_lat_lon(element: dict) -> tuple[float, float] | None:
    if element["type"] == "node":
        return element.get("lat"), element.get("lon")
    center = element.get("center")
    if center:
        return center.get("lat"), center.get("lon")
    return None, None


# -------------------------------------------------------------------
# Calcola count e distanza minima per una categoria
# -------------------------------------------------------------------
def poi_stats(elements: list[dict], ref_lat: float, ref_lon: float) -> tuple[int, float]:
    count = len(elements)
    if count == 0:
        return 0, float("nan")
    min_dist = float("inf")
    for el in elements:
        elat, elon = get_lat_lon(el)
        if elat is not None and elon is not None:
            d = haversine_m(ref_lat, ref_lon, elat, elon)
            if d < min_dist:
                min_dist = d
    return count, round(min_dist, 1) if min_dist != float("inf") else float("nan")


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
def main():
    print(f"Caricamento {INPUT_FILE}…")
    df = pd.read_excel(INPUT_FILE)
    print(f"  {len(df)} righe, {len(df.columns)} colonne\n")

    # Colonne di output
    poi_cols = []
    for cat in POI_CATEGORIES:
        poi_cols += [f"{cat}_count", f"{cat}_dist_m"]
    poi_cols.append("raggio_ricerca_m")
    for col in poi_cols:
        df[col] = None

    # Sedi uniche: ateneo + città + provincia
    sede_keys = ["Ateneo (nome breve)", "Città Ateneo", "Provincia Sede Corso"]
    unique_sedi = df[sede_keys].drop_duplicates().reset_index(drop=True)
    total = len(unique_sedi)
    print(f"Sedi uniche da elaborare: {total}\n")

    cache: dict[tuple, dict] = {}   # (ateneo, città) → poi result dict
    failed_geocoding = []
    elaborated = 0

    for idx, row in unique_sedi.iterrows():
        ateneo  = row["Ateneo (nome breve)"]
        city    = row["Città Ateneo"]
        prov    = row["Provincia Sede Corso"]
        key     = (ateneo, city)

        print(f"[{idx+1}/{total}] {ateneo} — {city} ({prov})")

        if key in cache:
            print("  (cached)")
            result = cache[key]
        else:
            # Geocoding
            coords = geocode(city, prov)
            time.sleep(1)  # rispetta rate limit Nominatim

            if coords is None:
                print(f"  GEOCODING FALLITO — salto")
                failed_geocoding.append(f"{ateneo} ({city})")
                cache[key] = {}
                result = {}
            else:
                lat, lon = coords
                print(f"  Coord: {lat:.4f}, {lon:.4f}")
                result = {}

                for cat, tag_groups in POI_CATEGORIES.items():
                    elements = query_overpass(lat, lon, RADIUS_M, tag_groups)
                    count, dist = poi_stats(elements, lat, lon)
                    result[f"{cat}_count"] = count
                    result[f"{cat}_dist_m"] = dist
                    print(f"    {cat}: {count} POI, min {dist:.0f}m" if not math.isnan(dist) else f"    {cat}: {count} POI")
                    time.sleep(1.5)  # rispetta rate limit Overpass

                result["raggio_ricerca_m"] = RADIUS_M
                cache[key] = result

        # Applica al dataframe
        mask = (df["Ateneo (nome breve)"] == ateneo) & (df["Città Ateneo"] == city)
        for col, val in result.items():
            df.loc[mask, col] = val

        elaborated += 1

    # Converti colonne numeriche
    for col in poi_cols:
        if col != "raggio_ricerca_m":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["raggio_ricerca_m"] = pd.to_numeric(df["raggio_ricerca_m"], errors="coerce").fillna(RADIUS_M).astype(int)

    # Salva
    print(f"\nSalvataggio in {OUTPUT_FILE}…")
    df.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")
    print("  Fatto!")

    # Riepilogo
    print("\n" + "=" * 50)
    print("RIEPILOGO")
    print("=" * 50)
    print(f"  Sedi totali:     {total}")
    print(f"  Elaborate:       {elaborated}")
    print(f"  Geocoding falliti ({len(failed_geocoding)}):")
    for s in failed_geocoding:
        print(f"    - {s}")
    print("=" * 50)


if __name__ == "__main__":
    main()
