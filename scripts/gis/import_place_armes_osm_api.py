#!/usr/bin/env python3
"""Download real OSM building ways using the OSM core map API (no Overpass).
Study area is a small bounding box around Place d'Armes, Valenciennes.
Only closed building ways are supported. Multipolygon relations are skipped.
"""
import json, math, time, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"data"/"valenciennes"
OUT.mkdir(parents=True,exist_ok=True)
W,S,E,N=3.5205,50.3558,3.5260,50.3584
LON0,LAT0=3.52325,50.3571
URL=f"https://api.openstreetmap.org/api/0.6/map?bbox={W},{S},{E},{N}"
def project(lon,lat):
    return [round((lon-LON0)*111320*math.cos(math.radians(LAT0)),3),
            round((lat-LAT0)*111132,3)]
def main():
    data=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(URL,headers={"User-Agent":"Valenciennes4D/0.1 (educational heritage mapping)","Accept":"application/xml"})
            with urllib.request.urlopen(req,timeout=45) as response: data=response.read()
            break
        except Exception as e:
            print("OSM core API attempt failed:",repr(e),flush=True)
            if attempt<2: time.sleep(8*(attempt+1))
    if data is None: raise RuntimeError("OSM API unreachable; no data modified")
    root=ET.fromstring(data)
    nodes={n.attrib["id"]:(float(n.attrib["lon"]),float(n.attrib["lat"])) for n in root.findall("node")}
    geo=[];local=[];skipped=0
    for way in root.findall("way"):
        tags={t.attrib["k"]:t.attrib["v"] for t in way.findall("tag")}
        if "building" not in tags: continue
        ids=[n.attrib["ref"] for n in way.findall("nd")]
        if len(ids)<4 or ids[0]!=ids[-1] or any(i not in nodes for i in ids):
            skipped+=1;continue
        ring=[[nodes[i][0],nodes[i][1]] for i in ids]
        height=None;status="estimated"
        try:
            height=float(tags.get("height","").lower().replace("m","").strip().replace(",","."))
            if height<=0 or height>250: height=None
            else: status="osm_tag_unverified"
        except ValueError: pass
        if height is None:
            try: height=float(tags["building:levels"])*3
            except (KeyError,ValueError): height=8.0
        props={"id":"osm_way_"+way.attrib["id"],"osm_type":"way","osm_id":int(way.attrib["id"]),
               "building":tags["building"],"height":tags.get("height"),
               "building_levels":tags.get("building:levels"),
               "height_status":status,"source":"OpenStreetMap contributors"}
        geo.append({"type":"Feature","properties":props,"geometry":{"type":"Polygon","coordinates":[ring]}})
        local.append({"type":"Feature","properties":dict(props,height_m=height),
                      "geometry":{"type":"Polygon","coordinates":[[project(*pt) for pt in ring]]}})
    if not geo: raise RuntimeError("No closed building ways found; no data modified")
    metadata={"source":"OpenStreetMap core API","retrieved_at":datetime.now(timezone.utc).isoformat(),
              "bbox":[W,S,E,N],"attribution":"© OpenStreetMap contributors (ODbL)",
              "note":f"{skipped} incomplete building ways skipped; building multipolygon relations not included"}
    for name,features,meta in [
        ("place_armes_buildings_wgs84.geojson",geo,dict(metadata,crs="EPSG:4326")),
        ("place_armes_buildings_local.geojson",local,dict(metadata,crs="local metre approximation",origin_lon_lat=[LON0,LAT0]))]:
        (OUT/name).write_text(json.dumps({"type":"FeatureCollection","metadata":meta,"features":features},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Imported {len(geo)} closed building ways; skipped {skipped}; multipolygon relations not yet supported")
if __name__=="__main__":main()
