# Campus Transport Distance Mapper

Enriches Italian university datasets with **real-time transport proximity data** — for each university, it calculates the distance to the nearest train station, metro stop, bus stop, and city center using open geospatial APIs.

## What it does

For each university in the dataset:
- Finds the **nearest train station** (via Overpass API + OpenStreetMap)
- Finds the **nearest metro station**
- Finds the **nearest bus stop**
- Calculates distance to **city center** (centroid of the main square)
- Computes walking/distance scores for student accessibility

## How it works

```
University address
    └─ Nominatim (OSM) → GPS coordinates
    └─ Overpass API → nearby transport nodes
    └─ Haversine formula → distance in meters
    └─ Enriched dataset (JSON/CSV output)
```

Includes crash recovery via checkpoint files — the enrichment can be stopped and resumed without losing progress.

## Scripts

| File | Purpose |
|---|---|
| `poi_enricher_v3.py` | Main enricher (train + metro + bus + centroid) |
| `poi_enricher_v2.py` | Earlier version — metro + bus only |
| `centro_piazza.py` | City center geocoding helper |
| `test_centroide.py` | Centroid calculation tests |
| `test_piazza.py` | Main square geocoding tests |
| `fix_satellite.py` | Coordinate correction utilities |

## Tech stack

- Python 3
- `requests` — Nominatim + Overpass API calls
- `json` — checkpoint management
- OpenStreetMap data via [Overpass API](https://overpass-api.de)
- [Nominatim](https://nominatim.org) — free geocoding, no key required

## Usage

```bash
pip install requests
python poi_enricher_v3.py
```

Checkpoint is saved automatically every N universities — safe to interrupt and resume.

## Topics

`python` `geolocation` `openstreetmap` `overpass-api` `nominatim` `distance-calculation` `universities` `transport` `gis`
