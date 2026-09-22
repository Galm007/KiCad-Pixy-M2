#!/usr/bin/env python3
"""Motor-region rework of the routed board — REVIEW.md issues 1-3.

Reads `base-routed.kicad_pcb` (the 2026-09-21 autorouted board) and writes
`../../Pixy-M2.kicad_pcb`.  Re-runnable: it never edits the file it reads.

  1  MOT_A_*/MOT_B_* rerouted as 0.8 mm trunks; 0.2 mm only in the driver
     pin escapes.
  2  U4/U5 exposed pads get in-pad thermal vias, wide neck copper out of the
     pad, extra plane vias and an F.Cu GND pour over the whole motor region.
  3  C18/C20 moved hard against their driver's VM/GND pins so the bypass loop
     closes in local top copper; C21 shifted clear of the new escape corridor.
"""
import sys, math, heapq, os, uuid
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board import (H, NX, NY, ROUTE, gx, gy, wx, wy, disc_mask, stamp, seg_disc_stamp)
from pcbedit import Pcb, fx
from grid import G, CL, VIA_D, VIA_DRILL, H2H

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'base-routed.kicad_pcb')
OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'Pixy-M2.kicad_pcb'))

TRUNK = 0.8          # motor trunk width
NECK = 0.2           # width inside the driver pin field only
EP_VIA = (0.45, 0.25)   # thermal via in the WSON exposed pad

# driver origin, bypass cap, connector pads
DRIVERS = [
    dict(u='U4', ox=109.0, oy=114.0, cap='C18', cx=111.25,
         out1='/MOT_A_1', out2='/MOT_A_2', j1=('J8', '1'), j2=('J8', '6')),
    dict(u='U5', ox=117.0, oy=114.0, cap='C20', cx=119.25,
         out1='/MOT_B_1', out2='/MOT_B_2', j1=('J9', '1'), j2=('J9', '6')),
]
MOTOR_NETS = ['/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2']

# footprints that move (ref -> x, y, rot)
MOVES = {
    'C18': (111.25, 114.25, 90),    # across U4 VM(5)/GND(7)
    'C20': (119.25, 114.25, 90),    # across U5 VM(5)/GND(7)
    'C21': (119.30, 109.40, 90),    # out of the new U5 escape corridor
}

# nets ripped whole
RIP_NETS = ['/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2', '/GPIO6']
# (net, x0,y0,x1,y1) boxes ripped: old cap stubs and the old driver GND/VM stubs
RIP_BOXES = [
    ('/VBAT', 108.5, 112.0, 111.5, 116.0), ('GND', 108.5, 112.0, 111.5, 116.0),
    ('/VBAT', 116.5, 112.0, 119.5, 116.0), ('GND', 116.5, 112.0, 119.5, 116.0),
    ('/VBAT', 105.0, 109.0, 107.0, 112.9), ('GND', 105.0, 109.0, 107.0, 112.9),
    ('/VBAT', 119.0, 109.0, 121.0, 112.6), ('GND', 119.0, 109.0, 121.0, 112.6),
    ('/VBAT', 111.9, 110.9, 114.2, 116.2), ('GND', 111.9, 110.9, 114.2, 116.2),
    ('/ESP_3V3', 118.3, 115.4, 118.7, 115.8),   # via that C20 pad 1 would land on
]

# reference text moved out of the reworked area (local offsets, footprint frame)
REFS = {'C18': (-2.15, 0.0), 'C20': (-2.15, 0.0), 'C21': (-2.1, 2.7),
        'U5': (0.0, -2.2)}

# F.Cu ground pour over the motor region (issue 2 heat spreading, issue 3 return)
GND_POUR = (104.2, 104.6, 123.2, 120.2)

# rule areas: the only places a motor net may neck below the DRC minimum
ESCAPE_AREAS = [(107.0, 112.0, 112.9, 116.0), (115.0, 112.0, 120.9, 116.0)]

RULE_AREA = '''	(zone
		(layer "F.Cu")
		(uuid "{uuid}")
		(name "Motor pin escape")
		(hatch edge 0.5)
		(connect_pads
			(clearance 0)
		)
		(min_thickness 0.25)
		(keepout
			(tracks allowed)
			(vias allowed)
			(pads allowed)
			(copperpour allowed)
			(footprints allowed)
		)
		(placement
			(enabled no)
			(sheetname "")
		)
		(fill
			(thermal_gap 0.5)
			(thermal_bridge_width 0.5)
			(island_removal_mode 0)
		)
		(polygon
			(pts
				{pts}
			)
		)
	)
'''

ZONE = '''	(zone
		(net "GND")
		(layer "F.Cu")
		(uuid "{uuid}")
		(name "{name}")
		(hatch edge 0.5)
		(priority 0)
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


# ---------------------------------------------------------------- router
class Router:
    """A* over the *current* board copper, writing straight into the Pcb text."""

    def __init__(self, p, ignore=()):
        self.p = p
        self.g = G(p, ignore_nets=ignore)

    def track(self, net, layer, x1, y1, x2, y2, w):
        seg_disc_stamp(self.g.cu[layer], x1, y1, x2, y2, w / 2, self.g.netid[net])
        self.p.add_track(net, layer, x1, y1, x2, y2, w)

    def via(self, net, x, y, size=VIA_D, drill=VIA_DRILL):
        nid = self.g.netid[net]
        for l in ROUTE:
            stamp(self.g.cu[l], disc_mask(x, y, size / 2), nid)
        self.g.holes.append((x, y, drill / 2, nid))
        sel = disc_mask(x, y, VIA_DRILL / 2 + H2H + drill / 2)
        if sel:
            iy0, iy1, ix0, ix1, m = sel
            self.g.hole_block[iy0:iy1 + 1, ix0:ix1 + 1] |= m
        self.p.add_via(net, x, y, size, drill)

    # ---- masks
    def masks(self, net, w):
        d = self.g.dist(net)
        return d, self.g.ok_masks(d, w), self.g.via_mask(d)

    def _find_via(self, vm, ok, x, y, want, maxr=3.0):
        ux, uy = want
        n = math.hypot(ux, uy) or 1.0
        ux, uy = ux / n, uy / n
        cx, cy = int(round(gx(x))), int(round(gy(y)))
        rad = int(maxr / H)
        y0, y1 = max(0, cy - rad), min(NY, cy + rad + 1)
        x0, x1 = max(0, cx - rad), min(NX, cx + rad + 1)
        ys, xs = np.mgrid[y0:y1, x0:x1]
        dx = (xs - cx) * H; dy = (ys - cy) * H
        dist = np.hypot(dx, dy)
        cosang = (dx * ux + dy * uy) / np.maximum(dist, 1e-6)
        score = dist + 3.0 * (1 - cosang)          # prefer the requested side
        score[~vm[y0:y1, x0:x1]] = 1e9
        score[(dist < 0.45) | (dist > maxr)] = 1e9
        for idx in np.argsort(score, axis=None)[:600]:
            iy, ix = np.unravel_index(idx, score.shape)
            if score[iy, ix] >= 1e9: break
            vx, vy = wx(int(xs[iy, ix])), wy(int(ys[iy, ix]))
            if self._clear_line(ok, x, y, vx, vy):
                return vx, vy
        return None

    def stitch(self, net, x, y, want, w=0.4, maxr=3.0):
        """plane via near (x,y), preferring direction `want`, tracked back to it"""
        d = self.g.dist(net)
        ok = self.g.ok_masks(d, w)['F.Cu']
        spot = self._find_via(self.g.via_mask(d), ok, x, y, want, maxr)
        if spot is None:
            print(f'    ! no stitch via for {net} near ({x},{y})')
            return None
        self.track(net, 'F.Cu', x, y, *spot, w)
        self.via(net, *spot)
        return spot

    def neck_stitch(self, net, x0, y0, cands):
        """first candidate (ex,ey,width) whose neck AND plane via both fit"""
        d = self.g.dist(net)
        vm = self.g.via_mask(d)
        okc = {}
        for (ex, ey, w) in cands:
            ok = okc.setdefault(w, self.g.ok_masks(d, w)['F.Cu'])
            if not self._clear_line(ok, x0, y0, ex, ey): continue
            spot = self._find_via(vm, okc.setdefault(0.6, self.g.ok_masks(d, 0.6)['F.Cu']),
                                  ex, ey, (ex - x0, ey - y0))
            if spot is None: continue
            self.track(net, 'F.Cu', x0, y0, ex, ey, w)
            self.track(net, 'F.Cu', ex, ey, *spot, 0.6)
            self.via(net, *spot)
            return spot
        print(f'    ! no neck+via for {net} from ({x0},{y0})')
        return None

    @staticmethod
    def _clear_line(ok, x1, y1, x2, y2):
        steps = max(1, int(math.hypot(x2 - x1, y2 - y1) / H))
        for i in range(steps + 1):
            t = i / steps
            jx = int(round(gx(x1 + (x2 - x1) * t))); jy = int(round(gy(y1 + (y2 - y1) * t)))
            if not (0 <= jx < NX and 0 <= jy < NY) or not ok[jy, jx]:
                return False
        return True

    def spread_vias(self, net, cx, cy, r_in, r_out, n, sep=1.0, box=None, anchors=()):
        """extra plane vias in an annulus, connected by the surrounding pour"""
        out, anchors = [], [a for a in anchors if a]
        for _ in range(n):
            d = self.g.dist(net)
            vm = self.g.via_mask(d)
            ok = self.g.ok_masks(d, 0.4)['F.Cu']
            ix0, ix1 = int(gx(cx - r_out)), int(gx(cx + r_out)) + 1
            iy0, iy1 = int(gy(cy - r_out)), int(gy(cy + r_out)) + 1
            ys, xs = np.mgrid[iy0:iy1, ix0:ix1]
            dist = np.hypot((xs - gx(cx)) * H, (ys - gy(cy)) * H)
            good = vm[iy0:iy1, ix0:ix1] & (dist >= r_in) & (dist <= r_out)
            if box:
                good &= ((wx(xs) >= box[0] + 0.5) & (wx(xs) <= box[2] - 0.5) &
                         (wy(ys) >= box[1] + 0.5) & (wy(ys) <= box[3] - 0.5))
            score = np.where(good, dist, 1e9)
            for (px, py) in out:
                score[np.hypot((xs - gx(px)) * H, (ys - gy(py)) * H) < sep] = 1e9
            placed = False
            for idx in np.argsort(score, axis=None)[:300]:
                iy, ix = np.unravel_index(idx, score.shape)
                if score[iy, ix] >= 1e9: break
                vx, vy = wx(int(xs[iy, ix])), wy(int(ys[iy, ix]))
                anc = sorted(anchors + out, key=lambda a: math.hypot(a[0] - vx, a[1] - vy))
                for (ax, ay) in anc[:4]:
                    if not self._clear_line(ok, ax, ay, vx, vy): continue
                    self.track(net, 'F.Cu', ax, ay, vx, vy, 0.4)
                    self.via(net, vx, vy)
                    out.append((vx, vy))
                    placed = True
                    break
                if placed: break
            if not placed: break
        return out

    # ---- A*
    def route(self, net, w, groups):
        """groups: list of dicts {'m': {layer: mask}, 'pts': [(x,y,r)]}"""
        while len(groups) > 1:
            d, ok, vm = self.masks(net, w)
            groups.sort(key=lambda g: -sum(g['m'][l].sum() for l in ROUTE))
            src = groups[0]
            order = sorted(range(1, len(groups)),
                           key=lambda i: min(math.hypot(px - qx, py - qy)
                                             for px, py, _ in src['pts']
                                             for qx, qy, _ in groups[i]['pts']))
            done = False
            for gi in order:
                tgt = groups[gi]
                path = astar(ok, vm, src['m'], tgt['m'], tgt['pts'])
                if path:
                    pm = self._emit(net, path, w)
                    for l in ROUTE:
                        src['m'][l] |= pm[l]
                        src['m'][l] |= tgt['m'][l]
                    src['pts'] += tgt['pts']
                    groups.pop(gi)
                    done = True
                    break
            if not done:
                print(f'    FAIL {net}: {len(groups)} groups left')
                return False
        return True

    def _emit(self, net, path, w):
        m = {l: np.zeros((NY, NX), bool) for l in ROUTE}
        prev_end = None
        for li, pts in simplify(path):
            layer = ROUTE[li]
            if prev_end is not None:
                self.via(net, wx(prev_end[0]), wy(prev_end[1]))
            for a, b in zip(pts, pts[1:]):
                x1, y1, x2, y2 = wx(a[0]), wy(a[1]), wx(b[0]), wy(b[1])
                self.track(net, layer, x1, y1, x2, y2, w)
                seg_disc_stamp(m[layer].view(np.int8), x1, y1, x2, y2, w / 2, 1)
            prev_end = pts[-1]
        return m

    # ---- groups
    def pad_group(self, ref, num, w):
        pad = next(q for q in self.g.byref[ref]['pads'] if q['num'] == num)
        lay = pad['layers']
        m = {l: np.zeros((NY, NX), bool) for l in ROUTE}
        sel = self.g.pad_sel(pad, -(w / 2 + H / 2))
        if sel is None or not sel[4].any():
            sel = disc_mask(pad['x'], pad['y'], H)
        for l in ROUTE:
            if l in lay or '*.Cu' in lay:
                iy0, iy1, ix0, ix1, mm = sel
                m[l][iy0:iy1 + 1, ix0:ix1 + 1] |= mm
        return dict(m=m, pts=[(pad['x'], pad['y'], min(pad['w'], pad['h']) / 2)])

    def point_group(self, x, y, layers=ROUTE, r=0.1):
        m = {l: np.zeros((NY, NX), bool) for l in ROUTE}
        sel = disc_mask(x, y, r)
        for l in layers:
            iy0, iy1, ix0, ix1, mm = sel
            m[l][iy0:iy1 + 1, ix0:ix1 + 1] |= mm
        return dict(m=m, pts=[(x, y, r)])


# ---------------------------------------------------------------- A* core
DIRS = [(1, 0, 10), (-1, 0, 10), (0, 1, 10), (0, -1, 10),
        (1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14)]
VIA_COST = 400


def astar(ok, via_ok, src, goal, goal_pts, limit=6_000_000):
    L = ROUTE
    okf = [ok[l].ravel() for l in L]
    goalf = [goal[l].ravel() for l in L]
    vf = via_ok.ravel()
    N = NX * NY
    g = np.full(2 * N, np.float32(np.inf), np.float32)
    prev = np.full(2 * N, -1, np.int32)
    gp = [(gx(x), gy(y), r / H) for x, y, r in goal_pts[:10]]
    hcache = {}

    def hh(idx):
        v = hcache.get(idx)
        if v is not None: return v
        iy, ix = divmod(idx % N, NX)
        best = 1e18
        for (px, py, pr) in gp:
            dx = abs(ix - px); dy = abs(iy - py)
            v = 14 * min(dx, dy) + 10 * (max(dx, dy) - min(dx, dy)) - 10 * pr
            best = min(best, max(0.0, v))
        hcache[idx] = best
        return best

    heap = []
    for li, l in enumerate(L):
        for i in np.flatnonzero(src[l].ravel() & ok[l].ravel()):
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
            path, k = [], j
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
            if dx and dy and not (okf[li][iy * NX + nx_] and okf[li][ny_ * NX + ix]): continue
            nj = li * N + nr
            ng = gj + c
            if ng < g[nj]:
                g[nj] = ng; prev[nj] = j
                heapq.heappush(heap, (ng + hh(nj), nj))
        if vf[rest]:
            for li2 in range(len(L)):
                if li2 == li or not okf[li2][rest]: continue
                nj = li2 * N + rest
                ng = gj + VIA_COST
                if ng < g[nj]:
                    g[nj] = ng; prev[nj] = j
                    heapq.heappush(heap, (ng + hh(nj), nj))
    return None


def simplify(path):
    runs, cur = [], [path[0]]
    for q in path[1:]:
        if q[0] != cur[-1][0]:
            runs.append(cur); cur = [q]
        else:
            cur.append(q)
    runs.append(cur)
    out = []
    for run in runs:
        pts = [(run[0][1], run[0][2])]
        for k in range(1, len(run)):
            if k == len(run) - 1:
                pts.append((run[k][1], run[k][2])); break
            a, b, c = run[k - 1], run[k], run[k + 1]
            if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]):
                pts.append((b[1], b[2]))
        out.append((run[0][0], pts))
    return out


# ---------------------------------------------------------------- rework
def rip(p):
    n = 0
    n += p.drop(lambda b: Pcb.net(b) in RIP_NETS)
    for net, x0, y0, x1, y1 in RIP_BOXES:
        def hit(b, net=net, x0=x0, y0=y0, x1=x1, y1=y1):
            if Pcb.net(b) != net: return False
            if Pcb.kind(b) == 'segment':
                ax, ay, bx, by, w, l = Pcb.geom(b)
                return ((x0 <= ax <= x1 and y0 <= ay <= y1) or
                        (x0 <= bx <= x1 and y0 <= by <= y1))
            vx, vy, s, d = Pcb.geom(b)
            return x0 <= vx <= x1 and y0 <= vy <= y1
        n += p.drop(hit)
    return n


def driver_fixed(r, d):
    """issue 2 + 3, deterministic part: exposed-pad vias and the local VM loop.

    The 0.5 mm pin pitch puts OUT1 between VM (pin 5) and GND (pin 7), so the
    VM and GND runs out to the cap are 0.3 mm until they clear the pin field
    and 0.35 mm across to the pad — 1.3 mm of it, about 2 mOhm.
    """
    ox, oy, px, cx = d['ox'], d['oy'], d['ox'] + 0.95, d['cx']
    # exposed pad: two in-pad thermal vias.  0.45/0.25 is the board's minimum
    # via; the 0.8 mm pitch keeps hole-to-hole at 0.55 mm against a 0.45 rule.
    for k in (-0.4, 0.4):
        r.via('GND', ox, oy + k, EP_VIA[0], EP_VIA[1])
    # pin 7 (device ground) across to the cap's ground pad
    r.track('GND', 'F.Cu', px, oy - 0.25, px + 0.65, oy - 0.25, 0.3)
    r.track('GND', 'F.Cu', px + 0.65, oy - 0.25, cx, oy - 0.25, 0.35)
    # pin 5 (VM) across to the cap's VBAT pad
    r.track('/VBAT', 'F.Cu', px, oy + 0.75, px + 0.65, oy + 0.75, 0.3)
    r.track('/VBAT', 'F.Cu', px + 0.65, oy + 0.75, cx, oy + 0.75, 0.35)


def driver_stitch(r, d):
    """issue 2 + 3, searched part: plane vias, once the trunks are down"""
    ox, oy, cx = d['ox'], d['oy'], d['cx']
    anchors = []
    for s in (-1, 1):
        anchors.append(r.neck_stitch('GND', ox, oy + s * 0.8,
                      [(ox, oy + s * 1.45, 0.8), (ox + 0.45, oy + s * 1.5, 0.7),
                       (ox - 0.45, oy + s * 1.5, 0.7), (ox + 0.6, oy + s * 1.3, 0.6),
                       (ox - 0.6, oy + s * 1.3, 0.6), (ox, oy + s * 1.2, 0.6)]))
    anchors.append(r.stitch('GND', cx, oy - 0.525, (1, 0), w=0.5))
    r.stitch('/VBAT', cx, oy + 1.025, (1, 0), w=TRUNK)
    r.stitch('/VBAT', cx, oy + 1.025, (1, 0.8), w=0.5)
    return [a for a in anchors if a]


def escapes(r, d):
    """0.2 mm only between the driver pins; the trunk starts clear of the cap"""
    ox, oy, px, cx = d['ox'], d['oy'], d['ox'] + 0.95, d['cx']
    # OUT1 threads the 0.65 mm gap between the cap pads, then steps up in width
    b1x = cx + 1.2
    r.track(d['out1'], 'F.Cu', px, oy + 0.25, cx + 0.8, oy + 0.25, NECK)
    r.track(d['out1'], 'F.Cu', cx + 0.8, oy + 0.25, b1x, oy + 0.25, 0.4)
    # OUT2 steps clear of the exposed pad before the trunk starts
    r.track(d['out2'], 'F.Cu', px, oy - 0.75, px, oy - 1.25, 0.3)
    r.track(d['out2'], 'F.Cu', px, oy - 1.25, px + 0.35, oy - 1.6, 0.4)
    return (b1x, oy + 0.25), (px + 0.35, oy - 1.6)


def main():
    p = Pcb(BASE)
    for ref, (x, y, rot) in MOVES.items():
        p.move_footprint(ref, x, y, rot)
    for ref, (dx, dy) in REFS.items():
        p.move_property(ref, 'Reference', dx, dy)
    print('moved', ', '.join(MOVES), '| silk refs', ', '.join(REFS))
    print('ripped', rip(p), 'segments/vias')

    # ESP_3V3 layer change shifted clear of C20 pad 1
    p.add_via('/ESP_3V3', 118.2, 115.9)
    p.add_track('/ESP_3V3', 'F.Cu', 118.2, 115.9, 118.1, 116.0, 0.32)
    p.add_track('/ESP_3V3', 'B.Cu', 119.25, 114.85, 118.2, 115.9, 0.32)

    r = Router(p)
    breakouts = {}
    for d in DRIVERS:
        print(f"{d['u']}: escapes + {d['cap']} bypass loop")
        breakouts[d['u']] = escapes(r, d)
        driver_fixed(r, d)

    for d in DRIVERS:
        b1, b2 = breakouts[d['u']]
        for net, bp, (ref, num) in ((d['out1'], b1, d['j1']),
                                    (d['out2'], b2, d['j2'])):
            groups = [r.point_group(bp[0], bp[1], ['F.Cu'], r=0.2),
                      r.pad_group(ref, num, TRUNK)]
            ok = r.route(net, TRUNK, groups)
            print(f"  {net:10s} -> {ref}.{num}  {'ok' if ok else 'FAILED'}")

    anchors = {d['u']: driver_stitch(r, d) for d in DRIVERS}
    # C21 moved, so its plane taps move with it
    r.stitch('/VBAT', 119.3, 110.875, (0, 1), w=0.6)
    r.stitch('GND', 119.3, 107.925, (0, -1), w=0.5)
    for d in DRIVERS:
        v = r.spread_vias('GND', d['ox'], d['oy'], 1.55, 2.6, 4, box=GND_POUR,
                          anchors=anchors[d['u']])
        print(f"  {d['u']} exposed-pad heat spreading: {len(v)} extra GND vias")

    # XSHUT 3 was ripped to clear C20; put it back
    groups = [r.pad_group('U1', '6', 0.2), r.pad_group('J6', '6', 0.2)]
    print('  /GPIO6 ->', 'ok' if r.route('/GPIO6', 0.2, groups) else 'FAILED')

    def rect(x0, y0, x1, y1):
        return f'(xy {x0} {y0}) (xy {x1} {y0}) (xy {x1} {y1}) (xy {x0} {y1})'
    p.add_zone(ZONE.format(uuid=uuid.uuid4(), name='GND pour motor region',
                           pts=rect(*GND_POUR)))
    for a in ESCAPE_AREAS:
        p.add_zone(RULE_AREA.format(uuid=uuid.uuid4(), pts=rect(*a)))
    p.write(OUT)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
