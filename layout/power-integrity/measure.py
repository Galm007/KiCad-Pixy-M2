#!/usr/bin/env python3
"""Copper totals, part-field audit and the corridor clearances of the power stage.

    /usr/bin/python3 layout/power-integrity/measure.py BOARD [REPLAY_BOARD]

Reports, besides totals: each watched net's closest same-layer approach to
motor-output copper and to the buck's SW/BST copper, its track length and via
count. With a second board, asserts that both have identical copper (UUIDs and
zone fills excluded), i.e. that a full replay reproduces the board.
"""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools' / 'autoroute'))
from power_integrity_data import PARTS, CURRENT_FIELDS
from pcbedit import Pcb
from sexp import parse, children, child, val

WATCH = ['/GPIO11', '/GPIO12', '/GPIO13', '/GPIO14', '/GPIO15', '/GPIO16', '/GPIO17',
         '/GPIO18', '/GPIO21', '/GPIO47', '/GPIO48', '/GPIO2', '/GPIO10', '/GPIO8', '/GPIO9',
         '/MOTOR_UVLO', '/MOTOR_VREF', '/MOTOR_OK', '/BUCK_3V3', '/BUCK_PASS', '/BUCK_GATE',
         '/BUCK_ENABLE', '/USB_PRIORITY', '/DEVKIT_5V', '/DRV_A_IN1', '/DRV_A_IN2',
         '/DRV_B_IN1', '/DRV_B_IN2']


def _xf(fx, fy, rot, px, py):
    a = math.radians(rot)
    return fx + px * math.cos(a) + py * math.sin(a), fy - px * math.sin(a) + py * math.cos(a)


def _pseg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = dx * dx + dy * dy
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d)) if d else 0
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _segseg(a, b, c, d):
    def cr(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if (cr(c, d, a) > 0) != (cr(c, d, b) > 0) and (cr(a, b, c) > 0) != (cr(a, b, d) > 0):
        return 0.0
    return min(_pseg(a, c, d), _pseg(b, c, d), _pseg(c, a, b), _pseg(d, a, b))


def copper(p, t):
    """net -> [(layers, a, b, radius)]: tracks, vias and pads (pads as their
    inscribed-width capsule along the long axis, adequate for clearance)"""
    out = defaultdict(list)
    for b in p.blocks:
        k = Pcb.kind(b)
        if k == 'segment':
            g = Pcb.geom(b)
            out[Pcb.net(b)].append(({g[5]}, g[:2], g[2:4], g[4] / 2))
        elif k == 'via':
            g = Pcb.geom(b)
            out[Pcb.net(b)].append(({'F.Cu', 'B.Cu'}, g[:2], g[:2], g[2] / 2))
    for f in children(t, 'footprint'):
        at = child(f, 'at')
        fx, fy, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
        for pad in children(f, 'pad'):
            net = child(pad, 'net')
            if not net:
                continue
            pa, sz = child(pad, 'at'), child(pad, 'size')
            w, h = float(sz[1]), float(sz[2])
            ang = math.radians(float(pa[3]) if len(pa) > 3 else 0.0)
            cx, cy = _xf(fx, fy, rot, float(pa[1]), float(pa[2]))
            ln = max(w, h) / 2 - min(w, h) / 2
            ux, uy = (math.cos(ang), -math.sin(ang)) if w >= h else (math.sin(ang), math.cos(ang))
            lay = {val(l) for l in child(pad, 'layers')[1:]}
            lay = {'F.Cu', 'B.Cu'} if '*.Cu' in lay else lay & {'F.Cu', 'B.Cu'}
            out[val(net[1])].append((lay, (cx - ux * ln, cy - uy * ln), (cx + ux * ln, cy + uy * ln),
                                     min(w, h) / 2))
    return out


def closest(cu, a_nets, b_nets):
    best = math.inf
    for na in a_nets:
        for la, a1, a2, ra in cu.get(na, []):
            for nb in b_nets:
                for lb, b1, b2, rb in cu.get(nb, []):
                    if la & lb:
                        best = min(best, _segseg(a1, a2, b1, b2) - ra - rb)
    return round(best, 2)


def measure(path):
    p = Pcb(path)
    t = parse(p.text)
    raw = {}
    for f in children(t, 'footprint'):
        props = {val(c[1]): val(c[2]) for c in children(f, 'property')}
        raw[props['Reference']] = (f, props)
    checked = 0
    for ref, fields in {**{r: d['fields'] for r, d in PARTS.items()},
                        'R17': CURRENT_FIELDS, 'R18': CURRENT_FIELDS}.items():
        f, props = raw[ref]
        for k, v in fields.items():
            got = val(f[1]) if k == 'Footprint' else props.get(k)
            assert got == v, (ref, k, v, got)
        checked += 1
    segs = [Pcb.geom(b) for b in p.blocks if Pcb.kind(b) == 'segment']
    vias = [Pcb.geom(b) for b in p.blocks if Pcb.kind(b) == 'via']
    ground = []
    for z in children(t, 'zone'):
        layer = child(z, 'layer')
        if layer and val(layer[1]) == 'In1.Cu':
            assert val(child(z, 'net')[1]) == 'GND'
            ground.append(z)
    assert len(ground) == 1 and not any(s[5] == 'In1.Cu' for s in segs)
    cu = copper(p, t)
    motor = {n for n in cu if n.startswith('/MOT_')}
    sw = {'Net-(U3-SW)', 'Net-(U3-BST)'}
    length, nvia = defaultdict(float), Counter()
    for b in p.blocks:
        if Pcb.kind(b) == 'segment':
            g = Pcb.geom(b)
            length[Pcb.net(b)] += math.dist(g[:2], g[2:4])
        elif Pcb.kind(b) == 'via':
            nvia[Pcb.net(b)] += 1
    nets = {n: dict(to_motor_mm=closest(cu, [n], motor), to_sw_bst_mm=closest(cu, [n], sw),
                    length_mm=round(length[n], 1), vias=nvia[n]) for n in WATCH if n in cu}
    return dict(footprints=len(raw), vias=len(vias), segments=len(segs),
                track_length_mm=round(sum(math.dist(s[:2], s[2:4]) for s in segs), 1),
                segments_by_layer=dict(Counter(s[5] for s in segs)),
                uninterrupted_In1_GND_zone=True, parts_with_fields_checked=checked,
                ordinary_via_dimensions_mm=sorted(set((v[2], v[3]) for v in vias if v[3] != .25)),
                new_parts_top_side_only=all(val(child(raw[r][0], 'layer')[1]) == 'F.Cu' for r in PARTS),
                same_layer_clearance_and_length=nets)


def geometry(path):
    p = Pcb(path)
    return sorted((Pcb.kind(b), Pcb.net(b), Pcb.geom(b)) for b in p.blocks)


if __name__ == '__main__':
    print(json.dumps(measure(sys.argv[1]), indent=2))
    if len(sys.argv) > 2:
        assert geometry(sys.argv[1]) == geometry(sys.argv[2]), 'replay copper differs'
        print('Replay copper geometry matches exactly (UUIDs and zone fills excluded).')
