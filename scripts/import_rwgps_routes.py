#!/usr/bin/env python3
"""import public ridewithgps route json into the static route dataset.

uses only public `/routes/<id>.json` endpoints. gpx/tcx export endpoints are not used
because they are login-gated for the routes tested.
"""
import json, math, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "manual" / "rwgps_routes.json"
DATASET = ROOT / "data" / "routes.json"
HOME = {"lat": 44.9632163, "lon": -93.2833701, "label": "pleasant ave / minneapolis home area (approx; exact address was not geocodable)"}
UA = "Mozilla/5.0 (compatible; hermes-twin-cities-gravel-routes/0.2; +https://github.com/trevorlitsey/twin-cities-gravel-routes)"

SURFACE_DEFAULTS = {
    "mostly_unpaved": 75,
    "mixed_surfaces": 45,
    "mostly_paved": 20,
    "paved": 0,
    "unknown": 35,
    None: 35,
}


def fetch_json(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            last = e
            time.sleep(0.5 * (i + 1))
    raise last or RuntimeError(f"failed to fetch {url}")


def haversine_m(a, b, c, d):
    R = 6371000
    p1 = math.radians(a); p2 = math.radians(c); dp = math.radians(c-a); dl = math.radians(d-b)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(x))


def sample_coords(coords, max_points=450):
    if len(coords) <= max_points:
        return coords
    step = max(1, math.ceil(len(coords) / max_points))
    sampled = coords[::step]
    if sampled[-1] != coords[-1]:
        sampled.append(coords[-1])
    return sampled


def osrm_drive(start):
    straight = haversine_m(HOME['lat'], HOME['lon'], start['lat'], start['lon']) / 1609.344
    fallback = round((straight / 42) * 60 + 8)
    try:
        url = ("https://router.project-osrm.org/route/v1/driving/"
               f"{HOME['lon']},{HOME['lat']};{start['lon']},{start['lat']}?overview=false")
        data = fetch_json(url, tries=1)
        route = data.get('routes', [{}])[0]
        if route.get('duration'):
            return round(route['duration'] / 60), round(route.get('distance', 0) / 1609.344, 1), "OSRM driving estimate from approximate home area"
    except Exception:
        pass
    return fallback, None, "fallback straight-line estimate; OSRM failed"


def convert(entry):
    rid = int(entry['id'])
    src_url = f"https://ridewithgps.com/routes/{rid}"
    data = fetch_json(src_url + ".json")
    points = data.get('track_points') or []
    coords = []
    for p in points:
        # rwgps track points use x=longitude, y=latitude
        if p.get('x') is not None and p.get('y') is not None:
            coords.append([round(float(p['y']), 6), round(float(p['x']), 6)])
    if not coords:
        raise ValueError(f"route {rid} has no public track_points")
    start = {"lat": coords[0][0], "lon": coords[0][1]}
    drive, drive_dist, drive_method = osrm_drive(start)
    surface_key = data.get('surface') or data.get('surface_type') or data.get('pavement_type')
    unpaved = data.get('unpaved_pct')
    if unpaved is None:
        gravel = SURFACE_DEFAULTS.get(surface_key, 35)
        method = f"Ride with GPS surface label '{surface_key}' mapped to estimate; OSM segment matching pending"
    else:
        gravel = int(round(float(unpaved)))
        method = "Ride with GPS public unpaved_pct; OSM segment matching pending"
    distance_m = float(data.get('distance') or 0)
    gain_m = data.get('elevation_gain')
    desc = (data.get('description') or entry.get('why') or "").strip()
    city = ', '.join(x for x in [data.get('locality'), data.get('administrative_area')] if x) or entry.get('query', '')
    return {
        "id": f"rwgps-{rid}",
        "name": data.get('name') or f"Ride with GPS route {rid}",
        "source": "Ride with GPS",
        "sourceUrl": src_url,
        "dataUrl": src_url + ".json",
        "gpxUrl": None,
        "city": city,
        "distanceMi": round(distance_m / 1609.344, 1),
        "elevationGainFt": round(float(gain_m) * 3.28084) if gain_m is not None else None,
        "surface": {"gravelPct": max(0, min(100, gravel)), "pavedPct": max(0, 100 - max(0, min(100, gravel)) - 5), "unknownPct": 5, "method": method, "label": surface_key},
        "driveMinutes": drive,
        "driveDistanceMi": drive_dist,
        "driveMethod": drive_method,
        "start": start,
        "description": desc or f"Public Ride with GPS route by {data.get('bylineName') or 'unknown author'}.",
        "byline": entry.get('bylineName') or (data.get('user') or {}).get('name'),
        "photos": [],
        "coordinates": sample_coords(coords),
    }


def main():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    dataset = json.loads(DATASET.read_text(encoding='utf-8'))
    existing = {r['id']: r for r in dataset.get('routes', [])}
    imported = []
    for entry in manifest.get('routes', []):
        try:
            r = convert(entry)
            # keep only useful app-scope routes: local-ish drive, plausible gravel/mixed, reasonable ride length
            if r['driveMinutes'] <= 110 and 3 <= r['distanceMi'] <= 130 and r['surface']['gravelPct'] >= 15:
                existing[r['id']] = r
                imported.append(r)
            else:
                print('skipped scope/filter', r['id'], r['driveMinutes'], r['distanceMi'], r['surface']['gravelPct'], r['name'])
        except Exception as e:
            print('failed', entry.get('id'), e)
        time.sleep(0.2)
    routes = list(existing.values())
    routes.sort(key=lambda r: (r.get('driveMinutes') or 999, r.get('source') != 'Ride with GPS', r.get('distanceMi') or 0))
    dataset['routes'] = routes
    dataset['generatedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    notes = dataset.setdefault('notes', [])
    note = "added public Ride with GPS route JSON imports; GPX export links are omitted when login-gated"
    if note not in notes:
        notes.append(note)
    DATASET.write_text(json.dumps(dataset, indent=2), encoding='utf-8')
    print(f"imported/updated {len(imported)} Ride with GPS routes; dataset now has {len(routes)} routes")
    for r in imported:
        print(r['driveMinutes'], r['distanceMi'], r['surface']['gravelPct'], r['name'])

if __name__ == '__main__':
    main()
