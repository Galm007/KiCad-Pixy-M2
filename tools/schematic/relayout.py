"""Re-lay the Pixy-M2 schematic sheet without changing its connectivity.

    python3 relayout.py [in.kicad_sch] [out.kicad_sch]

Phase 1 redraws two blocks internally (coordinates are in the sheet's original
frame): the USB input, so the CC resistors no longer cross D+/D-, and the
buck, whose UVLO divider is split off onto its existing REG_EN label.
Phase 2 moves every functional block, rigidly, into its own region of the
sheet and frames it. Verify with a netlist diff: nothing electrical may move.

One-shot: phase 1 addresses items by UUID and by their old coordinates, so it
only applies to the sheet as it was before the re-layout, and refuses to run
on the re-laid file.
"""
import sys
from schlib import *
from schlib import _effects, _uuid
from clusters import clusters


def phase1(text):
    e = Editor(text)

    # --- USB: CC resistors drop to GND without crossing the data pair --------
    for u in ('248f51cc', '4f26c0b9', 'f1061b38', 'a217f9a0',                  # U2's VBUS tap
              '2d23af29', '74eaa285', '451ec4e3', '6e2df671', '51c6e753', '6e88ff7f',   # CC runs
              '6178a566', '311e4685', 'b90b827d', '5b960651', '2a96e3ae', 'fd6997b0',   # D-/D+
              'a75a4287'):                                                      # U2 GND stub
        e.delete(u)
    e.wire((73.66, 137.16), (93.98, 137.16))              # F2 -> D1, VBUS label stays on it
    e.move_to(e.sym('R1'), 76.2, 156.21)                  # CC2 (B5)
    e.move_to(e.sym('#PWR08'), 76.2, 162.56)
    e.wire((60.96, 144.78), (76.2, 144.78), (76.2, 152.4))
    e.wire((76.2, 160.02), (76.2, 162.56))
    e.move_to(e.sym('R6'), 88.9, 156.21)                  # CC1 (A5)
    e.move_to(e.sym('#PWR010'), 88.9, 162.56)
    e.wire((60.96, 142.24), (88.9, 142.24), (88.9, 152.4))
    e.wire((88.9, 160.02), (88.9, 162.56))
    # the pair steps down together, passing under both CC ground symbols
    e.move_to(e.sym('U2'), 99.06, 172.72)
    e.wire((60.96, 152.4), (68.58, 152.4), (68.58, 172.72), (93.98, 172.72))    # D- -> U2.1
    e.wire((60.96, 154.94), (66.04, 154.94), (66.04, 175.26), (93.98, 175.26))  # D+ -> U2.3
    e.wire((104.14, 172.72), (109.22, 172.72))                                  # U2.6
    e.move_label('43f38579', 109.22, 172.72)                                    # USB_D-
    e.wire((104.14, 175.26), (109.22, 175.26))                                  # U2.4
    e.move_label('69b3c7bb', 109.22, 175.26)                                    # USB_D+
    e.wire((99.06, 167.64), (99.06, 165.1))
    e.label('VBUS', 99.06, 165.1, 90, 'left bottom')                            # U2.5
    e.move_to(e.sym('#PWR09'), 99.06, 182.88)
    e.wire((99.06, 180.34), (99.06, 182.88))
    # C8's text sat on R5; put it on C8's other side
    c8 = e.sym('C8')
    e.set_field(c8, 'Reference', 20.32, 180.34, 'right')
    e.set_field(c8, 'Value', 20.32, 182.88, 'right')

    # C1's value text ran into C2
    c1 = e.sym('C1')
    x, y, _ = c1.at()
    e.set_field(c1, 'Reference', x - 2.54, y - 1.27, 'right')
    e.set_field(c1, 'Value', x - 2.54, y + 1.27, 'right')

    # --- buck / UVLO split on REG_EN ------------------------------------------
    e.delete('84ee355c')                                  # node -> under U3
    e.delete('d30b5e09')                                  # ... -> U3.2 (EN)
    e.wire((140.97, 143.51), (146.05, 143.51))
    e.move_label('1480accb', 146.05, 143.51)              # REG_EN, UVLO side
    e.wire((158.75, 118.11), (158.75, 137.16), (161.29, 137.16))
    e.label('REG_EN', 161.29, 137.16)                     # REG_EN, U3 side
    # ... which needs C12's text off that side, and C17 further out to make room
    c12 = e.sym('C12')
    e.set_field(c12, 'Reference', 153.67, 125.73, 'right')
    e.set_field(c12, 'Value', 153.67, 128.27, 'right')
    e.move_to(e.sym('C17'), 138.43, 121.92)
    e.move_to(e.sym('#PWR033'), 138.43, 128.27)
    e.delete('dad6a1f9')
    e.wire((156.21, 118.11), (138.43, 118.11))
    e.translate(e.item('f5ce9c87'), -5.08, 0)
    # C7's value was printed across C11: move C11 and the rail's end label out
    for u in ('e82eacff', '66918b30', '4c779494', 'f3ea0493', '96b8369a'):
        e.translate(e.item(u), 5.08, 0)
    for r in ('C11', '#PWR013'):
        e.translate(e.sym(r), 5.08, 0)
    e.delete('c1da4684')
    e.wire((214.63, 113.03), (231.14, 113.03))
    return e.build()


G = 1.27                                          # schematic grid


def snap(v):
    return round(v / G) * G


class Placer:
    """Moves whole wire-connected clusters and notes; remembers where they went."""

    def __init__(self, text):
        self.e = Editor(text)
        self.s = self.e.s
        self.groups = clusters(self.s)
        self.boxes = {}                           # block name -> list of boxes

    def group(self, ref):
        hits = [g for g in self.groups if any(it.kind == 'symbol' and it.ref == ref for it in g)]
        assert len(hits) == 1, ref
        return hits[0]

    def box(self, items):
        return union([b for it in items for b in extents(self.s, it)])

    def shift(self, items, dx, dy, block):
        for it in items:
            self.e.translate(it, dx, dy)
        b = self.box(items)
        self.boxes.setdefault(block, []).append((b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy))

    def put(self, block, ref, x0, y0, extra=()):
        """Move the cluster holding `ref` so its extents' top-left lands at (x0, y0)."""
        g = self.group(ref) + list(extra)
        b = self.box(g)
        dx, dy = snap(x0 - b[0]), snap(y0 - b[1])
        self.shift(g, dx, dy, block)
        return dx, dy

    def text(self, prefix):
        hits = [it for it in self.s.items if it.kind == 'text' and sval(it.tree[1]).startswith(prefix)]
        assert len(hits) == 1, prefix
        return hits[0]

    def note(self, block, prefix, x, y, wrap=None):
        """Move a note so its first line starts at (x, y); optionally re-wrap it."""
        it = self.text(prefix)
        txt = self.e.cur(it)
        if wrap:
            words = sval(it.tree[1]).split(' ')
            lines, cur = [], ''
            for w in words:
                if cur and len(cur) + 1 + len(w) > wrap:
                    lines.append(cur)
                    cur = w
                else:
                    cur = (cur + ' ' + w) if cur else w
            lines.append(cur)
            old = txt[txt.index('"'):txt.index('\n')]
            txt = txt.replace(old, '"%s"' % '\\n'.join(l.replace('"', '\\"') for l in lines), 1)
        x0, y0, a = it.at()
        txt = re.sub(r'\(at \S+ \S+ ', '(at %s %s ' % (fmt(snap(x)), fmt(snap(y))), txt, count=1)
        self.e.new_text[it.uuid] = txt
        size, just, _ = _effects(it.tree)
        lines = sval(it.tree[1]).split('\n') if not wrap else lines
        for k, line in enumerate(lines):
            self.boxes.setdefault(block, []).append(
                text_box(snap(x), snap(y) + k * size * 1.6, 0, line, size, just))

    def frame(self, block, title, x0, y0, x1, y1):
        """Dashed box round a block, titled in its top-left corner.

        A title that already exists on the sheet as a note is moved there
        rather than duplicated.
        """
        e = self.e
        e.raw('(rectangle\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(stroke\n\t\t\t(width 0)\n'
              '\t\t\t(type dash)\n\t\t)\n\t\t(fill\n\t\t\t(type none)\n\t\t)\n\t\t(uuid "%s")\n\t)'
              % (fmt(x0), fmt(y0), fmt(x1), fmt(y1), _uuid.uuid4()))
        tx, ty = x0 + G, y0 + 2 * G
        have = [it for it in self.s.items if it.kind == 'text' and sval(it.tree[1]) == title]
        if have:
            it = have[0]
            self.e.new_text[it.uuid] = re.sub(r'\(at \S+ \S+ ', '(at %s %s ' % (fmt(tx), fmt(ty)),
                                              self.e.cur(it), count=1)
        else:
            e.raw('(text "%s"\n\t\t(at %s %s 0)\n\t\t(effects\n\t\t\t(font\n'
                  '\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left)\n\t\t)\n\t\t(uuid "%s")\n\t)'
                  % (title, fmt(tx), fmt(ty), _uuid.uuid4()))
        self.frames = getattr(self, 'frames', []) + [(block, title, (x0, y0, x1, y1))]

    def put_bat(self, block, ref, x0, y0):
        """The battery switch cluster, carrying SW3's OFF/ON position tags."""
        tags = [it for it in self.s.items if it.kind == 'text' and sval(it.tree[1]) in ('OFF', 'ON')]
        assert len(tags) == 2
        return self.put(block, ref, x0, y0, extra=tags)

    def put_tof(self, block, ref, x0, y0):
        """A ToF connector, carrying the 'INT' tag printed beside its pin 5."""
        j = self.e.sym(ref)
        jx, jy, _ = j.at()
        tag = [it for it in self.s.items if it.kind == 'text' and sval(it.tree[1]) == 'INT'
               and abs(it.at()[0] - (jx - 7.62)) < 0.1 and abs(it.at()[1] - (jy + 5.08)) < 0.1]
        assert len(tag) == 1, ref
        return self.put(block, ref, x0, y0, extra=tag)


def phase2(text):
    P = Placer(text)
    for r in LAYOUT:
        getattr(P, r[0])(*r[1:])
    check(P)
    return P.e.build()


def check(P):
    """Report content that leaves its frame or strays into another block."""
    fr = {b: box for b, _, box in P.frames}
    for b, boxes in P.boxes.items():
        u = union(boxes)
        f = fr.get(b)
        if f and (u[0] < f[0] + 1 or u[1] < f[1] + 3.5 or u[2] > f[2] - 1 or u[3] > f[3] - 1):
            print('! %-8s content (%.1f,%.1f)-(%.1f,%.1f) vs frame (%.1f,%.1f)-(%.1f,%.1f)' % (b, *u, *f))
    names = list(fr)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = fr[a], fr[b]
            if A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
                print('! frames overlap:', a, b)


# Frames tile the sheet in three rows. A3's drawable area is about
# x 12-408, y 12-284 mm; the title block takes x > 298 below y 251.
R1, R2, R3 = (13.97, 135.89), (138.43, 214.63), (217.17, 284.48)
LAYOUT = [
    # ---- row 1: MCU, reset/boot, indicators, debug, battery sense, ToF -------
    ('frame', 'mcu', 'MCU — ESP32-S3-WROOM-1-N16', 13.97, R1[0], 133.35, R1[1]),
    ('put', 'mcu', 'U1', 17.78, 20.32),

    ('frame', 'reset', 'RESET / BOOT', 135.89, R1[0], 210.82, 64.77),
    ('put', 'reset', 'R2', 139.7, 19.05),
    ('put', 'reset', 'SW1', 167.64, 20.32),
    ('put', 'reset', 'SW2', 170.18, 41.91),

    ('frame', 'leds', 'INDICATORS / TEST POINTS', 135.89, 67.31, 210.82, R1[1]),
    ('put', 'leds', 'R12', 140.97, 73.66),
    ('put', 'leds', 'R13', 158.75, 75.69),
    ('put', 'leds', 'TP1', 176.53, 86.36),
    ('put', 'leds', 'TP2', 186.69, 86.36),
    ('put', 'leds', 'TP3', 199.39, 86.36),

    ('frame', 'debug', 'DEBUG / PROGRAMMING', 213.36, R1[0], 299.72, 88.9),
    ('note', 'debug', 'J11 pins', 215.9, 20.32),
    ('note', 'debug', 'auto-reset', 215.9, 22.86),
    ('note', 'debug', 'ever disables', 215.9, 25.4),
    ('note', 'debug', 'header: U1', 215.9, 27.94),
    ('put', 'debug', 'J11', 220.98, 31.75),
    ('put', 'debug', 'TP5', 222.25, 66.04),
    ('put', 'debug', 'TP6', 232.41, 66.04),
    ('put', 'debug', 'TP7', 242.57, 66.04),
    ('put', 'debug', 'TP8', 252.73, 66.04),
    ('put', 'debug', 'TP9', 264.16, 66.04),
    ('note', 'debug', 'TP5-TP8', 215.9, 78.74),
    ('note', 'debug', 'GPIO35/36/37', 215.9, 81.28, 60),

    ('frame', 'sense', 'BATTERY SENSE', 213.36, 91.44, 299.72, R1[1]),
    ('put', 'sense', 'R10', 219.71, 96.52),

    ('frame', 'tof', 'TOF WALL SENSORS — 4× VL53L0X', 302.26, R1[0], 406.4, R1[1]),
    ('note', 'tof', 'VL53L0X', 304.8, 20.32),
    ('note', 'tof', '1 VCC', 304.8, 22.86),
    ('note', 'tof', 'The module pulls', 304.8, 25.4),
    ('note', 'tof', 'Firmware must pull', 304.8, 27.94),
    ('note', 'tof', 'Drive GPIO4-7', 304.8, 30.48),
    ('note', 'tof', 'Module VIN', 304.8, 33.02),
    ('put_tof', 'tof', 'J4', 304.8, 38.1),
    ('put_tof', 'tof', 'J5', 335.28, 38.1),
    ('put_tof', 'tof', 'J6', 304.8, 71.12),
    ('put_tof', 'tof', 'J7', 335.28, 71.12),
    ('put', 'tof', 'R15', 370.84, 39.37),
    ('put', 'tof', 'R16', 370.84, 49.53),
    ('put', 'tof', 'C15', 372.11, 63.5),
    ('put', 'tof', 'C16', 387.35, 63.5),
    ('note', 'tof', 'R15/R16', 304.8, 106.68),
    ('note', 'tof', 'C15/C16', 304.8, 109.22),

    # ---- row 2: the power path, left to right ---------------------------------
    ('frame', 'usb', 'USB-C INPUT', 13.97, R2[0], 123.19, R2[1]),
    ('put', 'usb', 'J1', 16.51, 143.51),

    ('frame', 'battery', 'BATTERY INPUT / POWER SWITCH', 125.73, R2[0], 210.82, R2[1]),
    ('note', 'battery', 'F1:', 128.27, 143.51),
    ('note', 'battery', 'SW3 switches', 128.27, 146.05),
    ('put_bat', 'battery', 'BT1', 129.54, 148.59),
    ('put', 'battery', 'D6', 129.54, 189.23),
    ('note', 'battery', 'D6:', 146.05, 194.31),
    ('put', 'battery', '#FLG04', 147.32, 200.66),
    ('note', 'battery', 'VBAT is fed', 162.56, 203.2, 42),

    ('frame', 'buck', '3V3 BUCK — AP63203', 213.36, R2[0], 339.09, R2[1]),
    ('put', 'buck', 'U3', 217.17, 146.05),

    ('frame', 'uvlo', 'UVLO — REGULATOR ENABLE', 341.63, R2[0], 406.4, R2[1]),
    ('put', 'uvlo', 'R7', 347.98, 146.05),

    # ---- row 3: motor drive and IMU -------------------------------------------
    ('frame', 'motor_a', 'MOTOR A', 13.97, R3[0], 107.95, R3[1]),
    ('note', 'motor_a', "DRV8231A VM abs max 35V clears D6's 15.4V clamp. R17", 16.51, 222.25, 64),
    ('put', 'motor_a', 'C18', 16.51, 226.06),
    ('put', 'motor_a', 'C19', 33.02, 226.06),
    ('put', 'motor_a', 'R17', 50.8, 226.06),
    ('put', 'motor_a', 'R19', 69.85, 226.06),
    ('put', 'motor_a', 'R20', 83.82, 226.06),
    ('put', 'motor_a', 'U4', 16.51, 245.11),
    ('put', 'motor_a', 'J8', 63.5, 247.65),

    ('frame', 'motor_b', 'MOTOR B', 110.49, R3[0], 204.47, R3[1]),
    ('note', 'motor_b', "DRV8231A VM abs max 35V clears D6's 15.4V clamp. R18", 113.03, 222.25, 64),
    ('put', 'motor_b', 'C20', 113.03, 226.06),
    ('put', 'motor_b', 'C21', 129.54, 226.06),
    ('put', 'motor_b', 'R18', 147.32, 226.06),
    ('put', 'motor_b', 'R21', 166.37, 226.06),
    ('put', 'motor_b', 'R22', 180.34, 226.06),
    ('put', 'motor_b', 'U5', 113.03, 245.11),
    ('put', 'motor_b', 'J9', 160.02, 247.65),

    ('frame', 'imu', 'IMU — BNO08x module (external, SPI)', 207.01, R3[0], 296.93, R3[1]),
    ('note', 'imu', 'SPI:', 209.55, 222.25, 70),
    ('note', 'imu', 'Jumper PS1', 209.55, 227.33, 70),
    ('put', 'imu', 'C22', 209.55, 240.03),
    ('put', 'imu', 'R23', 228.6, 240.03),
    ('put', 'imu', 'J10', 246.38, 236.22),
]


if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else '../../Pixy-M2.kicad_sch'
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    text = open(src).read()
    if '(rectangle' in text.split('(sheet_instances')[0].split('\n\t(symbol', 1)[-1] \
            and 'USB-C INPUT' in text:
        sys.exit('%s is already re-laid out; this script only runs on the old sheet '
                 '(git show a0b645a:Pixy-M2.kicad_sch)' % src)
    text = phase1(text)
    if 'phase2' in globals():
        text = phase2(text)
    open(dst, 'w').write(text)
