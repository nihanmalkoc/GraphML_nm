"""Builds FINAL/PlanAnalysis-3D.ipynb : 3D building graph (floors 3&4 + stair cores),
MST, and cross-floor shortest path. Visuals styled like the reference."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []
def md(s): cells.append(nbf.v4.new_markdown_cell(s))
def code(s): cells.append(nbf.v4.new_code_cell(s))

md("""# 3D Building Graph — The Interlace (Floors 3 & 4)

A multi-floor spatial graph: each floor plate is turned into a grid graph, and the
floors are connected by **vertical stair edges** at the three stair cores. We then
compute a **Minimum Spanning Tree** and a **cross-floor shortest path** that climbs
from the lower floor to the upper floor through a stair.""")

code('''from topologicpy.Vertex import Vertex
from topologicpy.Edge import Edge
from topologicpy.Wire import Wire
from topologicpy.Face import Face
from topologicpy.Shell import Shell
from topologicpy.Cluster import Cluster
from topologicpy.Topology import Topology
from topologicpy.Dictionary import Dictionary
from topologicpy.Helper import Helper
from topologicpy.Grid import Grid
from topologicpy.Graph import Graph
from topologicpy.Color import Color
import time''')

code('print("topologicpy", Helper.Version())')

md("## Renderer\n* VS Code: `vscode`  ·  Browser: `browser`  ·  Colab: `colab`")
code('renderer = "vscode"\n# isometric-style 3D view\nCAM = [1.7, -1.7, 1.1]\nPROJ = "orthographic"')

md("## 1. Inputs and parameters")
code('''BREP = r"C:/PROJECTS/GRAPH-ML-DOCUMENTS/FINAL/floorplate3-4--182-180.brep"
CORE = r"C:/PROJECTS/GRAPH-ML-DOCUMENTS/FINAL/floorplate3-4-core-182-180.obj"
SCALE = 0.01      # the core OBJ is in cm; the brep is already in meters
STEP  = 3.0       # grid cell size (m)

def frange(stop, step):
    out, x = [], 0.0
    while x <= stop + step:
        out.append(round(x, 3)); x += step
    return out

def reset_dictionaries(shell):
    for f in Topology.Faces(shell):
        d = Topology.Dictionary(f)
        for key in Dictionary.Keys(d):
            if key != "face_id":
                d = Dictionary.RemoveKey(d, key)
        f = Topology.SetDictionary(f, d)

def transfer_dicts_by_key(topologies, selectors, key):
    lut = {}
    for s in selectors:
        val = Dictionary.ValueAtKey(Topology.Dictionary(s), key, None)
        if val is not None:
            lut[str(val)] = Topology.Dictionary(s)
    for t in topologies:
        val = Dictionary.ValueAtKey(Topology.Dictionary(t), key, None)
        if val is not None and str(val) in lut:
            Topology.SetDictionary(t, lut[str(val)])''')

md("## 2. Stair core locations\nEach core in the OBJ is a vertical box; its footprint centroid is a stair location.")
code('''def core_centroids(path):
    groups, cur, V = {}, None, []
    for line in open(path):
        if line.startswith(("g ", "o ")):
            cur = line.strip(); groups[cur] = []
        elif line.startswith("v "):
            p = line.split(); V.append((float(p[1]), float(p[2]), float(p[3])))
            if cur: groups[cur].append(len(V) - 1)
    cents = []
    for g, idxs in groups.items():
        xs = [V[i][0] for i in idxs]; zs = [V[i][2] for i in idxs]
        cents.append((sum(xs)/len(xs)*SCALE, sum(zs)/len(zs)*SCALE))   # topologic (X=x, Y=z)
    return cents

cores = core_centroids(CORE)
print("Stair cores:", len(cores))
for c in cores: print("  ", (round(c[0],1), round(c[1],1)))''')

md("## 3. Load the two floor plates")
code('''gallery = Topology.ByBREPPath(BREP)
print("faces:", len(Topology.Faces(gallery) or []))
Topology.Show(gallery, faceColor=[170,180,210], faceOpacity=0.5,
              edgeColor="white", edgeWidth=1, showVertices=False,
              backgroundColor="black", camera=CAM, projection=PROJ,
              width=950, height=700, renderer=renderer)''')

md("## 4. Per-floor grid cells → building graph (intra-floor edges)")
code('''b_r = Wire.BoundingRectangle(gallery)
d = Topology.Dictionary(b_r)
width  = Dictionary.ValueAtKey(d, "width")
length = Dictionary.ValueAtKey(d, "length")
uRange = frange(width, STEP)
vRange = frange(length, STEP)

# Slice each floor face into a Shell of connected cells (preserves adjacency).
wing_shells = []
for f in Topology.Faces(gallery):
    gf = Grid.EdgesByDistances(f, clip=True, uRange=uRange, vRange=vRange)
    wing_shells.append(Topology.Slice(f, gf))
shell = Cluster.ByTopologies(wing_shells)

# unique id per cell (needed to transfer graph results back to the faces)
faces = Topology.Faces(shell)
for i, f in enumerate(faces):
    f = Topology.SetDictionary(f, Dictionary.ByKeyValue("face_id", "face_"+str(i+1)))

bg = Graph.ByTopology(shell)
verts = Graph.Vertices(bg)
intra_edges = Graph.Edges(bg)
zlevels = sorted(set(round(Vertex.Z(v), 2) for v in verts))
print("cells:", len(verts), "| intra-floor edges:", len(intra_edges), "| floor Z:", zlevels)''')

md("## 5. Add vertical stair edges connecting the floors")
code('''def nearest(vs, x, y):
    return min(vs, key=lambda p: (Vertex.X(p)-x)**2 + (Vertex.Y(p)-y)**2)

zlo, zhi = zlevels[0], zlevels[-1]
low  = [p for p in verts if round(Vertex.Z(p), 2) == zlo]
high = [p for p in verts if round(Vertex.Z(p), 2) == zhi]

stair_edges = []
for (cx, cy) in cores:
    a = nearest(low, cx, cy); b = nearest(high, cx, cy)
    e = Edge.ByVertices([a, b])
    if e is not None:
        e = Topology.SetDictionary(e, Dictionary.ByKeysValues(["color","width"], ["red", 6]))
        stair_edges.append(e)

# style the intra-floor edges
for e in intra_edges:
    e = Topology.SetDictionary(e, Dictionary.ByKeysValues(["color","width"], ["#4F86C6", 1]))

building_graph = Graph.ByVerticesEdges(verts, intra_edges + stair_edges)
components = Graph.ConnectedComponents(building_graph)
print("stair edges:", len(stair_edges))
print("building graph -> verts:", len(Graph.Vertices(building_graph) or []),
      "edges:", len(Graph.Edges(building_graph) or []),
      "components:", len(components))''')

md("""## 6. Stair Edges — 3D Building Graph
Apartments on each floor form a grid graph; the **red vertical edges** are the stair
connections that turn the stacked plates into a single 3-dimensional building graph.""")
code('''edge_cluster = Cluster.ByTopologies(intra_edges + stair_edges)
Topology.Show(gallery, edge_cluster,
              faceColor=[120,130,150], faceOpacity=0.12,
              edgeColorKey="color", edgeWidthKey="width",
              showVertices=False,
              backgroundColor="black", camera=CAM, projection=PROJ,
              width=1000, height=750, renderer=renderer)''')

md("""## 7. Minimum Spanning Tree
The MST keeps, for every connected part of the building, the lightest set of edges that
still links all of its cells. (The four blocks are physically separate, so each
stair-linked block-pair yields its own tree.)""")
code('''mst_edges = []
for c in components:
    m = Graph.MinimumSpanningTree(c)
    mst_edges += (Graph.Edges(m) or [])
for e in mst_edges:
    e = Topology.SetDictionary(e, Dictionary.ByKeysValues(["color","width"], ["#7FB069", 2]))
mst_cluster = Cluster.ByTopologies(mst_edges)
print("MST edges:", len(mst_edges), "of", len(Graph.Edges(building_graph) or []), "graph edges")

Topology.Show(gallery, mst_cluster,
              faceColor=[120,130,150], faceOpacity=0.10,
              edgeColorKey="color", edgeWidthKey="width",
              showVertices=False,
              backgroundColor="black", camera=CAM, projection=PROJ,
              width=1000, height=750, renderer=renderer)''')

md("""## 8. Cross-floor Shortest Path
Navigation from one end of the lower floor to the far end of the upper floor. The route
must climb through a **stair edge**, demonstrating genuine cross-floor connectivity.
`Wire.Straighten` is then used to shorten/clean the path.""")
code('''# pick a component that spans both floors (i.e. has a stair) and its two extreme ends
best = None
for c in components:
    cv = Graph.Vertices(c)
    czl = [p for p in cv if round(Vertex.Z(p),2) == zlo]
    czh = [p for p in cv if round(Vertex.Z(p),2) == zhi]
    if czl and czh and (best is None or len(cv) > best[0]):
        best = (len(cv), czl, czh)

_, czl, czh = best
start_vertex = min(czl, key=lambda p: Vertex.X(p) + Vertex.Y(p))   # lower-floor end
end_vertex   = max(czh, key=lambda p: Vertex.X(p) + Vertex.Y(p))   # upper-floor far end

crg = Graph.CompiledRoutingGraph(building_graph, precomputeTurns=False)
t = time.time()
shortest_path = Graph.ShortestPath(crg, vertexA=start_vertex, vertexB=end_vertex)
print("Cross-floor shortest path:", round(time.time()-t, 2), "s")
print("  start Z =", round(Vertex.Z(start_vertex),1), " end Z =", round(Vertex.Z(end_vertex),1))
print("  path length:", round(Wire.Length(shortest_path), 1), "m")

try:
    straight_path = Wire.Straighten(shortest_path, host=gallery)
    print("  straightened length:", round(Wire.Length(straight_path), 1), "m")
except Exception as ex:
    straight_path = shortest_path
    print("  (straighten skipped)")

for e in Topology.Edges(shortest_path):
    e = Topology.SetDictionary(e, Dictionary.ByKeysValues(["color","width"], ["red", 7]))
for e in Topology.Edges(straight_path):
    e = Topology.SetDictionary(e, Dictionary.ByKeysValues(["color","width"], ["#00E0A0", 4]))
path_cluster = Cluster.ByTopologies(Topology.Edges(shortest_path) + Topology.Edges(straight_path))

Topology.Show(gallery, edge_cluster, path_cluster,
              faceColor=[120,130,150], faceOpacity=0.08,
              edgeColorKey="color", edgeWidthKey="width",
              showVertices=False,
              backgroundColor="black", camera=CAM, projection=PROJ,
              width=1000, height=750, renderer=renderer)''')

md("""## 9. Community Detection (3D)
Community detection groups densely-connected cells. Because the graph includes the stair
edges, communities can span both floors through a stair core.""")
code('''community_list = Graph.CommunityPartition(building_graph, colorScale="thermal")
g_verts = Graph.Vertices(building_graph)
n_comm = len(set(Dictionary.ValueAtKey(Topology.Dictionary(v), "community") for v in g_verts))
print("Number of communities:", n_comm)

reset_dictionaries(shell)
faces = Topology.Faces(shell)
transfer_dicts_by_key(faces, g_verts, "face_id")

Topology.Show(faces,
              faceColorKey="cp_color", faceOpacity=1.0,
              showEdges=False, showVertices=False,
              backgroundColor="black", camera=CAM, projection=PROJ,
              width=1000, height=750, renderer=renderer)''')

md("""## 10. Degree Centrality (3D)
Degree centrality highlights cells with the most neighbours — circulation-like, central
locations. Values are computed on the full 3D building graph and painted on the cells.""")
code('''degree_centralities = Graph.DegreeCentrality(building_graph, normalize=True)
g_verts = Graph.Vertices(building_graph)
mn, mx = min(degree_centralities), max(degree_centralities)
print("Degree centrality for", len(degree_centralities), "cells | min:", round(mn, 4), " max:", round(mx, 4))

# Spread the colour scale manually across the actual value range. The built-in
# colouring rounds these small values into too few bins (~4), which looks flat;
# Color.ByValueInRange over [min, max] gives the full gradient (as in HW02).
for v in g_verts:
    d = Topology.Dictionary(v)
    dc = Dictionary.ValueAtKey(d, "degree_centrality")
    col = Color.AnyToHex(Color.ByValueInRange(dc, minValue=mn, maxValue=mx, colorScale="thermal"))
    d = Dictionary.SetValueAtKey(d, "dc_color", col)
    v = Topology.SetDictionary(v, d)

reset_dictionaries(shell)
faces = Topology.Faces(shell)
transfer_dicts_by_key(faces, g_verts, "face_id")

Topology.Show(faces,
              faceColorKey="dc_color", faceOpacity=1.0,
              showEdges=False, showVertices=False,
              backgroundColor="black", camera=CAM, projection=PROJ,
              width=1000, height=750, renderer=renderer)''')

nb["cells"] = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = r"C:/PROJECTS/GRAPH-ML-DOCUMENTS/FINAL/PlanAnalysis-3D.ipynb"
nbf.write(nb, out)
print("wrote", out, "with", len(cells), "cells")
