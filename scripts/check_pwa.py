#!/usr/bin/env python3
"""verify the static app has the minimum pwa wiring."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def assert_contains(haystack: str, needle: str, label: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"missing {label}: {needle}")


def main() -> None:
    index = (ROOT / "index.html").read_text()
    assert_contains(index, 'rel="manifest"', "manifest link")
    assert_contains(index, 'name="theme-color"', "theme color meta")
    assert_contains(index, "serviceWorker.register", "service worker registration")

    manifest_path = ROOT / "manifest.webmanifest"
    if not manifest_path.exists():
        raise AssertionError("missing manifest.webmanifest")
    manifest = json.loads(manifest_path.read_text())

    expected = {
        "name": "twin cities gravel route finder",
        "short_name": "tc gravel",
        "start_url": "./",
        "display": "standalone",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise AssertionError(f"manifest {key!r} expected {value!r}, got {manifest.get(key)!r}")

    icons = manifest.get("icons", [])
    icon_srcs = {icon.get("src") for icon in icons}
    for src in {"./icons/icon-192.png", "./icons/icon-512.png"}:
        if src not in icon_srcs:
            raise AssertionError(f"manifest missing icon {src}")
        if not (ROOT / src.removeprefix("./")).exists():
            raise AssertionError(f"icon file missing {src}")

    sw_path = ROOT / "sw.js"
    if not sw_path.exists():
        raise AssertionError("missing sw.js")
    sw = sw_path.read_text()
    for asset in ["./", "./index.html", "./styles.css", "./app.js", "./data/routes.json"]:
        assert_contains(sw, asset, f"service worker precache asset {asset}")
    assert_contains(sw, "fetch", "service worker fetch handler")
    assert_contains(sw, "caches.open", "service worker cache usage")

    print("pwa checks passed")


if __name__ == "__main__":
    main()
