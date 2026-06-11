#!/usr/bin/env python3
"""
Aggiunge al dataset universitario le distanze (dall'università) a:
  - stazione ferroviaria più vicina
  - stazione metro più vicina
  - fermata pullman/autobus più vicina
  - centro città

Geocoding via Nominatim, dati di trasporto via Overpass API.
Checkpoint JSON separato (checkpoint_v3.json) per ripresa dopo crash.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import math
import time
from pathlib import Path

import pandas as pd
import requests

# ── Percorsi ─────────────────────────────────────────────────────────────────
INPUT_FILE   = r"C:\Users\Utente\Desktop\DISTANZA\dataset_universita_POI.xlsx"
OUTPUT_FILE  = r"C:\Users\Utente\Desktop\DISTANZA\dataset_universita_TRASPORTI.xlsx"
CHECKPOINT   = r"C:\Users\Utente\Desktop\DISTANZA\checkpoint_v3.json"

RADIUS_M      = 5000          # raggio più ampio per trovare stazioni più lontane
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
HEADERS       = {"User-Agent": "UniversityTransportEnricher/3.0 (educational project)"}

# ── Categorie trasporti (Overpass tag groups) ─────────────────────────────────
TRANSPORT_CATEGORIES = {
    "stazione_treno": [
        {"railway": "station"},
        {"railway": "halt"},
    ],
    "metro": [
        {"railway": "subway_station"},
        {"station": "subway"},
        {"railway": "station", "station": "subway"},
    ],
    "pullman": [
        {"highway": "bus_stop"},
        {"amenity": "bus_station"},
    ],
}


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def geocode_university(uni_name: str, city: str, province: str) -> tuple[float, float] | None:
    """Geocodifica l'università tramite Nominatim."""
    queries = [
        f"{uni_name}, {city}, Italy",
        f"{uni_name}, Italy",
        f"{city}, {province}, Italy",
        f"{city}, Italy",
    ]
    for q in queries:
        for attempt in range(3):
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
                    print("      [Nominatim 429] attendo 15s…")
                    time.sleep(15)
                    continue
            except requests.RequestException as e:
                print(f"      [Nominatim errore] {e}")
                time.sleep(2)
            time.sleep(1)
    return None


def geocode_city_center(city: str, province: str) -> tuple[float, float] | None:
    """Geocodifica il centro città (piazza principale o centro storico)."""
    queries = [
        f"piazza principale, {city}, Italy",
        f"centro storico, {city}, Italy",
        f"{city}, {province}, Italy",
        f"{city}, Italy",
    ]
    for q in queries:
        for attempt in range(3):
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
                    print("      [Nominatim 429] attendo 15s…")
                    time.sleep(15)
                    continue
            except requests.RequestException as e:
                print(f"      [Nominatim errore] {e}")
                time.sleep(2)
            time.sleep(1)
    return None


def build_overpass_query(lat, lon, radius, tag_groups):
    parts = []
    for tags in tag_groups:
        for ntype in ("node", "way", "relation"):
            filters = "".join(f'["{k}"="{v}"]' for k, v in tags.items())
            parts.append(f'  {ntype}(around:{radius},{lat},{lon}){filters};')
    return f"[out:json][timeout:40];\n(\n" + "\n".join(parts) + "\n);\nout center;"


def query_overpass(lat, lon, radius, tag_groups) -> list[dict]:
    ql = build_overpass_query(lat, lon, radius, tag_groups)
    for attempt in range(4):
        try:
            r = requests.post(OVERPASS_URL, data={"data": ql}, headers=HEADERS, timeout=50)
            if r.status_code == 200:
                return r.json().get("elements", [])
            elif r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"      [Overpass 429] attendo {wait}s…")
                time.sleep(wait)
            elif r.status_code in (502, 503, 504):
                wait = 10 * (attempt + 1)
                print(f"      [Overpass {r.status_code}] attendo {wait}s…")
                time.sleep(wait)
            else:
                print(f"      [Overpass {r.status_code}]")
                time.sleep(3)
        except requests.RequestException as e:
            print(f"      [Overpass errore] {e}")
            time.sleep(5)
    return []


def nearest_poi_dist(elements, ref_lat, ref_lon) -> tuple[int, float | None]:
    """Restituisce (count, distanza_minima_m) dall'università ai POI trovati."""
    count = len(elements)
    if count == 0:
        return 0, None
    min_dist = float("inf")
    for el in elements:
        if el["type"] == "node":
            elat, elon = el.get("lat"), el.get("lon")
        else:
            c = el.get("center", {})
            elat, elon = c.get("lat"), c.get("lon")
        if elat and elon:
            d = haversine_m(ref_lat, ref_lon, elat, elon)
            min_dist = min(min_dist, d)
    dist = round(min_dist, 1) if min_dist != float("inf") else None
    return count, dist


def load_checkpoint() -> dict:
    p = Path(CHECKPOINT)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(data: dict):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("Caricamento dataset…")
    df = pd.read_excel(INPUT_FILE)
    print(f"  {len(df)} righe, {len(df.columns)} colonne")

    sede_keys = ["Università (nome esteso)", "Ateneo (nome breve)", "Città Ateneo", "Provincia Sede Corso"]
    unique_sedi = df[sede_keys].drop_duplicates().reset_index(drop=True)
    total = len(unique_sedi)
    print(f"  Sedi uniche: {total}\n")

    ckpt = load_checkpoint()
    print(f"Checkpoint v3: {len(ckpt)} sedi già elaborate\n")

    failed = []

    for idx, row in unique_sedi.iterrows():
        uni_name = row["Università (nome esteso)"]
        ateneo   = row["Ateneo (nome breve)"]
        city     = row["Città Ateneo"]
        prov     = row["Provincia Sede Corso"]
        ck_key   = f"{uni_name}||{city}"

        print(f"[{idx+1}/{total}] {ateneo} — {city}")

        if ck_key in ckpt:
            print("  (già elaborata, skip)")
            continue

        # ── Geocoding università ─────────────────────────────────────────────
        coords = geocode_university(uni_name, city, prov)
        time.sleep(1)

        if coords is None:
            print(f"  GEOCODING UNI FALLITO")
            failed.append(f"{ateneo} ({city})")
            ckpt[ck_key] = {}
            save_checkpoint(ckpt)
            continue

        lat, lon = coords
        print(f"  Coord uni: {lat:.5f}, {lon:.5f}")

        result = {"lat": lat, "lon": lon}

        # ── Trasporti via Overpass ────────────────────────────────────────────
        for cat, tag_groups in TRANSPORT_CATEGORIES.items():
            elements = query_overpass(lat, lon, RADIUS_M, tag_groups)
            count, dist = nearest_poi_dist(elements, lat, lon)
            result[f"{cat}_count"] = count
            result[f"{cat}_dist_m"] = dist
            dist_str = f"{dist:.0f}m" if dist is not None else "—"
            print(f"    {cat}: {count} trovati, più vicino a {dist_str}")
            time.sleep(1.5)

        # ── Distanza centro città via Nominatim ───────────────────────────────
        centro_coords = geocode_city_center(city, prov)
        time.sleep(1)

        if centro_coords is not None:
            clat, clon = centro_coords
            centro_dist = round(haversine_m(lat, lon, clat, clon), 1)
            result["centro_lat"] = clat
            result["centro_lon"] = clon
            result["centro_dist_m"] = centro_dist
            print(f"    centro città: {centro_dist:.0f}m")
        else:
            result["centro_lat"] = None
            result["centro_lon"] = None
            result["centro_dist_m"] = None
            print(f"    centro città: geocoding fallito")

        result["raggio_trasporti_m"] = RADIUS_M
        ckpt[ck_key] = result
        save_checkpoint(ckpt)

    # ── Applica checkpoint al dataframe ──────────────────────────────────────
    print("\nApplico dati al dataset…")

    transport_cols = []
    for cat in TRANSPORT_CATEGORIES:
        transport_cols += [f"{cat}_count", f"{cat}_dist_m"]
    transport_cols += ["centro_dist_m", "raggio_trasporti_m"]

    for col in transport_cols:
        df[col] = None

    matched = 0
    for idx, row in df.iterrows():
        ck_key = f"{row['Università (nome esteso)']}||{row['Città Ateneo']}"
        rec = ckpt.get(ck_key, {})
        if rec:
            for cat in TRANSPORT_CATEGORIES:
                df.at[idx, f"{cat}_count"] = rec.get(f"{cat}_count")
                df.at[idx, f"{cat}_dist_m"] = rec.get(f"{cat}_dist_m")
            df.at[idx, "centro_dist_m"] = rec.get("centro_dist_m")
            df.at[idx, "raggio_trasporti_m"] = rec.get("raggio_trasporti_m", RADIUS_M)
            matched += 1

    # Converti a numerico
    for cat in TRANSPORT_CATEGORIES:
        df[f"{cat}_count"] = pd.to_numeric(df[f"{cat}_count"], errors="coerce").astype("Int64")
        df[f"{cat}_dist_m"] = pd.to_numeric(df[f"{cat}_dist_m"], errors="coerce").round(1)
    df["centro_dist_m"] = pd.to_numeric(df["centro_dist_m"], errors="coerce").round(1)
    df["raggio_trasporti_m"] = pd.to_numeric(df["raggio_trasporti_m"], errors="coerce").fillna(RADIUS_M).astype(int)

    print(f"Salvataggio {OUTPUT_FILE}…")
    df.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")

    print("\n" + "=" * 60)
    print("RIEPILOGO")
    print("=" * 60)
    print(f"  Sedi totali:              {total}")
    print(f"  Sedi nel checkpoint:      {len(ckpt)}")
    print(f"  Righe dataset aggiornate: {matched} / {len(df)}")
    if failed:
        print(f"  Geocoding falliti ({len(failed)}):")
        for s in failed:
            print(f"    - {s}")

    print("\nColonne aggiunte:")
    new_cols = [c for c in transport_cols]
    for c in new_cols:
        print(f"    + {c}")
    print("=" * 60)
    print("COMPLETATO.")


if __name__ == "__main__":
    main()
