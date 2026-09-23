#!/usr/bin/env python3
"""Silkscreen assembly marks for the off-board parts (2026-09-23).

Prints where the four ToF sensors, the IMU and the two N20 motors go.  The
reservations in `layout/README.md` already exist, but only on Dwgs.User and
User.1/2, which are not fabricated.  These marks go on F.SilkS and B.SilkS:

  top     four ToF mount outlines, 13 x 18 mm (the 14 x 19 mm reservations
          inset 0.5 mm so the corner ones clear the R3 board corners), each
          with its aim arrow (FL/FR forward, LOOK L/R 45 deg outward) and the
          connector its cable plugs into;
          the Adafruit BNO085 (#4754) outline, 25.4 x 22.86 mm, its four
          2.5 mm mounting holes, and its chip centred on the rotation centre
          (133, 126).  Module +Y points forward and +X to the right, so the
          chip's frame matches the robot's; this puts the BT/P0/P1/RST/DI/CS
          header at the front, nearest J10.  Geometry is from Adafruit's
          Adafruit_BNO08x.brd.  The module is 0.2 mm wider than the 25 mm
          reservation on each side; it stands on its own holes, above the
          board, so nothing collides;
  bottom  both Pololu Micro Metal Gearmotors (HP 6V, 12 CPR encoder), 12 mm
          wide, split gearbox 9 / motor 15 / encoder 8 mm per Pololu's
          dimension drawing (0J949), gearbox face on the board edge and shaft
          on the wheel axle (y = 110 left, 142 right).  The 4 mm side-connector
          allowance of each 16 mm reservation is left for the text.

Runs after f1_fuse.py in rework.py.  Standalone, it adds the marks to an
existing board once:

    /usr/bin/python3 tools/autoroute/assembly_marks.py [board.kicad_pcb]
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcbedit import Pcb, fx, uid

W = 0.15            # silk stroke; also the text thickness
MARKER = 'ToF FL'   # present once the marks are on a board

# name, envelope x0..x1, aim (dx, dy) in the board frame, connector
TOF = [('LOOK L', 101, 115, (-1, -1), 'J6'),
       ('FL', 117, 131, (0, -1), 'J4'),
       ('FR', 135, 149, (0, -1), 'J5'),
       ('LOOK R', 151, 165, (1, -1), 'J7')]
TOF_Y = (61.5, 79.5)

IMU_C = (133.0, 126.0)                # chip centre = rotation centre
BNO_W, BNO_H = 25.4, 22.86            # Adafruit_BNO08x.brd outline
BNO_CHIP = (12.7, 12.2555)            # U1 in board coordinates (y up)
BNO_HOLES = [(2.54, 2.54), (22.86, 2.54), (2.54, 20.32), (22.86, 20.32)]

# motor, side, gearbox face x, direction of the body from it, axle y, text y
MOTORS = [('MOTOR A', 'LEFT', 'J8', 100.0, 1, 110.0, 118.0),
          ('MOTOR B', 'RIGHT', 'J9', 166.0, -1, 142.0, 134.0)]
GEARBOX, MOTOR, ENCODER, WIDTH = 9.0, 15.0, 8.0, 12.0
EDGE_INSET = 0.5

# reference fields the IMU outline would touch, in each footprint's own frame
# (both parts are rot 90): C20's moves 0.6 mm west, R15's 0.45 mm south
REF_NUDGE = {'C20': (-2.15, -0.6), 'R15': (1.55, -2.65)}


class Marks:
    def __init__(self):
        self.items, self.groups = [], []

    def _add(self, s):
        u = uid()
        self.items.append(s.replace('@UUID@', u))
        self.members.append(u)

    def group(self, name):
        self.members = []
        self.groups.append((name, self.members))

    def line(self, layer, x1, y1, x2, y2):
        self._add(f'\t(gr_line\n\t\t(start {fx(x1)} {fx(y1)})\n\t\t(end {fx(x2)} {fx(y2)})\n'
                  f'\t\t(stroke\n\t\t\t(width {W})\n\t\t\t(type solid)\n\t\t)\n'
                  f'\t\t(layer "{layer}")\n\t\t(uuid "@UUID@")\n\t)\n')

    def rect(self, layer, x0, y0, x1, y1):
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                     ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            self.line(layer, *a, *b)

    def circle(self, layer, x, y, r):
        self._add(f'\t(gr_circle\n\t\t(center {fx(x)} {fx(y)})\n\t\t(end {fx(x + r)} {fx(y)})\n'
                  f'\t\t(stroke\n\t\t\t(width {W})\n\t\t\t(type solid)\n\t\t)\n'
                  f'\t\t(fill no)\n\t\t(layer "{layer}")\n\t\t(uuid "@UUID@")\n\t)\n')

    def arrow(self, layer, x1, y1, x2, y2, head=1.0):
        self.line(layer, x1, y1, x2, y2)
        a = math.atan2(y1 - y2, x1 - x2)
        for s in (-1, 1):
            b = a + s * math.radians(30)
            self.line(layer, x2, y2, x2 + head * math.cos(b), y2 + head * math.sin(b))

    def text(self, layer, s, x, y):
        mirror = '\t\t\t(justify mirror)\n' if layer.startswith('B.') else ''
        self._add(f'\t(gr_text "{s}"\n\t\t(at {fx(x)} {fx(y)} 0)\n\t\t(layer "{layer}")\n'
                  f'\t\t(uuid "@UUID@")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n'
                  f'\t\t\t\t(thickness {W})\n\t\t\t)\n{mirror}\t\t)\n\t)\n')

    def sexpr(self):
        out = ''.join(self.items)
        for name, members in self.groups:
            out += (f'\t(group "{name}"\n\t\t(uuid "{uid()}")\n\t\t(members\n'
                    + ''.join(f'\t\t\t"{m}"\n' for m in members) + '\t\t)\n\t)\n')
        return out


def tof(m):
    L = 'F.SilkS'
    m.group('ToF sensor mounts')
    y0, y1 = TOF_Y
    for name, x0, x1, (dx, dy), conn in TOF:
        cx = (x0 + x1) / 2
        m.rect(L, x0 + EDGE_INSET, y0, x1 - EDGE_INSET, y1)
        n = math.hypot(dx, dy)
        tail = (cx - 1.5 * dx / n, 70.0 - 1.5 * dy / n) if dx else (cx, 70.0)
        k = 6.0 if not dx else 5.5
        m.arrow(L, *tail, tail[0] + k * dx / n, tail[1] + k * dy / n)
        m.text(L, f'ToF {name}', cx, 74.0)
        m.text(L, f'cable {conn}', cx, 76.5)


def imu(m):
    L = 'F.SilkS'
    m.group('IMU module')
    cx, cy = IMU_C

    def at(ex, ey):     # Adafruit board frame (y up) -> ours, +Y forward
        return cx + ex - BNO_CHIP[0], cy - (ey - BNO_CHIP[1])
    x0, y1 = at(0, 0)
    x1, y0 = at(BNO_W, BNO_H)
    m.rect(L, x0, y0, x1, y1)
    for h in BNO_HOLES:
        m.circle(L, *at(*h), 1.25)
    m.circle(L, cx, cy, 0.6)                        # Z, out of the board
    m.arrow(L, cx, cy - 0.9, cx, cy - 5.5)          # +Y forward
    m.arrow(L, cx + 0.9, cy, cx + 5.5, cy)          # +X right
    m.text(L, 'Y FWD', cx, cy - 7.0)
    m.text(L, 'X', cx + 6.7, cy)
    m.text(L, 'IMU BNO085', cx, cy + 4.5)
    m.text(L, 'chip over O', cx, cy + 6.5)
    m.text(L, 'cable J10', cx, cy + 8.5)


def motors(m):
    L = 'B.SilkS'
    for name, side, conn, face, d, axle, ty in MOTORS:
        m.group(f'{name} {side.lower()}')
        f = face + d * EDGE_INSET              # silk stays off the board edge
        g, mo, e = (face + d * GEARBOX, face + d * (GEARBOX + MOTOR),
                    face + d * (GEARBOX + MOTOR + ENCODER))
        top, bot = axle - WIDTH / 2, axle + WIDTH / 2
        m.line(L, f, top, e, top)
        m.line(L, f, bot, e, bot)
        m.line(L, e, top, e, bot)
        m.line(L, g, top, g, bot)
        m.line(L, mo, top, mo, bot)
        m.arrow(L, (face + g) / 2 + d * 1.5, axle + 2.5, f + d * 0.3, axle + 2.5, head=0.8)
        m.text(L, 'GEAR', (face + g) / 2, axle - 2.5)
        m.text(L, 'WHEEL', (face + g) / 2, axle)
        m.text(L, name, (g + mo) / 2, axle - 1.5)
        m.text(L, f'{side} {conn}', (g + mo) / 2, axle + 1.5)
        m.text(L, 'ENC', (mo + e) / 2, axle)
        m.text(L, 'Pololu HP 6V N20', (face + e) / 2, ty)


def assembly_marks(p):
    """append every mark to the board held by a pcbedit.Pcb"""
    p.sync()                    # a field move re-splits the text
    for ref, (dx, dy) in REF_NUDGE.items():
        p.move_property(ref, 'Reference', dx, dy)
    m = Marks()
    tof(m)
    imu(m)
    motors(m)
    p.add_zone(m.sexpr())
    return len(m.items)


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..', 'Pixy-M2.kicad_pcb')
    p = Pcb(path)
    if f'(gr_text "{MARKER}"' in p.text:
        sys.exit(f'{path}: assembly marks already present')
    n = assembly_marks(p)
    p.write()
    print(f'added {n} silkscreen items to {path}')
