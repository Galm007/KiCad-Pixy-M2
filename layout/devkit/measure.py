#!/usr/bin/env python3
"""Measurements for the DevKitC-1 daughterboard stage (tools/autoroute/devkit.py).

    python3 layout/devkit/measure.py BEFORE.kicad_pcb AFTER.kicad_pcb [--json OUT]

For each board: the custom-rule clearances by DRC descent (issue8-rules/
clearmin.py, the method whose numbers match KiCad's DRC), the motor pair loop
areas (tools/autoroute/loop.py) and their lobes, via and track totals, and
where the parts this stage moved ended up.  For AFTER also: how far the
devkit's pad 1 is from the R3 corner and the IMU chip from the rotation centre.
"""
import collections
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'autoroute'))
sys.path.insert(0, os.path.join(ROOT, 'layout', 'issue8-rules'))
import clearmin                                 # noqa: E402
import loop                                     # noqa: E402
from sexp import parse, children, child, val    # noqa: E402
from load import fp_info                        # noqa: E402

OX, OY = 100.0, 60.0
ROT_CENTRE = (133.0, 126.0)
PAIRS = ['REG_EN-SW', 'REG_EN-motor', 'VBAT_SENSE-SW', 'VBAT_SENSE-motor', 'IPROPI-motor']
REFS = ['U1', 'J8', 'J9', 'J10', 'SW3', 'C22', 'R10', 'C14', 'R11', 'D4', 'D5', 'R12', 'R13',
        'TP3', 'TP9', 'C1', 'C2', 'R19', 'R20', 'R23']


def board_coords(x, y):
    return round(x - OX, 3), round(y - OY, 3)


def totals(t):
    vias = collections.Counter()
    for v in children(t, 'via'):
        n = val(child(v, 'net')[1])
        vias['GND' if n == 'GND' else ('3V3' if n == '/ESP_3V3' else
                                         ('VBAT' if n == '/VBAT' else 'signal'))] += 1
    length = collections.Counter()
    for s in children(t, 'segment'):
        a, b = child(s, 'start'), child(s, 'end')
        length[val(child(s, 'layer')[1])] += math.dist((float(a[1]), float(a[2])),
                                                       (float(b[1]), float(b[2])))
    return ({k: vias[k] for k in sorted(vias)} | {'total': sum(vias.values())},
            {k: round(v, 1) for k, v in sorted(length.items())} | {'total': round(sum(length.values()), 1)})


def lobes(path, h=0.02):
    """the motor loops split by winding number: area enclosed clockwise and
    anticlockwise.  loop.py's signed area is their difference, so where a pair
    crosses itself the lobes either side cancel; their sum is the copper the
    loop actually encloses."""
    p = loop.Pcb(path)
    out = {}
    for name, n1, d1, n2, d2, ref in loop.PAIRS:
        a = loop.polyline(p, n1, d1, loop.connector_pad(p, ref, n1))
        b = loop.polyline(p, n2, d2, loop.connector_pad(p, ref, n2))
        ring = a + b[::-1] + [a[0]]
        xs, ys = [q[0] for q in ring], [q[1] for q in ring]
        X, Y = np.meshgrid(np.arange(min(xs), max(xs), h) + h / 2,
                           np.arange(min(ys), max(ys), h) + h / 2)
        w = np.zeros(X.shape, int)
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            cross = (x2 - x1) * (Y - y1) - (X - x1) * (y2 - y1)
            w += (((y1 <= Y) & (y2 > Y) & (cross > 0)).astype(int)
                  - ((y1 > Y) & (y2 <= Y) & (cross < 0)).astype(int))
        pos, neg = (w > 0).sum() * h * h, (w < 0).sum() * h * h
        out[name] = {'lobes': sorted([round(pos, 1), round(neg, 1)], reverse=True),
                     'enclosed': round(np.abs(w).sum() * h * h, 1)}
    return out


def zone_box(t, name):
    for z in children(t, 'zone'):
        nm = child(z, 'name')
        if nm and val(nm[1]) == name:
            pts = [(float(q[1]), float(q[2])) for pg in children(z, 'polygon')
                   for q in children(child(pg, 'pts'), 'xy')]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            return min(xs), min(ys), max(xs), max(ys)
    return None


def measure(path, pro):
    t = parse(open(path).read())
    fps = {f['ref']: f for f in (fp_info(x) for x in children(t, 'footprint'))}
    out = {'footprints': len(fps)}
    out['vias'], out['track_mm'] = totals(t)
    res = clearmin.measure_all(path, pro)
    out['clearance_mm'] = {k: (round(res[k][0], 4) if res.get(k) else '> 20') for k in PAIRS}
    out['loop_mm2'] = {k: round(v, 1) for k, v in loop.report(path).items()}
    out['loop_lobes_mm2'] = lobes(path)
    out['placement'] = {r: board_coords(fps[r]['x'], fps[r]['y']) + (fps[r]['rot'],)
                        for r in REFS if r in fps}
    imu = zone_box(t, 'IMU module and bracket reservation')
    if imu:
        c = ((imu[0] + imu[2]) / 2, (imu[1] + imu[3]) / 2)
        out['imu_reservation'] = [*board_coords(imu[0], imu[1]), *board_coords(imu[2], imu[3])]
        out['imu_offset_from_rotation_centre_mm'] = [round(c[0] - ROT_CENTRE[0], 2),
                                                     round(c[1] - ROT_CENTRE[1], 2),
                                                     round(math.dist(c, ROT_CENTRE), 2)]
    u1 = fps.get('U1')
    if u1 and 'DevKitC' in u1['lib']:
        p1 = next(q for q in u1['pads'] if q['num'] == '1')
        # the pad's outer corner against the rear-right R3 corner arc, centre (163, 157)
        cx = p1['x'] + p1['w'] / 2 if abs(math.cos(math.radians(p1['rot']))) > 0.5 else p1['x'] + p1['h'] / 2
        cy = p1['y'] + p1['h'] / 2 if abs(math.cos(math.radians(p1['rot']))) > 0.5 else p1['y'] + p1['w'] / 2
        out['devkit_pad1_to_corner_mm'] = round(3.0 - math.dist((cx, cy), (163.0, 157.0)), 3)
    return out


def main():
    argv = sys.argv[1:]
    out_json = None
    if '--json' in argv:
        k = argv.index('--json')
        out_json = argv[k + 1]
        argv = argv[:k] + argv[k + 2:]
    args = argv
    pro = os.path.join(ROOT, 'Pixy-M2.kicad_pro')
    res = {os.path.basename(os.path.dirname(os.path.abspath(a))) + '/' + os.path.basename(a):
           measure(a, pro) for a in args}
    print(json.dumps(res, indent=1))
    if out_json:
        json.dump(res, open(out_json, 'w'), indent=1)


if __name__ == '__main__':
    main()
