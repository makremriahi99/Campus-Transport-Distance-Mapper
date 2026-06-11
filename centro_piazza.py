#!/usr/bin/env python3
"""
Ricalcola centro_dist_m con approccio ibrido:
  - Grandi città: piazza principale curata manualmente → geocodifica via Nominatim
  - Città minori: place=square con tag wikidata in OSM (più vicina al centroide admin)
  - Fallback: centroide admin via Overpass
Aggiorna dataset_universita_TRASPORTI.xlsx con la colonna corretta.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json, math, time
from pathlib import Path
import pandas as pd
import requests

INPUT_FILE   = r"C:\Users\Utente\Desktop\DISTANZA\dataset_universita_TRASPORTI.xlsx"
OUTPUT_FILE  = r"C:\Users\Utente\Desktop\DISTANZA\dataset_universita_TRASPORTI.xlsx"
CHECKPOINT   = r"C:\Users\Utente\Desktop\DISTANZA\checkpoint_centro.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
HEADERS       = {"User-Agent": "UniversityCentroEnricher/1.0 (educational project)"}

# ── Mappa curata: città → piazza principale ───────────────────────────────────
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
    "Caserta":              "Piazza Dante, Caserta, Italy",
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


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def nominatim_geocode(query: str) -> tuple[float, float] | None:
    for attempt in range(3):
        try:
            r = requests.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers=HEADERS, timeout=10
            )
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
    for attempt in range(3):
        try:
            r = requests.post(OVERPASS_URL, data={"data": ql}, headers=HEADERS, timeout=35)
            if r.status_code == 200:
                return r.json().get("elements", [])
            elif r.status_code == 429:
                time.sleep(15 * (attempt + 1))
            elif r.status_code in (502, 503, 504):
                time.sleep(10 * (attempt + 1))
        except requests.RequestException:
            time.sleep(5)
    return []


def el_coords(el: dict) -> tuple[float, float] | None:
    if el["type"] == "node":
        lat, lon = el.get("lat"), el.get("lon")
    else:
        c = el.get("center", {})
        lat, lon = c.get("lat"), c.get("lon")
    return (lat, lon) if lat and lon else None


def centroide_admin(city: str) -> tuple[float, float] | None:
    ql = f"""
[out:json][timeout:30];
relation["admin_level"="8"]["name"="{city}"]["boundary"="administrative"];
out center;
"""
    els = overpass_query(ql)
    if els:
        c = els[0].get("center", {})
        if c:
            return c["lat"], c["lon"]
    return None


def piazza_osm_wikidata(city: str, ref_lat: float, ref_lon: float) -> tuple[float, float, str] | None:
    """Cerca place=square con tag wikidata dentro il comune, prende la più vicina al centroide."""
    ql = f"""
[out:json][timeout:30];
area["admin_level"="8"]["name"="{city}"]->.a;
(
  node["place"="square"]["wikidata"](area.a);
  way["place"="square"]["wikidata"](area.a);
);
out center;
"""
    els = overpass_query(ql)
    time.sleep(1.5)
    if not els:
        return None
    best, best_d, best_name = None, float("inf"), ""
    for el in els:
        coords = el_coords(el)
        if coords:
            d = haversine_m(ref_lat, ref_lon, *coords)
            if d < best_d:
                best_d, best = d, coords
                best_name = el.get("tags", {}).get("name", "?")
    return (*best, best_name) if best else None


def get_centro(city: str, uni_lat: float, uni_lon: float) -> tuple[float | None, float | None, str]:
    """Restituisce (lat, lon, metodo) del punto di riferimento centrale."""

    # ── 1. Piazza curata manualmente ────────────────────────────────────────
    if city in PIAZZA_CURATA:
        coords = nominatim_geocode(PIAZZA_CURATA[city])
        time.sleep(1)
        if coords:
            return coords[0], coords[1], f"curata: {PIAZZA_CURATA[city].split(',')[0]}"

    # ── 2. Centroide admin per trovare il punto di riferimento OSM ──────────
    centroide = centroide_admin(city)
    time.sleep(1.5)
    ref_lat = centroide[0] if centroide else uni_lat
    ref_lon = centroide[1] if centroide else uni_lon

    # ── 3. place=square con wikidata nel comune ──────────────────────────────
    result = piazza_osm_wikidata(city, ref_lat, ref_lon)
    if result:
        lat, lon, name = result
        return lat, lon, f"OSM piazza wikidata: {name}"

    # ── 4. Fallback: centroide amministrativo ────────────────────────────────
    if centroide:
        return centroide[0], centroide[1], "centroide admin (fallback)"

    return None, None, "non trovato"


def load_ckpt() -> dict:
    p = Path(CHECKPOINT)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_ckpt(data: dict):
    Path(CHECKPOINT).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    print("Caricamento dataset…")
    df = pd.read_excel(INPUT_FILE)
    print(f"  {len(df)} righe")

    # Sedi uniche con le coordinate uni già nel dataset v3
    sede_keys = ["Università (nome esteso)", "Città Ateneo", "Provincia Sede Corso"]
    unique = df[sede_keys + ["stazione_treno_dist_m"]].drop_duplicates(subset=sede_keys).reset_index(drop=True)
    total = len(unique)
    print(f"  Sedi uniche: {total}")

    # Recupera coordinate uni dal checkpoint v3
    ckpt_v3_path = r"C:\Users\Utente\Desktop\DISTANZA\checkpoint_v3.json"
    ckpt_v3 = json.loads(Path(ckpt_v3_path).read_text(encoding="utf-8"))

    ckpt = load_ckpt()
    print(f"  Checkpoint centro: {len(ckpt)} già elaborate\n")

    for idx, row in unique.iterrows():
        uni_name = row["Università (nome esteso)"]
        city     = row["Città Ateneo"]
        prov     = row["Provincia Sede Corso"]
        ck_key   = f"{uni_name}||{city}"

        if ck_key in ckpt:
            continue

        # Recupera coordinate uni dal checkpoint v3
        v3_rec = ckpt_v3.get(ck_key, {})
        uni_lat = v3_rec.get("lat")
        uni_lon = v3_rec.get("lon")
        if not uni_lat:
            print(f"[{idx+1}/{total}] {city}: coords uni mancanti, skip")
            ckpt[ck_key] = {}
            save_ckpt(ckpt)
            continue

        print(f"[{idx+1}/{total}] {city} ({'curata' if city in PIAZZA_CURATA else 'auto'})")
        lat, lon, metodo = get_centro(city, uni_lat, uni_lon)

        if lat:
            dist = round(haversine_m(uni_lat, uni_lon, lat, lon), 1)
            print(f"  → {metodo} | {dist:.0f}m")
            ckpt[ck_key] = {"centro_lat": lat, "centro_lon": lon,
                            "centro_dist_m": dist, "centro_metodo": metodo}
        else:
            print(f"  → non trovato")
            ckpt[ck_key] = {}

        save_ckpt(ckpt)
        time.sleep(0.5)

    # ── Applica al dataframe ─────────────────────────────────────────────────
    print("\nApplico al dataset…")
    df["centro_dist_m"]  = None
    df["centro_metodo"]  = None

    for idx, row in df.iterrows():
        ck_key = f"{row['Università (nome esteso)']}||{row['Città Ateneo']}"
        rec = ckpt.get(ck_key, {})
        if rec:
            df.at[idx, "centro_dist_m"] = rec.get("centro_dist_m")
            df.at[idx, "centro_metodo"] = rec.get("centro_metodo")

    df["centro_dist_m"] = pd.to_numeric(df["centro_dist_m"], errors="coerce").round(1)

    print(f"Salvataggio {OUTPUT_FILE}…")
    df.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")

    # ── Riepilogo ────────────────────────────────────────────────────────────
    metodi = df["centro_metodo"].dropna().value_counts()
    copertura = df["centro_dist_m"].notna().sum()
    print(f"\nCopertura: {copertura}/{len(df)} righe ({copertura/len(df)*100:.1f}%)")
    print("\nMetodi usati:")
    for m, n in metodi.items():
        label = m.split(":")[0] if ":" in m else m
        print(f"  {label}: {n} righe")
    print("\nCOMPLETATO.")


if __name__ == "__main__":
    main()
