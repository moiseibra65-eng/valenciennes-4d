import bpy, json, sys
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
root=Path(__file__).resolve().parents[2]
src=Path(args[0]).resolve() if args else root/'data/demo/buildings.geojson'
out=Path(args[1]).resolve() if len(args)>1 else root/'exports/valenciennes_demo.glb'
out.parent.mkdir(parents=True,exist_ok=True)
features=json.loads(src.read_text(encoding='utf-8'))['features']
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for i,f in enumerate(features):
    g=f['geometry']
    if g['type']!='Polygon' or len(g['coordinates'])!=1: raise ValueError('Simple Polygon only')
    pts=g['coordinates'][0]
    if pts[0]==pts[-1]: pts=pts[:-1]
    if len(pts)<3: raise ValueError('Invalid polygon')
    h=float(f.get('properties',{}).get('height_m',8))
    if not 0<h<=200: raise ValueError('Invalid height')
    n=len(pts)
    verts=[(float(x),float(y),z) for z in (0,h) for x,y in pts]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    for j in range(n): faces.append((j,(j+1)%n,(j+1)%n+n,j+n))
    mesh=bpy.data.meshes.new('BuildingMesh')
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    obj=bpy.data.objects.new(str(f.get('properties',{}).get('id',f'building_{i}')),mesh)
    bpy.context.collection.objects.link(obj)
    obj['evidence']='synthetic_demo'
bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',export_apply=True)
print('EXPORT_OK',out,'BUILDINGS',len(features))
