import sys, csv
csv.field_size_limit(10**7)
N = int(sys.argv[1]) if len(sys.argv)>1 else 25
r = csv.reader(sys.stdin)
header = next(r)
idx = {name:i for i,name in enumerate(header)}
pid, fid = idx['plan_id'], idx['floor_id']
seen = []          # ordered unique (plan,floor)
seen_set = set()
out_rows = [header]
for row in r:
    key = (row[pid], row[fid])
    if key not in seen_set:
        if len(seen_set) >= N:
            # stop once we've collected N groups AND passed them
            if key not in seen_set:
                continue
        seen_set.add(key); seen.append(key)
    if key in seen_set:
        out_rows.append(row)
import io
w = csv.writer(open(r"C:/PROJECTS/GRAPH-ML-DOCUMENTS/FINAL/data/msd_subset.csv","w",newline="",encoding="utf-8"))
w.writerows(out_rows)
print("collected groups:", len(seen))
print("rows written:", len(out_rows)-1)
