# route source plan

## currently imported

- gravelmap public minnesota city browse pages
- gravelmap public route pages
- gravelmap public gpx endpoints
- OSRM public route API for drive estimates
- OpenStreetMap tiles for display

## good next sources to add

these are feasible as long as the route page or gpx file is public:

1. ride with gps public routes
   - best path: import manually saved/public gpx links or public route exports where accessible
   - limitation: bulk search and exports may require account/session and should not be scraped aggressively

2. strava public routes/segments
   - best path: import specific route links or gpx files exported by the owner
   - limitation: most useful route data is login-gated and should not be bypassed

3. local event pages
   - examples: almanzo, heck of the north, filthy 50, local gravel fondos/races
   - best path: scrape linked gpx/ridewithgps/strava/course files from public event pages

4. local club/blog route libraries
   - best path: crawl public pages for gpx/tcx/fit/geojson links and normalize them

5. openstreetmap/overpass
   - use for true surface matching and route enrichment, not necessarily as a route source
   - planned: match route coordinates to osm ways and compute gravel/paved/unknown percentages

## import format

add manual external routes to `data/manual/routes.csv` or drop gpx files into `data/manual/gpx/`, then run a future importer to merge them into `data/routes.json`.
