"""
Parsa il log e genera Excel parziale usando i numeri di record [N/309]
per mappare direttamente alle sedi univoche del dataset originale.
"""
import re
import math
import pandas as pd

LOG_FILE    = r"C:\Users\Utente\AppData\Local\Temp\claude\C--Users-Utente-Desktop-DISTANZA\d2429238-666e-4a7e-8d7b-56357ea1818b\tasks\bnxh6ayvd.output"
INPUT_FILE  = r"C:\Users\Utente\Downloads\dataset_universita_ARRICCHITO.xlsx"
OUTPUT_FILE = r"C:\Users\Utente\Desktop\DISTANZA\dataset_universita_POI_parziale.xlsx"

CATS = ["cinema", "palestre", "bar", "ristoranti", "mense"]

# ── 1. Carica dataset e ricava unique_sedi NELLO STESSO ORDINE dello script ──
df = pd.read_excel(INPUT_FILE)
sede_keys = ["Ateneo (nome breve)", "Città Ateneo", "Provincia Sede Corso"]
unique_sedi = df[sede_keys].drop_duplicates().reset_index(drop=True)
# L'indice 0-based corrisponde al numero 1-based nel log

# ── 2. Leggi log ──
with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
    raw = f.read()

blocks = re.split(r'\[(\d+)/309\]', raw)
# blocks: ['header_text', '1', 'blocco1', '2', 'blocco2', ...]

# ── 3. Parsa ogni blocco ──
records = {}   # num (1-based) → dict con dati POI

i = 1
while i + 1 < len(blocks):
    num  = int(blocks[i])
    body = blocks[i + 1]
    i += 2

    rec = {"num": num}
    for cat in CATS:
        # "cinema: 3 POI, min 317m"
        m = re.search(rf'{cat}:\s*(\d+)\s*POI,\s*min\s*([\d.]+)m', body)
        if m:
            rec[f"{cat}_count"] = int(m.group(1))
            rec[f"{cat}_dist_m"] = float(m.group(2))
        else:
            # "cinema: 0 POI"
            m0 = re.search(rf'{cat}:\s*0\s*POI', body)
            rec[f"{cat}_count"] = 0 if m0 else None
            rec[f"{cat}_dist_m"] = float("nan") if m0 else None

    records[num] = rec

print(f"Blocchi parsati: {len(records)}")

# ── 4. Costruisci lookup (ateneo, città) → dati POI ──
poi_by_sede = {}   # (ateneo_norm, city_norm) → rec
for num, rec in records.items():
    idx = num - 1   # 0-based
    if idx >= len(unique_sedi):
        print(f"  WARN: num={num} fuori range ({len(unique_sedi)} sedi)")
        continue
    row = unique_sedi.iloc[idx]
    ateneo = str(row["Ateneo (nome breve)"]).strip()
    city   = str(row["Città Ateneo"]).strip()
    print(f"  [{num:3d}] {ateneo[:40]:40s} | {city}")
    poi_by_sede[(ateneo, city)] = rec

# ── 5. Aggiungi colonne al dataframe ──
for cat in CATS:
    df[f"{cat}_count"] = None
    df[f"{cat}_dist_m"] = None
df["raggio_ricerca_m"] = None

matched_rows = 0
for idx, row in df.iterrows():
    ateneo = str(row["Ateneo (nome breve)"]).strip()
    city   = str(row["Città Ateneo"]).strip()
    rec = poi_by_sede.get((ateneo, city))
    if rec:
        for cat in CATS:
            df.at[idx, f"{cat}_count"] = rec.get(f"{cat}_count")
            df.at[idx, f"{cat}_dist_m"] = rec.get(f"{cat}_dist_m")
        df.at[idx, "raggio_ricerca_m"] = 2000
        matched_rows += 1

# ── 6. Converti tipi ──
for cat in CATS:
    df[f"{cat}_count"] = pd.to_numeric(df[f"{cat}_count"], errors="coerce")
    df[f"{cat}_dist_m"] = pd.to_numeric(df[f"{cat}_dist_m"], errors="coerce").round(1)
df["raggio_ricerca_m"] = pd.to_numeric(df["raggio_ricerca_m"], errors="coerce")

# ── 7. Salva ──
df.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")

sedi_con_dati = len(poi_by_sede)
print(f"\nSedi con dati POI:  {sedi_con_dati} / {len(unique_sedi)}")
print(f"Righe dataset aggiornate: {matched_rows} / {len(df)}")
print(f"Salvato: {OUTPUT_FILE}")
