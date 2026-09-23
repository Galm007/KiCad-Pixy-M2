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

Later review findings run as further stages of main(): 4 (motor-B pairing),
5 (buck block), 6 (vias out of pad openings, finish_issue6.py), 7 (the USB
pair, usb_pair.py), 8 (the copper the rule set requires, issue8.py), J8/J9
moved to JST SH in the Pololu encoder pin order (pololu_conn.py) and, last, F1
replaced by a high-breaking-capacity fuse (f1_fuse.py).
"""
import sys, math, heapq, os, uuid
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board import (H, NX, NY, ROUTE, gx, gy, wx, wy, disc_mask, stamp, seg_disc_stamp)
from pcbedit import Pcb, fx
from grid import G, CL, VIA_D, VIA_DRILL, H2H
from sexp import parse, children
from load import fp_info
from loop import polyline

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'base-routed.kicad_pcb')
OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'Pixy-M2.kicad_pcb'))

TRUNK = 0.8          # motor trunk width
NECK = 0.2           # width inside the driver pin field only
EP_VIA = (0.45, 0.25)   # thermal via in the WSON exposed pad

# driver origin, bypass cap, connector pads
DRIVERS = [
    # U4 is not paired: both its outputs have to leave the package on the east
    # side while J8's two motor pins straddle the driver in x, so MOT_A_2 must
    # round U4 whatever happens.  Pairing it was measured and gained 0 mm^2.
    dict(u='U4', ox=109.0, oy=114.0, cap='C18', cx=111.25,
         out1='/MOT_A_1', out2='/MOT_A_2', j1=('J8', '1'), j2=('J8', '6')),
    dict(u='U5', ox=117.0, oy=114.0, cap='C20', cx=119.25,
         out1='/MOT_B_1', out2='/MOT_B_2', j1=('J9', '1'), j2=('J9', '6'),
         pair=True),
]
MOTOR_NETS = ['/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2']

# footprints that move (ref -> x, y, rot)
MOVES = {
    'C18': (111.25, 114.25, 90),    # across U4 VM(5)/GND(7)
    'C20': (119.25, 114.25, 90),    # across U5 VM(5)/GND(7)
    'C21': (119.30, 109.40, 90),    # out of the new U5 escape corridor
    # --- buck block, review issue 5 ---
    'C6':  (139.50,  93.30, 0),     # bootstrap, beside BST/SW instead of 4.2 mm away
    'C17': (139.00,  98.60, 0),     # straddles U3 IN(3) -> GND(4): tight input loop
    'C7':  (147.00,  99.00, 0),     # output filter pulled up under L1
    'C11': (147.00, 101.30, 0),
    'R8':  (136.60, 100.60, 0),     # clear of C17 and of the new FB corridor
    'TP4': (141.90,  99.60, None),  # SW probe: short top stub, no back-layer branch
}

# nets ripped whole
RIP_NETS = ['/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2', '/GPIO6',
            'Net-(U3-SW)', 'Net-(U3-BST)', '/VSYS', '/REG_EN']
# (net, x0,y0,x1,y1) boxes ripped: old cap stubs and the old driver GND/VM stubs
RIP_BOXES = [
    ('/VBAT', 108.5, 112.0, 111.5, 116.0), ('GND', 108.5, 112.0, 111.5, 116.0),
    ('/VBAT', 116.5, 112.0, 119.5, 116.0), ('GND', 116.5, 112.0, 119.5, 116.0),
    ('/VBAT', 105.0, 109.0, 107.0, 112.9), ('GND', 105.0, 109.0, 107.0, 112.9),
    ('/VBAT', 119.0, 109.0, 121.0, 112.6), ('GND', 119.0, 109.0, 121.0, 112.6),
    ('/VBAT', 111.9, 110.9, 114.2, 116.2), ('GND', 111.9, 110.9, 114.2, 116.2),
    ('/ESP_3V3', 118.3, 115.4, 118.7, 115.8),   # via that C20 pad 1 would land on
    ('/ESP_3V3', 136.0, 93.0, 150.0, 106.0),    # buck: FB tap, L1 out, C7/C11 taps
    ('GND', 136.0, 93.0, 150.0, 106.0),         # buck: U3, C17, C7, C11, R8, C13, TP3
]

# reference text moved out of the reworked area (local offsets, footprint frame)
REFS = {'C18': (-2.15, 0.0), 'C20': (-2.15, 0.0), 'C21': (-2.1, 2.7),
        'U5': (0.0, -2.2), 'C17': (-3.2, -0.8), 'U3': (0.0, -4.5)}

# KiCad 10 supports per-via filling/capping. Keep the drawing and native
# via properties consistent; this final pass also clears complete drill edges.
from finish_issue6 import finish_issue6, FAB_NOTE
from usb_pair import usb_pair
from issue8 import issue8, rule_areas as issue8_rule_areas, _drill_clear_of_pads
from pololu_conn import pololu_conn
from f1_fuse import f1_fuse
FAB_NOTE_AT = (100.0, 164.0)

# board-level silkscreen labels that follow a moved pad
TEXTS = {'TP4 SW': (141.9, 101.9)}

# signal nets ripped above, re-routed after the motor trunks have their space
RERUN_SIGNALS = [('/GPIO6', (('U1', '6'), ('J6', '6')))]

# buck nets ripped whole and re-routed once the block's own copper is placed
RERUN_NETS = [
    ('/REG_EN', 0.2, [('R7', '2'), ('R9', '2'), ('R8', '1'), ('C13', '1'), ('U3', '2')]),
]
# /VSYS reaches D1 through the corridor north of the buck.  Left to itself A*
# prefers a shorter path straight through the output filter, which puts the 8.4 V
# input rail between L1 and C7/C11.
VSYS_WEST = [('C12', '1'), ('C17', '1'), ('D2', '1')]
VSYS_NORTH = [(145.0, 90.4)]

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

    def _find_via(self, vm, ok, x, y, want, maxr=3.0, rmin=0.45, outside=None,
                  ok2=None):
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
        score[(dist < rmin) | (dist > maxr)] = 1e9
        if outside:                      # stay clear of this pad's mask opening
            px, py, pw, ph, margin = outside
            score[(np.abs(wx(xs) - px) < pw / 2 + margin) &
                  (np.abs(wy(ys) - py) < ph / 2 + margin)] = 1e9
        for idx in np.argsort(score, axis=None)[:600]:
            iy, ix = np.unravel_index(idx, score.shape)
            if score[iy, ix] >= 1e9: break
            vx, vy = wx(int(xs[iy, ix])), wy(int(ys[iy, ix]))
            if not self._clear_line(ok, x, y, vx, vy): continue
            if ok2 is not None and not self._clear_line(ok2, x, y, vx, vy): continue
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
    def route(self, net, w, groups, quiet=False):
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
                if not quiet: print(f'    FAIL {net}: {len(groups)} groups left')
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

    def route_waypoints(self, net, w, start, waypoints, end):
        """route start -> each waypoint in turn -> end, skipping any that block"""
        prev = start
        for (wx_, wy_) in waypoints:
            leg = self.point_group(wx_, wy_, ['F.Cu', 'B.Cu'], r=0.2)
            if self.route(net, w, [prev, leg], quiet=True):
                prev = self.point_group(wx_, wy_, ['F.Cu', 'B.Cu'], r=0.2)
            else:
                print(f'    (waypoint {wx_:.1f},{wy_:.1f} skipped)')
        return self.route(net, w, [prev, end])

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


def pair_waypoints(pts, side, offset=1.15, step=None, skip_end=1.5):
    """sample a routed polyline and offset each sample to one side of it.

    `side` is the vector from the first output's connector pad to the second's.
    Offsetting consistently toward it keeps the two tracks from crossing and
    puts the second one on the side it has to end up on: J9's two motor pins
    differ in y, J8's in x, so a hardcoded side is wrong for one of them.
    """
    sx, sy = side
    sn = math.hypot(sx, sy) or 1.0
    sx, sy = sx / sn, sy / sn
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(math.dist(a, b) for a, b in segs)
    if step is None:
        step = min(8.0, max(3.0, total / 5.0))    # ~5 samples on a short run
    out, travelled, next_at = [], 0.0, step
    for (ax, ay), (bx, by) in segs:
        L = math.dist((ax, ay), (bx, by))
        if L < 1e-9: continue
        while next_at <= travelled + L:
            f = (next_at - travelled) / L
            px, py = ax + (bx - ax) * f, ay + (by - ay) * f
            nx, ny = -(by - ay) / L, (bx - ax) / L
            if nx * sx + ny * sy < 0: nx, ny = -nx, -ny      # onto `side`
            if next_at <= total - skip_end:
                out.append((round(px + nx * offset, 2), round(py + ny * offset, 2)))
            next_at += step
        travelled += L
    return out


def buck_block(r):
    """issue 5: a compact regulator block around U3.

    U3 is a TSOT-23-6: FB/EN/IN down the left edge, GND/SW/BST down the right.
    IN (pin 3) and GND (pin 4) sit at the same y on opposite sides, so the input
    capacitor goes *under* the package spanning the two — the tightest input loop
    this pinout allows.  BST (6) and SW (5) are adjacent on the right, but L1's
    courtyard starts 0.45 mm past U3's, so the bootstrap capacitor goes above
    instead; that still cuts the BST run from 4.15 mm to 1.9 mm.

    Every track is laid before any via is searched for — a stitching via placed
    into a corridor a later track needs is how the first attempt shorted SW to
    GND under the package.
    """
    IN, GND4 = (137.863, 96.95), (140.137, 96.95)
    FB, SW5, BST6 = (137.863, 95.05), (140.137, 96.0), (140.137, 95.05)
    C17_1, C17_2 = (138.225, 98.6), (139.775, 98.6)
    C6_1, C6_2 = (138.725, 93.3), (140.275, 93.3)
    L1_2 = (147.25, 95.0)
    C7_1, C7_2 = (146.05, 99.0), (147.95, 99.0)
    C11_1, C11_2 = (146.05, 101.3), (147.95, 101.3)

    # --- input loop: IN -> C17 -> GND, both legs short and wide
    r.track('/VSYS', 'F.Cu', IN[0], IN[1] + 0.3, C17_1[0], C17_1[1], 0.5)
    r.track('GND', 'F.Cu', GND4[0], GND4[1] + 0.3, C17_2[0], C17_2[1], 0.5)

    # --- bootstrap, and the switch node.  0.3 mm out of U3.5 until it clears the
    #     0.95 mm pin pitch, then 0.6 mm across to L1.
    r.track('Net-(U3-BST)', 'F.Cu', BST6[0], BST6[1], 139.9, 94.35, 0.25)
    r.track('Net-(U3-BST)', 'F.Cu', 139.9, 94.35, C6_1[0] + 0.3, C6_1[1], 0.25)
    r.track('Net-(U3-SW)', 'F.Cu', SW5[0], SW5[1], 141.0, 96.0, 0.3)
    r.track('Net-(U3-SW)', 'F.Cu', 141.0, 96.0, 142.2, 95.2, 0.6)
    r.track('Net-(U3-SW)', 'F.Cu', C6_2[0], C6_2[1], 142.2, 94.6, 0.4)
    r.track('Net-(U3-SW)', 'F.Cu', 142.3, 95.7, 141.9, 98.9, 0.3)       # TP4 stub

    # --- output filter: one top-layer run L1 -> C7 -> C11
    r.track('/ESP_3V3', 'F.Cu', L1_2[0] - 0.6, L1_2[1], 146.5, 96.4, 0.8)
    r.track('/ESP_3V3', 'F.Cu', 146.5, 96.4, C7_1[0], C7_1[1], 0.8)
    r.track('/ESP_3V3', 'F.Cu', C7_1[0], C7_1[1], C11_1[0], C11_1[1], 0.8)

    # --- feedback: a dedicated sense from FB round the south of the block to
    #     C11, the far output capacitor.  Long, but never near SW, L1 or BST.
    for a, b in (((FB[0] - 0.4, FB[1]), (136.6, 94.7)), ((136.6, 94.7), (136.6, 101.8)),
                 ((136.6, 101.8), (145.6, 101.8)), ((145.6, 101.8), C11_1)):
        r.track('/ESP_3V3', 'F.Cu', a[0], a[1], b[0], b[1], 0.2)

    # --- now the plane vias.  U3.4 gets its own, hand-placed: the search has no
    #     room left between the C17 pad, the SW stub and the package.
    r.track('GND', 'F.Cu', GND4[0], GND4[1] + 0.3, 140.95, 97.7, 0.4)
    r.via('GND', 140.95, 97.7)
    r.stitch('GND', C17_2[0], C17_2[1], (1, 0.5), w=0.5)
    r.stitch('/ESP_3V3', C7_1[0], C7_1[1], (-1, -0.4), w=0.5)
    r.stitch('/ESP_3V3', C11_1[0], C11_1[1], (-1, 0.4), w=0.5)
    for ref, num, want in (('C7', '2', (1, 0)), ('C11', '2', (1, 0)),
                           ('R8', '2', (0, 1)), ('C13', '2', (1, 0)),
                           ('TP3', '1', (-1, 0))):
        pad = next(q for q in r.g.byref[ref]['pads'] if q['num'] == num)
        r.stitch('GND', pad['x'], pad['y'], want, w=0.4)


# the only vias allowed to sit in a pad opening: the driver exposed-pad
# thermal vias, which are there on purpose and carry a fabrication note
THERMAL_VIA_PADS = {('U4', '9'), ('U5', '9')}


def stuck_vias(p):
    """vias sitting inside a pad's solder-mask opening — review issue 6"""
    pcb = parse(p.text)
    pads = []
    for f in children(pcb, 'footprint'):
        fi = fp_info(f)
        for pd in fi['pads']:
            if pd['drill'] or not any(l in pd['layers'] for l in ROUTE): continue
            if not any('Mask' in l for l in pd['layers']): continue
            if (fi['ref'], pd['num']) in THERMAL_VIA_PADS: continue
            w, h = pd['w'], pd['h']
            if abs(pd['rot'] % 180 - 90) < 1: w, h = h, w
            pads.append((f"{fi['ref']}.{pd['num']}", pd['x'], pd['y'], w, h))
    out = []
    for b in p.blocks:
        if Pcb.kind(b) != 'via': continue
        vx, vy, s, dr = Pcb.geom(b)
        for (name, px, py, w, h) in pads:
            if abs(vx - px) <= w / 2 and abs(vy - py) <= h / 2:
                out.append(dict(blk=b, net=Pcb.net(b), at=(vx, vy), size=s, drill=dr,
                                pad=(px, py, w, h), name=name))
                break
    return out


def unstick_vias(p):
    """move each of those vias out of its pad, leaving a stub behind.

    The hole has to clear the pad's *mask opening*, not just its copper: the
    opening exposes the barrel however the board's tenting is set, and that is
    what solder wicks down.  Copper overlap is harmless — via and pad are the
    same net — so only the drill needs the margin.
    """
    stuck = stuck_vias(p)
    if not stuck:
        return 0, []
    blks = {s['blk'] for s in stuck}
    bcu = set()
    for b in p.blocks:
        if Pcb.kind(b) != 'segment': continue
        x1, y1, x2, y2, w, l = Pcb.geom(b)
        if l == 'B.Cu':
            bcu.add((round(x1, 2), round(y1, 2)))
            bcu.add((round(x2, 2), round(y2, 2)))
    p.drop(lambda b: b in blks)
    r = Router(p)
    failed = []
    for s in sorted(stuck, key=lambda s: min(s['pad'][2], s['pad'][3])):
        (vx, vy), (px, py, pw, ph) = s['at'], s['pad']
        dx, dy = vx - px, vy - py
        if math.hypot(dx, dy) < 0.05:
            dx, dy = (0.0, 1.0) if pw >= ph else (1.0, 0.0)
        on_back = (round(vx, 2), round(vy, 2)) in bcu
        d = r.g.dist(s['net'])
        ok = r.g.ok_masks(d, 0.25)
        spot = r._find_via(r.g.via_mask(d), ok['F.Cu'], vx, vy, (dx, dy), maxr=2.6,
                           rmin=0.3, outside=(px, py, pw, ph, s['drill'] / 2 + 0.1),
                           ok2=ok['B.Cu'] if on_back else None)
        if spot is None:
            failed.append((s['name'], s['net']))
            p.add_via(s['net'], vx, vy, s['size'], s['drill'])      # leave it be
            continue
        r.track(s['net'], 'F.Cu', vx, vy, *spot, 0.25)
        if on_back:
            r.track(s['net'], 'B.Cu', vx, vy, *spot, 0.25)
        r.via(s['net'], *spot, s['size'], s['drill'])
    return len(stuck) - len(failed), failed


def reroute_stuck_nets(p, nets):
    """last resort for a via that cannot step out of its pad: rip the whole net
    and route it again.  The router's own via search already refuses to land in
    a pad, so the replacement route simply does not need one there."""
    p.drop(lambda b: Pcb.net(b) in nets)
    r = Router(p)
    done = []
    for net in sorted(nets):
        pads = r.g.nets.get(net, [])
        if len(pads) < 2: continue
        w = 0.2 if net != 'Net-(J1-D--PadA7)' else 0.2
        groups = [r.pad_group(ref, q['num'], w) for ref, q in pads]
        done.append((net, r.route(net, w, groups, quiet=True)))
    return done


def encoder48_cleanup(p):
    """Audit P3: retain the verified 26.03 mm J8/R20/U1 route.

    Apply after the generic via-in-pad reroute, which otherwise sends GPIO48
    around TP5 and J11 (72.36 mm). These paths match the current fixed placement,
    use 0.2 mm tracks and 0.6/0.3 mm vias, and keep every drill at least 0.45 mm
    clear of SMD mask openings. The west bottom branch feeds R20; the top bridge
    above R20 avoids its crowded pad field without adding a via inside a pad.
    """
    net = '/GPIO48'
    paths = [
        ('F.Cu', [(115.2, 134.25), (115.45, 134.25), (115.5, 134.2),
                  (115.55, 134.2), (115.6, 134.15), (115.75, 134.15),
                  (115.85, 134.05), (117.25, 134.05), (117.8, 134.6)]),
        ('F.Cu', [(116.1, 135.2), (116.15, 135.25), (116.65, 135.25),
                  (116.7, 135.3), (116.8, 135.3), (116.8, 135.35),
                  (116.9, 135.35), (116.9, 135.4), (117.0, 135.4),
                  (117.1, 135.5), (117.1, 135.55), (117.15, 135.6),
                  (117.15, 135.65), (117.2, 135.7), (117.2, 135.8),
                  (117.25, 135.85), (117.25, 136.15), (117.55, 136.45)]),
        ('F.Cu', [(126.3, 139.15), (126.6, 139.45), (126.65, 139.45),
                  (126.7, 139.5), (126.75, 139.5), (126.75, 139.55),
                  (126.8, 139.6), (126.8, 139.65), (126.85, 139.7),
                  (126.85, 139.75), (127.0, 139.9)]),
        ('B.Cu', [(109.45, 128.75), (109.65, 128.75), (116.1, 135.2)]),
        ('B.Cu', [(117.8, 134.6), (121.75, 134.6), (126.3, 139.15)]),
    ]
    p.drop(lambda b: Pcb.net(b) == net)
    for layer, pts in paths:
        for a, b in zip(pts, pts[1:]):
            p.add_track(net, layer, *a, *b, 0.2)
    for x, y in [(115.2, 134.25), (116.1, 135.2),
                 (117.8, 134.6), (126.3, 139.15)]:
        p.add_via(net, x, y, 0.6, 0.3)


def main():
    p = Pcb(BASE)
    for ref, (x, y, rot) in MOVES.items():
        p.move_footprint(ref, x, y, rot)
    for ref, (dx, dy) in REFS.items():
        p.move_property(ref, 'Reference', dx, dy)
    for label, (x, y) in TEXTS.items():
        p.move_text(label, x, y)
    p.add_notes(FAB_NOTE, *FAB_NOTE_AT)
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
        wps = []
        for net, bp, (ref, num) in ((d['out1'], b1, d['j1']),
                                    (d['out2'], b2, d['j2'])):
            start = r.point_group(bp[0], bp[1], ['F.Cu'], r=0.2)
            end = r.pad_group(ref, num, TRUNK)
            if wps:
                ok = r.route_waypoints(net, TRUNK, start, wps, end)
            else:
                ok = r.route(net, TRUNK, [start, end])
            print(f"  {net:10s} -> {ref}.{num}  {'ok' if ok else 'FAILED'}"
                  + (f"  (via {len(wps)} pair waypoints)" if wps else ''))
            if d.get('pair') and net == d['out1'] and ok:
                pts = polyline(p, net, (bp[0], bp[1]),
                               r.g.byref[ref]['pads'][0]['x'] and
                               next((q['x'], q['y']) for q in r.g.byref[ref]['pads']
                                    if q['num'] == num))
                p2 = next((q['x'], q['y']) for q in r.g.byref[d['j2'][0]]['pads']
                          if q['num'] == d['j2'][1])
                p1 = pts[-1]
                wps = pair_waypoints(pts, (p2[0] - p1[0], p2[1] - p1[1]))
                print(f"    pair corridor: {len(wps)} waypoints offset from {net}")

    anchors = {d['u']: driver_stitch(r, d) for d in DRIVERS}
    print('buck block')
    buck_block(r)
    # C21 moved, so its plane taps move with it
    r.stitch('/VBAT', 119.3, 110.875, (0, 1), w=0.6)
    r.stitch('GND', 119.3, 107.925, (0, -1), w=0.5)
    for d in DRIVERS:
        v = r.spread_vias('GND', d['ox'], d['oy'], 1.55, 2.6, 4, box=GND_POUR,
                          anchors=anchors[d['u']])
        print(f"  {d['u']} exposed-pad heat spreading: {len(v)} extra GND vias")

    ok = r.route('/VSYS', 0.6, [r.pad_group(*q, 0.6) for q in VSYS_WEST])
    ok &= r.route_waypoints('/VSYS', 0.6, r.pad_group('C12', '1', 0.6),
                            VSYS_NORTH, r.pad_group('D1', '1', 0.6))
    print('  /VSYS ->', 'ok' if ok else 'FAILED')
    for net, w, pads in RERUN_NETS:
        groups = [r.pad_group(*q, w) for q in pads]
        print(f'  {net} ->', 'ok' if r.route(net, w, groups) else 'FAILED')

    # XSHUT 3 was ripped to clear C20's new position; put it back
    for net, (a, b) in RERUN_SIGNALS:
        groups = [r.pad_group(*a, 0.2), r.pad_group(*b, 0.2)]
        print(f'  {net} ->', 'ok' if r.route(net, 0.2, groups) else 'FAILED')

    n, failed = unstick_vias(p)
    print(f'vias moved out of pad openings: {n}' +
          (f'; no room for {", ".join(f[0] for f in failed)}' if failed else ''))
    if failed:
        nets = {f[1] for f in failed}
        done = reroute_stuck_nets(p, nets)
        bad = [q for q, okr in done if not okr]
        print(f'  re-routed {len(done) - len(bad)}/{len(done)} of their nets'
              + (f'; FAILED {bad}' if bad else ''))
        n2, failed2 = unstick_vias(p)
        print(f'  second pass moved {n2} more' +
              (f'; still stuck: {", ".join(f[0] for f in failed2)}' if failed2 else
               '; no via centre left in a solder pad (drill audit still required)'))

    encoder48_cleanup(p)
    print('  /GPIO48: restored compact encoder route (audit P3)')
    finish_issue6(p)
    print('  issue 6: cleared drill edges and specified four filled/capped vias')
    print('USB pair (issue 7)')
    usb_pair(p, Router)
    print('rule-set copper (issue 8)')
    issue8(p, Router)
    print('J8/J9 in the Pololu encoder pin order')
    if not pololu_conn(p, Router, pair_waypoints, _drill_clear_of_pads):
        raise RuntimeError('J8/J9 connector routing failed')
    print('F1 -> Littelfuse 885 (1500 A breaking)')
    if not f1_fuse(p, Router):
        raise RuntimeError('F1 routing failed')

    # U1 keeps its antenna outline on F.Fab (it overhangs the board edge); that
    # variant lives in the project library, so the placed copy matches it
    p.set_fpid('U1', 'Pixy-M2:ESP32-S3-WROOM-1_AntennaOverhang')

    def rect(x0, y0, x1, y1):
        return f'(xy {x0} {y0}) (xy {x1} {y0}) (xy {x1} {y1}) (xy {x0} {y1})'
    p.add_zone(ZONE.format(uuid=uuid.uuid4(), name='GND pour motor region',
                           pts=rect(*GND_POUR)))
    for a in ESCAPE_AREAS:
        p.add_zone(RULE_AREA.format(uuid=uuid.uuid4(), pts=rect(*a)))
    for z in issue8_rule_areas():
        p.add_zone(z)
    # Keep the current PCB intact if replay or the drill/paste audit fails.
    import pathlib, shutil, subprocess, tempfile
    out = pathlib.Path(OUT)
    with tempfile.TemporaryDirectory(prefix='issue6-check-') as tmp:
        candidate = pathlib.Path(tmp) / out.name
        project = out.with_suffix('.kicad_pro')
        if project.exists():
            shutil.copy2(project, candidate.with_suffix('.kicad_pro'))
        p.write(candidate)
        subprocess.run(['/usr/bin/python3', str(pathlib.Path(__file__).with_name('via_openings.py')),
                        str(candidate), '--output', str(pathlib.Path(tmp) / 'apertures.json')], check=True)
        shutil.copyfile(candidate, out)
    print('wrote', OUT, '(aperture audit passed; refill zones and run DRC)')


if __name__ == '__main__':
    main()
