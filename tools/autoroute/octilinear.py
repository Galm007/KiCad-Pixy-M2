#!/usr/bin/env python3
"""Straight 0/45/90 degree runs: the last copper stage (rework, after devkit.py).

The A* router steps on a 0.05 mm grid in eight directions, with no cost for
turning.  A run at any other angle comes out as a staircase of 0.05-0.3 mm
segments, which renders as a curve.  On the devkit board that was 1060 of the
1678 segments.  This stage rebuilds each routed chain as the fewest straight
legs at 0/45/90 degrees that keep the clearances the router kept:

- A chain is the copper of one net, on one layer, at one width, between two
  nodes.  Nodes are pads, vias, junctions of three or more segments, width
  changes and T-joints.
- From each vertex, the next vertex is the farthest point along the chain that
  one leg, or a 45 degree leg plus an orthogonal one, reaches in the clear.
  A 90 degree turn is taken only where it reaches farther than any 45 degree
  one, and is then chamfered to two 45 degree turns where the chamfer fits.
- "Clear" is the router's own raster test: CL 0.26 mm plus half the width (and
  0.02 mm more for a new leg), the board edge and keep-outs.  devkit.make_router
  adds the custom floors: IPROPI 0.75 mm from motor copper, REG_EN and
  VBAT_SENSE 5 mm.  A cell on the chain's own old centreline is always clear,
  because the old copper there passed DRC.
- The hand-placed buck block keeps its copper: SW, BST and REG_EN, and every
  chain touching U3, L1, C6, R8 or C13.  The piece on each U4/U5 pin stays
  too.  Necks below the class minimum are legal only inside the `Motor pin
  escape` areas, so their new legs must lie wholly inside one.
- New legs also keep 0.85 mm (raster) between IPROPI and motor copper, so
  GPIO10's 0.80 mm floor holds.  A motor output's new legs stay within 1.5 mm
  of its partner's copper, or no more than 0.3 mm farther than its old path
  was at that spot, so a pair straightens together and its loop stays shut.
- Pieces that meet only by overlapping are first joined exactly (_heal), so
  every chain runs between real nodes.  A pair at minimum spacing frees room
  for its partner only once it has moved, so the pass repeats until a round
  changes nothing.

Nodes never move, so connectivity is unchanged.  A chain is replaced only when
the new one has fewer segments or fewer sharp turns.  Standalone:

    python3 octilinear.py [in.kicad_pcb [out.kicad_pcb]]
"""
import collections
import functools
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from board import ROUTE, NX, NY, H, gx, gy, stamp, seg_disc_stamp, disc_mask   # noqa: E402
from pcbedit import Pcb                                                       # noqa: E402
from grid import CL                                                           # noqa: E402
from pololu_conn import _in_pad, _layers                                      # noqa: E402
import devkit                                                                 # noqa: E402

FROZEN_NETS = {'Net-(U3-SW)', 'Net-(U3-BST)', '/REG_EN'}
HAND_REFS = {'U3', 'L1', 'C6', 'R8', 'C13'}       # the buck block: whole chains stay
PIN_REFS = {'U4', 'U5'}                         # driver pins: the piece on the pin stays
ESCAPES = [(107.0, 112.0, 112.9, 116.0), (115.0, 112.0, 120.9, 116.0)]   # rework.ESCAPE_AREAS
NEW_MARGIN = 0.02            # extra clearance for a leg off the old centreline
# new legs keep these floors (raster distance; the 0.05 mm raster reads up to
# ~0.03 mm generous): GPIO10's escape via held 0.80 mm to motor copper before
# this stage, and CLAUDE.md records that as the floor
FLOORS = [({'/GPIO2', '/GPIO10'}, devkit.MOTOR_NETS, 0.85)]
# a motor output's new legs stay within this distance (mm, centreline to the
# partner's copper on either layer) of its partner, so a pair straightens as a
# pair rather than opening up its loop
PAIR = {'/MOT_A_1': '/MOT_A_2', '/MOT_A_2': '/MOT_A_1', '/MOT_B_1': '/MOT_B_2', '/MOT_B_2': '/MOT_B_1'}
PAIR_BAND = 1.5
PAIR_SLACK = 0.3
CHAMFERS = (1.5, 1.0, 0.7, 0.5, 0.35, 0.25)


def _key(q):
    return (round(q[0], 3), round(q[1], 3))


def _dir(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L) if L > 1e-9 else None


def _turn(u, v):
    if u is None or v is None:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))))


def _octo(a, b):
    dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
    return dx < 1e-4 or dy < 1e-4 or abs(dx - dy) < 1e-4


def _r(q):
    return (round(q[0], 4), round(q[1], 4))


def ways(a, b):
    """octilinear paths a -> b: one leg, or 45 degrees then orthogonal, or
    orthogonal then 45 degrees"""
    if _octo(a, b):
        return [[a, b]]
    dx, dy = b[0] - a[0], b[1] - a[1]
    sx, sy = math.copysign(1, dx), math.copysign(1, dy)
    m = min(abs(dx), abs(dy))
    diag_first = _r((a[0] + sx * m, a[1] + sy * m))
    orth_first = _r((b[0] - sx * m, a[1]) if abs(dx) > abs(dy) else (a[0], b[1] - sy * m))
    return [[a, diag_first, b], [a, orth_first, b]]


def _turns(path, din, dout):
    dirs = [d for d in (_dir(path[k], path[k + 1]) for k in range(len(path) - 1)) if d]
    t = [_turn(din, dirs[0])] + [_turn(dirs[k], dirs[k + 1]) for k in range(len(dirs) - 1)]
    if dout is not None:
        t.append(_turn(dirs[-1], dout))
    return max(t), dirs[-1]


class Clear:
    def __init__(self, ok):
        self.ok = ok

    def seg(self, a, b):
        n = max(2, int(math.dist(a, b) / (H / 2)) + 2)
        t = np.linspace(0.0, 1.0, n)
        ix = np.rint(gx(a[0] + (b[0] - a[0]) * t)).astype(int)
        iy = np.rint(gy(a[1] + (b[1] - a[1]) * t)).astype(int)
        if ix.min() < 0 or iy.min() < 0 or ix.max() >= NX or iy.max() >= NY:
            return False
        return bool(self.ok[iy, ix].all())

    def path(self, pts):
        return all(self.seg(pts[k], pts[k + 1]) for k in range(len(pts) - 1))


def simplify(P, clear, din=None, dout=None):
    """the fewest clear octilinear legs through the chain P[0] .. P[-1]"""
    along = [0.0]
    for a, b in zip(P, P[1:]):
        along.append(along[-1] + math.dist(a, b))
    out, d, i, n = [P[0]], din, 0, len(P) - 1
    while i < n:
        gentle = sharp = None
        for j in range(n, i, -1):
            for path in ways(P[i], P[j]):
                worst, last = _turns(path, d, dout if j == n else None)
                if worst > 90.5 or (worst > 45.5 and sharp):
                    continue
                if clear.path(path):
                    if worst <= 45.5:
                        gentle = (j, path, last)
                        break
                    sharp = (j, path, last)
            if gentle:
                break
        # a 90 degree turn only where it reaches clearly farther than 45 degrees
        if gentle and (not sharp or along[gentle[0]] - along[i] >= 0.6 * (along[sharp[0]] - along[i])):
            best = gentle
        else:
            best = sharp
        if best is None:                       # the old segment, as it was
            best = (i + 1, [P[i], P[i + 1]], _dir(P[i], P[i + 1]))
        i, path, last = best
        out += path[1:]
        d = last or d
    return merge(out)


def merge(pts):
    out = [pts[0]]
    for q in pts[1:]:
        if math.dist(q, out[-1]) < 1e-6:
            continue
        if len(out) >= 2:
            u, v = _dir(out[-2], out[-1]), _dir(out[-1], q)
            if u and v and _turn(u, v) < 0.5:
                out[-1] = q
                continue
        out.append(q)
    return out


def chamfer(pts, clear):
    """cut each 90 degree corner to two 45 degree turns where the cut fits"""
    out, k = list(pts), 1
    while k < len(out) - 1:
        u, v = _dir(out[k - 1], out[k]), _dir(out[k], out[k + 1])
        if u and v and abs(_turn(u, v) - 90) < 1:
            la, lb = math.dist(out[k - 1], out[k]), math.dist(out[k], out[k + 1])
            for t in CHAMFERS:
                t = min(t, la if k - 1 == 0 else la / 2, lb if k + 1 == len(out) - 1 else lb / 2)
                if t < 0.2:
                    break
                a = _r((out[k][0] - u[0] * t, out[k][1] - u[1] * t))
                b = _r((out[k][0] + v[0] * t, out[k][1] + v[1] * t))
                if _octo(a, b) and clear.seg(a, b):
                    out[k:k + 1] = [a, b]
                    k += 1
                    break
        k += 1
    return merge(out)


def _score(pts, din, dout):
    sharp = 0
    dirs = [d for d in (_dir(pts[k], pts[k + 1]) for k in range(len(pts) - 1)) if d]
    seq = ([din] if din else []) + dirs + ([dout] if dout else [])
    for a, b in zip(seq, seq[1:]):
        sharp += _turn(a, b) > 45.5
    off = sum(not _octo(pts[k], pts[k + 1]) for k in range(len(pts) - 1))
    return (len(pts) - 1) + 3 * sharp + 3 * off


# ---------------------------------------------------------------- chains
def _seg_d(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)


def _heal(pieces, anchored):
    """join every loose end that lies inside another piece's copper to that
    piece exactly: split the host at the end's projection and add a link, no
    wider than either, which stays inside the copper that is already there.
    The router's pieces often meet only by overlapping like this."""
    for _ in range(200):
        at = collections.defaultdict(list)
        for i, (x1, y1, x2, y2, w) in enumerate(pieces):
            at[_key((x1, y1))].append(i)
            at[_key((x2, y2))].append(i)
        nbr = collections.defaultdict(set)
        for ids in at.values():
            for i in ids:
                nbr[i] |= set(ids) - {i}
        done = False
        for k, ids in at.items():
            if len(ids) != 1 or anchored(k):
                continue
            i = ids[0]
            near, front = {i}, [i]
            for _d in range(10):                 # its own staircase is not a host
                front = [q for c in front for q in nbr[c] if q not in near]
                near |= set(front)
            best = None
            for h, (x1, y1, x2, y2, w) in enumerate(pieces):
                if h in near:
                    continue
                dd = _seg_d(k[0], k[1], x1, y1, x2, y2)
                if dd <= w / 2 + 1e-3 and (best is None or dd < best[0]):
                    best = (dd, h)
            if best is None:
                continue
            h = best[1]
            x1, y1, x2, y2, wh = pieces[h]
            L2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
            s = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((k[0] - x1) * (x2 - x1) + (k[1] - y1) * (y2 - y1)) / L2))
            q = _r((x1 + s * (x2 - x1), y1 + s * (y2 - y1)))
            e = (pieces[i][0], pieces[i][1]) if _key(pieces[i][:2]) == k else (pieces[i][2], pieces[i][3])
            if math.dist(q, (x1, y1)) > 1e-4 and math.dist(q, (x2, y2)) > 1e-4:
                pieces[h] = (x1, y1, q[0], q[1], wh)
                pieces.append((q[0], q[1], x2, y2, wh))
            if math.dist(e, q) > 1e-4:
                pieces.append((e[0], e[1], q[0], q[1], min(wh, pieces[i][4])))
            done = True
            break
        if not done:
            return pieces
    return pieces


def chains(p, g, net, layer):
    """the net's copper on one layer as pieces, and its chains:
    (width, points, piece ids, din, dout, frozen, neck)"""
    pads = [(f['ref'], pd) for f in g.fps for pd in f['pads']
            if pd['net'] == net and layer in _layers(pd)]
    vias = [Pcb.geom(b) for b in p.blocks if Pcb.kind(b) == 'via' and Pcb.net(b) == net]

    def refs_at(k):
        return {ref for ref, pd in pads if _in_pad(pd, k[0], k[1])}

    def at_via(k):
        return any(math.hypot(k[0] - vx, k[1] - vy) <= s / 2 + 1e-3 for (vx, vy, s, dr) in vias)

    blocks = [b for b in p.blocks if Pcb.kind(b) == 'segment' and Pcb.net(b) == net
              and Pcb.geom(b)[5] == layer]
    pieces = [Pcb.geom(b)[:5] for b in blocks]
    pieces = _heal(pieces, lambda k: bool(refs_at(k)) or at_via(k))
    at = collections.defaultdict(list)
    for i, (x1, y1, x2, y2, w) in enumerate(pieces):
        at[_key((x1, y1))].append(i)
        at[_key((x2, y2))].append(i)
    node, touch = set(), {}
    for k, ids in at.items():
        r = refs_at(k)
        if r:
            touch[k] = r
        if len(ids) != 2 or abs(pieces[ids[0]][4] - pieces[ids[1]][4]) > 1e-6 or r or at_via(k):
            node.add(k)
    # a piece on a driver pin keeps its place; the chain beyond it may move
    pinned = set()
    for i, (x1, y1, x2, y2, w) in enumerate(pieces):
        if (touch.get(_key((x1, y1)), set()) | touch.get(_key((x2, y2)), set())) & PIN_REFS:
            pinned.add(i)
            node |= {_key((x1, y1)), _key((x2, y2))}
    out, used = [], set()
    for start in sorted(node):
        for i0 in at[start]:
            if i0 in used:
                continue
            pts, ids, cur, i = [start], [], start, i0
            while True:
                used.add(i)
                ids.append(i)
                x1, y1, x2, y2, w = pieces[i]
                cur = _key((x2, y2)) if _key((x1, y1)) == cur else _key((x1, y1))
                pts.append(cur)
                if cur in node:
                    break
                rest = [q for q in at[cur] if q != i]
                if not rest or rest[0] in used:
                    break
                i = rest[0]
            # the file's own coordinates, not the rounded keys
            exact = []
            for k, q in zip(pts, [pieces[j] for j in ids] + [pieces[ids[-1]]]):
                exact.append((q[0], q[1]) if _key(q[:2]) == k else (q[2], q[3]))

            def side(k, own):
                other = [q for q in at[k] if q != own]
                if len(other) == 1 and k not in touch:
                    x1, y1, x2, y2 = pieces[other[0]][:4]
                    far = (x1, y1) if _key((x2, y2)) == k else (x2, y2)
                    return _dir(far, k)
                return None
            w = pieces[ids[0]][4]
            din = side(pts[0], ids[0])
            back = side(pts[-1], ids[-1])
            dout = (-back[0], -back[1]) if back else None
            refs = touch.get(pts[0], set()) | touch.get(pts[-1], set())
            # copper below its class minimum is legal only inside a
            # `Motor pin escape` area, so it must not move
            neck = w < (0.6 if net in devkit.MOTOR_NETS else 0.2) - 1e-6
            frozen = bool(refs & HAND_REFS) or any(j in pinned for j in ids)
            out.append((w, exact, ids, din, dout, frozen, neck))
    return pieces, out


# ---------------------------------------------------------------- the pass
def _restamp(g, p, net):
    nid = g.netid[net]
    for l in ROUTE:
        g.cu[l][g.cu[l] == nid] = -1
    for f in g.fps:
        for pd in f['pads']:
            if pd['net'] == net:
                sel = g.pad_sel(pd, 0.0)
                for l in ROUTE:
                    if l in pd['layers'] or '*.Cu' in pd['layers']:
                        stamp(g.cu[l], sel, nid)
    for b in p.blocks:
        if Pcb.net(b) != net:
            continue
        if Pcb.kind(b) == 'segment':
            x1, y1, x2, y2, w, l = Pcb.geom(b)
            if l in g.cu:
                seg_disc_stamp(g.cu[l], x1, y1, x2, y2, w / 2, nid)
        else:
            x, y, s, dr = Pcb.geom(b)
            for l in ROUTE:
                stamp(g.cu[l], disc_mask(x, y, s / 2), nid)


def _line_mask(pts, layer_shape):
    m = np.zeros(layer_shape, bool)
    for a, b in zip(pts, pts[1:]):
        n = max(2, int(math.dist(a, b) / (H / 2)) + 2)
        t = np.linspace(0.0, 1.0, n)
        ix = np.clip(np.rint(gx(a[0] + (b[0] - a[0]) * t)).astype(int), 0, NX - 1)
        iy = np.clip(np.rint(gy(a[1] + (b[1] - a[1]) * t)).astype(int), 0, NY - 1)
        m[iy, ix] = True
    return m


def _extra(g, net, layer, w, line=None):
    """the stage's own floors and the motor pair band, as a cell mask.  Where
    the old chain already ran farther from its partner than the band (at the
    pins, where a pair parts), a new leg may stray PAIR_SLACK beyond the old
    path's own distance at that spot."""
    from scipy import ndimage
    m = np.ones((NY, NX), bool)
    for a, b, c in FLOORS:
        agg = b if net in a else (a if net in b else None)
        if agg:
            ids = [g.netid[n] for n in agg if n in g.netid]
            da = ndimage.distance_transform_edt(~np.isin(g.cu[layer], ids)) * H
            m &= da >= c + w / 2
    if net in PAIR and PAIR[net] in g.netid:
        pid = g.netid[PAIR[net]]
        other = np.zeros((NY, NX), bool)
        for l in ROUTE:
            other |= g.cu[l] == pid
        pd = ndimage.distance_transform_edt(~other) * H
        ok = pd <= PAIR_BAND + w / 2
        if line is not None and line.any():
            _, (iy, ix) = ndimage.distance_transform_edt(~line, return_indices=True)
            ok |= pd <= pd[iy, ix] + PAIR_SLACK
        m &= ok
    return m


@functools.lru_cache(maxsize=None)
def _escape_mask(w):
    """cells where a neck of width w lies wholly inside a `Motor pin escape`
    area (DRC's enclosedByArea tests the round caps too)"""
    from board import wx, wy
    xs, ys = wx(np.arange(NX)), wy(np.arange(NY))
    m = np.zeros((NY, NX), bool)
    for x0, y0, x1, y1 in ESCAPES:
        e = w / 2 + 0.05
        m |= ((xs[None, :] >= x0 + e) & (xs[None, :] <= x1 - e)
              & (ys[:, None] >= y0 + e) & (ys[:, None] <= y1 - e))
    return m


def octilinear(p, Router, rounds=4):
    r = devkit.make_router(Router, p)
    g = r.g
    nets = sorted({Pcb.net(b) for b in p.blocks if Pcb.kind(b) == 'segment'} - {None} - FROZEN_NETS)
    before = sum(1 for b in p.blocks if Pcb.kind(b) == 'segment')
    changed = 0
    # a pair at minimum spacing frees room for its partner only once it has
    # moved, so repeat until a round changes nothing
    for _round in range(rounds):
        n0 = changed
        changed += _round_pass(p, g, nets)
        if changed == n0:
            break
    after = sum(1 for b in p.blocks if Pcb.kind(b) == 'segment')
    vias = devkit.stitch_islands(devkit.make_router(Router, p))
    print(f'  {changed} chains straightened in {_round + 1} rounds: {before} -> {after} segments; '
          f'{vias} GND vias for B.Cu pour pieces left without one')
    return changed


def _round_pass(p, g, nets):
    changed = 0
    for net in nets:
        d, edits = None, 0
        for layer in ROUTE:
            pieces, work = chains(p, g, net, layer)
            if not work:
                continue
            new_of = {}
            for n_, (w, pts, ids, din, dout, frozen, neck) in enumerate(work):
                if frozen or (len(ids) == 1 and _octo(pts[0], pts[-1])):
                    continue
                if d is None:
                    d = g.dist(net)
                dd, own = d[layer]
                base = (((dd >= CL + w / 2 + NEW_MARGIN) | (own >= w / 2 + H))
                        & (g.dist_edge >= CL + w / 2) & g.inside & ~g.keepout)
                if neck:
                    base &= _escape_mask(w)
                line = _line_mask(pts, base.shape)
                base &= _extra(g, net, layer, w, line if net in PAIR else None)
                clear = Clear(base | line)
                new = chamfer(simplify(pts, clear, din, dout), clear)
                if _score(new, din, dout) < _score(pts, din, dout):
                    new_of[n_] = new
            if not new_of:
                continue
            # rewrite the layer's copper of this net: kept pieces as they are
            # (split where a loose end was joined), straightened chains anew
            p.blocks = [b for b in p.blocks if not (Pcb.kind(b) == 'segment' and Pcb.net(b) == net
                                                    and Pcb.geom(b)[5] == layer)]
            emitted = set()

            def emit(x1, y1, x2, y2, w):
                k = (min(_key((x1, y1)), _key((x2, y2))), max(_key((x1, y1)), _key((x2, y2))), round(w, 4))
                if k[0] != k[1] and k not in emitted:
                    emitted.add(k)
                    p.add_track(net, layer, x1, y1, x2, y2, w)
            for n_, (w, pts, ids, din, dout, frozen, neck) in enumerate(work):
                if n_ in new_of:
                    q = new_of[n_]
                    for a_, b_ in zip(q, q[1:]):
                        emit(a_[0], a_[1], b_[0], b_[1], w)
                else:
                    for j in ids:
                        emit(*pieces[j])
            edits += len(new_of)
        if edits:
            _restamp(g, p, net)
            changed += edits
    return changed


def main(src, dst):
    import rework
    p = Pcb(src)
    octilinear(p, rework.Router)
    p.write(dst)
    print('wrote', dst)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0] if a else os.path.join(HERE, '..', '..', 'Pixy-M2.kicad_pcb'),
         a[1] if len(a) > 1 else os.path.join(HERE, '..', '..', 'Pixy-M2.kicad_pcb'))
