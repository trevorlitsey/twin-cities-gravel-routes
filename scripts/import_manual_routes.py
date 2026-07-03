#!/usr/bin/env python3
"""placeholder importer for future non-gravelmap routes.

intended inputs:
- data/manual/routes.csv with public source/gpx urls
- data/manual/gpx/*.gpx for files manually exported from rwgps/strava/event pages

this script is intentionally conservative: it does not bypass logins or scrape private data.
"""
from pathlib import Path
import csv, json

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "manual" / "routes.csv"
ROUTES = ROOT / "data" / "routes.json"


def main():
    rows = []
    if CSV.exists():
        with CSV.open(newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get("name")]
    data = json.loads(ROUTES.read_text(encoding="utf-8")) if ROUTES.exists() else {"routes": []}
    print(f"manual rows ready to import: {len(rows)}")
    print(f"existing route dataset: {len(data.get('routes', []))} routes")
    print("next step: parse gpx/source metadata and merge by stable source id")

if __name__ == "__main__":
    main()
