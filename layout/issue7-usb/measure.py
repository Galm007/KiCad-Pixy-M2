#!/usr/bin/env python3
"""Issue-7 USB measurements: per-net copper, end-to-end path per polarity,
pair gap along the coupled run, and which nets differ from a reference board.

    python3 layout/issue7-usb/measure.py BEFORE.kicad_pcb AFTER.kicad_pcb [--json OUT]
"""
import heapq, json, math, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'autoroute'))
from pcbedit import Pcb
from sexp import parse, children
from load import fp_info

NETS = {'D+': ('Net-(J1-D+-PadA6)', '/USB_D+'), 'D-': ('Net-(J1-D--PadA7)', '/USB_D-')}
# connector pad, U2 connector-side pin, U2 module-side pin, U1 pin
ENDS = {'D+': (('J1', 'A6'), ('U2', '3'), ('U2', '4'), ('U1', '14')),
        'D-': (('J1', 'B7'), ('U2', '1'), ('U2', '6'), ('U1', '13'))}


def load(path):
    p = Pcb(path)
    pads = {}
    for f in children(parse(p.text), 'footprint'):
        fi = fp_info(f)
        for q in fi['pads']:
            pads[(fi['ref'], q['num'])] = q
    return p, pads


def inside(q, x, y):
    w, h = q['w'], q['h']
    if abs(q['rot'] % 180 - 90) < 1: w, h = h, w
    return abs(x - q['x']) <= w / 2 + 1e-6 and abs(y - q['y']) <= h / 2 + 1e-6


def path_len(p, pads, net, a, b):
    """shortest copper path between two pads over one net's tracks and vias"""
    adj = {}
    def edge(u, v, d):
        adj.setdefault(u, []).append((v, d)); adj.setdefault(v, []).append((u, d))
    nodes = set()
    for blk in p.blocks:
        if Pcb.net(blk) != net: continue
        g = Pcb.geom(blk)
        if Pcb.kind(blk) == 'segment':
            u, v = (round(g[0], 4), round(g[1], 4), g[5]), (round(g[2], 4), round(g[3], 4), g[5])
            edge(u, v, math.dist(u[:2], v[:2])); nodes |= {u, v}
        else:
            for l in ('F.Cu', 'B.Cu'):
                nodes.add((round(g[0], 4), round(g[1], 4), l))
            edge((round(g[0], 4), round(g[1], 4), 'F.Cu'), (round(g[0], 4), round(g[1], 4), 'B.Cu'), 0.0)
    nodes = list(nodes)
    for i, u in enumerate(nodes):          # endpoints that coincide
        for v in nodes[i + 1:]:
            if u[2] == v[2] and math.dist(u[:2], v[:2]) < 1e-3: edge(u, v, 0.0)
    for tag, key in (('A', a), ('B', b)):
        q = pads[key]
        for u in nodes:
            if u[2] == 'F.Cu' and inside(q, u[0], u[1]):
                edge(tag, u, math.dist((q['x'], q['y']), u[:2]))
    dist, h = {'A': 0.0}, [(0.0, 'A')]
    while h:
        d, u = heapq.heappop(h)
        if u == 'B': return d
        if d > dist.get(u, 1e9): continue
        for v, w in adj.get(u, []):
            if d + w < dist.get(v, 1e9):
                dist[v] = d + w; heapq.heappush(h, (d + w, v))
    return None


def per_net(p, net):
    L, widths, layers, vias = 0.0, set(), {}, 0
    for b in p.blocks:
        if Pcb.net(b) != net: continue
        g = Pcb.geom(b)
        if Pcb.kind(b) == 'segment':
            d = math.dist(g[:2], g[2:4]); L += d; widths.add(g[4])
            layers[g[5]] = round(layers.get(g[5], 0) + d, 2)
        else:
            vias += 1
    return dict(track_mm=round(L, 2), vias=vias, widths=sorted(widths), layers=layers)


def segs(p, net, layer='F.Cu'):
    return [Pcb.geom(b) for b in p.blocks if Pcb.net(b) == net and Pcb.kind(b) == 'segment'
            and Pcb.geom(b)[5] == layer]


def pt_seg(px, py, s):
    x1, y1, x2, y2 = s[:4]
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)


def pair_gap(p, a, b, couple=0.35, step=0.01):
    """edge-to-edge gap sampled along net a, where b is within `couple` mm"""
    sb = segs(p, b)
    gaps, coupled = [], 0.0
    for s in segs(p, a):
        L = math.dist(s[:2], s[2:4]); n = max(1, int(L / step))
        for i in range(n):
            t = (i + 0.5) / n
            x, y = s[0] + (s[2] - s[0]) * t, s[1] + (s[3] - s[1]) * t
            g = min(pt_seg(x, y, q) - q[4] / 2 for q in sb) - s[4] / 2
            if g <= couple:
                gaps.append(g); coupled += L / n
    return dict(coupled_mm=round(coupled, 2),
                gap_min=round(min(gaps), 3) if gaps else None,
                gap_max=round(max(gaps), 3) if gaps else None)


def other_net_clearance(p, pads, nets):
    """closest other-net F.Cu copper (tracks and via pads) to the USB tracks"""
    mine = [s for n in nets for s in segs(p, n)]
    best = (9.0, None)
    for b in p.blocks:
        n = Pcb.net(b)
        if n in nets: continue
        g = Pcb.geom(b)
        if Pcb.kind(b) == 'segment':
            if g[5] != 'F.Cu': continue
            L =math.dist(g[:2], g[2:4]); k = max(1, int(L / 0.02))
            for i in range(k + 1):
                x, y = g[0] + (g[2] - g[0]) * i / k, g[1] + (g[3] - g[1]) * i / k
                for s in mine:
                    d = pt_seg(x, y, s) - s[4] / 2 - g[4] / 2
                    if d < best[0]: best = (d, n)
        else:
            for s in mine:
                d = pt_seg(g[0], g[1], s) - s[4] / 2 - g[2] / 2
                if d < best[0]: best = (d, n)
    return dict(min_mm=round(best[0], 3), net=best[1])


def report(path):
    p, pads = load(path)
    out = {'nets': {n: per_net(p, n) for pol in NETS.values() for n in pol}}
    ends = {}
    for pol, (j, uc, um, u1) in ENDS.items():
        conn = path_len(p, pads, NETS[pol][0], j, uc)
        mod = path_len(p, pads, NETS[pol][1], um, u1)
        ends[pol] = dict(connector_to_U2=round(conn, 2), U2_to_U1=round(mod, 2),
                         total=round(conn + mod, 2))
    ends['skew_mm'] = round(ends['D+']['total'] - ends['D-']['total'], 2)
    out['end_to_end'] = ends
    out['module_side_pair'] = pair_gap(p, '/USB_D+', '/USB_D-')
    out['connector_side_pair'] = pair_gap(p, 'Net-(J1-D+-PadA6)', 'Net-(J1-D--PadA7)')
    out['nearest_other_fcu'] = other_net_clearance(p, pads, [n for v in NETS.values() for n in v])
    out['vias_total'] = sum(Pcb.kind(b) == 'via' for b in p.blocks)
    return out


def changed_nets(a, b):
    def items(path):
        p = Pcb(path); s = set()
        for blk in p.blocks:
            s.add((Pcb.kind(blk), Pcb.net(blk)) + tuple(round(v, 4) if isinstance(v, float) else v
                                                          for v in Pcb.geom(blk)))
        return s
    A, B = items(a), items(b)
    nets = {}
    for tag, S in (('removed', A - B), ('added', B - A)):
        for it in S:
            nets.setdefault(it[1], {'removed': 0, 'added': 0})[tag] += 1
    return nets


if __name__ == '__main__':
    before, after = sys.argv[1], sys.argv[2]
    res = {'before': report(before), 'after': report(after),
           'changed_nets': changed_nets(before, after)}
    txt = json.dumps(res, indent=2)
    if '--json' in sys.argv:
        open(sys.argv[sys.argv.index('--json') + 1], 'w').write(txt + '\n')
    print(txt)
