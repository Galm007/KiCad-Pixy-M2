#!/usr/bin/env python3
"""REG_EN rework measurements: the enable node, the FB sense and the VSYS hop
beside U3, and which nets differ from a reference board.

    python3 layout/reg-en/measure.py BEFORE.kicad_pcb AFTER.kicad_pcb [--json OUT]

Gaps are copper edge to copper edge, on the same layer.  Pads are measured as
their rounded rectangles, tracks as capsules and vias as discs.  The REG_EN to
switch-node figure including U3's own pad reproduces clearmin.py's DRC result
(0.40 mm before, 0.95 mm after); that cross-check is what makes the other gaps
trustworthy.
"""
import heapq, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'autoroute'))
from pcbedit import Pcb
from sexp import parse, children, child, val
from load import fp_info

SWITCH = ('Net-(U3-SW)', 'Net-(U3-BST)')
U3_CRTYD = (136.95, 94.3, 141.05, 97.7)


# ---------------------------------------------------------------- geometry
def load(path):
    p = Pcb(path)
    pads = {}
    for f in children(parse(p.text), 'footprint'):
        fi = fp_info(f)
        for q, raw in zip(fi['pads'], children(f, 'pad')):
            rr = child(raw, 'roundrect_rratio')
            w, h = q['w'], q['h']
            if abs(q['rot'] % 180 - 90) < 1: w, h = h, w
            r = min(w, h) / 2 if q['shape'] in ('circle', 'oval') else (
                float(rr[1]) * min(w, h) if q['shape'] == 'roundrect' and rr else 0.0)
            q.update(ref=fi['ref'], bw=w, bh=h, r=r)
            pads.setdefault((fi['ref'], q['num']), []).append(q)
    return p, pads


def _pt_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0.0 if not L2 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)


def _seg_seg(a, b):
    (x1, y1, x2, y2), (x3, y3, x4, y4) = a, b
    def cross(ox, oy, ax, ay, bx, by): return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)
    d1, d2 = cross(x3, y3, x4, y4, x1, y1), cross(x3, y3, x4, y4, x2, y2)
    d3, d4 = cross(x1, y1, x2, y2, x3, y3), cross(x1, y1, x2, y2, x4, y4)
    if d1 * d2 < 0 and d3 * d4 < 0: return 0.0
    return min(_pt_seg(x1, y1, *b), _pt_seg(x2, y2, *b), _pt_seg(x3, y3, *a), _pt_seg(x4, y4, *a))


def shape(kind, *g):
    """('seg', x1,y1,x2,y2, r) | ('box', x0,y0,x1,y1, r): a core and its rounding"""
    return (kind,) + g


def pad_shape(q):
    hw, hh = q['bw'] / 2 - q['r'], q['bh'] / 2 - q['r']
    return shape('box', q['x'] - hw, q['y'] - hh, q['x'] + hw, q['y'] + hh, q['r'])


def _edges(b):
    x0, y0, x1, y1 = b
    return [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]


def gap(a, b):
    """edge-to-edge distance between two shapes (0 if they touch)"""
    if a[0] == 'box' and b[0] == 'seg': a, b = b, a
    if a[0] == 'seg' and b[0] == 'seg':
        d = _seg_seg(a[1:5], b[1:5])
    elif a[0] == 'seg':
        x0, y0, x1, y1 = b[1:5]
        inside = any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in (a[1:3], a[3:5]))
        d = 0.0 if inside else min(_seg_seg(a[1:5], e) for e in _edges(b[1:5]))
    else:
        dx = max(b[1] - a[3], a[1] - b[3], 0.0)
        dy = max(b[2] - a[4], a[2] - b[4], 0.0)
        d = math.hypot(dx, dy)
    return max(0.0, d - a[5] - b[5])


def copper(p, pads, net, layer, skip_pads=()):
    """every shape of one net on one layer"""
    out = []
    for blk in p.blocks:
        if Pcb.net(blk) != net: continue
        g = Pcb.geom(blk)
        if Pcb.kind(blk) == 'segment':
            if g[5] == layer: out.append(shape('seg', *g[:4], g[4] / 2))
        else:
            out.append(shape('seg', g[0], g[1], g[0], g[1], g[2] / 2))
    for key, qs in pads.items():
        for q in qs:
            if q['net'] == net and key not in skip_pads and (layer in q['layers'] or '*.Cu' in q['layers']):
                out.append(pad_shape(q))
    return out


def min_gap(A, B):
    return round(min((gap(a, b) for a in A for b in B), default=float('inf')), 3)


# ---------------------------------------------------------------- copper paths
def graph(p, pads, net):
    adj, nodes = {}, set()
    def edge(u, v, d):
        adj.setdefault(u, []).append((v, d)); adj.setdefault(v, []).append((u, d))
    segs = []
    for blk in p.blocks:
        if Pcb.net(blk) != net: continue
        g = Pcb.geom(blk)
        if Pcb.kind(blk) == 'segment':
            u, v = (round(g[0], 4), round(g[1], 4), g[5]), (round(g[2], 4), round(g[3], 4), g[5])
            edge(u, v, math.dist(u[:2], v[:2])); nodes |= {u, v}; segs.append((u, v))
        else:
            a, b = (round(g[0], 4), round(g[1], 4), 'F.Cu'), (round(g[0], 4), round(g[1], 4), 'B.Cu')
            edge(a, b, 0.0); nodes |= {a, b}
    nodes = list(nodes)
    for i, u in enumerate(nodes):
        for v in nodes[i + 1:]:
            if u[2] == v[2] and math.dist(u[:2], v[:2]) < 1e-3: edge(u, v, 0.0)
        for a, b in segs:                       # a track ending on another's centre line
            if a[2] == u[2] and u not in (a, b) and _pt_seg(u[0], u[1], *a[:2], *b[:2]) < 1e-3:
                edge(u, a, math.dist(u[:2], a[:2])); edge(u, b, math.dist(u[:2], b[:2]))
    for key, qs in pads.items():                # a pad joins every track end inside it
        for q in qs:
            if q['net'] != net: continue
            for u in nodes:
                if (u[2] in q['layers'] or '*.Cu' in q['layers']) and \
                        abs(u[0] - q['x']) <= q['bw'] / 2 and abs(u[1] - q['y']) <= q['bh'] / 2:
                    edge(key, u, math.dist((q['x'], q['y']), u[:2]))
    return adj, nodes


def path_len(p, pads, net, a, b):
    """shortest copper path, pad centre to pad centre, over one net's tracks and vias"""
    adj, nodes = graph(p, pads, net)
    dist, h, n = {a: 0.0}, [(0.0, 0, a)], 0
    while h:
        d, _, u = heapq.heappop(h)
        if u == b: return round(d, 2)
        if d > dist.get(u, 1e9): continue
        for v, w in adj.get(u, []):
            if d + w < dist.get(v, 1e9):
                n += 1; dist[v] = d + w; heapq.heappush(h, (d + w, n, v))
    return None


def fb_items(p, pads):
    """the FB sense: ESP_3V3 copper reachable from U3.1 without passing through C11.1"""
    q1, q11 = pads[('U3', '1')][0], pads[('C11', '1')][0]
    def in_pad(q, x, y): return abs(x - q['x']) <= q['bw'] / 2 and abs(y - q['y']) <= q['bh'] / 2
    items = [b for b in p.blocks if Pcb.net(b) == '/ESP_3V3']
    def ends(b):
        g = Pcb.geom(b)
        if Pcb.kind(b) == 'segment': return [(g[0], g[1], g[5]), (g[2], g[3], g[5])]
        return [(g[0], g[1], 'F.Cu'), (g[0], g[1], 'B.Cu')]
    seen = {i for i, b in enumerate(items) if any(l == 'F.Cu' and in_pad(q1, x, y) for x, y, l in ends(b))}
    todo = list(seen)
    while todo:
        i = todo.pop()
        frontier = [e for e in ends(items[i]) if not (e[2] == 'F.Cu' and in_pad(q11, e[0], e[1]))]
        for j, b in enumerate(items):
            if j in seen: continue
            if any(e[2] == f[2] and math.dist(e[:2], f[:2]) < 1e-3 for e in frontier for f in ends(b)):
                seen.add(j); todo.append(j)
    return [items[i] for i in sorted(seen)]


def lengths(blocks):
    out, vias = {}, 0
    for b in blocks:
        g = Pcb.geom(b)
        if Pcb.kind(b) == 'segment':
            out[g[5]] = round(out.get(g[5], 0.0) + math.dist(g[:2], g[2:4]), 2)
        else:
            vias += 1
    return out, vias


def report(path):
    p, pads = load(path)
    sw = {l: sum((copper(p, pads, n, l) for n in SWITCH), []) for l in ('F.Cu', 'B.Cu')}
    en = [b for b in p.blocks if Pcb.net(b) == '/REG_EN']
    en_len, en_vias = lengths(en)
    x0, y0, x1, y1 = U3_CRTYD
    under = [Pcb.geom(b)[:2] for b in en if Pcb.kind(b) == 'via']
    fb = fb_items(p, pads)
    fb_len, fb_vias = lengths(fb)
    fb_f = [shape('seg', *g[:4], g[4] / 2) if Pcb.kind(b) == 'segment' else shape('seg', g[0], g[1], g[0], g[1], g[2] / 2)
            for b in fb for g in [Pcb.geom(b)] if Pcb.kind(b) == 'via' or g[5] == 'F.Cu']
    fb_b = [shape('seg', *g[:4], g[4] / 2) for b in fb for g in [Pcb.geom(b)]
            if Pcb.kind(b) == 'segment' and g[5] == 'B.Cu']
    vsys_vias = [Pcb.geom(b)[:2] for b in p.blocks if Pcb.net(b) == '/VSYS' and Pcb.kind(b) == 'via']
    return {
        'REG_EN': {
            'track_mm': en_len, 'vias': en_vias,
            'vias_inside_U3_courtyard': sum(x0 <= x <= x1 and y0 <= y <= y1 for x, y in under),
            'copper_path_mm': {'U3.2 -> C13.1': path_len(p, pads, '/REG_EN', ('U3', '2'), ('C13', '1')),
                               'U3.2 -> R8.1': path_len(p, pads, '/REG_EN', ('U3', '2'), ('R8', '1')),
                               'U3.2 -> R7.2': path_len(p, pads, '/REG_EN', ('U3', '2'), ('R7', '2')),
                               'U3.2 -> R9.2': path_len(p, pads, '/REG_EN', ('U3', '2'), ('R9', '2'))},
            'vias_gap_to_SW_BST_mm': min_gap([shape('seg', g[0], g[1], g[0], g[1], g[2] / 2)
                                              for b in en if Pcb.kind(b) == 'via' for g in [Pcb.geom(b)]],
                                             sw['F.Cu'] + sw['B.Cu']),
            'gap_to_SW_BST_mm': {
                'including U3.2 itself (= DRC)': min_gap(copper(p, pads, '/REG_EN', 'F.Cu'), sw['F.Cu']),
                'copper the layout places (U3.2 excluded)': min(
                    min_gap(copper(p, pads, '/REG_EN', l, skip_pads={('U3', '2')}), sw[l]) for l in ('F.Cu', 'B.Cu'))},
        },
        'FB (U3.1 -> C11.1)': {
            'track_mm': fb_len, 'vias': fb_vias,
            'copper_path_mm': path_len(p, pads, '/ESP_3V3', ('U3', '1'), ('C11', '1')),
            'F.Cu gap to SW_BST_mm': min_gap(fb_f, sw['F.Cu']),
            'B.Cu run, plan distance to F.Cu SW_BST_mm': min_gap(fb_b, sw['F.Cu']) if fb_b else None,
        },
        'VSYS': {'vias': len(vsys_vias),
                 'copper_path_mm C12.1 -> C17.1': path_len(p, pads, '/VSYS', ('C12', '1'), ('C17', '1'))},
        'vias_total': sum(Pcb.kind(b) == 'via' for b in p.blocks),
    }


def changed_nets(a, b):
    def items(path):
        return {(Pcb.kind(x), Pcb.net(x)) + tuple(round(v, 4) if isinstance(v, float) else v for v in Pcb.geom(x))
                for x in Pcb(path).blocks}
    A, B = items(a), items(b); out = {}
    for tag, S in (('removed', A - B), ('added', B - A)):
        for it in S: out.setdefault(it[1], {'removed': 0, 'added': 0})[tag] += 1
    return dict(sorted(out.items()))


if __name__ == '__main__':
    res = {'before': report(sys.argv[1]), 'after': report(sys.argv[2]),
           'changed_nets': changed_nets(sys.argv[1], sys.argv[2])}
    txt = json.dumps(res, indent=2)
    if '--json' in sys.argv: open(sys.argv[sys.argv.index('--json') + 1], 'w').write(txt + '\n')
    print(txt)
