"""Enclosed loop area of a motor output pair: OUT1 track + connector + OUT2 track.

The H-bridge drives current out one output and back through the other, so the
area between the two tracks is the radiating loop.  Reported in mm^2, projected
to 2D — the 1.6 mm layer offset is negligible next to the in-plane geometry.

Track endpoints are chained into an ordered path by breadth-first search over a
node graph, with endpoints merged when their copper overlaps.  Do not chain by
"nearest unused endpoint": a routed net branches at vias and a greedy walk takes
a shortcut, which silently reports the straight-line quadrilateral between the
four pads no matter how the board is routed.
"""
import sys, math, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcbedit import Pcb

TOL = 0.5          # endpoint merge distance, mm


def polyline(p, net, start, end):
    """ordered start -> end point list along the net's tracks"""
    pts, edges = [], []
    for b in p.blocks:
        if Pcb.net(b) != net or Pcb.kind(b) != 'segment': continue
        x1, y1, x2, y2, w, l = Pcb.geom(b)
        if math.dist((x1, y1), (x2, y2)) < 1e-9: continue
        i = len(pts); pts += [(x1, y1), (x2, y2)]
        edges.append((i, i + 1))
    pts += [start, end]
    si, ei = len(pts) - 2, len(pts) - 1

    adj = collections.defaultdict(set)
    for a, b in edges:
        adj[a].add(b); adj[b].add(a)
    for i in range(len(pts)):                       # merge coincident endpoints
        for j in range(i + 1, len(pts)):
            if math.dist(pts[i], pts[j]) <= TOL:
                adj[i].add(j); adj[j].add(i)
    for k in (si, ei):                             # pad centres: nearest endpoint
        if not adj[k] and len(pts) > 2:
            n = min(range(len(pts) - 2), key=lambda i: math.dist(pts[i], pts[k]))
            adj[k].add(n); adj[n].add(k)

    prev = {si: None}
    q = collections.deque([si])
    while q:
        n = q.popleft()
        if n == ei: break
        for m in adj[n]:
            if m not in prev:
                prev[m] = n; q.append(m)
    if ei not in prev:
        raise SystemExit(f'{net}: no path from {start} to {end}')
    out, n = [], ei
    while n is not None:
        out.append(pts[n]); n = prev[n]
    out.reverse()
    return [q for i, q in enumerate(out) if i == 0 or math.dist(q, out[i - 1]) > 1e-9]


def area(poly):
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def length(poly):
    return sum(math.dist(poly[i], poly[i + 1]) for i in range(len(poly) - 1))


PAIRS = [('motor A', '/MOT_A_1', (109.95, 114.25), (115.0, 128.0),
          '/MOT_A_2', (109.95, 113.25), (105.0, 128.0)),
         ('motor B', '/MOT_B_1', (117.95, 114.25), (158.0, 107.0),
          '/MOT_B_2', (117.95, 113.25), (158.0, 97.0))]


def report(path, verbose=False):
    p = Pcb(path)
    out = {}
    for name, n1, d1, c1, n2, d2, c2 in PAIRS:
        a = polyline(p, n1, d1, c1)
        b = polyline(p, n2, d2, c2)
        out[name] = area(a + b[::-1])
        if verbose:
            print(f'  {name}: {n1} path {length(a):5.1f} mm ({len(a)} pts), '
                  f'{n2} path {length(b):5.1f} mm ({len(b)} pts)')
    return out


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    v = '-v' in sys.argv
    for path in args or ['/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/Pixy-M2.kicad_pcb']:
        print(os.path.basename(path))
        r = report(path, v)
        for k, val in r.items():
            print(f'  {k}: {val:7.1f} mm^2')
