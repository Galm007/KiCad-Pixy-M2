"""USB D+/D- as a coupled pair, connector to module — REVIEW.md issue 7.

Runs as the last routing stage of rework.py, after the issue-6 via repairs, so
nothing before it changes.  It rips the four USB nets and the two CC nets, turns
U2 so its flow-through direction matches the signal direction, and lays the
pair by hand; CC1/CC2 are then searched around it.

Geometry (field-solved for this board's stackup; CLAUDE.md "Issue 7 — the USB pair"):
  WIDTH 0.25 mm, GAP 0.15 mm on F.Cu over the In1 ground plane -> ~90 ohm diff.

Why U2 turns.  USBLC6-2SC6 carries each line in on one side of the package and
out of the other (1->6 for D-, 3->4 for D+).  At rot 0 that flow ran west->east
while the signal runs south (J1) -> north-west (U1), so D+ had to come out of
the east side and wrap round the package.  At rot 90 the connector-side pins
(1, 2, 3) face J1 and the module-side pins (6, 5, 4) face U1, with D- on the
west in both rows: the pair goes straight through the part and never crosses.

The two middle pins sit between the lines, so they leave *under the body*,
through the 1 mm gap between the pin rows: GND (2) straight down a plane via
there; VBUS (5) sideways to the east, to the existing feed from F2.  Neither
crosses the pair.

At J1 the USB-C pads alternate D-, D+, D-, D+ (B7 A6 A7 B6).  D+ joins A6 to
B6 with a bridge over the top of A7; D- joins A7 to B7 with a loop under the
bottom of A6.  Both joins are on F.Cu, so the whole path, connector to module,
has no via and never leaves the layer referenced to the In1 ground plane.
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcbedit import Pcb
from board import seg_disc_stamp

WIDTH, GAP = 0.25, 0.15
PITCH = WIDTH + GAP
STUB = WIDTH         # the J1 bridge and loop: 0.225 mm clear of the pads either side
U2_AT = (153.5, 149.5, 90)

DP, DN = '/USB_D+', '/USB_D-'
CP, CN = 'Net-(J1-D+-PadA6)', 'Net-(J1-D--PadA7)'
USB_NETS = [DP, DN, CP, CN]
CC_NETS = [('Net-(J1-CC1)', ('J1', 'A5'), ('R6', '1')),
           ('Net-(J1-CC2)', ('J1', 'B5'), ('R1', '1'))]
# old U2 pin-2 ground stub and its via; old U2 pin-5 VBUS fan-in
RIP_BOXES = [('GND', 151.5, 147.6, 153.3, 148.4),
             ('/VBUS', 153.5, 147.8, 156.7, 149.7)]
VBUS_FEED = (156.65, 148.05)       # end of the 0.36 mm run down from F2
# U2's clamp return: a plane via under the package, between the pin rows, off
# the pin-2 side.  0.22 mm copper clearance to pins 1, 5 and 6; the drill clears
# every pad opening by >= 0.37 mm.  About 0.7 mm from pin 2 to the In1 plane.
GND_VIA = (153.0, 149.5)
# reference text off the new pads and the pair: (x, y, angle) in the footprint
# frame, angle in the board frame.  U2 reads upright beside its module-side pins;
# J1's moves off U2's connector-side pins, which now sit where it was.
SILK_REFS = {'U2': (2.3, 2.1, 0), 'J1': (6.5, -6.2, None)}


def offset(poly, d):
    """offset a polyline by d to the LEFT of travel (board frame, y down), mitred"""
    def left(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy)
        return (dy / n, -dx / n)          # left of travel when y points down
    out = []
    for i, p in enumerate(poly):
        if i == 0:
            nx, ny = left(poly[0], poly[1])
        elif i == len(poly) - 1:
            nx, ny = left(poly[-2], poly[-1])
        else:
            n1, n2 = left(poly[i - 1], p), left(p, poly[i + 1])
            mx, my = n1[0] + n2[0], n1[1] + n2[1]
            k = 1.0 / (1.0 + n1[0] * n2[0] + n1[1] * n2[1])
            nx, ny = mx * k, my * k
        out.append((round(p[0] + nx * d, 4), round(p[1] + ny * d, 4)))
    return out


def geometry():
    """every USB track as (net, width, [points]).  Coordinates are absolute mm."""
    x0, y0, _ = U2_AT
    pin_dx, pin_dy = 0.95, 1.1375          # SOT-23-6 at rot 90
    top, bot = y0 - pin_dy, y0 + pin_dy     # module-side / connector-side pin rows
    h = PITCH / 2
    tracks = []

    # --- module side: centreline north out of U2, 45 deg, west to U1
    yc = 143.0                   # between R15/R16 above and the GPIO8 run below
    yb = 145.0
    xw = 143.6                   # where the pair splits for U1's 1.27 mm pitch
    centre = [(x0, top - 1.45), (x0, yb), (x0 - (yb - yc), yc), (xw, yc)]
    ln, lp = offset(centre, h), offset(centre, -h)   # heading north: left = west = D-
    # fan-in from the pins (1.9 mm apart) to the pair pitch, 45 degrees
    tracks.append((DN, WIDTH, [(x0 - pin_dx, top - 0.3), (x0 - pin_dx, top - 0.6),
                               ln[0]] + ln[1:]))
    tracks.append((DP, WIDTH, [(x0 + pin_dx, top - 0.3), (x0 + pin_dx, top - 0.6),
                               lp[0]] + lp[1:]))
    # U1: D- runs straight into pin 13; D+ climbs 45 deg to pin 14
    tracks[-2][2].append((142.3, ln[-1][1]))
    ydp = lp[-1][1]
    tracks[-1][2].extend([(xw - 0.25, ydp), (xw - 0.25 - (ydp - 141.85), 141.85)])

    # --- connector side: fan-in from the pins to J1's 0.5 mm pad pitch
    xn, xp = 153.25, 153.75                  # B7 (D-) and A6 (D+)
    yj = 152.1                              # pair reaches pad pitch here
    tracks.append((CN, WIDTH, [(x0 - pin_dx, bot + 0.3), (x0 - pin_dx, yj - (xn - x0 + pin_dx)),
                               (xn, yj), (xn, 153.0)]))
    tracks.append((CP, WIDTH, [(x0 + pin_dx, bot + 0.3), (x0 + pin_dx, yj - (x0 + pin_dx - xp)),
                               (xp, yj), (xp, 153.0)]))
    # D+ bridge A6 -> B6 over the top of A7; D- loop A7 -> B7 under the bottom of A6
    tracks.append((CP, STUB, [(xp, 152.45), (154.75, 152.45), (154.75, 153.0)]))
    tracks.append((CN, STUB, [(154.25, 154.1), (154.25, 154.6), (153.25, 154.6),
                              (153.25, 154.1)]))

    # --- the two middle pins, out under the body between the pin rows
    tracks.append(('GND', 0.3, [(x0 - 0.1, bot - 0.55), GND_VIA]))
    tracks.append(('/VBUS', 0.3, [(x0 + 0.1, top + 0.45), (x0 + 0.45, y0 - 0.05),
                                  (155.4, y0 - 0.05)]))
    tracks.append(('/VBUS', 0.36, [(155.4, y0 - 0.05), VBUS_FEED]))
    return tracks, [('GND', *GND_VIA)]


def rip(p):
    n = p.drop(lambda b: Pcb.net(b) in USB_NETS + [c[0] for c in CC_NETS])
    for net, x0, y0, x1, y1 in RIP_BOXES:
        def hit(b, net=net, x0=x0, y0=y0, x1=x1, y1=y1):
            if Pcb.net(b) != net: return False
            g = Pcb.geom(b)
            pts = [(g[0], g[1]), (g[2], g[3])] if Pcb.kind(b) == 'segment' else [(g[0], g[1])]
            return all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in pts)
        n += p.drop(hit)
    return n


def usb_pair(p, Router):
    """rip, turn U2, lay the pair, then search CC1/CC2 round it"""
    p.sync()
    p.move_footprint('U2', *U2_AT)
    for ref, at in SILK_REFS.items():          # text edits before any track edit
        p.move_property(ref, 'Reference', *at)
    print('  U2 ->', U2_AT, '| ripped', rip(p), 'USB/CC segments and vias')
    tracks, vias = geometry()
    for net, w, pts in tracks:
        for a, b in zip(pts, pts[1:]):
            p.add_track(net, 'F.Cu', *a, *b, w)
    for net, x, y in vias:
        p.add_via(net, x, y)
    # CC lines have to cross the pair on B.Cu.  Keep their F.Cu copper and
    # their vias a further 0.15 mm off it, except where the pair drops into
    # J1's 0.5 mm pad field, which leaves no room for anything extra.
    r = Router(p)
    for net, w, pts in tracks:
        if net not in USB_NETS or w != WIDTH: continue
        nid = r.g.netid[net]
        for a, b in zip(pts, pts[1:]):
            if min(a[1], b[1]) > 151.9: continue
            seg_disc_stamp(r.g.cu['F.Cu'], *a, *b, w / 2 + 0.15, nid)
    for net, a, b in CC_NETS:
        ok = r.route(net, 0.2, [r.pad_group(*a, 0.2), r.pad_group(*b, 0.2)])
        print(f'  {net} ->', 'ok' if ok else 'FAILED')
