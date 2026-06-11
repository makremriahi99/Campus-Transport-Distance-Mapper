# Calcolatore Distanze Trasporti — Campus Universitari

Tool per l'**arricchimento di POI (Punti di Interesse)** universitari con dati di prossimità ai trasporti pubblici, usando Nominatim per la geocodifica e l'API Overpass per i dati OpenStreetMap.

## Cosa fa

- Geocodifica automatica degli indirizzi universitari con Nominatim
- Ricerca dei mezzi di trasporto vicini (metro, bus, treni) tramite Overpass API
- Calcolo delle distanze tra campus e fermate del trasporto pubblico
- Esportazione dei risultati in CSV/Excel con checkpoint di ripresa

## Come si usa

```bash
pip install requests pandas openpyxl
python distance_mapper.py
```

## Tecnologie

- `Nominatim` (OpenStreetMap) — geocodifica indirizzi
- `Overpass API` — query sui dati OSM (fermate, stazioni)
- `pandas` — elaborazione e export dati
- Checkpoint JSON per riprendere elaborazioni interrotte

## Tag

`python` `openstreetmap` `nominatim` `overpass-api` `geolocalizzazione` `trasporti` `università` `pandas`
