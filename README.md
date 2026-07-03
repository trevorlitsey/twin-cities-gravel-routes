# twin cities gravel route finder

standalone static web app for browsing public gravel / mixed-surface routes near minneapolis.

live app target: github pages from this repo.

## current data

- current imported route source: public gravelmap city pages + public `/gpx/<route id>` endpoint
- drive time: OSRM estimate from an approximate pleasant ave / minneapolis home area
- surface percentage: source-estimated in this first pass; next step is OSM segment matching against route geometry using `surface`, `highway`, and `tracktype` tags

see `SOURCES.md` for the expansion plan for ride with gps, strava, local event pages, club/blog libraries, and OSM surface matching.

## local preview

```bash
python3 -m http.server 8766
# open http://localhost:8766/
```

## refresh gravelmap data

```bash
python3 scripts/scrape_gravelmap.py
```

## import future manual/public external routes

```bash
python3 scripts/import_manual_routes.py
```
