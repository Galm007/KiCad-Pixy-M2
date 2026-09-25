#!/usr/bin/env python3
"""The UVLO enable network beside U3.2 (2026-09-24).

REG_EN is a ~20 kOhm node sitting 1.2 V above the AP63203's EN comparator
threshold (CLAUDE.md issue 2).  The layout rule for it was to put R8 and C13
next to U3.2 and run the long leg from R7/R9 into them.  The issue-5 buck
block did not do that.  Its FB sense trace left U3.1 west and ran down
x = 136.6, round the south of the block, 0.5 mm from U3's west pins, so EN
could only leave the package through a via *under* it, 0.40 mm from the SW
pin.  R8 sat 7.4 mm of copper away, straddling the FB trace; C13 was 9.9 mm
away, below it.

  1  C13 and R8 stand vertical (rot 270) in a row just west of U3, with their
     REG_EN pads level with EN.  U3.2 -> C13.1 -> R8.1 is one straight
     top-layer run along y = 96, filter capacitor first.  Their GND pads face
     south, and each has its own plane via.
  2  FB stays what issue 5 made it: a dedicated top-layer trace from U3.1 to
     C11.1 with no via, so it touches the 3V3 plane nowhere but at C11.  It
     now leaves U3.1 along y = 95.4, between C12 and the new parts, and turns
     south at x = 132.2 instead of x = 136.6.  The rest of its old run to C11
     is unchanged.  A via would have bonded FB to the In2 3V3 pour beside U3,
     undoing the output-capacitor pickup that review finding 5 asked for.
  3  The long leg crosses FB underneath: a via west of R8.1, 45 degrees down
     on B.Cu, then a via beside R7.  It then drops down x = 130.1 on top to
     R7.2 and R9.2, as before.  Both REG_EN vias are over 5.6 mm from the
     switch node.  They carry no plane net, so they tie nothing to In1 or In2.
  4  The VSYS hop from C12 to C17 moves its upper via north of FB.  Its lower
     via at (137.6, 97.95) and the C17 stub stay.

Every via is at least 1.35 mm from any other non-plane via, so its In1/In2
antipad stays a separate hole in the plane.  Every coordinate is
hand-computed against the 0.2 mm clearance and issue 6's 0.10 mm
drill-to-opening floor; DRC and via_openings.py check them.

Runs after battery_bay.py in rework.py.  Standalone, it converts an existing
board once:

    /usr/bin/python3 tools/autoroute/reg_en.py [board.kicad_pcb]
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcbedit import Pcb

SIG, GND_W, VSYS_W = 0.2, 0.4, 0.6
VIA = (0.6, 0.3)

# (x, y, rot): old, then new.  rot 270 puts pad 1 (REG_EN) to the north.
OLD = {'R8': (136.6, 100.6, 0), 'C13': (137.0, 103.0, 0)}
NEW = {'C13': (136.18, 97.0, 270),   # courtyard 0.04 mm clear of U3's (x 136.95)
       'R8': (134.47, 97.175, 270)}  # courtyard clears C12's (y 95.3) and C13's
# reference fields: local offset in the footprint frame, board-frame angle
REFS = {'R8': ((1.125, 1.87), 0),    # west of R8, reading left to right
        'C13': ((3.3, 0.88), 0),     # under the pair, clear of the GND vias
        'C17': ((0.3, 1.75), 0)}     # was upright at x = 135.8, where C13 now sits

# /REG_EN.  Pad centres: C13.1 (136.18, 96.225), R8.1 (134.47, 96.2625)
EN_ROW = [(137.5, 96.0), (136.18, 96.0), (134.47, 96.0)]   # U3.2 -> C13.1 -> R8.1
EN_VIA_A = (133.0, 96.35)                                   # inside FB's turn
EN_VIA_B = (130.1, 98.2)                                    # beside R7
EN_OUT = [(134.47, 96.35), EN_VIA_A]                        # R8.1 -> via A
EN_B = [EN_VIA_A, (131.15, 98.2), EN_VIA_B]                 # under FB
EN_LEG = [EN_VIA_B, (130.1, 99.0875), (130.1, 102.4), (129.5, 103.0)]   # -> R9.2
R7_TAP = [(130.1, 99.0875), (129.0, 99.0875)]               # -> R7.2
GND_VIAS = {(136.18, 97.775): (136.18, 98.85),              # C13.2
            (134.47, 98.0875): (134.47, 99.2)}              # R8.2

# /ESP_3V3 FB sense, top copper only
FB_OLD = [((137.463, 95.05), (136.6, 94.7)), ((136.6, 94.7), (136.6, 101.8)),
          ((136.6, 101.8), (145.6, 101.8))]
FB = [(137.463, 95.05), (137.1, 95.05), (136.75, 95.4), (132.2, 95.4),
      (132.2, 101.8), (145.6, 101.8)]                       # then the kept stub into C11.1

# /VSYS hop C12 -> C17
VSYS_OLD_F = [((134.55, 94.7), (134.55, 94.9)), ((134.55, 94.9), (135.95, 96.3))]
VSYS_OLD_VIA = (135.95, 96.3)
VSYS_OLD_B = ((135.95, 96.3), (137.6, 97.95))
VSYS_LOW_VIA = (137.6, 97.95)                               # kept, with its C17 stub
VSYS_TOP_VIA = (135.45, 94.55)                              # north of FB
VSYS_F = [(134.55, 94.55), VSYS_TOP_VIA]                    # from inside C12.1
VSYS_B = [VSYS_TOP_VIA, (135.45, 95.8), VSYS_LOW_VIA]       # down, then 45 degrees

# the old GND stitches of R8.2 and C13.2
GND_OLD = [((137.5125, 100.6), (138.2, 101.15)), ((138.2, 101.15), (138.275, 101.15)),
           ((137.775, 103.0), (138.4, 103.0)), ((138.4, 103.0), (138.475, 103.0))]
GND_OLD_VIAS = [(138.275, 101.15), (138.475, 103.0)]


def _at(p, ref):
    i, j = p.footprint_span(ref)
    m = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\n', p.text[i:j])
    return float(m[1]), float(m[2]), float(m[3] or 0)


def converted(p):
    return _at(p, 'R8') == NEW['R8']


def _same(a, b):
    return all(abs(u - v) < 1e-4 for u, v in zip(a, b))


def _seg(b, net, layer, a, c):
    if Pcb.kind(b) != 'segment' or Pcb.net(b) != net: return False
    x1, y1, x2, y2, w, l = Pcb.geom(b)
    return l == layer and ((_same((x1, y1), a) and _same((x2, y2), c)) or
                           (_same((x1, y1), c) and _same((x2, y2), a)))


def _via(b, net, at):
    return Pcb.kind(b) == 'via' and Pcb.net(b) == net and _same(Pcb.geom(b)[:2], at)


def _drop_exact(p, pred, what):
    n = p.drop(pred)
    assert n == 1, f'{what}: expected 1 item, found {n}'


def _run(p, net, layer, pts, w):
    for a, b in zip(pts, pts[1:]):
        p.add_track(net, layer, *a, *b, w)


def reg_en(p):
    """move R8/C13 beside U3.2 and re-lay REG_EN, FB and the VSYS hop;
    returns the number of old REG_EN items replaced"""
    p.sync()
    for ref, at in OLD.items():
        assert _at(p, ref) == at, f'{ref} is not where issue 5 left it: {_at(p, ref)}'
    for ref, (x, y, rot) in NEW.items():
        p.move_footprint(ref, x, y, rot)
    for ref, ((dx, dy), ang) in REFS.items():
        p.move_property(ref, 'Reference', dx, dy, ang)

    # 1  REG_EN: every old item goes; the node is laid again from U3.2 out
    n = p.drop(lambda b: Pcb.net(b) == '/REG_EN')
    _run(p, '/REG_EN', 'F.Cu', EN_ROW, SIG)
    _run(p, '/REG_EN', 'F.Cu', EN_OUT, SIG)
    for v in (EN_VIA_A, EN_VIA_B):
        p.add_via('/REG_EN', *v, *VIA)
    _run(p, '/REG_EN', 'B.Cu', EN_B, SIG)
    _run(p, '/REG_EN', 'F.Cu', EN_LEG, SIG)
    _run(p, '/REG_EN', 'F.Cu', R7_TAP, SIG)
    for (a, b) in GND_OLD:
        _drop_exact(p, lambda q, a=a, b=b: _seg(q, 'GND', 'F.Cu', a, b), f'GND {a}-{b}')
    for v in GND_OLD_VIAS:
        _drop_exact(p, lambda q, v=v: _via(q, 'GND', v), f'GND via {v}')
    for pad, v in GND_VIAS.items():
        p.add_track('GND', 'F.Cu', *pad, *v, GND_W)
        p.add_via('GND', *v, *VIA)

    # 2  FB: the same dedicated top-layer sense, turned south further west
    for a, b in FB_OLD:
        _drop_exact(p, lambda q, a=a, b=b: _seg(q, '/ESP_3V3', 'F.Cu', a, b), f'FB {a}-{b}')
    _run(p, '/ESP_3V3', 'F.Cu', FB, SIG)

    # 3  VSYS: the upper via moves north of FB
    for a, b in VSYS_OLD_F:
        _drop_exact(p, lambda q, a=a, b=b: _seg(q, '/VSYS', 'F.Cu', a, b), f'VSYS {a}-{b}')
    _drop_exact(p, lambda b: _via(b, '/VSYS', VSYS_OLD_VIA), 'VSYS upper via')
    _drop_exact(p, lambda b: _seg(b, '/VSYS', 'B.Cu', *VSYS_OLD_B), 'VSYS hop')
    assert sum(_via(b, '/VSYS', VSYS_LOW_VIA) for b in p.blocks) == 1, 'VSYS lower via moved'
    _run(p, '/VSYS', 'F.Cu', VSYS_F, VSYS_W)
    p.add_via('/VSYS', *VSYS_TOP_VIA, *VIA)
    _run(p, '/VSYS', 'B.Cu', VSYS_B, VSYS_W)
    return n


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..', 'Pixy-M2.kicad_pcb')
    p = Pcb(path)
    if converted(p):
        sys.exit(f'{path}: the enable network is already beside U3.2')
    n = reg_en(p)
    p.write()
    print(f'{path}: R8/C13 beside U3.2, {n} old REG_EN items replaced; refill zones and run DRC')
