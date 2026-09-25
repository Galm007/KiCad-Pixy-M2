#!/usr/bin/env python3
"""The IPROPI current-sense runs, clear of motor and drive copper (2026-09-24).

GPIO2 (U4.1 -> R17 -> U1.38) and GPIO10 (U5.1 -> R18 -> U1.18) carry each
driver's IPROPI output: 1500 uA/A into 2.2 kOhm, read by the ADC.  The layout
rule was to keep them short and away from the motor outputs.  Two placement
choices had defeated it:

  R17  sat east of U4's IN1/IN2 escapes (GPIO39/40), so GPIO2 hopped over
       them on B.Cu, over the In2 VBAT island, and GPIO39 threaded between
       R17's own pads.  Further down, GPIO2 ran 0.70 mm from the MOT_A_1
       trunk beside J8 and 0.23 mm from SW3's gate pad.
  R18  sat west of U5's IN1/IN2 pair (GPIO41 on F.Cu, GPIO42 on B.Cu,
       stacked at x ~ 116 for 15 mm).  GPIO10 reached it down the channel
       beside U4's MOT_A_2 loop, 0.53 mm away.  It then crossed the pair
       under U5 and ran 8 mm beside GPIO42 on B.Cu, 0.25 mm away, over the
       VBAT island.

For motor A the three nets leave U4 west in the order they reach U1's west
column (IPROPI outermost), so GPIO2 never has to cross the drive lines.
R17 moves to their west side (rot 90, IPROPI pad south).  GPIO2 runs down
between C19 and the escapes, through R17 and on down x = 105 to its old run,
1.7 mm from MOT_A_1 and centred between SW3's pads.

For motor B, GPIO10 has to cross the pair, because it lands on U1's bottom
row, east of where GPIO41/42 land.  It still crosses under U5's own pins,
where the pair starts and the proximity is the pin pitch's.  But it now
leaves eastward at once, not down beside GPIO42.  It comes up to R18, which
moves east of the pair (rot 180, GND pad toward the pair).  From there it
drops on F.Cu to rejoin its old B.Cu diagonal to U1 just past the island.
The channel beside MOT_A_2 is left empty.

Runs after reg_en.py in rework.py.  Standalone, it converts an existing board
once:

    /usr/bin/python3 tools/autoroute/ipropi.py [board.kicad_pcb]
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcbedit import Pcb

SIG, GND_W = 0.2, 0.4
VIA = (0.6, 0.3)

OLD = {'R17': (109.0, 118.0, 0), 'R18': (116.0, 118.0, 0)}
NEW = {'R17': (104.5, 120.3, 90),     # pad 1 (GPIO2) south at y 121.21, GND north
       'R18': (118.5, 118.6, 180)}    # pad 1 (GPIO10) east at x 119.41, GND west
# reference fields: local offset in the footprint frame, board-frame angle
REFS = {'R17': ((0.0, -2.4), 0),     # west of R17
        'R18': ((0.0, -1.75), 0),    # below R18
        'C19': ((0.0, -2.8), 0)}     # west of C19; it sat where R17 now is

U4_FIELD = (107.0, 112.0, 112.9, 116.0)       # rework.ESCAPE_AREAS
U5_FIELD = (115.0, 112.0, 120.9, 116.0)

# /GPIO2: everything above the old long run's start, except the pin escape,
# is replaced.  The run from (106.05, 135.7) to U1.38 is kept.
GPIO2_KEEP_FROM = 135.7
GPIO2_IN = [(107.1, 113.45), (106.4, 114.15), (106.4, 118.3),    # between C19 and the escapes,
            (105.6, 119.1), (105.6, 120.8), (105.1, 121.3)]       # then R17's east side -> R17.1
GPIO2_OUT = [(105.0, 121.3), (105.0, 132.2), (105.75, 132.95), (105.75, 135.4),
             (106.05, 135.7)]                                                   # R17.1 -> old run
R17_GND = [(104.5, 119.4), (103.375, 119.4)]      # between GPIO6 and VBAT on B.Cu

# /GPIO10: the pin escape, its via and the B.Cu crossing under U5's pins are
# kept up to (116.45, 114.3); the descent beside MOT_A_2 and the B.Cu run
# beside GPIO42 are replaced.
GPIO10_OLD_B = [((116.45, 114.3), (116.45, 120.35)), ((116.45, 120.35), (135.25, 139.15))]
GPIO10_B = [(116.45, 114.3), (116.45, 114.9), (117.4, 115.85), (117.4, 116.3),
            (118.45, 117.35), (119.4, 117.35)]            # east, clear of the pair
GPIO10_UP = (119.4, 117.35)
GPIO10_F = [(119.4, 117.35), (119.4, 118.6), (119.4, 123.3)]   # through R18.1
GPIO10_DOWN = (119.4, 123.3)                              # on the old diagonal, past the island
GPIO10_DIAG = [(119.4, 123.3), (135.25, 139.15)]
R18_GND = [(117.5875, 118.6), (117.6, 119.95)]

# old GND stubs of R17.2 / R18.2.  R17's via stays: J8's west MP tie ends on it.
GND_OLD = [((109.9125, 118.0), (111.05, 118.0)), ((116.9125, 118.0), (118.05, 118.0))]
GND_OLD_VIAS = [(118.05, 118.0)]


def _at(p, ref):
    i, j = p.footprint_span(ref)
    m = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\n', p.text[i:j])
    return float(m[1]), float(m[2]), float(m[3] or 0)


def converted(p):
    return _at(p, 'R17') == NEW['R17']


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


def _inside(box, x, y):
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _escape(b, field):
    """a 0.15 mm pin escape inside a driver's pin field: kept"""
    x1, y1, x2, y2, w, l = Pcb.geom(b)
    return l == 'F.Cu' and w < 0.2 and _inside(field, x1, y1) and _inside(field, x2, y2)


def ipropi(p):
    """move R17/R18 and re-lay the near-driver parts of GPIO2/GPIO10;
    returns the number of old items replaced"""
    p.sync()
    for ref, at in OLD.items():
        assert _at(p, ref) == at, f'{ref} is not where it was placed: {_at(p, ref)}'
    for ref, (x, y, rot) in NEW.items():
        p.move_footprint(ref, x, y, rot)
    for ref, ((dx, dy), ang) in REFS.items():
        p.move_property(ref, 'Reference', dx, dy, ang)

    # GPIO2: keep the pin escape and the long run from y 135.7 on
    def old2(b):
        if Pcb.net(b) != '/GPIO2': return False
        if Pcb.kind(b) == 'via':
            return Pcb.geom(b)[1] < GPIO2_KEEP_FROM
        x1, y1, x2, y2, w, l = Pcb.geom(b)
        return max(y1, y2) <= GPIO2_KEEP_FROM + 1e-6 and not _escape(b, U4_FIELD)
    n = p.drop(old2)
    assert n > 20, f'GPIO2: only {n} items to replace'
    _run(p, '/GPIO2', 'F.Cu', GPIO2_IN, SIG)
    _run(p, '/GPIO2', 'F.Cu', GPIO2_OUT, SIG)

    # GPIO10: drop the descent to the old R18 (F.Cu west of the escape end)
    # and the B.Cu run beside GPIO42
    def old10(b):
        if Pcb.net(b) != '/GPIO10' or Pcb.kind(b) != 'segment': return False
        x1, y1, x2, y2, w, l = Pcb.geom(b)
        return l == 'F.Cu' and max(x1, x2) <= 115.1 + 1e-6 and max(y1, y2) > 113.06
    k = p.drop(old10)
    assert k > 8, f'GPIO10: only {k} descent segments'
    n += k
    for a, c in GPIO10_OLD_B:
        _drop_exact(p, lambda b, a=a, c=c: _seg(b, '/GPIO10', 'B.Cu', a, c), f'GPIO10 {a}-{c}')
        n += 1
    _run(p, '/GPIO10', 'B.Cu', GPIO10_B, SIG)
    p.add_via('/GPIO10', *GPIO10_UP, *VIA)
    _run(p, '/GPIO10', 'F.Cu', GPIO10_F, SIG)
    p.add_via('/GPIO10', *GPIO10_DOWN, *VIA)
    _run(p, '/GPIO10', 'B.Cu', GPIO10_DIAG, SIG)

    # GND: the resistors' old stubs go, each gets a new one
    for a, c in GND_OLD:
        _drop_exact(p, lambda b, a=a, c=c: _seg(b, 'GND', 'F.Cu', a, c), f'GND {a}-{c}')
    for v in GND_OLD_VIAS:
        _drop_exact(p, lambda b, v=v: _via(b, 'GND', v), f'GND via {v}')
    for stub in (R17_GND, R18_GND):
        _run(p, 'GND', 'F.Cu', stub, GND_W)
        p.add_via('GND', *stub[-1], *VIA)
    return n


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..', 'Pixy-M2.kicad_pcb')
    p = Pcb(path)
    if converted(p):
        sys.exit(f'{path}: the IPROPI runs are already re-laid')
    n = ipropi(p)
    p.write()
    print(f'{path}: R17/R18 moved, {n} old IPROPI items replaced; refill zones and run DRC')
