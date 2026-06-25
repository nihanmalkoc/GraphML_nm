"""
MSD (Modified Swiss Dwellings) CSV  ->  TopologicPy graphs  ->  node-classification CSV dataset.

One graph per (plan_id, floor_id). Nodes = rooms ('area' entities).
Node label = roomtype (0..8). Node features = geometric descriptors (no roomtype leakage).
Edges = room adjacency (rooms sharing a wall), detected with shapely.

Output: <out_dir>/{graphs.csv, nodes.csv, edges.csv} in the schema PyG.ByCSVPath expects
(matches course notebook S06-15).
"""
import csv, math, sys
from collections import defaultdict

from shapely import wkt
from shapely.geometry import Polygon

from topologicpy.Vertex import Vertex
from topologicpy.Edge import Edge
from topologicpy.Graph import Graph
from topologicpy.Dictionary import Dictionary
from topologicpy.Topology import Topology

csv.field_size_limit(10**7)

# ---- 9 area room-type classes (index by global frequency in MSD) ----
ROOMTYPE_TO_IDX = {
    "Bedroom": 0, "Bathroom": 1, "Corridor": 2, "Balcony": 3, "Kitchen": 4,
    "Livingroom": 5, "Stairs": 6, "Storeroom": 7, "Dining": 8,
}
IDX_TO_ROOMTYPE = {v: k for k, v in ROOMTYPE_TO_IDX.items()}

# dict keys are plain indices so ExportToCSV (header 'feat') yields columns feat_0..feat_5
# meaning: 0=area, 1=perimeter, 2=compactness, 3=n_corners, 4=bbox_aspect, 5=rectangularity
FEATURE_NAMES = ["0", "1", "2", "3", "4", "5"]

ADJ_BUFFER = 0.30      # meters; ~ wall thickness to bridge
ADJ_MIN_AREA = 0.15    # min buffered-overlap area => shared wall (~0.5 m long)


def _features(poly: Polygon):
    """Geometric descriptors for a room polygon."""
    area = poly.area
    per = poly.length
    compact = (4 * math.pi * area) / (per * per) if per > 0 else 0.0
    n_corners = len(poly.exterior.coords) - 1
    minx, miny, maxx, maxy = poly.bounds
    w, h = (maxx - minx), (maxy - miny)
    aspect = (min(w, h) / max(w, h)) if max(w, h) > 0 else 0.0
    # feat_5: rectangularity (area / bbox area)
    bbox_area = w * h
    rect = (area / bbox_area) if bbox_area > 0 else 0.0
    return [round(area, 4), round(per, 4), round(compact, 4),
            float(n_corners), round(aspect, 4), round(rect, 4)]


def _adjacent(pi: Polygon, pj: Polygon):
    if pi.distance(pj) > ADJ_BUFFER:
        return False
    inter = pi.buffer(ADJ_BUFFER).intersection(pj)
    return inter.area >= ADJ_MIN_AREA


def load_plans(csv_path):
    """Group area rows by (plan_id, floor_id). Returns dict key -> list of (roomtype_idx, polygon)."""
    plans = defaultdict(list)
    with open(csv_path, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row["entity_type"] != "area":
                continue
            rt = row["roomtype"]
            if rt not in ROOMTYPE_TO_IDX:
                continue  # skip non-room areas if any
            try:
                poly = wkt.loads(row["geom"])
            except Exception:
                continue
            if poly.is_empty or poly.area <= 0:
                continue
            key = (row["plan_id"], row["floor_id"])
            plans[key].append((ROOMTYPE_TO_IDX[rt], poly))
    return plans


def build_graph(rooms):
    """rooms: list of (label_idx, polygon) -> a TopologicPy Graph with node dicts."""
    verts = []
    for label, poly in rooms:
        c = poly.representative_point()  # guaranteed inside polygon
        v = Vertex.ByCoordinates(c.x, c.y, 0.0)
        feats = _features(poly)
        keys = ["label"] + FEATURE_NAMES
        vals = [int(label)] + feats
        d = Dictionary.ByKeysValues(keys, vals)
        v = Topology.SetDictionary(v, d)
        verts.append(v)

    edges = []
    n = len(rooms)
    for i in range(n):
        for j in range(i + 1, n):
            if _adjacent(rooms[i][1], rooms[j][1]):
                e = Edge.ByVertices([verts[i], verts[j]], tolerance=0.0001)
                if e is not None:
                    edges.append(e)

    g = Graph.ByVerticesEdges(verts, edges)
    return g, len(verts), len(edges)


def main(csv_path, out_dir):
    plans = load_plans(csv_path)
    print(f"Loaded {len(plans)} plans from {csv_path}")
    graphs = []
    skipped = 0
    for key, rooms in plans.items():
        if len(rooms) < 2:
            skipped += 1
            continue
        g, nv, ne = build_graph(rooms)
        if g is None:
            skipped += 1
            continue
        graphs.append(g)
    print(f"Built {len(graphs)} graphs (skipped {skipped}).")

    status = Graph.ExportToCSV(
        graphs,
        path=out_dir,
        nodeLabelKey="label",
        nodeFeaturesKeys=FEATURE_NAMES,
        nodeTrainRatio=0.7, nodeValidateRatio=0.15, nodeTestRatio=0.15,
        overwrite=True,
        silent=True,
    )
    print("ExportToCSV status:", status)


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else r"C:/PROJECTS/GRAPH-ML-DOCUMENTS/FINAL/data/msd_subset.csv"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else r"C:/PROJECTS/GRAPH-ML-DOCUMENTS/FINAL/out/msd_dataset"
    main(csv_path, out_dir)
