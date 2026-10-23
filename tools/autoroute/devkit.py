#!/usr/bin/env python3
"""U1 -> ESP32-S3-DevKitC-1-N8R8 on two SMD female headers (branch devkit-daughterboard).

Runs after ipropi.py.  The schematic (tools/schematic/devkit.py) swapped the
WROOM-1 module for a plug-in DevKitC-1 and deleted what the devkit carries
itself; this stage makes the board match, inside the same 66 x 100 mm outline.

  1  deletes the 21 footprints the schematic dropped (USB-C input, reset/boot,
     J11, TP5-TP8, D1/D3/R9) and every copper item of the nets that went with
     them;
  2  puts U1 on `Pixy-M2:ESP32-S3-DevKitC-1_SMD_Sockets` along the right edge,
     antenna over the rear edge as before: socket rows at board x 39.84 and
     62.7, pin 1 at y 97.98.  The right row's pad 1 clears the R3 corner by
     0.27 mm.  The devkit, 25.4 x 62.7 mm, fits nowhere else: the left corner
     is the motor and power region, and the middle is too narrow beside the IMU;
  3  moves the IMU 8.6 mm left of the rotation centre (the only 25 mm column
     left beside the devkit), J10 and C22 behind it, facing it, J8 and SW3
     clear of it, J9 to the front of the right edge so the motor B trunks keep
     their old corridor, the LEDs to the rear-left corner where they stay
     visible past the devkit, and the battery-sense parts hard against GPIO1;
  4  rips every signal that ran to the old module and every net of a moved
     part, keeping the hand-placed copper inside the motor corner (driver pin
     escapes, the IPROPI runs, VREF), the buck block, FB and REG_EN;
  5  routes the motor trunks of both connectors (paired, as pololu_conn.py),
     then every signal at 0.2 mm, then the plane stitches, then one GND via
     in each piece of the B.Cu pour that has none;
  6  moves the IMU reservation, the antenna exclusion and the IMU silkscreen
     marks.

Standalone, it converts an existing board once:

    python3 devkit.py [in.kicad_pcb [out.kicad_pcb]]
"""
import math
import os
import re
import sys
import uuid

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from board import ROUTE, NX, NY, H, disc_mask, gx, gy, wx, wy          # noqa: E402
from pcbedit import Pcb, fx                                           # noqa: E402
from grid import VIA_D, VIA_DRILL, CL                                 # noqa: E402
import pololu_conn                                                    # noqa: E402
from pololu_conn import (dangling, components, _group, _pad, _in_pad, rip_conflicts,   # noqa: E402
                         plane_vias, orphan_3v3, PLANE_NETS)
from issue8 import _drill_clear_of_pads                               # noqa: E402
import assembly_marks                                                 # noqa: E402

LIB = os.path.join(HERE, '..', '..', 'Pixy-M2.pretty', 'ESP32-S3-DevKitC-1_SMD_Sockets.kicad_mod')
FPID = 'Pixy-M2:ESP32-S3-DevKitC-1_SMD_Sockets'
OX, OY = 100.0, 60.0                     # KiCad = board + (100, 60)


def K(x, y, *rot):
    return (round(x + OX, 4), round(y + OY, 4)) + rot


SIGNAL, PLANE_TAP = 0.2, 0.3
# Pixy-M2.kicad_dru's clearance floors above the router's 0.26 mm, seen by A*
# as extra distance: IPROPI from motor copper, the two sense nodes from motor
# and switch-node copper
_SW = {'Net-(U3-SW)', 'Net-(U3-BST)'}
WIDE_RULES = [({'/GPIO2', '/GPIO10'}, {'/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2'}, 0.75),
              ({'/REG_EN'}, {'/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2'}, 5.0),
              ({'/VBAT_SENSE'}, {'/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2'} | _SW, 5.0)]
SIG_VIA_SEP = 1.35                       # CLAUDE.md: non-plane via antipads must not merge

REMOVE = ['J1', 'U2', 'F2', 'R1', 'R5', 'R6', 'C8', 'D1', 'D3', 'R9',
          'R2', 'C3', 'C4', 'C5', 'SW1', 'SW2', 'J11', 'TP5', 'TP6', 'TP7', 'TP8']
GONE_NETS = {'/USB_D+', '/USB_D-', 'Net-(J1-D+-PadA6)', 'Net-(J1-D--PadA7)', '/VBUS',
             'Net-(F2-Pad1)', 'Net-(J1-CC1)', 'Net-(J1-CC2)', 'Net-(J1-SHIELD)', 'Net-(D3-K)',
             '/CHIP_PU', '/GPIO0', '/GPIO43', '/GPIO44', '/GPIO35', '/GPIO36', '/GPIO37',
             '/GPIO38', 'unconnected-(U1-GPIO45-Pad26)', 'unconnected-(U1-GPIO46-Pad16)'}

U1_AT = K(62.7, 97.98, 180)
U1_NETS = {
    '1': '/ESP_3V3', '2': '/ESP_3V3', '3': 'unconnected-(U1-CHIP_PU-Pad3)', '4': '/GPIO4',
    '5': '/GPIO5', '6': '/GPIO6', '7': '/GPIO7', '8': '/GPIO15', '9': '/GPIO16', '10': '/GPIO17',
    '11': '/GPIO18', '12': '/GPIO8', '13': '/GPIO3', '14': 'unconnected-(U1-GPIO46-Pad14)',
    '15': '/GPIO9', '16': '/GPIO10', '17': '/GPIO11', '18': '/GPIO12', '19': '/GPIO13',
    '20': '/GPIO14', '21': 'unconnected-(U1-5V-Pad21)', '22': 'GND', '23': 'GND', '24': 'GND',
    '25': 'unconnected-(U1-GPIO19{slash}USB_D--Pad25)',
    '26': 'unconnected-(U1-GPIO20{slash}USB_D+-Pad26)', '27': '/GPIO21', '28': '/GPIO47',
    '29': '/GPIO48', '30': 'unconnected-(U1-GPIO45-Pad30)', '31': 'unconnected-(U1-GPIO0-Pad31)',
    '32': 'unconnected-(U1-GPIO35-Pad32)', '33': 'unconnected-(U1-GPIO36-Pad33)',
    '34': 'unconnected-(U1-GPIO37-Pad34)', '35': 'unconnected-(U1-GPIO38-Pad35)',
    '36': '/GPIO39', '37': '/GPIO40', '38': '/GPIO41', '39': '/GPIO42', '40': '/GPIO2',
    '41': '/VBAT_SENSE', '42': 'unconnected-(U1-GPIO44{slash}U0RXD-Pad42)',
    '43': 'unconnected-(U1-GPIO43{slash}U0TXD-Pad43)', '44': 'GND'}
# must match the schematic's U1 fields, or parity reports a field mismatch
U1_FIELDS = {
    'Value': 'ESP32-S3-DevKitC-1-N8R8',
    'Datasheet': 'https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/'
                 'esp32-s3-devkitc-1/user_guide_v1.1.html',
    'Description': 'ESP32-S3-DevKitC-1 v1.1, N8R8 (8 MB flash, 8 MB octal PSRAM), plugged into two '
                   '1x22 2.54 mm SMD female headers. Fed on its 3V3 pins from the AP63203.',
    'MPN': 'ESP32-S3-DevKitC-1-N8R8',
}

# ref -> (old KiCad x, y, rot) asserted, new (x, y, rot)
MOVES = {
    'J8':  ((110.0, 125.5, 180), K(6.6, 65.5, 180)),     # clear of the IMU's new column
    'SW3': ((107.0, 137.0, 0), K(6.6, 77.0, 0)),
    'J9':  ((160.0, 103.4, 90), K(62.3, 37.3, 90)),      # front of the right edge, cable east
    # J10 behind the IMU, facing it: the SPI bus stays in the devkit and rear
    # area, and the front of the IMU is left to the motor B trunks and the
    # driver inputs (in front of it, J10 sat in the trunks' exit from U5)
    'J10': ((133.0, 110.0, 0), K(24.5, 89.5, 180)),
    'C22': ((124.0, 110.0, 0), K(32.1, 89.5, 90)),       # beside J10.1/J10.2
    'TP9': ((118.0, 149.0, 0), K(15.5, 89.0, 0)),        # clear of J10
    'R23': ((143.0, 110.0, 0), K(57.0, 77.66, 0)),       # under the devkit, at GPIO16
    'R19': ((117.0, 133.0, 0), K(46.0, 57.34, 180)),     # under the devkit, at GPIO47
    'R20': ((117.0, 137.0, 0), K(46.0, 59.88, 180)),     # at GPIO48
    'R10': ((114.0, 150.0, 90), K(35.0, 88.0, 0)),       # sense chain hard against GPIO1
    'C14': ((121.0, 157.0, 90), K(35.0, 90.36, 180)),
    'R11': ((118.0, 154.0, 90), K(35.0, 92.7, 180)),
    'C1':  ((146.0, 151.0, 0), K(57.6, 92.9, 180)),      # beside the 3V3 pins
    'C2':  ((145.0, 158.0, 0), K(57.9, 95.44, 180)),
    'D5':  ((158.0, 113.0, 0), K(3.5, 89.5, 0)),         # rear-left corner: visible past the
    'R13': ((153.0, 113.0, 0), K(8.0, 89.5, 180)),       # devkit and the IMU
    'D4':  ((158.0, 117.0, 0), K(3.5, 93.5, 0)),
    'R12': ((153.0, 117.0, 0), K(8.0, 93.5, 180)),
    'TP3': ((142.0, 104.0, 0), K(54.5, 31.5, 0)),        # beside TP2, out of the trunk corridor
}
PAD_NETS = {('J9', '2'): '/GPIO18', ('R22', '2'): '/GPIO18'}   # encoder B OUT B off GPIO38

# board-level silkscreen that follows a moved part: text -> (old KiCad x, y), new
# (x, y[, angle]).  TP3's and J9's labels stand upright in the strip west of J9.
TEXTS = {
    'MOTOR A': ((110.0, 131.5), K(6.6, 71.0)),
    'BAT ON/OFF': ((107.0, 142.5), K(6.6, 82.5)),
    'MOTOR B': ((152.5, 99.0), K(58.6, 37.8, 90)),
    'PS1 HIGH = SPI': ((133.0, 114.0), K(24.5, 95.0)),
    'GND': ((118.0, 151.1), K(15.5, 91.1)),               # TP9's label
    'TP3 GND': ((142.0, 106.1), K(56.8, 32.6, 90)),
}
# reference fields of moved parts, board position (KiCad) of the text; None hides
# it on F.SilkS (C14 sits between R10 and R11 against the socket; F.Fab keeps it)
REF_AT = {
    'SW3': K(6.6, 84.2), 'D5': K(3.5, 87.6), 'R13': K(8.0, 87.6), 'D4': K(3.5, 95.4),
    'R12': K(8.0, 95.4), 'R10': K(32.6, 86.65), 'R11': K(35.0, 94.6), 'C14': None,
    'J9': K(59.8, 31.3),
    'C22': K(32.1, 91.85), 'R19': K(49.6, 57.34), 'R20': K(49.6, 59.88),
    'C1': K(54.9, 92.9), 'C2': K(55.2, 95.44),
}
TEXT_DROP = ['GPIO18', 'GPIO35', 'GPIO36', 'GPIO37']          # TP5-TP8 labels

IMU_OLD, IMU_NEW = (133.0, 126.0), K(24.4, 73.5)
IMU_RES_OLD = (120.5, 113.5, 145.5, 138.5)
IMU_RES_NEW = (K(12.1, 61.0)[0], K(12.1, 61.0)[1], K(36.7, 86.0)[0], K(36.7, 86.0)[1])
ANT_OLD = (123.2, 160.0, 142.8, 167.0)
ANT_NEW = (K(43.5, 98.8)[0], K(43.5, 98.8)[1], K(59.5, 107.0)[0], K(59.5, 107.0)[1])
# the In2 VBAT island: a 3V3 via inside it reaches no 3V3 plane
ISLAND = (100.5, 88.0, 127.0, 122.0)

# copper kept inside these KiCad boxes when a partly kept net is ripped: the
# motor corner (driver escapes, IPROPI runs) inside the In2 VBAT island
MOTOR_CORNER = (100.0, 104.0, 127.5, 122.6)
VSYS_D1_X = 141.0                 # east of C17/U3.3, VSYS only ran on to D1


def in_island(x, y, margin=0.0):
    """inside ISLAND (scalars or numpy arrays)"""
    x0, y0, x1, y1 = ISLAND
    return (x >= x0 - margin) & (x <= x1 + margin) & (y >= y0 - margin) & (y <= y1 + margin)
PARTIAL = {'/GPIO2', '/GPIO10', '/GPIO39', '/GPIO40', '/GPIO41', '/GPIO42'}
FULL = {'/GPIO3', '/GPIO4', '/GPIO5', '/GPIO6', '/GPIO7', '/GPIO8', '/GPIO9', '/GPIO11',
        '/GPIO12', '/GPIO13', '/GPIO14', '/GPIO15', '/GPIO16', '/GPIO17', '/GPIO18', '/GPIO21',
        '/GPIO47', '/GPIO48', '/VBAT_SENSE', 'Net-(D4-A)', 'Net-(D5-A)', 'Net-(Q1-G)'}
MOTOR_NETS = {'/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2'}


# ---------------------------------------------------------------- router
def make_router(Router, p):
    """a Router whose searched vias keep 1.35 mm from every non-plane via, never
    put a 3V3 via inside the In2 VBAT island (it would reach no 3V3 plane), and
    clear SMD openings by drill radius + 0.10 mm"""
    class R(Router):
        def __init__(self, p_):
            super().__init__(p_)
            _drill_clear_of_pads(self)
            self.sig_block = np.zeros((NY, NX), bool)
            for b in self.p.blocks:
                if Pcb.kind(b) == 'via' and Pcb.net(b) not in PLANE_NETS:
                    x, y, s, d = Pcb.geom(b)
                    self._block(x, y)
            ys, xs = np.mgrid[0:NY, 0:NX]
            self.island = in_island(wx(xs), wy(ys), margin=0.5)
            g = self.g
            dist0, vmask0 = g.dist, g.via_mask

            from scipy import ndimage

            def dist(net):                 # Router.masks and stitch() both start here
                g.last_net = net
                out = dist0(net)
                for a, b, c in WIDE_RULES:
                    agg = b if net in a else (a if net in b else None)
                    if not agg:
                        continue
                    ids = [g.netid[n] for n in agg if n in g.netid]
                    for l in ROUTE:
                        dd, own = out[l]
                        da = ndimage.distance_transform_edt(~np.isin(g.cu[l], ids)) * H
                        out[l] = (np.minimum(dd, da - (c - CL) - 0.03), own)
                return out

            def via_mask(d, via_d=VIA_D):
                m = vmask0(d, via_d)
                net = getattr(g, 'last_net', None)
                if net == '/ESP_3V3':
                    m &= ~self.island
                if net not in PLANE_NETS:
                    m &= ~self.sig_block
                return m
            g.dist, g.via_mask = dist, via_mask

        def _block(self, x, y):
            sel = disc_mask(x, y, SIG_VIA_SEP)
            if sel:
                iy0, iy1, ix0, ix1, m = sel
                self.sig_block[iy0:iy1 + 1, ix0:ix1 + 1] |= m

        def via(self, net, x, y, size=VIA_D, drill=VIA_DRILL):
            super().via(net, x, y, size, drill)
            if net not in PLANE_NETS:
                self._block(x, y)
    return R(p)


# ---------------------------------------------------------------- footprints
def _span(p, ref):
    return p.footprint_span(ref)


def _at(p, ref):
    i, j = _span(p, ref)
    m = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\n', p.text[i:j])
    return float(m.group(1)), float(m.group(2)), float(m.group(3) or 0.0)


def delete_footprint(p, ref):
    i, j = _span(p, ref)
    p.text = p.text[:i] + p.text[j:]
    p._split()


def set_ref(p, ref, at):
    """put a footprint's Reference text at a board position, horizontal, or hide it"""
    x, y, rot = _at(p, ref)
    i, j = _span(p, ref)
    blk = p.text[i:j]
    m = re.search(r'(\(property "Reference" "[^"]*"\s*\n\s*\(at )([-\d.]+ [-\d.]+(?: [-\d.]+)?)\)', blk)
    assert m, ref
    if at is None:
        k = blk.index('\n', m.end())
        blk2 = blk[:k] + '\n\t\t\t(hide yes)' + blk[k:] if '(hide yes)' not in blk[m.end():blk.index('(effects', m.end())] else blk
    else:
        a = math.radians(rot)
        bx, by = at[0] - x, at[1] - y
        # board offset -> footprint frame (KiCad turns +rot counter-clockwise, y down)
        lx = bx * math.cos(a) - by * math.sin(a)
        ly = bx * math.sin(a) + by * math.cos(a)
        blk2 = blk[:m.start(2)] + '%s %s %s' % (fx(lx), fx(ly), fx(0)) + blk[m.end(2):]
    p.text = p.text[:i] + blk2 + p.text[j:]
    p._split()


def set_pad_net(p, ref, num, net):
    i, j = _span(p, ref)
    blk = p.text[i:j]
    pat = re.compile(r'(\t\t\(pad "%s" .*?\n\t\t\)\n)' % re.escape(num), re.S)
    m = pat.search(blk)
    assert m, (ref, num)
    new, n = re.subn(r'\(net "[^"]*"\)', '(net "%s")' % net, m.group(1), count=1)
    assert n == 1, (ref, num)
    p.text = p.text[:i] + blk[:m.start()] + new + blk[m.end():] + p.text[j:]
    p._split()


MPN_PROP = '''		(property "{k}" "{v}"
			(at 0 0 0)
			(layer "F.Fab")
			(hide yes)
			(uuid "{u}")
			(effects
				(font
					(size 1.27 1.27)
					(thickness 0.15)
				)
			)
		)
'''


def devkit_block(path_line):
    """the project footprint, re-indented as a board item at rotation 0"""
    lib = open(LIB).read()
    lines = [l for l in lib.splitlines(True)
             if not re.match(r'\t\((version|generator|generator_version) ', l)]
    blk = ''.join('\t' + l if l.strip() else l for l in lines)
    name = FPID.split(':')[1]
    blk = blk.replace('\t(footprint "%s"\n' % name, '\t(footprint "%s"\n' % FPID, 1)
    blk = blk.replace('\t\t(layer "F.Cu")\n',
                      '\t\t(layer "F.Cu")\n\t\t(uuid "%s")\n\t\t(at %s %s)\n'
                      % (uuid.uuid4(), fx(U1_AT[0]), fx(U1_AT[1])), 1)
    blk = blk.replace('(property "Reference" "REF**"', '(property "Reference" "U1"', 1)
    blk = re.sub(r'(\(property "Value" )"[^"]*"', lambda m: m.group(1) + '"%s"' % U1_FIELDS['Value'],
                 blk, count=1)
    blk = re.sub(r'\(uuid "[^"]+"\)', lambda _: '(uuid "%s")' % uuid.uuid4(), blk)
    extra = ''.join(MPN_PROP.format(k=k, v=U1_FIELDS[k], u=uuid.uuid4())
                    for k in ('Datasheet', 'Description', 'MPN'))
    i = blk.index('\t\t(attr smd)')
    blk = blk[:i] + extra + path_line + '\n' + blk[i:]

    def pad_net(m):
        return m.group(0).replace('\t\t\t(uuid', '\t\t\t(net "%s")\n\t\t\t(uuid' % U1_NETS[m.group(1)], 1)
    blk = re.sub(r'\t\t\(pad "(\d+)" .*?\n\t\t\)\n', pad_net, blk, flags=re.S)
    assert blk.count('(net "') == 44
    return blk


def swap_u1(p):
    i, j = _span(p, 'U1')
    old = p.text[i:j]
    assert '"Pixy-M2:ESP32-S3-WROOM-1_AntennaOverhang"' in old, 'U1 is not the WROOM-1'
    path = re.search(r'\t\t\(path "[^"]+"\)', old).group(0)
    p.text = p.text[:i] + devkit_block(path) + p.text[j:]
    p._split()
    p.move_footprint('U1', U1_AT[0], U1_AT[1], U1_AT[2])


# ---------------------------------------------------------------- board items
def _rect_pts(x0, y0, x1, y1):
    return '(xy %s %s) (xy %s %s) (xy %s %s) (xy %s %s)' % (
        fx(x0), fx(y0), fx(x1), fx(y0), fx(x1), fx(y1), fx(x0), fx(y1))


def move_zone(p, name, old, new):
    """rewrite a rectangular zone's outline (to a rectangle or a polygon),
    asserting the old one"""
    m = re.search(r'\(name "%s"\)' % re.escape(name), p.text)
    assert m, name
    k = p.text.index('(pts', m.end())
    e = p.text.index(')\n', p.text.index('(xy', k))
    seg = p.text[k:e]
    xs = [float(v) for v in re.findall(r'\(xy ([-\d.]+) ', seg)]
    ys = [float(v) for v in re.findall(r'\(xy [-\d.]+ ([-\d.]+)\)', seg)]
    got = (min(xs), min(ys), max(xs), max(ys))
    assert all(abs(a - b) < 1e-3 for a, b in zip(got, old)), (name, got)
    pts = re.compile(r'\(pts\s*(\(xy [^)]*\)\s*)+')
    mm = pts.match(p.text, k)
    xy = _rect_pts(*new) if len(new) == 4 and not isinstance(new[0], tuple) else \
        ' '.join('(xy %s %s)' % (fx(x), fx(y)) for x, y in new)
    p.text = p.text[:k] + '(pts\n\t\t\t\t%s\n\t\t\t' % xy + p.text[mm.end():]
    p._split()


def close_outline(p):
    """J1's rear-edge notch was drawn in J1's own footprint; with J1 gone the
    rear edge has a gap from x 47.3 to 60.7.  Close it with a straight edge."""
    a = '(start 147.3 160)\n\t\t(end 103 160)'
    b = '(start 163 160)\n\t\t(end 160.7 160)'
    assert a in p.text and b in p.text, 'rear edge segments not as expected'
    s = ('\t(gr_line\n\t\t(start 160.7 160)\n\t\t(end 147.3 160)\n\t\t(stroke\n'
         '\t\t\t(width 0.05)\n\t\t\t(type default)\n\t\t)\n\t\t(layer "Edge.Cuts")\n'
         '\t\t(uuid "%s")\n\t)\n' % uuid.uuid4())
    p.add_zone(s)


def drop_text(p, s):
    m = re.search(r'\n\t\(gr_text "%s"\n.*?\n\t\)\n' % re.escape(s), p.text, re.S)
    assert m, s
    p.text = p.text[:m.start() + 1] + p.text[m.end():]
    p._split()


def redraw_imu(p):
    """delete the 'IMU module' group and its members, draw it again round IMU_NEW"""
    m = re.search(r'\n\t\(group "IMU module"\n.*?\n\t\)\n', p.text, re.S)
    assert m, 'no IMU group'
    members = re.findall(r'"([0-9a-f-]{36})"', m.group(0))
    p.text = p.text[:m.start() + 1] + p.text[m.end():]
    n = 0
    for u in members[1:]:                      # the first uuid is the group's own
        k = p.text.index('\t\t(uuid "%s")\n' % u)
        s = p.text.rindex('\n\t(', 0, k) + 1  # the top-level item holding it
        e = p.text.index('\n\t)\n', k) + 4
        assert re.match(r'\t\((gr_line|gr_circle|gr_text)\b', p.text[s:]), p.text[s:s + 40]
        p.text = p.text[:s] + p.text[e:]
        n += 1
    p._split()
    old = assembly_marks.IMU_C
    assembly_marks.IMU_C = IMU_NEW
    mk = assembly_marks.Marks()
    assembly_marks.imu(mk)
    assembly_marks.IMU_C = old
    p.add_zone(mk.sexpr())
    return n, len(mk.items)


# ---------------------------------------------------------------- copper
def _pts(b):
    g = Pcb.geom(b)
    return [(g[0], g[1]), (g[2], g[3])] if Pcb.kind(b) == 'segment' else [(g[0], g[1])]


def _inside(box, x, y):
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def rip(p):
    def gone(b):
        n = Pcb.net(b)
        if n in GONE_NETS or n in FULL:
            return True
        if n in PARTIAL:
            return not all(_inside(MOTOR_CORNER, x, y) for x, y in _pts(b))
        if n in MOTOR_NETS:        # trunks and their vias; the driver escapes stay
            return Pcb.kind(b) == 'via' or Pcb.geom(b)[4] >= 0.6
        if n == '/VBAT':           # the old feed down to R10's old place
            return any(y > MOTOR_CORNER[3] for x, y in _pts(b))
        if n == '/VSYS':           # the run north of the buck out to D1
            return all(x > VSYS_D1_X for x, y in _pts(b))
        return False
    return p.drop(gone)


def _protected(b):
    """the cut ends of the motor-corner nets this stage re-connects: driver pin
    escapes and IPROPI runs.  Pruned back from a cut, the 0.15 mm pin escapes
    cannot be re-created by the router (pololu_conn.py)"""
    return Pcb.net(b) in PARTIAL | MOTOR_NETS and all(_inside(MOTOR_CORNER, x, y) for x, y in _pts(b))


def drop_vias_under(p, g, refs):
    """bare stitching vias the moved parts' SMD pads now land on (rip_conflicts
    keeps same-net copper; a via in a pad is a drill-to-pad violation)"""
    from pololu_conn import _pad_seg_gap
    pads = [pd for r_ in refs for pd in g.byref[r_]['pads'] if not pd['drill']]
    hit = set()
    for b in p.blocks:
        if Pcb.kind(b) != 'via':
            continue
        x, y, s, d = Pcb.geom(b)
        if any(abs(pd['x'] - x) < 4 and abs(pd['y'] - y) < 4 and
               _pad_seg_gap(pd, x, y, x, y, d / 2) < 0.12 for pd in pads):
            hit.add(b)
    p.blocks = [b for b in p.blocks if b not in hit]
    return len(hit)


def prune_all(p, g, nets, baseline, protect=True):
    total = 0
    while True:
        drop = {b for b in dangling(p, g, nets) - baseline if not (protect and _protected(b))}
        if not drop:
            return total
        p.blocks = [b for b in p.blocks if b not in drop]
        total += len(drop)


def _seg_d(px, py, x1, y1, x2, y2):
    from pololu_conn import _pt_seg
    return _pt_seg(px, py, x1, y1, x2, y2)


GND_POUR_F = (104.2, 104.6, 123.2, 120.2)       # rework.GND_POUR, the F.Cu motor-region pour


def prune_strict(p, g, nets, depth=10):
    """remove dead-end copper the way KiCad's track_dangling check sees it.

    pololu_conn.dangling() counts a track end as connected when it lies within
    half a width of any other track of the net.  The router's 0.05 mm staircase
    steps all overlap their own neighbours like that, so short dead tails at
    the ends of routes survive it (KiCad flags them).  Here a track end is
    connected if it meets another track end exactly, lies inside a pad, a via
    or a pour of its net (GND: all of B.Cu and the F.Cu motor region), or lies
    on another track that is not within `depth` segments of it along its own
    chain (a real T-joint).  A dead segment whose middle carries such a T-joint
    is split there and only the tail beyond it goes, so the joint survives.
    Geometry is never moved.  On signal nets a via joining fewer than two items
    goes too; plane-net vias stay (they meet a plane)."""
    from pololu_conn import _in_pad, _layers
    total = 0
    for net in nets:
        plane = net in PLANE_NETS
        pads = [pd for f in g.fps for pd in f['pads'] if pd['net'] == net]
        for _ in range(5000):
            segs = [b for b in p.blocks if Pcb.kind(b) == 'segment' and Pcb.net(b) == net]
            vias = [b for b in p.blocks if Pcb.kind(b) == 'via' and Pcb.net(b) == net]
            sg = {b: Pcb.geom(b) for b in segs}
            vg = [Pcb.geom(b) for b in vias]
            key = lambda x, y, l: (round(x, 3), round(y, 3), l)
            at = {}
            for b, (x1, y1, x2, y2, w, l) in sg.items():
                at.setdefault(key(x1, y1, l), []).append(b)
                at.setdefault(key(x2, y2, l), []).append(b)

            def chain(b):
                seen, front = {b}, [b]
                for _d in range(depth):
                    nxt = []
                    for c in front:
                        x1, y1, x2, y2, w, l = sg[c]
                        for q in at[key(x1, y1, l)] + at[key(x2, y2, l)]:
                            if q not in seen:
                                seen.add(q); nxt.append(q)
                    front = nxt
                return seen

            def anchored(px, py, l):
                if any(l in _layers(pd) and _in_pad(pd, px, py) for pd in pads):
                    return True
                if any(math.hypot(px - vx, py - vy) <= s / 2 + 1e-3 for (vx, vy, s, d) in vg):
                    return True
                return net == 'GND' and (l == 'B.Cu' or _inside(GND_POUR_F, px, py))

            dead, split = set(), None
            for b, (x1, y1, x2, y2, w, l) in sg.items():
                own = None
                free = []
                for (px, py) in ((x1, y1), (x2, y2)):
                    if len(at[key(px, py, l)]) >= 2 or anchored(px, py, l):
                        continue
                    own = own or chain(b)
                    if any(o not in own and sg[o][5] == l and _seg_d(px, py, *sg[o][:4]) <= sg[o][4] / 2 + 1e-3
                           for o in sg):
                        continue
                    free.append((px, py))
                if not free:
                    continue
                if len(free) == 1:
                    # a T-joint on this segment from elsewhere, or a via or pad
                    # it runs through: keep up to it
                    fx_, fy_ = free[0]
                    L = math.hypot(x2 - x1, y2 - y1)
                    best = None
                    through = [(vx, vy) for (vx, vy, s, d) in vg] + \
                        [(pd['x'], pd['y']) for pd in pads if l in _layers(pd)]
                    for (qx, qy) in through:
                        if L < 1e-6 or _seg_d(qx, qy, x1, y1, x2, y2) > w / 2 + 1e-3:
                            continue
                        t_ = ((qx - x1) * (x2 - x1) + (qy - y1) * (y2 - y1)) / (L * L)
                        sx, sy = x1 + t_ * (x2 - x1), y1 + t_ * (y2 - y1)
                        d = math.hypot(sx - fx_, sy - fy_)
                        if 0.02 < t_ * L < L - 0.02 and (best is None or d < best[0]):
                            best = (d, sx, sy, None, None)
                    for o in sg:
                        if o in own or sg[o][5] != l:
                            continue
                        for k_, (qx, qy) in enumerate((sg[o][:2], sg[o][2:4])):
                            if L < 1e-6 or _seg_d(qx, qy, x1, y1, x2, y2) > w / 2 + 1e-3:
                                continue
                            t_ = ((qx - x1) * (x2 - x1) + (qy - y1) * (y2 - y1)) / (L * L)
                            sx, sy = x1 + t_ * (x2 - x1), y1 + t_ * (y2 - y1)
                            d = math.hypot(sx - fx_, sy - fy_)
                            if 0.02 < t_ * L < L - 0.02 and (best is None or d < best[0]):
                                best = (d, sx, sy, o, k_)
                    if best:
                        split = (b, best[1], best[2], free[0], best[3], best[4])
                        break
                dead.add(b)
            if split:
                # cut the tail at the joint and bring the joining end onto it
                # (at most half a width, onto same-net copper of another branch)
                b, sx, sy, (fx_, fy_), o, k_ = split
                x1, y1, x2, y2, w, l = sg[b]
                keep = (x2, y2) if math.hypot(x1 - fx_, y1 - fy_) < 1e-6 else (x1, y1)
                p.blocks.remove(b)
                p.add_track(net, l, keep[0], keep[1], sx, sy, w)
                if o is not None:          # a joining track: bring its end onto the cut
                    ox1, oy1, ox2, oy2, ow, ol = sg[o]
                    p.blocks.remove(o)
                    if k_ == 0:
                        p.add_track(net, l, sx, sy, ox2, oy2, ow)
                    else:
                        p.add_track(net, l, ox1, oy1, sx, sy, ow)
                total += 1
                continue
            if not plane:
                for b, (vx, vy, s, d) in zip(vias, vg):
                    n = sum(1 for (x1, y1, x2, y2, w, l) in sg.values()
                            if math.hypot(x1 - vx, y1 - vy) <= s / 2 + 1e-3 or
                            math.hypot(x2 - vx, y2 - vy) <= s / 2 + 1e-3)
                    n += sum(1 for pd in pads if _in_pad(pd, vx, vy))
                    if n < 2:
                        dead.add(b)
            if not dead:
                break
            p.blocks = [b for b in p.blocks if b not in dead]
            total += len(dead)
    return total


def drop_via_only_gnd(p, g):
    """F.Cu GND copper outside the motor-region pour that reaches no pad: the
    stubs of a removed or moved part's GND pads (J1's A1/B12, TP3's old spot)
    left joining only vias.  Every GND via already meets the solid In1 plane,
    so such a group carries nothing.  The vias stay as stitching."""
    from pololu_conn import _in_pad, _layers
    pads = [pd for f in g.fps for pd in f['pads'] if pd['net'] == 'GND' and 'F.Cu' in _layers(pd)]
    segs = [b for b in p.blocks if Pcb.kind(b) == 'segment' and Pcb.net(b) == 'GND'
            and Pcb.geom(b)[5] == 'F.Cu']
    sg = {b: Pcb.geom(b) for b in segs}
    parent = {b: b for b in segs}

    def find(b):
        while parent[b] is not b:
            parent[b] = parent[parent[b]]
            b = parent[b]
        return b
    for i, a in enumerate(segs):
        for c in segs[i + 1:]:
            ga, gc = sg[a], sg[c]
            if min(_seg_d(ga[0], ga[1], *gc[:4]), _seg_d(ga[2], ga[3], *gc[:4]),
                   _seg_d(gc[0], gc[1], *ga[:4]), _seg_d(gc[2], gc[3], *ga[:4])) <= max(ga[4], gc[4]) / 2:
                parent[find(a)] = find(c)
    groups = {}
    for b in segs:
        groups.setdefault(find(b), []).append(b)
    dead = set()
    for members in groups.values():
        ends = [q for b in members for q in (sg[b][:2], sg[b][2:4])]
        if any(_inside(GND_POUR_F, x, y) for x, y in ends):
            continue
        if any(_in_pad(pd, x, y, sg[b][4] / 2 - 0.02) for b in members
               for x, y in (sg[b][:2], sg[b][2:4]) for pd in pads):
            continue
        dead |= set(members)
    p.blocks = [b for b in p.blocks if b not in dead]
    return len(dead)


def stitch_islands(r, min_area=2.0):
    """one GND via in each piece of the B.Cu GND pour that would otherwise be
    removed as an island.  Long B.Cu signal runs (the IMU bus, the driver
    inputs) cut the pour into pieces, and island_removal_mode 0 drops every
    piece with no GND connection.  The free area is modelled as the pour fills
    it: 0.25 mm clear of other copper and holes, 0.3 mm in from the edge, and
    necked down by the 0.25 mm minimum width."""
    from scipy import ndimage
    d = r.g.dist('GND')
    dd, own = d['B.Cu']
    free = (dd >= 0.25 + 0.125) & (r.g.dist_edge >= 0.3 + 0.125) & r.g.inside & ~r.g.keepout
    lab, n = ndimage.label(free, structure=np.ones((3, 3), bool))
    fed = set()
    for b in r.p.blocks:
        if Pcb.kind(b) == 'via' and Pcb.net(b) == 'GND':
            x, y, s, dr = Pcb.geom(b)
            sel = disc_mask(x, y, s / 2 + 0.3)
            if sel:
                iy0, iy1, ix0, ix1, m = sel
                fed |= set(np.unique(lab[iy0:iy1 + 1, ix0:ix1 + 1][m]).tolist())
    for f in r.g.fps:                         # through-hole GND pads reach B.Cu too
        for pd in f['pads']:
            if pd['net'] == 'GND' and pd['drill']:
                sel = disc_mask(pd['x'], pd['y'], max(pd['w'], pd['h']) / 2 + 0.3)
                if sel:
                    iy0, iy1, ix0, ix1, m = sel
                    fed |= set(np.unique(lab[iy0:iy1 + 1, ix0:ix1 + 1][m]).tolist())
    vm = r.g.via_mask(d)
    areas = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1)) * H * H
    added = 0
    for k in range(1, n + 1):
        if k in fed or areas[k - 1] < min_area:
            continue
        comp = lab == k
        spot = comp & vm
        if not spot.any():
            continue
        # the legal spot deepest inside the piece
        depth = ndimage.distance_transform_edt(comp)
        iy, ix = np.unravel_index(np.argmax(np.where(spot, depth, -1)), comp.shape)
        r.via('GND', wx(ix), wy(iy))
        added += 1
    return added


def pads_of(g, net):
    return [(f['ref'], pd) for f in g.fps for pd in f['pads'] if pd['net'] == net]


# plane pins that take their via before any signal is routed, and the side it
# goes: C22's away from J10's signal fan-out, J8's away from its signal
# escapes (pin 1 into the housing, pin 4 beside the M2 pad).  Routed last, they found no room (J10.1, J8.4), and the 3V3
# pieces over the VBAT island had nothing to reach.
VIA_SHARED = {('J10', '1'), ('J10', '2')}       # fed through C22's pads and vias
PLANE_FIRST = {('C22', '1'): (0.3, 1), ('C22', '2'): (0, -1), ('J10', 'MP'): (0, -1),
               ('J8', '1'): (0.3, -1), ('J8', '4'): (-1, 0.6), ('J8', 'MP'): (0, -1)}


def early_taps(r):
    ok = True
    for (ref, num), want in PLANE_FIRST.items():
        for pd in r.g.byref[ref]['pads']:
            if pd['num'] != num or _fed(r.p, pd):
                continue
            n = math.hypot(*want) or 1.0
            x, y = pd['x'] + 0.3 * want[0] / n, pd['y'] + 0.3 * want[1] / n
            spot = r.stitch(pd['net'], x, y, want, w=PLANE_TAP, maxr=3.0)
            print(f"  early tap {ref}.{num} {pd['net']}: {'ok' if spot else 'FAILED'}")
            ok &= spot is not None
    # J10's plane pins join C22's pads: 1 mm pitch leaves no room for vias there
    for a, b in ((('J10', '1'), ('C22', '1')), (('J10', '2'), ('C22', '2'))):
        pa, pb = _pad(r.g, *a), _pad(r.g, *b)
        res = r.route(pa['net'], PLANE_TAP, [_group(r.g, [('pad', pa)]), _group(r.g, [('pad', pb)])])
        print(f"  {a[0]}.{a[1]} -> {b[0]}.{b[1]}: {'ok' if res else 'FAILED'}")
        ok &= res
    return ok


def route_net(r, net, w=SIGNAL):
    comps = components(r.p, r.g, net)
    if len(comps) < 2:
        return True
    return r.route(net, w, [_group(r.g, c) for c in comps])


def stitch_pad(r, ref, num, want=(0, 0), w=PLANE_TAP, maxr=4.0):
    pd = _pad(r.g, ref, num)
    return r.stitch(pd['net'], pd['x'], pd['y'], want, w=w, maxr=maxr)


def _fed(p, pd):
    """a plane-net pad with a same-net via inside it or at the end of a track from it"""
    net = pd['net']
    ends = []
    for b in p.blocks:
        if Pcb.net(b) != net:
            continue
        if Pcb.kind(b) == 'via':
            x, y, s, d = Pcb.geom(b)
            if _in_pad(pd, x, y, s / 2):
                return True
            ends.append((x, y, s))
    for b in p.blocks:
        if Pcb.net(b) != net or Pcb.kind(b) != 'segment':
            continue
        x1, y1, x2, y2, w, l = Pcb.geom(b)
        for (ax, ay), (bx, by) in (((x1, y1), (x2, y2)), ((x2, y2), (x1, y1))):
            if _in_pad(pd, ax, ay, w / 2) and any(math.hypot(bx - vx, by - vy) <= s / 2 for vx, vy, s in ends):
                return True
    return False


def plane_taps(r, refs=None):
    """one via per plane-net SMD pad not already tapped, else a tie to a nearby via.
    refs None = every footprint on the board"""
    ok, n = True, 0
    for f in r.g.fps:
        if refs is not None and f['ref'] not in refs:
            continue
        for pd in f['pads']:
            if pd['net'] not in ('GND', '/ESP_3V3') or pd['drill']:
                continue
            if not any(l in pd['layers'] for l in ('F.Cu', 'B.Cu')):
                continue
            if (f['ref'], pd['num']) in VIA_SHARED or _fed(r.p, pd):
                continue
            n += 1
            spot = r.stitch(pd['net'], pd['x'], pd['y'], (0, 0), w=PLANE_TAP, maxr=3.0)
            if spot is None:
                tgt = plane_vias(r.p, pd['net'], pd['x'], pd['y'], 8.0)
                res = bool(tgt) and r.route(pd['net'], PLANE_TAP,
                                            [_group(r.g, [('pad', pd)]), _group(r.g, tgt)])
                print(f"    {f['ref']}.{pd['num']} {pd['net']} tied to a nearby via: {'ok' if res else 'FAILED'}")
                ok &= res
    print(f'  plane taps: {n} pads stitched')
    return ok


def fan_in_j8(r, ref):
    """J8's motor pins fan in under its own housing (north), not away from it.

    At rot 180 J8's M1/M2 (pins 6/5) are its west end and face south, away from
    U4.  pololu_conn's stubs go that way, so both trunks had to loop back under
    pins 1-4 and boxed in their escapes (GPIO48 and the GND tie failed).  J8 now
    sits 3.4 mm further west, beside the IMU, and the old corridor along the
    board edge is gone.  The housing spans 6.4 mm clear between its MP pads, so
    the trunks leave north through it and run almost straight to U4; pins 1-4
    escape south.  The stubs are 0.6 mm (Motor rule floor).  The pair heads
    north-east, so M2's stub steps 1.6 mm east over pin 4 (0.33 mm clear of pins
    3 and 4): started 1.3 mm apart in x, M1's diagonal passed 0.92 mm from M2's
    start, inside the 1.06 mm two 0.8 mm trunks need.  M1 stays 0.3 mm off the
    west MP pad."""
    if ref != 'J8':
        return _fan_in_stock(r, ref)
    g = r.g
    p5, p6 = _pad(g, ref, '5'), _pad(g, ref, '6')
    ux, uy = 0.0, -1.0                       # north, into the housing
    x, y = p6['x'], p6['y']
    e6 = (x, y + 1.3 * uy)
    r.track(p6['net'], 'F.Cu', x, y, *e6, pololu_conn.FAN)
    x, y = p5['x'], p5['y']
    k5 = (x, y + 1.3 * uy)
    e5 = (x + 1.6, y + 1.5 * uy)
    r.track(p5['net'], 'F.Cu', x, y, *k5, pololu_conn.FAN)
    r.track(p5['net'], 'F.Cu', *k5, *e5, pololu_conn.FAN)
    return {p5['net']: e5, p6['net']: e6}, (ux, uy)


_fan_in_stock = pololu_conn.fan_in

# M1's path to J9, each point pinned to one layer (Router.route_waypoints offers
# both and can join two legs on different layers with no via, issue8.py):
# north-east out of U5 between C21 and the IMU's front, east along the old
# corridor (5 mm south of REG_EN at R7), under the left socket on B.Cu (the sockets are SMD: no pads there),
# then up to the fan-in in front of the devkit.  Left to itself, A* hugged J10
# and the IMU's front edge and left M2 no room.
M1_WAYPOINTS = {'J9': [(K(24.0, 48.5), 'F.Cu'), (K(33.0, 48.0), 'F.Cu'),
                       (K(44.5, 47.0), 'B.Cu'), (K(54.0, 41.0), 'B.Cu')]}


def motor_wp(r, ref, pair_waypoints, wps1):
    """pololu_conn.motor() with M1 routed through layer-pinned waypoints"""
    from loop import polyline
    ends, _ = pololu_conn.fan_in(r, ref)
    br = pololu_conn.BREAKOUTS[ref]
    m1, m2 = sorted(br)
    res = {}
    prev = r.point_group(*br[m1], ['F.Cu'], r=0.2)
    ok1 = True
    for (x, y), layer in wps1:
        wp = r.point_group(x, y, [layer], r=0.2)
        if r.route(m1, pololu_conn.TRUNK, [prev, wp], quiet=True):
            prev = r.point_group(x, y, [layer], r=0.2)
        else:
            print(f'    (M1 waypoint {x - OX:.1f},{y - OY:.1f} {layer} skipped)')
    ok1 = r.route(m1, pololu_conn.TRUNK, [prev, r.point_group(*ends[m1], ['F.Cu'], r=0.2)])
    res[m1] = ok1
    wps = []
    if ok1:
        pts = polyline(r.p, m1, br[m1], ends[m1])
        side = (ends[m2][0] - ends[m1][0], ends[m2][1] - ends[m1][1])
        wps = pair_waypoints(pts, side)
    prev, used = r.point_group(*br[m2], ['F.Cu'], r=0.2), 0
    for (x, y) in wps:
        for layer in ('F.Cu', 'B.Cu'):
            if r.route(m2, pololu_conn.TRUNK, [prev, r.point_group(x, y, [layer], r=0.2)], quiet=True):
                prev, used = r.point_group(x, y, [layer], r=0.2), used + 1
                break
    res[m2] = r.route(m2, pololu_conn.TRUNK, [prev, r.point_group(*ends[m2], ['F.Cu'], r=0.2)])
    return res, used


# signal order: the long runs across the devkit first, while the corridors are open
# J8's two signals first, inner pin (2) before outer (3), both escaping south;
# then J10 from its east pad outward, so the bus nests (1 mm pads, entered from
# the south only); then the driver inputs, whose cut ends sit in the pin field;
# the I2C bus (six pads each) before the single XSHUT lines
ORDER = ['/GPIO48', '/GPIO47',
         '/GPIO12', '/GPIO11', '/GPIO13', '/GPIO14', '/GPIO15', '/GPIO16', '/GPIO17',
         '/GPIO39', '/GPIO40', '/GPIO41', '/GPIO42', '/GPIO2', '/GPIO10',
         '/GPIO21', '/GPIO18',
         '/GPIO8', '/GPIO9', '/GPIO4', '/GPIO5', '/GPIO6', '/GPIO7',
         '/VBAT_SENSE', '/GPIO3', 'Net-(D5-A)', 'Net-(D4-A)']


def devkit(p, Router, pair_waypoints):
    p.sync()
    g0 = Router(p).g
    baseline = dangling(p, g0, {n for b in p.blocks if (n := Pcb.net(b))})

    # every text-level edit first: each one re-splits the file from p.text and
    # would silently drop a track/via edit made before it (pcbedit.py)
    # 1. parts that are gone
    for ref in REMOVE:
        delete_footprint(p, ref)
    for s in TEXT_DROP:
        drop_text(p, s)

    # 2. U1, and 3. the parts that move
    swap_u1(p)
    for ref, (old, new) in MOVES.items():
        got = _at(p, ref)
        assert all(abs(a - b) < 1e-3 for a, b in zip(got, old)), (ref, got)
        p.move_footprint(ref, *new)
    for (ref, num), net in PAD_NETS.items():
        set_pad_net(p, ref, num, net)
    for s, (old, new) in TEXTS.items():
        m = re.search(r'\(gr_text "%s"\s*\n\s*\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)' % re.escape(s), p.text)
        assert m and abs(float(m.group(1)) - old[0]) < 1e-3 and abs(float(m.group(2)) - old[1]) < 1e-3, s
        ang = ' %s' % fx(new[2]) if len(new) > 2 else (m.group(3) or '')
        p.text = p.text[:m.start(1)] + '%s %s%s)' % (fx(new[0]), fx(new[1]), ang) + p.text[m.end():]
        p._split()
    for ref, at in REF_AT.items():
        set_ref(p, ref, at)
    move_zone(p, 'IMU module and bracket reservation', IMU_RES_OLD, IMU_RES_NEW)
    move_zone(p, 'Antenna all-layer copper exclusion', ANT_OLD, ANT_NEW)
    n_old, n_new = redraw_imu(p)
    close_outline(p)
    p.sync()
    # ... then the copper of the nets that are gone or will be re-routed
    n_gone = rip(p)
    print(f'  removed {len(REMOVE)} parts, ripped {n_gone} items; U1 -> DevKitC-1 sockets; '
          f'moved {len(MOVES)} parts; IMU marks {n_old} -> {n_new}')

    # 4. other-net copper under the new pads, then whatever is left dangling
    r = make_router(Router, p)
    k, hit = rip_conflicts(p, r.g, ['U1'] + list(MOVES))
    k += drop_vias_under(p, r.g, ['U1'] + list(MOVES))
    nets = {n for b in p.blocks if (n := Pcb.net(b))}
    r = make_router(Router, p)
    pr = prune_all(p, r.g, nets, baseline)
    print(f'  {k} items under new pads ({", ".join(sorted(hit))}), pruned {pr} dangling')

    ok = True
    # 5a. motor trunks
    r = make_router(Router, p)
    pololu_conn.fan_in = fan_in_j8
    for ref in ('J8', 'J9'):
        pololu_conn.PLACE[ref] = MOVES[ref][1]
        if ref in M1_WAYPOINTS:
            res, nw = motor_wp(r, ref, pair_waypoints, M1_WAYPOINTS[ref])
        else:
            res, nw = pololu_conn.motor(r, ref, pair_waypoints)
        print(f'  {ref}: ' + ', '.join(f'{k_} {"ok" if v else "FAILED"}' for k_, v in res.items())
              + (f' (paired, {nw} waypoints)' if nw else ''))
        ok &= all(res.values())

    pololu_conn.fan_in = _fan_in_stock

    # 5b. the plane pins that need their spot first, then the 3V3 pieces over
    # the VBAT island (U4/U5 VREF), which are fed from J8.4 as before
    ok &= early_taps(r)
    ok &= orphan_3v3(r)

    # 5c. signals
    rest = sorted(((FULL | PARTIAL | hit) - PLANE_NETS - MOTOR_NETS) - set(ORDER))
    for net in ORDER + rest:
        res = route_net(r, net)
        print(f'  {net} {"ok" if res else "FAILED"}')
        ok &= res

    # 5c. VBAT to R10: from the nearest VBAT via in the In2 island
    pd = _pad(r.g, 'R10', '1')
    tgt = plane_vias(r.p, '/VBAT', pd['x'], pd['y'], 60.0)
    res = r.route('/VBAT', PLANE_TAP, [_group(r.g, [('pad', pd)]), _group(r.g, tgt)])
    print(f'  /VBAT -> R10 {"ok" if res else "FAILED"}')
    ok &= res

    # 5d. plane stitches for every moved or new part
    ok &= plane_taps(r, ['U1'] + list(MOVES))
    ok &= orphan_3v3(r)
    if os.environ.get('DEVKIT_PREPRUNE'):        # debugging the clean-up without re-routing
        p.write(os.environ['DEVKIT_PREPRUNE'])
    nets = {n for b in p.blocks if (n := Pcb.net(b))}
    sig = (FULL | PARTIAL | MOTOR_NETS | {'/VSYS', '/REG_EN', '/VBAT'} | PLANE_NETS) & nets
    extra = prune_all(p, r.g, nets - sig, baseline)
    extra += prune_strict(p, r.g, sig) if ok else 0
    extra += drop_via_only_gnd(p, r.g)
    if extra:
        print(f'  pruned {extra} spurs left after routing')
    r = make_router(Router, p)
    print(f'  B.Cu GND pour: {stitch_islands(r)} vias for pieces with no GND connection')
    return ok


def main(src, dst):
    sys.path.insert(0, HERE)
    import rework
    p = Pcb(src)
    ok = devkit(p, rework.Router, rework.pair_waypoints)
    p.write(dst)
    print('wrote', dst, '' if ok else '(WITH ROUTING FAILURES)')


if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'Pixy-M2.kicad_pcb')
    main(src, sys.argv[2] if len(sys.argv) > 2 else src)
