"""A1: build data/hotspots/delhi_hotspots.json from researched spot lists.

Input  : research JSON files ({"spots": [...]}) given on the command line, plus
         data/hotspots/curation.json (hand-checked overrides: coordinates, Hindi
         names, drops, merges).
Output : data/hotspots/delhi_hotspots.json   base Hotspot fields (no DEM factors yet)
         data/hotspots/delhi_hotspots.geojson for eyeballing pins on a map
         data/hotspots/geocode_cache.json     Nominatim responses, so reruns are offline

Geocoding uses OSM Nominatim at one request a second with an identifying
User-Agent, per https://operations.osmfoundation.org/policies/nominatim/.
"""
import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "hotspots"
CACHE = OUT / "geocode_cache.json"
CURATION = OUT / "curation.json"
UA = "wlew-ews/0.1 (+https://github.com/Shash-012/waterlogging-aws)"
BBOX = (28.40, 28.90, 76.80, 77.40)  # lat_min, lat_max, lon_min, lon_max
MERGE_M = 150
SEASONS = range(2019, 2026)


def haversine_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def in_delhi(lat, lon):
    return BBOX[0] <= lat <= BBOX[1] and BBOX[2] <= lon <= BBOX[3]


class Nominatim:
    def __init__(self):
        self.cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        self.last = 0.0

    def _get(self, url, params):
        key = url + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
        if key not in self.cache:
            wait = 1.1 - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait)
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=30)
            self.last = time.monotonic()
            r.raise_for_status()
            self.cache[key] = r.json()
            CACHE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")
        return self.cache[key]

    def search(self, q):
        return self._get("https://nominatim.openstreetmap.org/search", {
            "q": q, "format": "jsonv2", "limit": 3, "countrycodes": "in",
            "viewbox": f"{BBOX[2]},{BBOX[1]},{BBOX[3]},{BBOX[0]}", "bounded": 1})

    def reverse(self, lat, lon):
        return self._get("https://nominatim.openstreetmap.org/reverse", {
            "lat": f"{lat:.5f}", "lon": f"{lon:.5f}", "format": "jsonv2", "zoom": 17})


def to_hindi(text, words, problems):
    """Transliterate a road description word by word using the curated glossary."""
    out = []
    for tok in re.split(r"(\W+)", text):
        if not tok or re.fullmatch(r"\W+|\d+", tok):
            out.append(tok)
        elif tok in words:
            out.append(words[tok])
        else:
            problems.append(f"no Hindi for road word '{tok}'")
            out.append(tok)
    return "".join(out)


def seasons_of(spot):
    years = {r["year"] for r in spot.get("reports", []) if r.get("year") in SEASONS and r.get("url")}
    return years


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("research", nargs="+", type=Path)
    ap.add_argument("--report", action="store_true", help="print a per-spot check table")
    args = ap.parse_args()

    cur = json.loads(CURATION.read_text(encoding="utf-8")) if CURATION.exists() else {}
    drops = set(cur.get("drop", []))
    coords = cur.get("coords", {})
    queries = cur.get("queries", {})
    names_hi = cur.get("names_hi", {})
    road_words_hi = cur.get("road_words_hi", {})
    merge_into = cur.get("merge_into", {})
    rename = cur.get("rename", {})
    site_types = cur.get("site_type", {})
    first = cur.get("first", "Minto Bridge underpass")

    spots = []
    for path in args.research:
        spots += json.loads(path.read_text(encoding="utf-8"))["spots"]
    spots = [s for s in spots if s["name_en"] not in drops]
    for s in spots:
        s["site_type"] = site_types.get(s["name_en"], s["site_type"])

    nom = Nominatim()
    problems = []
    for s in spots:
        name = s["name_en"]
        if name in coords:
            s["lat"], s["lon"] = coords[name]
            s["geo_from"] = "curated"
        else:
            hits = nom.search(queries.get(name, s["query"]))
            hits = [h for h in hits if in_delhi(float(h["lat"]), float(h["lon"]))]
            if hits:
                h = hits[0]
                guess = (s.get("lat"), s.get("lon"))
                s["lat"], s["lon"] = float(h["lat"]), float(h["lon"])
                s["geo_from"] = "nominatim"
                s["geo_label"] = h.get("display_name", "")[:90]
                if guess[0] and haversine_m(guess, (s["lat"], s["lon"])) > 2000:
                    problems.append(f"{name}: Nominatim pin is {haversine_m(guess, (s['lat'], s['lon'])) / 1000:.1f} km "
                                    f"from the researcher's coordinates")
            elif s.get("lat") and in_delhi(s["lat"], s["lon"]):
                s["geo_from"] = "research"
            else:
                problems.append(f"{name}: no geocode inside Delhi")
                s["lat"] = None
        if s.get("lat") is not None:
            rev = nom.reverse(s["lat"], s["lon"])
            addr = rev.get("address", {})
            s["osm_road"] = addr.get("road") or rev.get("name") or ""
            s["osm_area"] = addr.get("suburb") or addr.get("neighbourhood") or addr.get("city_district") or ""
    spots = [s for s in spots if s.get("lat") is not None]
    by_name = {s["name_en"]: s for s in spots}
    for src, dst in merge_into.items():  # same flooding site reported under two names
        if src in by_name and dst in by_name:
            by_name[src]["lat"], by_name[src]["lon"] = by_name[dst]["lat"], by_name[dst]["lon"]
            by_name[src]["merge_rank"] = 1

    # Merge duplicates within 150 m: keep the one with more evidence, union the reports.
    spots.sort(key=lambda s: (s.get("merge_rank", 0), -len(seasons_of(s))))
    merged = []
    for s in spots:
        twin = next((m for m in merged if haversine_m((m["lat"], m["lon"]), (s["lat"], s["lon"])) < MERGE_M), None)
        if twin is None:
            merged.append(s)
            continue
        problems.append(f"merged '{s['name_en']}' into '{twin['name_en']}' (<{MERGE_M} m)")
        seen = {r["year"] for r in twin.get("reports", [])}
        twin["reports"] = twin.get("reports", []) + [r for r in s.get("reports", []) if r["year"] not in seen]
        twin["official_list"] = twin.get("official_list") or s.get("official_list")
        twin["storm_reports"] = twin.get("storm_reports", []) + s.get("storm_reports", [])

    merged.sort(key=lambda s: (s["name_en"] != first, s["name_en"].lower()))
    hotspots = []
    for i, s in enumerate(merged, 1):
        years = seasons_of(s)
        n = len(years) + (1 if s.get("official_list") else 0)
        sources = [r["url"] for r in sorted(s.get("reports", []), key=lambda r: r["year"]) if r.get("url")]
        if s.get("official_list") and s["official_list"].get("url"):
            sources.append(s["official_list"]["url"])
        sources = list(dict.fromkeys(sources))
        if not sources:
            problems.append(f"{s['name_en']}: no source, dropped")
            continue
        name_en = rename.get(s["name_en"], s["name_en"])
        name_hi = names_hi.get(name_en)
        if not name_hi:
            problems.append(f"{name_en}: missing Hindi name")
        road, div = s.get("road") or name_en, s.get("diversion_road")
        road_hi, div_hi = to_hindi(road, road_words_hi, problems), to_hindi(div, road_words_hi, problems) if div else None
        hotspots.append({
            "hotspot_id": f"DL-{i:03d}",
            "name_en": name_en, "name_hi": name_hi or name_en,
            "lat": round(s["lat"], 5), "lon": round(s["lon"], 5),
            "site_type": s["site_type"], "ward": None, "importance": s["importance"],
            "flood_seasons": min(n, 7),
            "avoid_en": f"Avoid {name_en} ({road}) during heavy rain; water collects here.",
            "avoid_hi": f"भारी बारिश में {name_hi or name_en} ({road_hi}) से बचें; यहाँ पानी भर जाता है।",
            "diversion_en": f"Use {div} instead." if div else "Use a parallel arterial road and follow traffic police advisories.",
            "diversion_hi": f"इसके बजाय {div_hi} का उपयोग करें।" if div else "समानांतर मुख्य सड़क लें और ट्रैफ़िक पुलिस की सलाह का पालन करें।",
            "sources": sources,
            "evidence": {
                "seasons": sorted(years), "official_list": bool(s.get("official_list")),
                "reports": s.get("reports", []), "official": s.get("official_list"),
                "storm_reports": s.get("storm_reports", []),
                "geocode": {"from": s["geo_from"], "osm_road": s.get("osm_road", ""), "osm_area": s.get("osm_area", "")},
                "road": road, "diversion_road": div,
            },
        })

    (OUT / "delhi_hotspots.json").write_text(json.dumps(hotspots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [h["lon"], h["lat"]]},
                 "properties": {"id": h["hotspot_id"], "name": h["name_en"], "site_type": h["site_type"],
                                "osm_road": h["evidence"]["geocode"]["osm_road"], "seasons": h["flood_seasons"]}}
                for h in hotspots]
    (OUT / "delhi_hotspots.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")

    if args.report:
        for h in hotspots:
            g = h["evidence"]["geocode"]
            print(f"{h['hotspot_id']} {h['name_en'][:34]:34} {h['site_type'][:4]} n={h['flood_seasons']} "
                  f"src={len(h['sources'])} [{g['from'][:4]}] osm: {g['osm_road'][:28]} / {g['osm_area'][:20]}")
    print(f"{len(hotspots)} hotspots written", file=sys.stderr)
    for p in problems:
        print("  ! " + p, file=sys.stderr)


if __name__ == "__main__":
    main()
