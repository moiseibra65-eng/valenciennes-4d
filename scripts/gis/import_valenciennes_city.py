#!/usr/bin/env python3
"""Download and clip OSM building footprints to Valenciennes commune (INSEE 59606).
Outputs real geographic outlines, not surveyed 3D reconstructions.
Requires: requests, shapely. Does not overwrite valid data on partial failure.
"""
import json, math, os, random, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from shapely.geometry import shape, mapping, Polygon, box
from shapely.validation import make_valid
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"data"/"valenciennes"/"city_buildings.geojson"
BOUNDARY=ROOT/"data"/"valenciennes"/"commune_boundary.geojson"
API="https://geo.api.gouv.fr/communes/59606?fields=nom,code,contour&format=geojson&geometry=contour"
SERVERS=["https://overpass.kumi.systems/api/interpreter","https://overpass-api.de/api/interpreter","https://overpass.private.coffee/api/interpreter"]
SESSION=requests.Session()
SESSION.headers.update({"User-Agent":"Valenciennes4D/1.0 (open heritage research project)","Accept":"application/json"})
def commune():
    response=SESSION.get(API,timeout=50);response.raise_for_status()
    obj=response.json()
    geom=obj.get("geometry") or obj.get("contour")
    if not geom: raise RuntimeError("API Geo did not return commune geometry")
    polygon=make_valid(shape(geom))
    if polygon.is_empty: raise RuntimeError("Commune geometry empty")
    return polygon
def overpass(s,w,n,e):
    query=f'[out:json][timeout:90];way["building"]({s:.6f},{w:.6f},{n:.6f},{e:.6f});out geom;'
    errors=[]
    for attempt in range(3):
        for url in SERVERS:
            try:
                r=SESSION.post(url,data={"data":query},timeout=115)
                r.raise_for_status()
                data=r.json()
                if not isinstance(data.get("elements"),list): raise ValueError("Missing elements")
                return data["elements"]
            except (requests.RequestException,ValueError) as exc:
                errors.append(str(exc))
        time.sleep((attempt+1)*10+random.random())
    raise RuntimeError("Tile failed: "+" | ".join(errors[-3:]))
def height(tags):
    raw=tags.get("height","").lower().replace("m","").strip().replace(",",".")
    try:
        h=float(raw)
        if 1<=h<=250:return round(h,2),"osm_tag_unverified"
    except ValueError:pass
    try:
        floors=float(tags.get("building:levels",""))
        if 0<floors<=70:return round(floors*3,2),"estimated_from_levels"
    except ValueError:pass
    return 8.0,"estimated_default"
def main():
    boundary=commune()
    w,s,e,n=boundary.bounds
    step=0.012
    tiles=[]
    y=s
    while y<n:
        x=w
        while x<e:
            tile=box(x,y,min(x+step,e),min(y+step,n))
            if tile.intersects(boundary):tiles.append((y,x,min(y+step,n),min(x+step,e)))
            x+=step
        y+=step
    print("Tiles:",len(tiles),flush=True)
    ways={}
    for i,(south,west,north,east) in enumerate(tiles,1):
        print(f"Tile {i}/{len(tiles)}",flush=True)
        for el in overpass(south,west,north,east):
            if el.get("type")=="way":ways[el["id"]]=el
        time.sleep(.5)
    features=[]
    for osm_id,el in ways.items():
        tags=el.get("tags",{})
        coords=[(p["lon"],p["lat"]) for p in el.get("geometry",[]) if "lon" in p and "lat" in p]
        if len(coords)<4 or coords[0]!=coords[-1]:continue
        polygon=make_valid(Polygon(coords))
        clipped=polygon.intersection(boundary)
        if clipped.is_empty:continue
        parts=[clipped] if clipped.geom_type=="Polygon" else list(getattr(clipped,"geoms",[]))
        for j,part in enumerate(parts):
            if part.geom_type!="Polygon" or part.area<1e-12:continue
            h,status=height(tags)
            features.append({"type":"Feature","id":f"way/{osm_id}/{j}","properties":{
                "osm_id":osm_id,"name":tags.get("name",""),"building":tags.get("building","yes"),
                "height_m":h,"height_status":status,"building_levels":tags.get("building:levels"),
                "source":"© OpenStreetMap contributors (ODbL)"
            },"geometry":mapping(part)})
    if len(features)<500:raise RuntimeError(f"Only {len(features)} buildings: refusing incomplete export")
    metadata={"source":"OpenStreetMap via Overpass","commune":"Valenciennes","insee":"59606",
              "retrieved_at":datetime.now(timezone.utc).isoformat(),"tile_count":len(tiles),
              "building_count":len(features),"limitations":"OSM closed building ways only; multipolygon relations not imported; heights may be estimated"}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    fc={"type":"FeatureCollection","metadata":metadata,"features":features}
    tmp=OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(fc,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    tmp.replace(OUT)
    BOUNDARY.write_text(json.dumps({"type":"Feature","properties":{"name":"Valenciennes","insee":"59606"},"geometry":mapping(boundary)},ensure_ascii=False),encoding="utf-8")
    print("SUCCESS",len(features),"building polygons",flush=True)
if __name__=="__main__":main()
