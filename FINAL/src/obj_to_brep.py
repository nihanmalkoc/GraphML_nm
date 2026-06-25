"""
floorplate OBJ (triangulated mesh) -> clean BREP (meters).

Floor plates lie in horizontal planes (constant OBJ-y = level height). The mesh may
contain several levels (e.g. floors 3 & 4) and vertical walls. We:
  * keep only (near-)horizontal faces, grouped by their level (OBJ-y),
  * dissolve each level's triangle soup into footprint polygon(s) with shapely,
  * build TopologicPy faces in the XY plane at Z = level (mapping OBJ (x,y,z) -> (x, z, y)),
  * export all faces as one BREP, scaled to meters.

Usage:  python obj_to_brep.py <src.obj> [dst.brep] [scale]
Default scale 0.01 (cm -> m).
"""
import sys, time
from collections import defaultdict
from shapely.geometry import Polygon
from shapely.ops import unary_union

def log(*a): print(*a, flush=True)

SRC = sys.argv[1] if len(sys.argv) > 1 else r"C:/PROJECTS/GRAPH-ML-DOCUMENTS/FINAL/floorplate-182-180.obj"
DST = sys.argv[2] if len(sys.argv) > 2 else SRC.rsplit(".", 1)[0] + ".brep"
SCALE = float(sys.argv[3]) if len(sys.argv) > 3 else 0.01
SIMPLIFY = 5.0          # OBJ units (~0.05 m) outline simplification
LEVEL_TOL = 1.0         # OBJ units: face is "horizontal" if its y-span < this

# ---- 1. parse OBJ ----
t = time.time()
V = []   # (x, y, z)
F = []
with open(SRC) as f:
    for line in f:
        if line.startswith("v "):
            p = line.split()
            V.append((float(p[1]), float(p[2]), float(p[3])))
        elif line.startswith("f "):
            F.append([int(tok.split("/")[0]) for tok in line.split()[1:]])
log(f"parsed {len(V)} verts, {len(F)} faces in {time.time()-t:.1f}s")

# ---- 2. group horizontal faces by level (rounded OBJ-y) ----
levels = defaultdict(list)   # level_y -> list of (x,z) rings
skipped = 0
for idx in F:
    ys = [V[i-1][1] for i in idx]
    if max(ys) - min(ys) > LEVEL_TOL:
        skipped += 1            # vertical / sloped face (wall) -> skip
        continue
    lvl = round(sum(ys) / len(ys), 1)
    ring = [(V[i-1][0], V[i-1][2]) for i in idx]   # (x, z)
    if len(ring) >= 3:
        poly = Polygon(ring)
        if poly.is_valid and poly.area > 0:
            levels[lvl].append(poly)
log(f"horizontal faces grouped into {len(levels)} level(s): {sorted(levels)} ; skipped {skipped} non-horizontal")

# ---- 3. dissolve each level, build TopologicPy faces ----
from topologicpy.Vertex import Vertex
from topologicpy.Wire import Wire
from topologicpy.Face import Face
from topologicpy.Cluster import Cluster
from topologicpy.Topology import Topology

def ring_to_wire(coords, z):
    pts = list(coords)
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    vs = [Vertex.ByCoordinates(x*SCALE, y*SCALE, z*SCALE) for (x, y) in pts]
    return Wire.ByVertices(vs, close=True)

all_faces = []
for lvl in sorted(levels):
    foot = unary_union(levels[lvl]).buffer(0)
    pieces = [foot] if foot.geom_type == "Polygon" else [g for g in foot.geoms if g.geom_type == "Polygon"]
    pieces = [p.simplify(SIMPLIFY, preserve_topology=True) for p in pieces]
    log(f"  level {lvl}: {len(pieces)} footprint piece(s), areas(m^2)="
        + str([round(p.area*SCALE*SCALE, 1) for p in pieces]))
    for p in pieces:
        ext = ring_to_wire(p.exterior.coords, lvl)
        holes = [ring_to_wire(r.coords, lvl) for r in p.interiors]
        fc = Face.ByWires(ext, holes) if holes else Face.ByWire(ext)
        if fc is not None:
            all_faces.append(fc)
log(f"built {len(all_faces)} topologic faces")

topo = all_faces[0] if len(all_faces) == 1 else Cluster.ByTopologies(all_faces)

vs = Topology.Vertices(topo)
xs = [Vertex.X(v) for v in vs]; ys = [Vertex.Y(v) for v in vs]; zs = [Vertex.Z(v) for v in vs]
log(f"bbox (m): X {min(xs):.1f}..{max(xs):.1f}  Y {min(ys):.1f}..{max(ys):.1f}  Z {min(zs):.1f}..{max(zs):.1f}")

t = time.time()
status = Topology.ExportToBREP(topo, DST, overwrite=True)
log(f"ExportToBREP status={status} in {time.time()-t:.1f}s -> {DST}")
log("DONE_CONVERT")
