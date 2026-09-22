#!/usr/bin/env python3
"""Autorouter for Pixy-M2.kicad_pcb (4 layer: F.Cu / In1.Cu GND / In2.Cu power / B.Cu)."""
import sys, math, re, heapq, json, uuid, time
import numpy as np
from scipy import ndimage
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board import *
from sexp import parse, children, child, val
from load import fp_info

CL = 0.26          # clearance target (rule is 0.20)
VIA_D, VIA_DRILL = 0.6, 0.3
H2H = 0.45         # hole to hole
BASE = 'base.kicad_pcb'
OUT = '/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/Pixy-M2.kicad_pcb'

WIDTH = {'GND': 0.4, '/ESP_3V3': 0.4, '/VBAT': 1.0, '/VBAT_FUSED': 1.0, '/VBAT_RAW': 1.0,
         '/VSYS': 0.6, '/VBUS': 0.6, 'Net-(F2-Pad1)': 0.6, 'Net-(U3-SW)': 0.5, 'Net-(U3-BST)': 0.3,
         '/MOT_A_1': 0.8, '/MOT_A_2': 0.8, '/MOT_B_1': 0.8, '/MOT_B_2': 0.8,
         'Net-(J1-SHIELD)': 0.4, 'Net-(Q1-G)': 0.3}
DEF_W = 0.2

PLANE = {'GND': ('In1.Cu', None), '/ESP_3V3': ('In2.Cu', 'p3v3'), '/VBAT': ('In2.Cu', 'pvbat')}
NONET = 30000
VBAT_REGION = (100.5, 88.0, 127.0, 122.0)   # In2.Cu VBAT island

# ---------------------------------------------------------------- board data
class Board:
    def __init__(self):
        self.pcb = parse(open(BASE).read())
        self.fps = [fp_info(f) for f in children(self.pcb, 'footprint')]
        loops = board_polygon(edge_segments(self.pcb))
        self.inside = fill_polygon(loops)
        self.dist_edge = ndimage.distance_transform_edt(self.inside) * H
        # antenna / all-layer keepout zones
        self.keepout = np.zeros((NY, NX), bool)
        for z in children(self.pcb, 'zone'):
            ko = child(z, 'keepout')
            if not ko: continue
            rules = {c[0]: c[1] for c in ko[1:]}
            if rules.get('tracks') != 'not_allowed': continue
            for pg in children(z, 'polygon'):
                pts = [(float(p[1]), float(p[2])) for p in children(child(pg, 'pts'), 'xy')]
                sel = fill_polygon([pts])
                self.keepout |= sel
        # nets
        self.nets = {}
        for f in self.fps:
            for p in f['pads']:
                if p['net']: self.nets.setdefault(p['net'], []).append((f['ref'], p))
        self.netid = {n: i for i, n in enumerate(sorted(self.nets))}
        # copper grids (exact) + holes
        self.cu = {l: np.full((NY, NX), -1, np.int16) for l in ROUTE}
        self.holes = []
        for f in self.fps:
            for p in f['pads']:
                nid = self.netid.get(p['net'], NONET)
                lay = p['layers']
                on = [l for l in ROUTE if l in lay or '*.Cu' in lay]
                sel = self.pad_sel(p, 0.0)
                for l in on:
                    stamp(self.cu[l], sel, nid)
                if p['drill']:
                    self.holes.append((p['x'], p['y'], p['drill'] / 2, nid if p['net'] else NONET))
        self.hole_block = np.zeros((NY, NX), bool)
        for (hx, hy, hr, hn) in self.holes:
            self._hole_stamp(hx, hy, hr)
        self.tracks = []   # (net, layer, x1,y1,x2,y2, width)
        self.vias = []     # (net, x, y)

    def _hole_stamp(self, hx, hy, hr):
        r = VIA_DRILL / 2 + H2H + hr
        sel = disc_mask(hx, hy, r)
        if sel:
            iy0, iy1, ix0, ix1, m = sel
            self.hole_block[iy0:iy1 + 1, ix0:ix1 + 1] |= m

    def pad_sel(self, p, margin):
        if p['shape'] == 'circle':
            return disc_mask(p['x'], p['y'], p['w'] / 2 + margin)
        return rect_mask(p['x'], p['y'], p['w'], p['h'], p['rot'], margin)

    # ------- per-net fields
    def dist(self, net):
        nid = self.netid[net]
        out = {}
        hmask = np.zeros((NY, NX), bool)
        for (hx, hy, hr, hn) in self.holes:
            if hn == nid: continue
            sel = disc_mask(hx, hy, hr + 0.06)
            if sel:
                iy0, iy1, ix0, ix1, mm = sel
                hmask[iy0:iy1 + 1, ix0:ix1 + 1] |= mm
        for l in ROUTE:
            other = ((self.cu[l] >= 0) & (self.cu[l] != nid)) | hmask
            own = (self.cu[l] == nid) & (~hmask)
            out[l] = (ndimage.distance_transform_edt(~other) * H,
                      ndimage.distance_transform_edt(own) * H)
        return out

    def ok_masks(self, d, w):
        req = CL + w / 2
        out = {}
        for l in ROUTE:
            dd, downn = d[l]
            out[l] = (((dd >= req) | (downn >= w / 2 + H)) & (self.dist_edge >= req)) & self.inside & (~self.keepout)
        return out

    def via_mask(self, d):
        r = CL + VIA_D / 2
        m = (self.dist_edge >= r) & (~self.hole_block) & (~self.keepout) & self.inside
        for l in ROUTE:
            m &= (d[l][0] >= r) | (d[l][1] >= VIA_D / 2 + H / 2)
        return m

    # ------- adding copper
    def add_track(self, net, layer, x1, y1, x2, y2, w):
        nid = self.netid[net]
        seg_disc_stamp(self.cu[layer], x1, y1, x2, y2, w / 2, nid)
        self.tracks.append((net, layer, x1, y1, x2, y2, w))

    def add_via(self, net, x, y):
        nid = self.netid[net]
        for l in ROUTE:
            stamp(self.cu[l], disc_mask(x, y, VIA_D / 2), nid)
        self._hole_stamp(x, y, VIA_DRILL / 2)
        self.vias.append((net, x, y))

# ---------------------------------------------------------------- A*
DIRS = [(1,0,10),(-1,0,10),(0,1,10),(0,-1,10),(1,1,14),(1,-1,14),(-1,1,14),(-1,-1,14)]
VIA_COST = 400

def astar(ok, via_ok, src, goal, goal_pts, limit=4_000_000):
    """ok/src/goal: dict layer->bool array. goal_pts: list (x,y,radius_mm)."""
    L = ROUTE
    okf = [ok[l].ravel() for l in L]
    goalf = [goal[l].ravel() for l in L]
    vf = via_ok.ravel()
    N = NX * NY
    INF = np.float32(np.inf)
    g = np.full(2 * N, INF, np.float32)
    prev = np.full(2 * N, -1, np.int32)
    gpts = goal_pts
    if len(gpts) > 10:
        step = len(gpts) / 10.0
        gpts = [gpts[int(i * step)] for i in range(10)]
    gp = [(gx(x), gy(y), r / H) for x, y, r in gpts]
    hcache = {}
    def hh(idx):
        v = hcache.get(idx)
        if v is not None: return v
        iy, ix = divmod(idx % N, NX)
        best = 1e18
        for (px, py, pr) in gp:
            dx = abs(ix - px); dy = abs(iy - py)
            v = 10 * (14 * min(dx, dy) / 10 + 10 * (max(dx, dy) - min(dx, dy)) / 10) - 10 * pr
            best = min(best, max(0.0, v))
        hcache[idx] = best
        return best
    heap = []
    for li, l in enumerate(L):
        idxs = np.flatnonzero(src[l].ravel() & ok[l].ravel())
        for i in idxs:
            j = li * N + int(i)
            g[j] = 0
            heapq.heappush(heap, (hh(j), j))
    pops = 0
    while heap:
        f, j = heapq.heappop(heap)
        gj = g[j]
        if f > gj + hh(j) + 1e-3: continue
        pops += 1
        if pops > limit: return None
        li, rest = divmod(j, N)
        if goalf[li][rest]:
            # walk back
            path = []
            k = j
            while k >= 0:
                l2, r2 = divmod(k, N)
                iy, ix = divmod(r2, NX)
                path.append((l2, ix, iy))
                k = prev[k]
            return path[::-1]
        iy, ix = divmod(rest, NX)
        for dx, dy, c in DIRS:
            nx_, ny_ = ix + dx, iy + dy
            if not (0 <= nx_ < NX and 0 <= ny_ < NY): continue
            nr = ny_ * NX + nx_
            if not okf[li][nr]: continue
            if dx and dy:
                if not (okf[li][iy * NX + nx_] and okf[li][ny_ * NX + ix]): continue
            nj = li * N + nr
            ng = gj + c
            if ng < g[nj]:
                g[nj] = ng; prev[nj] = j
                heapq.heappush(heap, (ng + hh(nj), nj))
        # via
        if vf[rest]:
            for li2 in range(len(L)):
                if li2 == li: continue
                if not okf[li2][rest]: continue
                nj = li2 * N + rest
                ng = gj + VIA_COST
                if ng < g[nj]:
                    g[nj] = ng; prev[nj] = j
                    heapq.heappush(heap, (ng + hh(nj), nj))
    return None

def simplify(path):
    """path: list of (layer_idx, ix, iy) -> list of runs [(layer_idx,[(ix,iy),...])]"""
    runs = []
    cur = [path[0]]
    for p in path[1:]:
        if p[0] != cur[-1][0]:
            runs.append(cur); cur = [p]
        else:
            cur.append(p)
    runs.append(cur)
    out = []
    for run in runs:
        li = run[0][0]
        pts = [(run[0][1], run[0][2])]
        for k in range(1, len(run)):
            if k == len(run) - 1:
                pts.append((run[k][1], run[k][2])); break
            a = run[k - 1]; b = run[k]; c = run[k + 1]
            if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]):
                pts.append((b[1], b[2]))
        out.append((li, pts))
    return out

# ---------------------------------------------------------------- groups
def pad_mask(bd, p, w=0.2):
    lay = p['layers']
    on = [l for l in ROUTE if l in lay or '*.Cu' in lay]
    m = {l: np.zeros((NY, NX), bool) for l in ROUTE}
    sel = bd.pad_sel(p, -(w / 2 + H / 2))
    if sel is None or not sel[4].any():
        sel = disc_mask(p['x'], p['y'], H)
    for l in on:
        if sel:
            iy0, iy1, ix0, ix1, mm = sel
            m[l][iy0:iy1 + 1, ix0:ix1 + 1] |= mm
    r = min(p['w'], p['h']) / 2
    return {'m': m, 'pts': [(p['x'], p['y'], r)], 'cx': p['x'], 'cy': p['y'], 'th': '*.Cu' in lay}

def merge(a, b):
    for l in ROUTE:
        a['m'][l] |= b['m'][l]
    a['pts'] += b['pts']
    return a

def stamp_path(bd, net, path, w):
    """path list of (li,ix,iy) -> tracks+vias; returns cells mask dict"""
    runs = simplify(path)
    m = {l: np.zeros((NY, NX), bool) for l in ROUTE}
    prev_end = None
    for li, pts in runs:
        layer = ROUTE[li]
        if prev_end is not None:
            bd.add_via(net, wx(prev_end[0]), wy(prev_end[1]))
        for a, b in zip(pts, pts[1:]):
            x1, y1, x2, y2 = wx(a[0]), wy(a[1]), wx(b[0]), wy(b[1])
            bd.add_track(net, layer, x1, y1, x2, y2, w)
            seg_disc_stamp(m[layer].view(np.int8), x1, y1, x2, y2, w / 2, 1)
        prev_end = pts[-1]
    return m

def route_net(bd, net, groups, w, log):
    fails = 0
    while len(groups) > 1:
        d = bd.dist(net)
        ok = bd.ok_masks(d, w)
        vm = bd.via_mask(d)
        groups.sort(key=lambda g: -sum(g['m'][l].sum() for l in ROUTE))
        src = groups[0]
        order = sorted(range(1, len(groups)),
                       key=lambda i: min(math.hypot(px - qx, py - qy)
                                         for px, py, _ in src['pts'] for qx, qy, _ in groups[i]['pts']))
        done = False
        for gi in order:
            tgt = groups[gi]
            path = astar(ok, vm, {l: src['m'][l] for l in ROUTE}, {l: tgt['m'][l] for l in ROUTE}, tgt['pts'])
            if path:
                pm = stamp_path(bd, net, path, w)
                for l in ROUTE:
                    src['m'][l] |= pm[l]
                merge(src, tgt)
                groups.pop(gi)
                done = True
                break
        if not done:
            log.append(f"FAIL {net}: {len(groups)} groups unrouted")
            return False
    return True

# ---------------------------------------------------------------- stitching
def in_region(x, y, reg, inside=True, pad=0.4):
    x0, y0, x1, y1 = reg
    if inside:
        return x0 + pad <= x <= x1 - pad and y0 + pad <= y <= y1 - pad
    return not (x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad)

def net_width(bd, net, base=None):
    lim = min(min(p['w'], p['h']) for _, p in bd.nets[net])
    return max(0.15, min(base if base else WIDTH.get(net, DEF_W), round(lim - 0.1, 2)))

def stitch_pads(bd, net, w, log, nvia=1, pads=None, defer_fine=True):
    """place stitching vias from every SMD pad of a plane net -> (plane group, orphan groups)"""
    d = bd.dist(net)
    okc = {}
    def okm(ww):
        if ww not in okc: okc[ww] = bd.ok_masks(d, ww)
        return okc[ww]
    vm = bd.via_mask(d)
    plane_group = None
    orphans = []
    deferred = []
    region_test = None
    if net == '/VBAT': region_test = lambda x, y: in_region(x, y, VBAT_REGION, True)
    if net == '/ESP_3V3': region_test = lambda x, y: in_region(x, y, VBAT_REGION, False)
    for ref, p in sorted(pads if pads is not None else bd.nets[net], key=lambda rp: (rp[0], rp[1]['num'])):
        if defer_fine and min(p['w'], p['h']) < 0.4 and not p['drill']:
            deferred.append((ref, p))
            continue
        wp = max(0.15, min(w, round(min(p['w'], p['h']) - 0.1, 2)))
        ok = okm(wp)
        g = pad_mask(bd, p, wp)
        if p['drill'] and (region_test is None or region_test(p['x'], p['y'])):
            plane_group = g if plane_group is None else merge(plane_group, g)
            continue
        placed = 0
        cands = []
        if min(p['w'], p['h']) >= 1.2:            # via(s) inside the pad
            a = math.radians(p['rot'])
            long_x = p['w'] >= p['h']
            L = max(p['w'], p['h']) - 0.7
            k = max(1, int(L // 0.8) + 1)
            for i2 in range(k):
                t = (i2 / (k - 1) - 0.5) * L if k > 1 else 0.0
                u, v = (t, 0.0) if long_x else (0.0, t)
                cands.append((p['x'] + u * math.cos(a) + v * math.sin(a),
                              p['y'] - u * math.sin(a) + v * math.cos(a)))
        base = max(p['w'], p['h']) / 2
        for rad in (base + 0.45, base + 0.7, base + 1.0, base + 1.5, base + 2.1):
            for k in range(16):
                ang = math.radians(p['rot'] + k * 22.5)
                cands.append((p['x'] + rad * math.cos(ang), p['y'] - rad * math.sin(ang)))
        for (vx, vy) in cands:
            if placed >= nvia: break
            ix, iy = int(round(gx(vx))), int(round(gy(vy)))
            if not (0 <= ix < NX and 0 <= iy < NY): continue
            if not vm[iy, ix] or bd.hole_block[iy, ix]: continue
            if region_test and not region_test(wx(ix), wy(iy)): continue
            vx, vy = wx(ix), wy(iy)
            steps = max(1, int(math.hypot(vx - p['x'], vy - p['y']) / H))
            good = True
            for i2 in range(steps + 1):
                t = i2 / steps
                jx = int(round(gx(p['x'] + (vx - p['x']) * t))); jy = int(round(gy(p['y'] + (vy - p['y']) * t)))
                if not ok['F.Cu'][jy, jx]: good = False; break
            if not good: continue
            bd.add_via(net, vx, vy)
            if math.hypot(vx - p['x'], vy - p['y']) > 1e-9:
                bd.add_track(net, 'F.Cu', p['x'], p['y'], vx, vy, wp)
                seg_disc_stamp(g['m']['F.Cu'].view(np.int8), p['x'], p['y'], vx, vy, wp / 2, 1)
            for l in ROUTE:
                stamp(g['m'][l].view(np.int8), disc_mask(vx, vy, VIA_D / 2 - H), 1)
            placed += 1
        if placed:
            plane_group = g if plane_group is None else merge(plane_group, g)
        else:
            orphans.append(g)
            log.append(f"  no stitch via for {net} {ref}.{p['num']}")
    return plane_group, orphans, deferred

# ---------------------------------------------------------------- widening
def widen(bd, order):
    for net in order:
        if net not in bd.netid: continue
        target = WIDTH.get(net, DEF_W)
        d = bd.dist(net)
        for i, (n, l, x1, y1, x2, y2, w) in enumerate(bd.tracks):
            if n != net or w >= target: continue
            best = w
            for cand in [target, target * 0.8, target * 0.6, max(w, target * 0.4)]:
                cand = round(cand, 2)
                if cand <= best: continue
                req = CL + cand / 2
                steps = max(1, int(math.hypot(x2 - x1, y2 - y1) / H))
                good = True
                dd, downn = d[l]
                for k in range(steps + 1):
                    t = k / steps
                    jx = int(round(gx(x1 + (x2 - x1) * t))); jy = int(round(gy(y1 + (y2 - y1) * t)))
                    if not ((dd[jy, jx] >= req or downn[jy, jx] >= cand / 2 + H) and bd.dist_edge[jy, jx] >= req):
                        good = False; break
                if good: best = cand; break
            if best > w:
                bd.tracks[i] = (n, l, x1, y1, x2, y2, best)
                seg_disc_stamp(bd.cu[l], x1, y1, x2, y2, best / 2, bd.netid[net])

# ---------------------------------------------------------------- emit
def uid(): return str(uuid.uuid4())

def fx(v):
    return f'{round(v, 4):.4f}'.rstrip('0').rstrip('.')

ZONE_TMPL = '''	(zone
		(net "{net}")
		(layer "{layer}")
		(uuid "{uuid}")
		(name "{name}")
		(hatch edge 0.5)
		(priority {prio})
		(connect_pads yes
			(clearance 0.25)
		)
		(min_thickness 0.25)
		(filled_areas_thickness no)
		(fill yes
			(thermal_gap 0.4)
			(thermal_bridge_width 0.4)
			(island_removal_mode 0)
		)
		(polygon
			(pts
				{pts}
			)
		)
	)
'''

def emit(bd, extra_zones):
    txt = open(BASE).read().rstrip()
    assert txt.endswith(')')
    body = txt[:-1].rstrip('\n') + '\n'
    out = []
    for z in extra_zones:
        out.append(ZONE_TMPL.format(uuid=uid(), **z))
    for (net, l, x1, y1, x2, y2, w) in bd.tracks:
        if abs(x1 - x2) < 1e-9 and abs(y1 - y2) < 1e-9: continue
        out.append('\t(segment\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(width %s)\n'
                   '\t\t(layer "%s")\n\t\t(net "%s")\n\t\t(uuid "%s")\n\t)\n'
                   % (fx(x1), fx(y1), fx(x2), fx(y2), fx(w), l, net, uid()))
    for (net, x, y) in bd.vias:
        out.append('\t(via\n\t\t(at %s %s)\n\t\t(size %s)\n\t\t(drill %s)\n'
                   '\t\t(layers "F.Cu" "B.Cu")\n\t\t(net "%s")\n\t\t(uuid "%s")\n\t)\n'
                   % (fx(x), fx(y), fx(VIA_D), fx(VIA_DRILL), net, uid()))
    open(OUT, 'w').write(body + ''.join(out) + ')\n')

def zone_defs():
    full = '(xy 98 58) (xy 168 58) (xy 168 162) (xy 98 162)'
    x0, y0, x1, y1 = VBAT_REGION
    vb = f'(xy {x0} {y0}) (xy {x1} {y0}) (xy {x1} {y1}) (xy {x0} {y1})'
    return [
        dict(net='GND', layer='In1.Cu', name='GND plane', prio=0, pts=full),
        dict(net='GND', layer='B.Cu', name='GND pour bottom', prio=0, pts=full),
        dict(net='/ESP_3V3', layer='In2.Cu', name='3V3 pour', prio=0, pts=full),
        dict(net='/VBAT', layer='In2.Cu', name='VBAT motor rail island', prio=1, pts=vb),
    ]

# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    log = []
    bd = Board()
    print(f'nets={len(bd.nets)} pads={sum(len(v) for v in bd.nets.values())} setup={time.time()-t0:.1f}s')
    plane = {}
    for net in ('GND', '/ESP_3V3', '/VBAT'):
        w = 0.3 if net == '/VBAT' else min(WIDTH[net], 0.4)
        pg, orph, defr = stitch_pads(bd, net, w, log, nvia=(2 if net == '/VBAT' else 1))
        plane[net] = dict(g=pg, orph=orph, defer=defr, w=w)
        print(f'{net}: vias={len(bd.vias)} orphans={len(orph)} deferred={len(defr)} t={time.time()-t0:.0f}s')
    # signal nets, fine-pitch packages first, then shortest first
    sig = []
    for net, pads in bd.nets.items():
        if net in PLANE or net.startswith('unconnected-') or len(pads) < 2: continue
        xs = [p['x'] for _, p in pads]; ys = [p['y'] for _, p in pads]
        fine = 0 if any(min(p['w'], p['h']) < 0.4 for _, p in pads) else 1
        sig.append((fine, (max(xs) - min(xs)) + (max(ys) - min(ys)), net))
    sig.sort()
    ok_count = 0
    for fine, _, net in sig:
        wr = net_width(bd, net, min(WIDTH.get(net, DEF_W), 0.2))
        groups = [pad_mask(bd, p, wr) for _, p in bd.nets[net]]
        if route_net(bd, net, groups, wr, log): ok_count += 1
        print(f'  {net:22s} w={wr} tracks={len(bd.tracks)} vias={len(bd.vias)} t={time.time()-t0:.0f}s', flush=True)
    print('routed signal nets:', ok_count, 'of', len(sig))
    # second stitching pass for the fine-pitch pads that were deferred
    for net, info in plane.items():
        if info['defer']:
            pg, orph, _ = stitch_pads(bd, net, info['w'], log, nvia=1,
                                      pads=info['defer'], defer_fine=False)
            if pg: info['g'] = merge(info['g'], pg) if info['g'] else pg
            info['orph'] += orph
        print(f'{net}: stitch-2 vias={len(bd.vias)} orphans={len(info["orph"])} t={time.time()-t0:.0f}s')
    # connect whatever the planes could not stitch
    for net, info in plane.items():
        if not info['orph']: continue
        groups = ([info['g']] if info['g'] else []) + info['orph']
        route_net(bd, net, groups, 0.2, log)
        print(f'  {net} orphan routing done tracks={len(bd.tracks)} t={time.time()-t0:.0f}s', flush=True)
    widen(bd, ['/VBAT', '/VBAT_FUSED', '/VBAT_RAW', '/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2',
               '/VSYS', '/VBUS', 'Net-(F2-Pad1)', 'Net-(U3-SW)', 'GND', '/ESP_3V3'])
    emit(bd, zone_defs())
    print('\n'.join(log))
    print(f'tracks={len(bd.tracks)} vias={len(bd.vias)} total={time.time()-t0:.0f}s')

if __name__ == '__main__':
    main()
