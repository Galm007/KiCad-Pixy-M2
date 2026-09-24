"""Group schematic items into rigid blocks: anything touching by wire geometry."""
from schlib import *


def on_seg(p, a, b, eps=0.01):
    (px, py), (ax, ay), (bx, by) = p, a, b
    if abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) > eps * max(1, math.hypot(bx - ax, by - ay)):
        return False
    return min(ax, bx) - eps <= px <= max(ax, bx) + eps and min(ay, by) - eps <= py <= max(ay, by) + eps


def clusters(s):
    items = [it for it in s.items if it.kind in ('symbol', 'wire', 'label', 'junction', 'no_connect')]
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        parent[find(a)] = find(b)
    pts = {}
    for i, it in enumerate(items):
        for p in s.points(it):
            pts.setdefault((round(p[0], 2), round(p[1], 2)), []).append(i)
    for idx in pts.values():
        for j in idx[1:]:
            union(idx[0], j)
    wires = [(i, s.points(it)) for i, it in enumerate(items) if it.kind == 'wire']
    for p, idx in pts.items():
        for wi, (a, b) in wires:
            if on_seg(p, a, b):
                for j in idx:
                    union(wi, j)
    groups = {}
    for i, it in enumerate(items):
        groups.setdefault(find(i), []).append(it)
    return list(groups.values())


if __name__ == '__main__':
    s = Sch('../../Pixy-M2.kicad_sch')
    gs = clusters(s)
    out = []
    for g in gs:
        bb = [s.bbox(it) for it in g]
        box = (min(b[0] for b in bb), min(b[1] for b in bb), max(b[2] for b in bb), max(b[3] for b in bb))
        refs = sorted(it.ref for it in g if it.kind == 'symbol' and not it.ref.startswith('#'))
        pw = sorted(it.prop('Value') for it in g if it.kind == 'symbol' and it.ref.startswith('#'))
        labs = sorted(sval(it.tree[1]) for it in g if it.kind == 'label')
        out.append((box, refs, pw, labs, len(g)))
    for box, refs, pw, labs, n in sorted(out, key=lambda o: (o[0][1], o[0][0])):
        print('(%6.1f,%6.1f)-(%6.1f,%6.1f) n=%d %s | %s | %s' % (*box, n, ' '.join(refs), ' '.join(pw), ' '.join(labs)))
    texts = [it for it in s.items if it.kind == 'text']
    for t in texts:
        print('TEXT', t.at(), repr(sval(t.tree[1])[:70]))
