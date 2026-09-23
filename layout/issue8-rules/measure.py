#!/usr/bin/env python3
"""Issue-8 measurements: per-net track widths, supply-path resistance, and
which nets differ from a reference board.

    python3 layout/issue8-rules/measure.py BEFORE.kicad_pcb AFTER.kicad_pcb [--json OUT]
"""
import collections, heapq, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'autoroute'))
from pcbedit import Pcb
from sexp import parse, children
from load import fp_info

RHO, T_CU = 1.72e-8, 35e-6          # copper at 20 C, 1 oz outer layer
NETS = ['/GPIO2', '/GPIO10', '/GPIO39', '/GPIO40', '/GPIO41', '/VBUS', 'Net-(F2-Pad1)',
        '/VSYS', '/VBAT_RAW', '/VBAT_FUSED']
PATHS = [('USB input, J1.A9 -> F2.1', 'Net-(F2-Pad1)', ('J1', 'A9'), ('F2', '1')),
         ('USB input, J1.A4 -> F2.1', 'Net-(F2-Pad1)', ('J1', 'A4'), ('F2', '1')),
         ('VBUS, F2.2 -> D1.2', '/VBUS', ('F2', '2'), ('D1', '2')),
         ('battery, F1.2 -> Q1 source', '/VBAT_FUSED', ('F1', '2'), ('Q1', '1'))]


def load(path):
    p = Pcb(path); pads = collections.defaultdict(list)
    for f in children(parse(p.text), 'footprint'):
        fi = fp_info(f)
        for q in fi['pads']:
            pads[(fi['ref'], q['num'])].append(q)
    return p, pads


def inside(q, x, y):
    w, h = q['w'], q['h']
    if abs(q['rot'] % 180 - 90) < 1: w, h = h, w
    return abs(x - q['x']) <= w / 2 + 1e-6 and abs(y - q['y']) <= h / 2 + 1e-6


def graph(p, pads, net):
    """copper graph of one net: track endpoints, T-junctions, via barrels,
    overlapping end caps, and every node inside a common pad"""
    adj = collections.defaultdict(list)
    def e(u, v, r): adj[u].append((v, r)); adj[v].append((u, r))
    segs = [Pcb.geom(b) for b in p.blocks if Pcb.net(b) == net and Pcb.kind(b) == 'segment']
    vias = [Pcb.geom(b) for b in p.blocks if Pcb.net(b) == net and Pcb.kind(b) == 'via']
    nodes = set()
    for g in segs:
        u, v = (round(g[0], 3), round(g[1], 3), g[5]), (round(g[2], 3), round(g[3], 3), g[5])
        e(u, v, RHO * math.dist(g[:2], g[2:4]) * 1e-3 / (g[4] * 1e-3 * T_CU)); nodes |= {u, v}
    for g in vias:
        a, b = (round(g[0], 3), round(g[1], 3), 'F.Cu'), (round(g[0], 3), round(g[1], 3), 'B.Cu')
        e(a, b, 0.0); nodes |= {a, b}
    nodes = list(nodes)
    for i, u in enumerate(nodes):
        for v in nodes[i + 1:]:
            if u[2] == v[2] and math.dist(u[:2], v[:2]) < 0.3: e(u, v, 0.0)   # overlapping caps
        for g in segs:
            if g[5] != u[2]: continue
            x1, y1, x2, y2 = g[:4]; dx, dy = x2 - x1, y2 - y1; L2 = dx * dx + dy * dy
            if not L2: continue
            t = max(0, min(1, ((u[0] - x1) * dx + (u[1] - y1) * dy) / L2))
            if 1e-6 < t < 1 - 1e-6 and math.hypot(u[0] - x1 - t * dx, u[1] - y1 - t * dy) < g[4] / 2:
                r = RHO * math.sqrt(L2) * 1e-3 / (g[4] * 1e-3 * T_CU)
                e(u, (round(x1, 3), round(y1, 3), g[5]), r * t); e(u, (round(x2, 3), round(y2, 3), g[5]), r * (1 - t))
    for qs in pads.values():
        for q in qs:
            if q['net'] != net: continue
            inn = [u for u in nodes if (u[2] in q['layers'] or '*.Cu' in q['layers']) and inside(q, *u[:2])]
            for a in inn[1:]: e(inn[0], a, 0.0)
    return adj, nodes


def resistance(p, pads, net, a, b):
    adj, nodes = graph(p, pads, net)
    S = [u for q in pads[a] for u in nodes if (u[2] in q['layers']) and inside(q, *u[:2])]
    T = {u for q in pads[b] for u in nodes if (u[2] in q['layers']) and inside(q, *u[:2])}
    dist, h = {}, [(0.0, s) for s in S]
    for s in S: dist[s] = 0.0
    while h:
        d, u = heapq.heappop(h)
        if u in T: return d
        if d > dist.get(u, 1e9): continue
        for v, r in adj[u]:
            if d + r < dist.get(v, 1e9): dist[v] = d + r; heapq.heappush(h, (d + r, v))
    return None


def widths(p):
    W = collections.defaultdict(collections.Counter)
    for b in p.blocks:
        if Pcb.kind(b) == 'segment':
            g = Pcb.geom(b); W[Pcb.net(b)][g[4]] += math.dist(g[:2], g[2:4])
    return W


def report(path):
    p, pads = load(path); W = widths(p)
    allw = collections.Counter()
    for c in W.values(): allw.update(c)
    return {'widths_mm': {n: {str(w): round(l, 2) for w, l in sorted(W[n].items())} for n in NETS},
            'track_below_0.2mm': round(sum(l for w, l in allw.items() if w < 0.2), 2),
            'path_resistance_mohm': {k: (round(1e3 * r, 1) if (r := resistance(p, pads, n, a, b)) is not None else None)
                                     for k, n, a, b in PATHS},
            'vias': sum(Pcb.kind(b) == 'via' for b in p.blocks)}


def changed_nets(a, b):
    def items(path):
        return {(Pcb.kind(x), Pcb.net(x)) + tuple(round(v, 4) if isinstance(v, float) else v for v in Pcb.geom(x))
                for x in Pcb(path).blocks}
    A, B = items(a), items(b); out = {}
    for tag, S in (('removed', A - B), ('added', B - A)):
        for it in S: out.setdefault(it[1], {'removed': 0, 'added': 0})[tag] += 1
    return out


if __name__ == '__main__':
    res = {'before': report(sys.argv[1]), 'after': report(sys.argv[2]),
           'changed_nets': changed_nets(sys.argv[1], sys.argv[2])}
    txt = json.dumps(res, indent=2)
    if '--json' in sys.argv: open(sys.argv[sys.argv.index('--json') + 1], 'w').write(txt + '\n')
    print(txt)
