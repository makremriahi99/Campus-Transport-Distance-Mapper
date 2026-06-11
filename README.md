# Calcolatore Distanze Trasporti — Campus Universitari Italiani

Tool per l'**arricchimento di dati universitari italiani** con informazioni di prossimità ai trasporti pubblici, usando Nominatim per la geocodifica e l'API Overpass per i dati OpenStreetMap.

## Dataset

I file Excel non sono inclusi nel repository per via delle dimensioni.  
Scaricali da Kaggle:

```bash
kaggle datasets download -d makremriahi/italian-universities-dataset
```

oppure visita: [Italian Universities - POI and Transport Data — Kaggle](https://www.kaggle.com/datasets/makremriahi/italian-universities-dataset)

| File dataset | Contenuto |
|---|---|
| `dataset_universita_TOTALMENTE_COMPLETO.xlsx` | Dataset completo degli atenei italiani |
| `dataset_universita_POI.xlsx` | Punti di interesse vicino ai campus |
| `dataset_universita_TRASPORTI.xlsx` | Distanze da fermate trasporto pubblico |

## Come funziona

```
Indirizzi università
    └─ Geocodifica con Nominatim (OpenStreetMap)
    └─ Query Overpass API → fermate metro, bus, treni vicine
    └─ Calcolo distanze campus ↔ trasporto pubblico
    └─ Esportazione in Excel con checkpoint di ripresa
```

## Come si usa

```bash
pip install requests pandas openpyxl
python distance_mapper.py
```

I checkpoint JSON permettono di riprendere l'elaborazione in caso di interruzione.

## File

| File | Descrizione |
|---|---|
| `scraper_info_atenei.py` | Scraper dati atenei |
| `scraper_ateneo_stats.py` | Scraper statistiche ateneo |
| `genera_descrizioni.py` | Generazione descrizioni atenei |
| `aggiungi_citta_its.py` | Aggiunta città ITS al dataset |
| `checkpoint*.json` | Checkpoint per ripresa elaborazione |

## Tecnologie

- `Nominatim` (OpenStreetMap) — geocodifica indirizzi
- `Overpass API` — dati OSM (fermate, stazioni)
- `pandas` — elaborazione e export dati
- `openpyxl` — gestione file Excel

## Tag

`python` `openstreetmap` `nominatim` `overpass-api` `geolocalizzazione` `trasporti` `università` `pandas` `italia`
