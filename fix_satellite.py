#!/usr/bin/env python3
"""
Corregge le sedi satellite con coordinate errate.
Per ogni sede dove l'università geocodificata dista > 50km dalla città dichiarata:
  1. Ri-geocodifica usando il nome della città (non dell'università)
  2. Ri-calcola distanze trasporti (treno, metro, pullman) via Overpass
  3. Ri-calcola distanza centro città
Aggiorna dataset_universita_TRASPORTI.xlsx.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json, math, time
from pathlib import Path
import pandas as pd
import requests

INPUT_FILE  = r"C:\Users\Utente\Desktop\DISTANZA\dataset_universita_TRASPORTI.xlsx"
OUTPUT_FILE = r"C:\Users\Utente\Desktop\DISTANZA\dataset_universita_TRASPORTI.xlsx"
CHECKPOINT  = r"C:\Users\Utente\Desktop\DISTANZA\checkpoint_fix.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
HEADERS       = {"User-Agent": "UniversityFix/1.0 (educational project)"}
RADIUS_M      = 5000
SOGLIA_KM     = 50   # distanza massima accettabile università↔città

PIAZZA_CURATA = {
    "Agrigento":            "Piazza Aldo Moro, Agrigento, Italy",
    "Ancona":               "Piazza del Plebiscito, Ancona, Italy",
    "Aosta":                "Piazza Émile Chanoux, Aosta, Italy",
    "Arezzo":               "Piazza Grande, Arezzo, Italy",
    "Avellino":             "Piazza della Libertà, Avellino, Italy",
    "Bari":                 "Piazza del Ferrarese, Bari, Italy",
    "Benevento":            "Piazza IV Novembre, Benevento, Italy",
    "Bergamo":              "Piazza Vecchia, Bergamo, Italy",
    "Bologna":              "Piazza Maggiore, Bologna, Italy",
    "Bolzano - Bozen":      "Piazza Walther, Bolzano, Italy",
    "Brescia":              "Piazza della Loggia, Brescia, Italy",
    "Bressanone - Brixen":  "Piazza della Parrocchia, Bressanone, Italy",
    "Brindisi":             "Piazza Vittoria, Brindisi, Italy",
    "Cagliari":             "Piazza Yenne, Cagliari, Italy",
    "Caltanissetta":        "Piazza Garibaldi, Caltanissetta, Italy",
    "Campobasso":           "Piazza Vittorio Emanuele II, Campobasso, Italy",
    "Caserta":              "Piazza Carlo III, Caserta, Italy",
    "Catania":              "Piazza del Duomo, Catania, Italy",
    "Catanzaro":            "Piazza Prefettura, Catanzaro, Italy",
    "Chieti":               "Piazza G.B. Vico, Chieti, Italy",
    "Como":                 "Piazza Cavour, Como, Italy",
    "Cosenza":              "Piazza XI Settembre, Cosenza, Italy",
    "Cremona":              "Piazza del Comune, Cremona, Italy",
    "Enna":                 "Piazza Vittorio Emanuele, Enna, Italy",
    "Ferrara":              "Piazza Trento e Trieste, Ferrara, Italy",
    "Firenze":              "Piazza del Duomo, Firenze, Italy",
    "Foggia":               "Piazza Cavour, Foggia, Italy",
    "Forli'":               "Piazza Aurelio Saffi, Forlì, Italy",
    "Frosinone":            "Piazza Vittorio Emanuele II, Frosinone, Italy",
    "Genova":               "Piazza De Ferrari, Genova, Italy",
    "Gorizia":              "Piazza della Vittoria, Gorizia, Italy",
    "Imperia":              "Piazza Dante, Imperia, Italy",
    "L'Aquila":             "Piazza del Duomo, L'Aquila, Italy",
    "La Spezia":            "Piazza Garibaldi, La Spezia, Italy",
    "Latina":               "Piazza del Popolo, Latina, Italy",
    "Lecce":                "Piazza Sant'Oronzo, Lecce, Italy",
    "Livorno":              "Piazza della Repubblica, Livorno, Italy",
    "Lucca":                "Piazza San Michele, Lucca, Italy",
    "Macerata":             "Piazza della Libertà, Macerata, Italy",
    "Mantova":              "Piazza Sordello, Mantova, Italy",
    "Matera":               "Piazza Vittorio Veneto, Matera, Italy",
    "Messina":              "Piazza del Duomo, Messina, Italy",
    "Milano":               "Piazza del Duomo, Milano, Italy",
    "Modena":               "Piazza Grande, Modena, Italy",
    "Napoli":               "Piazza del Plebiscito, Napoli, Italy",
    "Novara":               "Piazza Martiri, Novara, Italy",
    "Nuoro":                "Piazza Italia, Nuoro, Italy",
    "Oristano":             "Piazza Roma, Oristano, Italy",
    "Padova":               "Piazza delle Erbe, Padova, Italy",
    "Palermo":              "Piazza Pretoria, Palermo, Italy",
    "Parma":                "Piazza Garibaldi, Parma, Italy",
    "Pavia":                "Piazza della Vittoria, Pavia, Italy",
    "Perugia":              "Piazza IV Novembre, Perugia, Italy",
    "Pesaro":               "Piazza del Popolo, Pesaro, Italy",
    "Pescara":              "Piazza della Repubblica, Pescara, Italy",
    "Piacenza":             "Piazza dei Cavalli, Piacenza, Italy",
    "Pisa":                 "Piazza del Duomo, Pisa, Italy",
    "Pordenone":            "Piazza XX Settembre, Pordenone, Italy",
    "Potenza":              "Piazza Mario Pagano, Potenza, Italy",
    "Prato":                "Piazza del Comune, Prato, Italy",
    "Ragusa":               "Piazza San Giovanni, Ragusa, Italy",
    "Ravenna":              "Piazza del Popolo, Ravenna, Italy",
    "Reggio Di Calabria":   "Piazza Italia, Reggio Calabria, Italy",
    "Reggio Nell'Emilia":   "Piazza Camillo Prampolini, Reggio Emilia, Italy",
    "Rieti":                "Piazza Vittorio Emanuele II, Rieti, Italy",
    "Rimini":               "Piazza Tre Martiri, Rimini, Italy",
    "Roma":                 "Piazza Venezia, Roma, Italy",
    "Salerno":              "Piazza Portanova, Salerno, Italy",
    "Sassari":              "Piazza d'Italia, Sassari, Italy",
    "Siena":                "Piazza del Campo, Siena, Italy",
    "Siracusa":             "Piazza del Duomo, Siracusa, Italy",
    "Sondrio":              "Piazza Garibaldi, Sondrio, Italy",
    "Taranto":              "Piazza Maria Immacolata, Taranto, Italy",
    "Teramo":               "Piazza Martiri della Libertà, Teramo, Italy",
    "Terni":                "Piazza Europa, Terni, Italy",
    "Torino":               "Piazza Castello, Torino, Italy",
    "Trapani":              "Piazza Vittorio Veneto, Trapani, Italy",
    "Trento":               "Piazza del Duomo, Trento, Italy",
    "Treviso":              "Piazza dei Signori, Treviso, Italy",
    "Trieste":              "Piazza Unità d'Italia, Trieste, Italy",
    "Udine":                "Piazza Libertà, Udine, Italy",
    "Urbino":               "Piazza della Repubblica, Urbino, Italy",
    "Varese":               "Piazza Monte Grappa, Varese, Italy",
    "Venezia":              "Piazza San Marco, Venezia, Italy",
    "Vercelli":             "Piazza Cavour, Vercelli, Italy",
    "Verona":               "Piazza Bra, Verona, Italy",
    "Vicenza":              "Piazza dei Signori, Vicenza, Italy",
    "Viterbo":              "Piazza del Plebiscito, Viterbo, Italy",
}

TRANSPORT_CATEGORIES = {
    "stazione_treno": [{"railway": "station"}, {"railway": "halt"}],
    "metro":          [{"railway": "subway_station"}, {"station": "subway"}, {"railway": "station", "station": "subway"}],
    "pullman":        [{"highway": "bus_stop"}, {"amenity": "bus_station"}],
}


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def nominatim(query: str) -> tuple[float, float] | None:
    for _ in range(3):
        try:
            r = requests.get(NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"])
            elif r.status_code == 429:
                time.sleep(15)
        except requests.RequestException:
            time.sleep(2)
        time.sleep(1)
    return None


def overpass_query(ql: str) -> list[dict]:
    for attempt in range(4):
        try:
            r = requests.post(OVERPASS_URL, data={"data": ql}, headers=HEADERS, timeout=50)
            if r.status_code == 200:
                return r.json().get("elements", [])
            elif r.status_code == 429:
                time.sleep(15 * (attempt + 1))
            elif r.status_code in (502, 503, 504):
                time.sleep(10 * (attempt + 1))
        except requests.RequestException:
            time.sleep(5)
    return []


def build_overpass_query(lat, lon, radius, tag_groups):
    parts = []
    for tags in tag_groups:
        for ntype in ("node", "way", "relation"):
            filters = "".join(f'["{k}"="{v}"]' for k, v in tags.items())
            parts.append(f'  {ntype}(around:{radius},{lat},{lon}){filters};')
    return f"[out:json][timeout:40];\n(\n" + "\n".join(parts) + "\n);\nout center;"


def nearest_dist(elements, ref_lat, ref_lon):
    count = len(elements)
    if count == 0:
        return 0, None
    min_d = float("inf")
    for el in elements:
        if el["type"] == "node":
            elat, elon = el.get("lat"), el.get("lon")
        else:
            c = el.get("center", {})
            elat, elon = c.get("lat"), c.get("lon")
        if elat and elon:
            min_d = min(min_d, haversine_m(ref_lat, ref_lon, elat, elon))
    return count, round(min_d, 1) if min_d != float("inf") else None


def geocode_city(city: str, prov: str) -> tuple[float, float] | None:
    """Geocodifica il centro fisico della città (non l'università)."""
    for q in [f"{city}, {prov}, Italy", f"{city}, Italy"]:
        coords = nominatim(q)
        if coords:
            return coords
    return None


def get_centro_coords(city: str, uni_lat: float, uni_lon: float) -> tuple[float, float, str] | None:
    """Piazza principale o centroide admin."""
    if city in PIAZZA_CURATA:
        coords = nominatim(PIAZZA_CURATA[city])
        time.sleep(1)
        if coords:
            return coords[0], coords[1], f"curata: {PIAZZA_CURATA[city].split(',')[0]}"

    # Centroide admin
    ql = f'[out:json][timeout:30];\nrelation["admin_level"="8"]["name"="{city}"]["boundary"="administrative"];\nout center;'
    els = overpass_query(ql)
    time.sleep(1.5)
    if els:
        c = els[0].get("center", {})
        if c:
            return c["lat"], c["lon"], "centroide admin"

    # Fallback Nominatim sulla città
    coords = nominatim(f"{city}, Italy")
    if coords:
        return coords[0], coords[1], "Nominatim città"
    return None


def load_ckpt():
    p = Path(CHECKPOINT)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_ckpt(data):
    Path(CHECKPOINT).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    print("Caricamento dati…")
    df = pd.read_excel(INPUT_FILE)
    ckpt_v3 = json.loads(Path(r"C:\Users\Utente\Desktop\DISTANZA\checkpoint_v3.json").read_text(encoding="utf-8"))
    ckpt_centro = json.loads(Path(r"C:\Users\Utente\Desktop\DISTANZA\checkpoint_centro.json").read_text(encoding="utf-8"))
    ckpt_fix = load_ckpt()

    sede_keys = ["Università (nome esteso)", "Ateneo (nome breve)", "Città Ateneo", "Provincia Sede Corso"]
    unique = df[sede_keys].drop_duplicates().reset_index(drop=True)

    # Identifica sedi da correggere
    da_correggere = []
    for _, row in unique.iterrows():
        uni_name = row["Università (nome esteso)"]
        city     = row["Città Ateneo"]
        ck_key   = f"{uni_name}||{city}"
        v3       = ckpt_v3.get(ck_key, {})
        centro   = ckpt_centro.get(ck_key, {})
        if not v3 or not v3.get("lat"):
            continue
        if not centro or not centro.get("centro_lat"):
            continue
        dist = haversine_m(v3["lat"], v3["lon"], centro["centro_lat"], centro["centro_lon"])
        if dist > SOGLIA_KM * 1000:
            da_correggere.append(row)

    total = len(da_correggere)
    print(f"Sedi da correggere: {total}\n")

    for idx, row in enumerate(da_correggere):
        uni_name = row["Università (nome esteso)"]
        city     = row["Città Ateneo"]
        prov     = row["Provincia Sede Corso"]
        ck_key   = f"{uni_name}||{city}"

        if ck_key in ckpt_fix:
            print(f"[{idx+1}/{total}] {city} — skip")
            continue

        print(f"[{idx+1}/{total}] {row['Ateneo (nome breve)']} — {city}")

        # 1. Nuove coordinate: geocodifica dalla città
        coords = geocode_city(city, prov)
        time.sleep(1)
        if not coords:
            print(f"  GEOCODING CITTÀ FALLITO")
            ckpt_fix[ck_key] = {}
            save_ckpt(ckpt_fix)
            continue

        lat, lon = coords
        print(f"  Nuove coord (città): {lat:.5f}, {lon:.5f}")

        result = {"lat": lat, "lon": lon}

        # 2. Trasporti via Overpass
        for cat, tag_groups in TRANSPORT_CATEGORIES.items():
            ql = build_overpass_query(lat, lon, RADIUS_M, tag_groups)
            els = overpass_query(ql)
            count, dist = nearest_dist(els, lat, lon)
            result[f"{cat}_count"] = count
            result[f"{cat}_dist_m"] = dist
            dist_str = f"{dist:.0f}m" if dist is not None else "—"
            print(f"    {cat}: {count} trovati, più vicino a {dist_str}")
            time.sleep(1.5)

        # 3. Centro città
        centro = get_centro_coords(city, lat, lon)
        if centro:
            clat, clon, metodo = centro
            result["centro_dist_m"]  = round(haversine_m(lat, lon, clat, clon), 1)
            result["centro_metodo"]  = metodo
            print(f"    centro: {result['centro_dist_m']:.0f}m ({metodo})")
        else:
            result["centro_dist_m"] = None
            result["centro_metodo"] = None
            print(f"    centro: non trovato")

        ckpt_fix[ck_key] = result
        save_ckpt(ckpt_fix)

    # ── Applica correzioni al dataframe ─────────────────────────────────────
    print("\nApplico correzioni al dataset…")
    corrette = 0
    for idx, row in df.iterrows():
        ck_key = f"{row['Università (nome esteso)']}||{row['Città Ateneo']}"
        fix = ckpt_fix.get(ck_key)
        if not fix:
            continue
        for cat in TRANSPORT_CATEGORIES:
            df.at[idx, f"{cat}_count"]  = fix.get(f"{cat}_count")
            df.at[idx, f"{cat}_dist_m"] = fix.get(f"{cat}_dist_m")
        df.at[idx, "centro_dist_m"] = fix.get("centro_dist_m")
        df.at[idx, "centro_metodo"] = fix.get("centro_metodo")
        corrette += 1

    # Converti tipi
    for cat in TRANSPORT_CATEGORIES:
        df[f"{cat}_count"]  = pd.to_numeric(df[f"{cat}_count"],  errors="coerce").astype("Int64")
        df[f"{cat}_dist_m"] = pd.to_numeric(df[f"{cat}_dist_m"], errors="coerce").round(1)
    df["centro_dist_m"] = pd.to_numeric(df["centro_dist_m"], errors="coerce").round(1)

    print(f"Salvataggio {OUTPUT_FILE}…")
    df.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")

    print(f"\nRighe corrette: {corrette}/{len(df)}")
    print("COMPLETATO.")


if __name__ == "__main__":
    main()
