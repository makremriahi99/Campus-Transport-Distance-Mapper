#!/usr/bin/env python3
"""
Arricchisce dataset universitario con POI di prossimità via Overpass API.
Geocoding tramite Nominatim usando il nome esteso dell'università.
Checkpoint JSON per riprendere in caso di crash.
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
INPUT_FILE  = r"C:\Users\Utente\Desktop\UNI-20260424T123855Z-3-001\UNI\dataset\dataset_universita_TOTALMENTE_COMPLETO.xlsx"
OUTPUT_FILE = r"C:\Users\Utente\Desktop\DISTANZA\dataset_universita_POI.xlsx"
CHECKPOINT  = r"C:\Users\Utente\Desktop\DISTANZA\checkpoint.json"

RADIUS_M      = 2000
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
HEADERS       = {"User-Agent": "UniversityPOIEnricher/2.0 (educational project)"}

# ── Categorie POI ─────────────────────────────────────────────────────────────
POI_CATEGORIES = {
    "cinema":     [{"amenity": "cinema"}],
    "palestre":   [{"leisure": "fitness_centre"}, {"leisure": "sports_centre"}],
    "bar":        [{"amenity": "bar"}, {"amenity": "cafe"}],
    "ristoranti": [{"amenity": "restaurant"}, {"amenity": "fast_food"}],
    "mense":      [{"amenity": "canteen"}, {"amenity": "university", "canteen": "yes"}],
}


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def geocode(uni_name: str, city: str, province: str) -> tuple[float, float] | None:
    """Nominatim: prova prima con nome università, poi con solo città."""
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


def build_overpass_query(lat, lon, radius, tag_groups):
    parts = []
    for tags in tag_groups:
        for ntype in ("node", "way", "relation"):
            filters = "".join(f'["{k}"="{v}"]' for k, v in tags.items())
            parts.append(f'  {ntype}(around:{radius},{lat},{lon}){filters};')
    return f"[out:json][timeout:30];\n(\n" + "\n".join(parts) + "\n);\nout center;"


def query_overpass(lat, lon, radius, tag_groups) -> list[dict]:
    ql = build_overpass_query(lat, lon, radius, tag_groups)
    for attempt in range(4):
        try:
            r = requests.post(OVERPASS_URL, data={"data": ql}, headers=HEADERS, timeout=40)
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


def poi_stats(elements, ref_lat, ref_lon):
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
    print(f"Caricamento dataset…")
    df = pd.read_excel(INPUT_FILE)
    print(f"  {len(df)} righe, {len(df.columns)} colonne")

    sede_keys = ["Università (nome esteso)", "Ateneo (nome breve)", "Città Ateneo", "Provincia Sede Corso"]
    unique_sedi = df[sede_keys].drop_duplicates().reset_index(drop=True)
    total = len(unique_sedi)
    print(f"  Sedi uniche: {total}\n")

    # Carica checkpoint
    ckpt = load_checkpoint()
    print(f"Checkpoint: {len(ckpt)} sedi già elaborate\n")

    failed_geocoding = []

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

        # Geocoding
        coords = geocode(uni_name, city, prov)
        time.sleep(1)

        if coords is None:
            print(f"  GEOCODING FALLITO")
            failed_geocoding.append(f"{ateneo} ({city})")
            ckpt[ck_key] = {}
            save_checkpoint(ckpt)
            continue

        lat, lon = coords
        print(f"  Coord: {lat:.5f}, {lon:.5f}")

        result = {"lat": lat, "lon": lon}
        for cat, tag_groups in POI_CATEGORIES.items():
            elements = query_overpass(lat, lon, RADIUS_M, tag_groups)
            count, dist = poi_stats(elements, lat, lon)
            result[f"{cat}_count"] = count
            result[f"{cat}_dist_m"] = dist
            dist_str = f"{dist:.0f}m" if dist is not None else "—"
            print(f"    {cat}: {count} POI, min {dist_str}")
            time.sleep(1.5)

        result["raggio_ricerca_m"] = RADIUS_M
        ckpt[ck_key] = result
        save_checkpoint(ckpt)

    # ── Applica checkpoint al dataframe ──────────────────────────────────────
    print("\nApplico dati al dataset…")
    poi_cols = []
    for cat in POI_CATEGORIES:
        poi_cols += [f"{cat}_count", f"{cat}_dist_m"]
    poi_cols.append("raggio_ricerca_m")
    for col in poi_cols:
        df[col] = None

    matched = 0
    for idx, row in df.iterrows():
        ck_key = f"{row['Università (nome esteso)']}||{row['Città Ateneo']}"
        rec = ckpt.get(ck_key, {})
        if rec:
            for cat in POI_CATEGORIES:
                df.at[idx, f"{cat}_count"] = rec.get(f"{cat}_count")
                df.at[idx, f"{cat}_dist_m"] = rec.get(f"{cat}_dist_m")
            df.at[idx, "raggio_ricerca_m"] = rec.get("raggio_ricerca_m", RADIUS_M)
            matched += 1

    for cat in POI_CATEGORIES:
        df[f"{cat}_count"] = pd.to_numeric(df[f"{cat}_count"], errors="coerce")
        df[f"{cat}_dist_m"] = pd.to_numeric(df[f"{cat}_dist_m"], errors="coerce").round(1)
    df["raggio_ricerca_m"] = pd.to_numeric(df["raggio_ricerca_m"], errors="coerce").fillna(RADIUS_M).astype(int)

    print(f"Salvataggio {OUTPUT_FILE}…")
    df.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")

    print("\n" + "=" * 55)
    print("RIEPILOGO")
    print("=" * 55)
    print(f"  Sedi totali:          {total}")
    print(f"  Sedi nel checkpoint:  {len(ckpt)}")
    print(f"  Righe dataset aggiornate: {matched} / {len(df)}")
    if failed_geocoding:
        print(f"  Geocoding falliti ({len(failed_geocoding)}):")
        for s in failed_geocoding:
            print(f"    - {s}")
    print("=" * 55)
    print("COMPLETATO.")


if __name__ == "__main__":
    main()
