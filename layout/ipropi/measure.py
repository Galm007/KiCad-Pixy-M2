#!/usr/bin/env python3
"""IPROPI rework measurements: how close GPIO2/GPIO10 come to motor and drive
copper, how much of each run sits near it, and which nets differ from a
reference board.

    python3 layout/ipropi/measure.py BEFORE.kicad_pcb AFTER.kicad_pcb [--json OUT]

Gaps are copper edge to copper edge on the same layer; a via counts on both
outer layers.  The geometry helpers are layout/reg-en/measure.py's, whose
gaps reproduce KiCad's DRC.  "Within d" sums the track length of the sense
net whose edge lies within d of the aggressor copper; it is the parallel-run
exposure that crosstalk scales with, which a single minimum does not show.
"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'reg-en'))
from measure import load, copper, gap, shape, min_gap, lengths, changed_nets, _pt_seg
from pcbedit import Pcb
import heapq

MOTOR = ['/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2']
DRIVE = {'/GPIO2': ['/GPIO39', '/GPIO40'], '/GPIO10': ['/GPIO41', '/GPIO42']}
ENDS = {'/GPIO2': (('U4', '1'), ('R17', '1'), ('U1', '38')),
        '/GPIO10': (('U5', '1'), ('R18', '1'), ('U1', '18'))}
ISLAND = (100.5, 88.0, 127.0, 122.0)          # In2 VBAT motor rail island
BANDS = (0.6, 1.0, 2.0, 3.0)
STEP = 0.05


def exposure(p, pads, net, aggressors):
    """track length of `net` within each band of the aggressor copper"""
    agg = {l: sum((copper(p, pads, n, l) for n in aggressors), []) for l in ('F.Cu', 'B.Cu')}
    out = {b: 0.0 for b in BANDS}
    for blk in p.blocks:
        if Pcb.net(blk) != net or Pcb.kind(blk) != 'segment': continue
        x1, y1, x2, y2, w, l = Pcb.geom(blk)
        L = math.dist((x1, y1), (x2, y2)); n = max(1, int(L / STEP))
        for i in range(n):
            t = (i + 0.5) / n
            me = shape('seg', x1 + (x2 - x1) * t, y1 + (y2 - y1) * t,
                       x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, w / 2)
            d = min((gap(me, a) for a in agg[l]), default=9e9)
            for b in BANDS:
                if d < b: out[b] += L / n
    return {f'{b} mm': round(v, 1) for b, v in out.items()}


def nearest(p, pads, net, aggressors):
    """minimum gap from the net's tracks, vias and pads, each kind separately"""
    res = {}
    for kind in ('segment', 'via', 'pad'):
        best = 9e9
        for l in ('F.Cu', 'B.Cu'):
            agg = sum((copper(p, pads, n, l) for n in aggressors), [])
            mine = []
            if kind == 'pad':
                mine = [s for s in copper(p, pads, net, l) if s[0] == 'box']
            else:
                for blk in p.blocks:
                    if Pcb.net(blk) != net or Pcb.kind(blk) != kind: continue
                    g = Pcb.geom(blk)
                    if kind == 'segment' and g[5] == l:
                        mine.append(shape('seg', *g[:4], g[4] / 2))
                    elif kind == 'via':
                        mine.append(shape('seg', g[0], g[1], g[0], g[1], g[2] / 2))
            best = min(best, min_gap(mine, agg))
        res[kind + 's'] = round(best, 3) if best < 1e8 else None
    return res


def over_island(p, net):
    L = 0.0
    x0, y0, x1, y1 = ISLAND
    for blk in p.blocks:
        if Pcb.net(blk) != net or Pcb.kind(blk) != 'segment': continue
        a, b, c, d, w, l = Pcb.geom(blk)
        if l != 'B.Cu': continue
        n = max(1, int(math.dist((a, b), (c, d)) / STEP))
        for i in range(n):
            t = (i + 0.5) / n
            x, y = a + (c - a) * t, b + (d - b) * t
            if x0 <= x <= x1 and y0 <= y <= y1: L += math.dist((a, b), (c, d)) / n
    return round(L, 1)


def path_len(p, pads, net, a, b):
    """shortest copper path, pad centre to pad centre.  Unlike reg-en's, this
    graph also joins a track end that lands anywhere on a via's annulus, and
    two ends whose 0.2 mm round caps overlap: the old GPIO2 route has both, and
    KiCad connects them where an exact-endpoint graph does not."""
    adj, nodes, vias, segs = {}, set(), [], []
    def edge(u, v, d):
        adj.setdefault(u, []).append((v, d)); adj.setdefault(v, []).append((u, d))
    for blk in p.blocks:
        if Pcb.net(blk) != net: continue
        g = Pcb.geom(blk)
        if Pcb.kind(blk) == 'segment':
            u, v = (round(g[0], 4), round(g[1], 4), g[5]), (round(g[2], 4), round(g[3], 4), g[5])
            edge(u, v, math.dist(u[:2], v[:2])); nodes |= {u, v}; segs.append((u, v))
        else:
            f, k = (round(g[0], 4), round(g[1], 4), 'F.Cu'), (round(g[0], 4), round(g[1], 4), 'B.Cu')
            edge(f, k, 0.0); nodes |= {f, k}; vias.append((f, k, g[2] / 2))
    nodes = list(nodes)
    for f, k, r in vias:
        for u in nodes:
            for c in (f, k):
                if u[2] == c[2] and u != c and math.dist(u[:2], c[:2]) <= r:
                    edge(u, c, math.dist(u[:2], c[:2]))
    for i, u in enumerate(nodes):
        for v in nodes[i + 1:]:
            if u[2] == v[2] and math.dist(u[:2], v[:2]) < 0.2:
                edge(u, v, math.dist(u[:2], v[:2]))
        for s0, s1 in segs:
            if s0[2] == u[2] and u not in (s0, s1) and _pt_seg(u[0], u[1], *s0[:2], *s1[:2]) < 1e-3:
                edge(u, s0, math.dist(u[:2], s0[:2])); edge(u, s1, math.dist(u[:2], s1[:2]))
    for key, qs in pads.items():
        for q in qs:
            if q['net'] != net: continue
            for u in nodes:
                if (u[2] in q['layers'] or '*.Cu' in q['layers']) and \
                        abs(u[0] - q['x']) <= q['bw'] / 2 and abs(u[1] - q['y']) <= q['bh'] / 2:
                    edge(key, u, math.dist((q['x'], q['y']), u[:2]))
    dist, h, n = {a: 0.0}, [(0.0, 0, a)], 0
    while h:
        d, _, u = heapq.heappop(h)
        if u == b: return round(d, 2)
        if d > dist.get(u, 1e9): continue
        for v, w in adj.get(u, []):
            if d + w < dist.get(v, 1e9):
                n += 1; dist[v] = d + w; heapq.heappush(h, (d + w, n, v))
    return None


def report(path):
    p, pads = load(path)
    out = {}
    for net, (pin, res, adc) in ENDS.items():
        blocks = [b for b in p.blocks if Pcb.net(b) == net]
        track, vias = lengths(blocks)
        out[net] = {
            'track_mm': track, 'vias': vias,
            'B.Cu over the VBAT island_mm': over_island(p, net),
            'copper_path_mm': {f'{pin[0]}.{pin[1]} -> {res[0]}.{res[1]}': path_len(p, pads, net, pin, res),
                               f'{pin[0]}.{pin[1]} -> {adc[0]}.{adc[1]}': path_len(p, pads, net, pin, adc)},
            'motor copper': {'nearest_mm': nearest(p, pads, net, MOTOR),
                             'track within': exposure(p, pads, net, MOTOR)},
            'drive copper (' + '/'.join(n.lstrip('/') for n in DRIVE[net]) + ')':
                {'nearest_mm': nearest(p, pads, net, DRIVE[net]),
                 'track within': exposure(p, pads, net, DRIVE[net])},
        }
    out['vias_total'] = sum(Pcb.kind(b) == 'via' for b in p.blocks)
    return out


if __name__ == '__main__':
    res = {'before': report(sys.argv[1]), 'after': report(sys.argv[2]),
           'changed_nets': changed_nets(sys.argv[1], sys.argv[2])}
    txt = json.dumps(res, indent=2)
    if '--json' in sys.argv: open(sys.argv[sys.argv.index('--json') + 1], 'w').write(txt + '\n')
    print(txt)
