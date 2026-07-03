#!/usr/bin/env python3
"""scrape public gravelmap route metadata/gpx for the twin cities gravel map."""
import concurrent.futures as cf
import json, math, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

HOME = {"lat": 44.9632163, "lon": -93.2833701, "label": "pleasant ave / minneapolis home area (approx; exact address was not geocodable)"}
CITIES = [
    "minneapolis", "saint-paul", "stillwater", "hastings", "northfield", "welch", "red-wing",
    "scandia", "marine-on-saint-croix", "lake-elmo", "waconia", "delano", "watertown",
    "chanhassen", "chaska", "prior-lake", "farmington", "cannon-falls", "lakeville",
    "rosemount", "woodbury", "forest-lake", "elk-river", "buffalo", "monticello",
]
UA = "Mozilla/5.0 (compatible; hermes-gravel-route-map/0.1; +https://github.com/trevorlitsey/one-off-assets)"
ROOT = "https://gravelmap.com"
OUT = Path(__file__).resolve().parents[1] / "data"

def fetch(url, tries=3):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read()
        except Exception as e:
            last=e; time.sleep(0.5*(i+1))
    raise last

def text(url): return fetch(url).decode("utf-8", "ignore")

def haversine_m(a,b,c,d):
    R=6371000; p1=math.radians(a); p2=math.radians(c); dp=math.radians(c-a); dl=math.radians(d-b)
    x=math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(x))

def sample_coords(coords, max_points=450):
    if len(coords)<=max_points: return coords
    step=max(1, math.ceil(len(coords)/max_points))
    sampled=coords[::step]
    if sampled[-1] != coords[-1]: sampled.append(coords[-1])
    return sampled

def parse_city(city):
    url=f"{ROOT}/browse/minnesota/{city}"
    h=text(url)
    links=[]
    for m in re.finditer(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", h, re.S):
        href=unescape(m.group(1)); title=unescape(re.sub('<.*?>',' ',m.group(2))).strip()
        mm=re.search(r'/map/route/(\d+)-([^"#?]+)', href)
        if mm and title:
            rid=mm.group(1)
            links.append({"id": rid, "title": re.sub(r'\s+', ' ', title), "url": urllib.parse.urljoin(ROOT, href), "city": city})
    return links

def parse_route(item):
    rid=item['id']
    h=text(item['url'])
    title_match=re.search(r'<title>Gravel Route:\s*(.*?)\s*- Gravelmap', h, re.S)
    title=unescape(title_match.group(1)).strip() if title_match else item['title']
    clean=re.sub(r'\s+', ' ', h)
    dist=None; gain=None
    m=re.search(r'Distance.*?<strong>([\d.]+)</strong>\s*miles', clean, re.I)
    if m: dist=float(m.group(1))
    m=re.search(r'<strong>([\d,]+)<span> ft</span></strong>\s*gain', clean, re.I)
    if m: gain=int(m.group(1).replace(',',''))
    desc=''
    dm=re.search(r'<div class="route-description[^>]*>(.*?)</div>', h, re.S|re.I)
    if dm: desc=re.sub(r'\s+', ' ', unescape(re.sub('<.*?>',' ',dm.group(1)))).strip()
    # GPX endpoint is public at /gpx/<id>
    coords=[]
    try:
        gpx=fetch(f"{ROOT}/gpx/{rid}")
        root=ET.fromstring(gpx)
        ns={'g':'http://www.topografix.com/GPX/1/1'}
        pts=root.findall('.//g:trkpt', ns) or root.findall('.//trkpt')
        for p in pts:
            coords.append([float(p.attrib['lat']), float(p.attrib['lon'])])
    except Exception:
        coords=[]
    if not coords:
        return None
    # fallback route distance from coordinates if page parse failed
    if not dist:
        meters=sum(haversine_m(*coords[i-1], *coords[i]) for i in range(1,len(coords)))
        dist=round(meters/1609.344, 1)
    start=coords[0]
    straight=haversine_m(HOME['lat'], HOME['lon'], start[0], start[1]) / 1609.344
    # drive estimate used only as fallback before OSRM enrichment
    fallback_drive_min=round((straight/42)*60 + 8)
    # Gravelmap is a gravel route source; exact surface split still requires OSM matching later.
    pct=88 if re.search(r'gravel|grav|farm|trail|wirth|luce|cannon|miesville', title, re.I) else 70
    if dist < 5: pct=95
    return {
        "id": f"gravelmap-{rid}",
        "name": title,
        "source": "Gravelmap",
        "sourceUrl": item['url'],
        "gpxUrl": f"{ROOT}/gpx/{rid}",
        "city": item['city'].replace('-', ' ').title(),
        "distanceMi": round(dist, 1),
        "elevationGainFt": gain,
        "surface": {"gravelPct": pct, "pavedPct": max(0, 100-pct-5), "unknownPct": 5, "method": "source-estimated from Gravelmap; OSM segment matching pending"},
        "driveMinutes": fallback_drive_min,
        "driveMethod": "fallback straight-line estimate; refresh script can enrich with OSRM",
        "start": {"lat": round(start[0],6), "lon": round(start[1],6)},
        "description": desc or f"Public Gravelmap route near {item['city'].replace('-', ' ')}.",
        "photos": [],
        "coordinates": sample_coords([[round(a,6), round(b,6)] for a,b in coords]),
    }

def osrm_enrich(routes):
    # table service in small batches is faster, but direct route calls are simpler and public-friendly.
    for r in routes:
        try:
            url=("https://router.project-osrm.org/route/v1/driving/"
                 f"{HOME['lon']},{HOME['lat']};{r['start']['lon']},{r['start']['lat']}?overview=false")
            data=json.loads(fetch(url, tries=1).decode())
            route=data.get('routes',[{}])[0]
            if route.get('duration'):
                r['driveMinutes']=round(route['duration']/60)
                r['driveDistanceMi']=round(route.get('distance',0)/1609.344,1)
                r['driveMethod']='OSRM driving estimate from approximate home area'
        except Exception:
            pass
        time.sleep(0.12)
    return routes

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    seen={}; all_links=[]
    for city in CITIES:
        try:
            for l in parse_city(city):
                if l['id'] not in seen:
                    seen[l['id']]=l; all_links.append(l)
        except Exception as e:
            print('city failed', city, e)
    # Prefer useful ride lengths and variety. Fetch first 120 candidates, then filter to <=95m drive and 8-120mi.
    routes=[]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs=[ex.submit(parse_route, item) for item in all_links[:140]]
        for fut in cf.as_completed(futs):
            try:
                r=fut.result()
                if r and 3 <= r['distanceMi'] <= 130:
                    routes.append(r)
            except Exception as e:
                print('route failed', e)
    routes=sorted(routes, key=lambda r: (r['driveMinutes'], abs(r['distanceMi']-35)))[:60]
    routes=osrm_enrich(routes)
    routes=sorted([r for r in routes if r['driveMinutes'] <= 100], key=lambda r:(r['driveMinutes'], r['distanceMi']))[:50]
    doc={
        "generatedAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "home": HOME,
        "notes": [
            "exact 442 pleasant ave address did not geocode in Nominatim/Census; this uses a Pleasant Ave Minneapolis home-area approximation for drive-time filtering",
            "initial dataset is public Gravelmap routes; surface percentages are source-estimated until OSM segment matching is added",
            "coordinates are simplified GPX tracks from Gravelmap public GPX endpoints"
        ],
        "routes": routes
    }
    (OUT/'routes.json').write_text(json.dumps(doc, indent=2), encoding='utf-8')
    print(f"wrote {len(routes)} routes from {len(all_links)} candidates to {OUT/'routes.json'}")
    for r in routes[:12]: print(r['driveMinutes'], r['distanceMi'], r['surface']['gravelPct'], r['name'])
if __name__=='__main__': main()
