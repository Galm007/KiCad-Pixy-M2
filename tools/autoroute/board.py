import sys, math, re
import numpy as np
from scipy import ndimage
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, children, child, val
from load import fp_info

H = 0.05
X0, Y0 = 99.0, 59.0
NX, NY = 1361, 2041
CU = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']
ROUTE = ['F.Cu', 'B.Cu']

def gx(x): return (x - X0) / H
def gy(y): return (y - Y0) / H
def wx(ix): return X0 + ix * H
def wy(iy): return Y0 + iy * H

# ---------- rasterisation ----------
def _box(cx, cy, rx, ry):
    ix0 = max(0, int(math.floor(gx(cx - rx)))); ix1 = min(NX - 1, int(math.ceil(gx(cx + rx))))
    iy0 = max(0, int(math.floor(gy(cy - ry)))); iy1 = min(NY - 1, int(math.ceil(gy(cy + ry))))
    return ix0, ix1, iy0, iy1

def rect_mask(cx, cy, w, h, rot, margin=0.0):
    """rotated rect inflated by margin -> (iy0,iy1,ix0,ix1,mask)"""
    a = math.radians(rot)
    hw, hh = w / 2 + margin, h / 2 + margin
    rx = abs(hw * math.cos(a)) + abs(hh * math.sin(a))
    ry = abs(hw * math.sin(a)) + abs(hh * math.cos(a))
    ix0, ix1, iy0, iy1 = _box(cx, cy, rx, ry)
    if ix1 < ix0 or iy1 < iy0: return None
    X = wx(np.arange(ix0, ix1 + 1))[None, :] - cx
    Y = wy(np.arange(iy0, iy1 + 1))[:, None] - cy
    # rotate into pad frame (KiCad y down, rot CCW)
    u = X * math.cos(a) - Y * math.sin(a)
    v = X * math.sin(a) + Y * math.cos(a)
    m = (np.abs(u) <= hw) & (np.abs(v) <= hh)
    return iy0, iy1, ix0, ix1, m

def disc_mask(cx, cy, r):
    ix0, ix1, iy0, iy1 = _box(cx, cy, r, r)
    if ix1 < ix0 or iy1 < iy0: return None
    X = wx(np.arange(ix0, ix1 + 1))[None, :] - cx
    Y = wy(np.arange(iy0, iy1 + 1))[:, None] - cy
    return iy0, iy1, ix0, ix1, (X * X + Y * Y <= r * r)

def stamp(arr, sel, value, only_free=False, free_val=-1):
    if sel is None: return
    iy0, iy1, ix0, ix1, m = sel
    sub = arr[iy0:iy1 + 1, ix0:ix1 + 1]
    if only_free:
        m = m & (sub == free_val)
    sub[m] = value

def seg_disc_stamp(arr, x1, y1, x2, y2, r, value):
    n = max(1, int(math.hypot(x2 - x1, y2 - y1) / (H * 0.7)))
    for i in range(n + 1):
        t = i / n
        stamp(arr, disc_mask(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r), value)

# ---------- board outline ----------
def arc_pts(p1, pm, p2, n=24):
    (x1, y1), (xm, ym), (x2, y2) = p1, pm, p2
    d = 2 * (x1 * (ym - y2) + xm * (y2 - y1) + x2 * (y1 - ym))
    if abs(d) < 1e-9: return [p1, p2]
    ux = ((x1**2 + y1**2) * (ym - y2) + (xm**2 + ym**2) * (y2 - y1) + (x2**2 + y2**2) * (y1 - ym)) / d
    uy = ((x1**2 + y1**2) * (x2 - xm) + (xm**2 + ym**2) * (x1 - x2) + (x2**2 + y2**2) * (xm - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    a1 = math.atan2(y1 - uy, x1 - ux); am = math.atan2(ym - uy, xm - ux); a2 = math.atan2(y2 - uy, x2 - ux)
    def norm(a): return (a + 2 * math.pi) % (2 * math.pi)
    # choose sweep direction containing am
    for sweep in (1, -1):
        span = norm(sweep * (a2 - a1))
        mid = norm(sweep * (am - a1))
        if mid <= span + 1e-9:
            return [(ux + r * math.cos(a1 + sweep * span * i / n), uy + r * math.sin(a1 + sweep * span * i / n)) for i in range(n + 1)]
    return [p1, p2]

def edge_segments(pcb):
    segs = []
    def add(shape, tf=lambda p: p):
        lay = child(shape, 'layer')
        if not lay or val(lay[1]) != 'Edge.Cuts': return
        s = child(shape, 'start'); e = child(shape, 'end'); m = child(shape, 'mid')
        if s is None or e is None: return
        p1 = tf((float(s[1]), float(s[2]))); p2 = tf((float(e[1]), float(e[2])))
        if m is not None:
            pm = tf((float(m[1]), float(m[2])))
            segs.append(arc_pts(p1, pm, p2))
        else:
            segs.append([p1, p2])
    for t in ('gr_line', 'gr_arc'):
        for s in children(pcb, t): add(s)
    for f in children(pcb, 'footprint'):
        at = child(f, 'at'); fx, fy = float(at[1]), float(at[2])
        rot = math.radians(float(at[3]) if len(at) > 3 else 0.0)
        def tf(p, fx=fx, fy=fy, rot=rot):
            return (fx + p[0] * math.cos(rot) + p[1] * math.sin(rot), fy - p[0] * math.sin(rot) + p[1] * math.cos(rot))
        for t in ('fp_line', 'fp_arc'):
            for s in children(f, t): add(s, tf)
    return segs

def board_polygon(segs):
    used = [False] * len(segs)
    def key(p): return (round(p[0], 3), round(p[1], 3))
    loops = []
    for i in range(len(segs)):
        if used[i]: continue
        used[i] = True
        loop = list(segs[i])
        grew = True
        while grew:
            grew = False
            for j in range(len(segs)):
                if used[j]: continue
                a, b = segs[j][0], segs[j][-1]
                if key(a) == key(loop[-1]): loop += segs[j][1:]; used[j] = True; grew = True
                elif key(b) == key(loop[-1]): loop += segs[j][::-1][1:]; used[j] = True; grew = True
                elif key(b) == key(loop[0]): loop = segs[j][:-1] + loop; used[j] = True; grew = True
                elif key(a) == key(loop[0]): loop = segs[j][::-1][:-1] + loop; used[j] = True; grew = True
        loops.append(loop)
    loops.sort(key=len, reverse=True)
    return loops

def fill_polygon(loops):
    """even-odd fill of all loops -> bool grid"""
    inside = np.zeros((NY, NX), bool)
    edges = []
    for loop in loops:
        pts = loop if key_eq(loop[0], loop[-1]) else loop + [loop[0]]
        for i in range(len(pts) - 1):
            edges.append((pts[i], pts[i + 1]))
    for iy in range(NY):
        y = wy(iy); xs = []
        for (x1, y1), (x2, y2) in edges:
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for a, b in zip(xs[0::2], xs[1::2]):
            ia = max(0, int(math.ceil(gx(a)))); ib = min(NX - 1, int(math.floor(gx(b))))
            if ib >= ia: inside[iy, ia:ib + 1] = True
    return inside

def key_eq(a, b): return abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3
