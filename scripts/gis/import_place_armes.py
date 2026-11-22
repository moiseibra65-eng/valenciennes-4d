#!/usr/bin/env python3
"""Fetch OSM building footprints around Place d'Armes, Valenciennes.
GeoJSON coordinates are projected into a local metre-based coordinate system
for Blender; original lon/lat footprints are saved separately.
"""
import json, math, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"data"/"valenciennes"
OUT.mkdir(parents=True,exist_ok=True)
# Small study area around Place d'Armes (not an administrative boundary).
S,W,N,E=50.3558,3.5205,50.3584,3.5260
LAT0,LON0=50.3571,3.52325
QUERY=f'''[out:json][timeout:45];
(
  way["building"]({S},{W},{N},{E});
  relation["building"]["type"="multipolygon"]({S},{W},{N},{E});
);
out geom;'''
ENDPOINTS=[
 "https://overpass-api.de/api/interpreter",
 "https://overpass.kumi.systems/api/interpreter",
]
def project(lon,lat):
    return [round((lon-LON0)*111320*math.cos(math.radians(LAT0)),3),
            round((lat-LAT0)*111132,3)]
def close_ring(ring):
    if ring and ring[0]!=ring[-1]: ring.append(ring[0])
    return ring
def rings_from_element(el):
    if el["type"]=="way":
        return [[(p["lon"],p["lat"]) for p in el.get("geometry",[])]]
    outers=[[(p["lon"],p["lat"]) for p in m.get("geometry",[])]
            for m in el.get("members",[]) if m.get("role")=="outer" and m.get("geometry")]
    # Do not stitch incomplete multipolygon members.
    return [r for r in outers if len(r)>=4 and r[0]==r[-1]]
def main():
    raw=None
    for endpoint in ENDPOINTS:
        try:
            req=urllib.request.Request(endpoint,
                data=urllib.parse.urlencode({"data":QUERY}).encode(),
                headers={"User-Agent":"Valenciennes4D/0.1 (heritage research; GitHub Actions)"})
            with urllib.request.urlopen(req,timeout=75) as response:
                raw=json.load(response)
            break
        except Exception as exc:
            print("Overpass unavailable:",endpoint,repr(exc))
            time.sleep(3)
    if raw is None: raise RuntimeError("No Overpass endpoint responded; keeping previous dataset unchanged.")
    geo_features=[]; local_features=[]
    for el in raw.get("elements",[]):
        tags=el.get("tags",{})
        for idx,ring in enumerate(rings_from_element(el)):
            if len(ring)<4 or ring[0]!=ring[-1]: continue
            geographic=close_ring([[lon,lat] for lon,lat in ring])
            local=close_ring([project(lon,lat) for lon,lat in ring])
            props={"id":f'osm_{el["type"]}_{el["id"]}_{idx}',
                   "osm_type":el["type"],"osm_id":el["id"],
                   "building":tags.get("building"),"height":tags.get("height"),
                   "building_levels":tags.get("building:levels"),
                   "source":"OpenStreetMap contributors",
                   "height_status":"unverified"}
            geo_features.append({"type":"Feature","properties":props,
                 "geometry":{"type":"Polygon","coordinates":[geographic]}})
            h=None
            try:
                h=float(str(tags.get("height","")).replace(" m","").replace(",","."))
            except ValueError: pass
            if h is None:
                try: h=float(tags["building:levels"])*3.0
                except (ValueError,KeyError,TypeError): h=8.0
                props["height_status"]="estimated"
            else: props["height_status"]="osm_tag_unverified"
            local_features.append({"type":"Feature",
                "properties":dict(props,height_m=h),
                "geometry":{"type":"Polygon","coordinates":[local]}})
    if not geo_features: raise RuntimeError("No usable building polygons; keeping previous dataset.")
    metadata={"type":"FeatureCollection","features":geo_features,
        "metadata":{"source":"OpenStreetMap via Overpass","retrieved_at":datetime.now(timezone.utc).isoformat(),
                    "bbox":[W,S,E,N],"crs":"EPSG:4326",
                    "attribution":"© OpenStreetMap contributors (ODbL)"}}
    local_data={"type":"FeatureCollection","features":local_features,
        "metadata":{"crs":"local metres (equirectangular approximation)",
                    "origin_lon_lat":[LON0,LAT0],
                    "warning":"Do not interpret estimated heights as surveyed heights."}}
    (OUT/"place_armes_buildings_wgs84.geojson").write_text(
        json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"place_armes_buildings_local.geojson").write_text(
        json.dumps(local_data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Imported {len(geo_features)} building polygons")
if __name__=="__main__": main()
