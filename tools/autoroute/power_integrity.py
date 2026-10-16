#!/usr/bin/env python3
"""Motor UVLO/current reference and USB-priority isolation (rework stage 21).

Runs after devkit.py and before octilinear.py.  Standalone it converts the
pre-revision devkit board once:

    python3 power_integrity.py [in.kicad_pcb [out.kicad_pcb]]

Placement keeps the corridors the devkit stage gave the existing signals:

  front   U8/Q2/Q3/R28-R31/C26 in front of the devkit's USB end, probe-able,
          fed straight from L1.2.  Motor B's stacked trunk (MOT_B_1 on B.Cu,
          MOT_B_2 on F.Cu) walls this area off from the socket rows, so every
          connection here arrives from the front side (DEVKIT_5V under J9).
  pocket  U7/C24 with TP10/TP11 between motor B's trunk and the IMU
          reservation, beside the drivers: the DRV_* runs stay short.
  rear    U6, its divider and C23/C25/C27/C30 at the rear of the socket rows,
          far from motor and switch copper; VBAT is taken from R10.1.
  corner  C28 on MOTOR_VREF where it splits to U4.4 and U5.4.

Every re-routable net (devkit.FULL, and GPIO2/GPIO10 outside the motor corner)
that the new parts displace is ripped whole and routed again from scratch, so
nothing is patched around an obstacle.  The SPI bus and the encoder lines keep
5 mm from motor and switch-node copper, and I2C 3 mm from the switch node
(router rule here and in octilinear, DRC rule in Pixy-M2.kicad_dru).  SCL and
SDA are always re-routed: C12's GND via moves east of its pad, which opens
SCL's lane under C15.  Motor-output copper, the driver escapes and the
via-free FB trace are asserted unchanged.
"""
import math
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from power_integrity_data import (PARTS, PCB_MOVES, CURRENT_FIELDS, DRIVER_NETS, BUCK_PADS,
                                  OLD_INPUTS, ROOT)
sys.path.insert(0, str(HERE))
from pcbedit import Pcb
from sexp import parse, children, child, val
import devkit
from pololu_conn import rip_conflicts, components, _group, _pad, _in_pad, plane_vias

SW = devkit._SW
MOTOR = devkit.MOTOR_NETS
SPI = {'/GPIO11', '/GPIO12', '/GPIO13', '/GPIO14', '/GPIO15', '/GPIO16', '/GPIO17'}
ENCODERS = {'/GPIO18', '/GPIO21', '/GPIO47', '/GPIO48'}
I2C = {'/GPIO8', '/GPIO9'}
# router clearance floors (mm) on top of the 0.26 mm default; DRC carries the same
NEW_RULES = [({'/MOTOR_UVLO'}, MOTOR | SW, 5.0),
             (SPI, MOTOR | SW, 5.0),
             (ENCODERS, SW, 5.0),
             (I2C, SW, 3.0)]
# C12's GND tap: the via north of the pad closed the lane between C15 and C12,
# so SCL dropped under C12 and past C6's BST pad at 0.45 mm.  East of the pad
# it leaves that lane open and sits nearer U3.4.
C12_GND_VIA = ((134.0, 90.2), (135.55, 91.525))
# nets the devkit stage routed entirely with A*: displaced ones are ripped whole
REROUTABLE = devkit.FULL - {'/VBAT_SENSE', 'Net-(D4-A)', 'Net-(D5-A)', 'Net-(Q1-G)'}
PARTIAL = {'/GPIO2', '/GPIO10'}               # IPROPI: kept inside the motor corner
# copper of re-routable nets inside these boxes is displaced by the new clusters
# board-level labels of the test pads (moved with TP2/TP3, new for TP10/TP11)
TP_LABELS = {'3V3': 'TP2', 'GND': 'TP3', 'MOTOR_OK': 'TP10', 'VREF': 'TP11'}
OLD_TP_TEXTS = {'TP2 3V3': (151.5, 97.1), 'TP3 GND': (156.8, 92.6)}
CLUSTERS = {'front': (146.0, 88.4, 159.2, 100.6),
            'pocket': (123.6, 115.6, 126.3, 118.4),
            'rear': (143.0, 142.8, 160.0, 158.6),
            'tp10': (130.6, 155.2, 133.4, 158.0)}


def quoted(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def dump(n, d=0):
    if isinstance(n, tuple):
        return quoted(n[1])
    if not isinstance(n, list):
        return n
    if not any(isinstance(c, list) for c in n):
        return '(' + ' '.join(dump(c, d + 1) for c in n) + ')'
    return ('(' + dump(n[0], d + 1) + ''.join(('\n' + '\t' * (d + 1) if isinstance(c, list) else ' ')
                                              + dump(c, d + 1) for c in n[1:]) + '\n' + '\t' * d + ')')


def field_tree(k, v, hide=True):
    return ['property', ('STR', k), ('STR', v), ['at', '0', '0', '0'], ['layer', ('STR', 'F.Fab')],
            *([['hide', 'yes']] if hide else []), ['effects', ['font', ['size', '1', '1'], ['thickness', '0.15']]]]


def footprint(ref, data, suid):
    fp = data['fields']['Footprint']
    lib, name = fp.split(':')
    t = parse(Path('/usr/share/kicad/footprints', lib + '.pretty', name + '.kicad_mod').read_text())
    t[1] = ('STR', fp)
    t = [t[0], t[1]] + [c for c in t[2:] if not isinstance(c, list) or c[0] not in ('version', 'generator', 'generator_version')]
    t.insert(2, ['uuid', ('STR', str(uuid.uuid5(uuid.NAMESPACE_URL, 'pixy-power-' + ref)))])
    t.insert(3, ['at', str(data['pcb'][0]), str(data['pcb'][1])])
    for prop in children(t, 'property'):
        k = val(prop[1])
        if k == 'Reference':
            prop[2] = ('STR', ref)
        elif k == 'Value':
            prop[2] = ('STR', data['fields']['Value'])
    for k in ('Datasheet', 'Description', 'MPN'):
        t.append(field_tree(k, data['fields'][k]))
    # the symbols are in the BOM, like TP1-TP4's: keep only the pos-file exclusion
    attr = child(t, 'attr')
    if attr and 'exclude_from_bom' in attr:
        attr.remove('exclude_from_bom')
    t.append(['path', ('STR', '/fefb2c5c-cd05-4562-bf27-32a51f81fd04/' + suid)])
    for pad in children(t, 'pad'):
        n = val(pad[1])
        net = data['nets'].get(n)
        if net is None:
            net = 'unconnected-(%s-NC-Pad%s)' % (ref, n)
        pad.append(['net', ('STR', net if net == 'GND' or net.startswith('unconnected-') else '/' + net)])
    return '\t' + dump(t, 1) + '\n'


def set_fields(p, ref, fields):
    a, b = p.footprint_span(ref)
    t = parse(p.text[a:b])
    for k, v in fields.items():
        if k == 'Footprint':
            continue
        found = next((c for c in children(t, 'property') if val(c[1]) == k), None)
        if found is not None:
            found[2] = ('STR', v)
        else:
            t.append(field_tree(k, v))
    p.text = p.text[:a] + '\t' + dump(t, 1) + '\n' + p.text[b:]
    p._split()


def inside(b, box):
    g = Pcb.geom(b)
    pts = [g[:2]] if Pcb.kind(b) == 'via' else [g[:2], g[2:4]]
    return all(box[0] <= x <= box[2] and box[1] <= y <= box[3] for x, y in pts)


def touches(b, box, margin=0.0):
    """any part of a track or via within a box (sampled along the track)"""
    g = Pcb.geom(b)
    x0, y0, x1, y1 = box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin
    if Pcb.kind(b) == 'via':
        return x0 <= g[0] <= x1 and y0 <= g[1] <= y1
    n = max(1, int(math.dist(g[:2], g[2:4]) / 0.1))
    return any(x0 <= g[0] + (g[2] - g[0]) * k / n <= x1 and y0 <= g[1] + (g[3] - g[1]) * k / n <= y1
               for k in range(n + 1))


def pointseg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = dx * dx + dy * dy
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d)) if d else 0
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def segdist(a, b, c, d):
    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if (max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0])) and
            max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1])) and
            cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0):
        return 0
    return min(pointseg(a, c, d), pointseg(b, c, d), pointseg(c, a, b), pointseg(d, a, b))


def drop_unused_signal_vias(p, g):
    """Remove one-layer holes while retaining copper that bridges offset ends.

    A one-layer via can still join two traces whose ends touch its annulus but
    do not touch each other. Replace those contacts by explicit copper links
    before removing the hole; a bare deletion silently disconnects that net.
    """
    drop = set()
    bridges = []
    for b in p.blocks:
        net = Pcb.net(b)
        if Pcb.kind(b) != 'via' or net in {'GND', '/ESP_3V3', '/VBAT'}:
            continue
        x, y, size, drill = Pcb.geom(b)
        layers = set()
        contacts = []
        for seg in p.blocks:
            if Pcb.kind(seg) != 'segment' or Pcb.net(seg) != net:
                continue
            a = Pcb.geom(seg)
            if pointseg((x, y), a[:2], a[2:4]) <= (size + a[4]) / 2 + 1e-6:
                layers.add(a[5])
                dx, dy = a[2] - a[0], a[3] - a[1]
                dd = dx * dx + dy * dy
                t = max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / dd)) if dd else 0
                contacts.append((a[0] + t * dx, a[1] + t * dy, a[4], a[5]))
        for fp in g.fps:
            for pd in fp['pads']:
                if pd['net'] == net and _in_pad(pd, x, y, size / 2):
                    layers.update(l for l in pd['layers'] if l in ('F.Cu', 'B.Cu'))
                    contacts.extend((pd['x'], pd['y'], 0.2, l) for l in pd['layers'] if l in ('F.Cu', 'B.Cu'))
        if len(layers) < 2:
            drop.add(b)
            bridges.extend((net, l, x, y, xx, yy, w) for xx, yy, w, l in contacts)
    p.blocks = [b for b in p.blocks if b not in drop]
    for net, l, x, y, xx, yy, w in bridges:
        p.add_track(net, l, x, y, xx, yy, w)
    return len(drop)


def pad_xy(g, ref, num):
    pd = _pad(g, ref, str(num))
    return pd['x'], pd['y']


def taps_of(p, pd):
    """the plane-tap stub and via hanging off a pad: a track from inside the pad
    to a same-net via, and that via"""
    net = pd['net']
    vias = [b for b in p.blocks if Pcb.kind(b) == 'via' and Pcb.net(b) == net]
    out = []
    for b in p.blocks:
        if Pcb.kind(b) != 'segment' or Pcb.net(b) != net:
            continue
        x1, y1, x2, y2, w, l = Pcb.geom(b)
        for (ax, ay), (bx, by) in (((x1, y1), (x2, y2)), ((x2, y2), (x1, y1))):
            if _in_pad(pd, ax, ay, w / 2):
                for v in vias:
                    vx, vy, s, d = Pcb.geom(v)
                    if math.hypot(bx - vx, by - vy) <= s / 2:
                        out += [b, v]
    return out


def symbol_uuid(ref):
    """the schematic conversion names its new symbols by this same uuid5"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'pixy-power-integrity/symbol/' + ref))


# ---------------------------------------------------------------- hand copper
def hand_copper(p, g):
    """the supply path and the switch's fine-pitch escapes, laid before any
    routing so the router cannot take their room"""
    def trk(net, layer, pts, w):
        for a, b in zip(pts, pts[1:]):
            p.add_track(net, layer, *a, *b, w)

    # BUCK_3V3 straight from L1.2 into U8 VIN, C26 beside it
    l12 = _pad(g, 'L1', '2')
    vin = pad_xy(g, 'U8', 1)
    trk('/BUCK_3V3', 'F.Cu', [(l12['x'] + l12['w'] / 2 - 0.3, vin[1]), vin], 0.4)
    c26 = pad_xy(g, 'C26', 1)
    trk('/BUCK_3V3', 'F.Cu', [c26, (c26[0], vin[1] - 0.2), (vin[0] - 0.2, vin[1] - 0.2)], 0.4)
    # BUCK_PASS: U8 VOUT -> Q2 source
    vout, src = pad_xy(g, 'U8', 6), pad_xy(g, 'Q2', 2)
    trk('/BUCK_PASS', 'F.Cu', [vout, (src[0], vout[1]), src], 0.45)
    # U8 GND: between the pad columns (0.65 mm apart, too narrow for a via
    # under the body) to a via just below the package
    gnd = pad_xy(g, 'U8', 2)
    ux8, uy8 = PARTS['U8']['pcb'][:2]
    trk('GND', 'F.Cu', [gnd, (ux8, gnd[1]), (ux8, uy8 + 1.55)], 0.2)
    p.add_via('GND', ux8, uy8 + 1.55)

    # U7's 0.65 mm pins: each signal pin escapes to its own via, staggered so
    # the vias keep 1.35 mm apart, before the long routes can fence them in
    # (the 2026-10-14 pattern, now relative to U7's centre)
    ux, uy = PARTS['U7']['pcb'][:2]
    def esc(num, pts, via=True, w=0.2):
        pd = _pad(g, 'U7', str(num))
        pts = [(pd['x'], pd['y'])] + [(ux + dx, uy + dy) for dx, dy in pts]
        trk(pd['net'], 'F.Cu', pts, w)
        if via:
            p.add_via(pd['net'], *pts[-1])
    esc(1, [(-3.3, -1.95), (-3.5, -2.15), (-4.2, -2.15)])
    esc(2, [(-5.7, -1.3)])
    esc(3, [(-3.2, -0.65), (-3.3, -0.55), (-4.2, -0.55)])
    esc(4, [(-3.7, 0.0), (-3.9, 0.2), (-5.7, 0.2)])
    esc(11, [(3.8, 0.0), (3.9, -0.1), (4.1, -0.1)])
    esc(10, [(5.65, 0.65)])
    esc(9, [(3.8, 1.3), (3.85, 1.35), (4.1, 1.35)])
    esc(8, [(3.8, 1.95), (3.95, 2.1), (5.65, 2.1)])
    esc(13, [(4.0, -1.3), (4.35, -1.65), (5.65, -1.65)])
    esc(12, [(3.8, -0.65), (3.8, -1.3)], via=False)
    esc(5, [(-3.1, 0.65), (-3.1, 1.3), (-4.2, 1.3)])
    esc(6, [(-3.1, 1.3)], via=False)
    c24 = pad_xy(g, 'C24', 1)
    esc(14, [(4.0, -1.95), (c24[0] - ux - 0.2, c24[1] - uy), (c24[0] - ux, c24[1] - uy)], via=False, w=0.3)


def c12_gnd_via(p, g):
    """move C12's GND via from north of its pad to east of it"""
    (ox, oy), (nx, ny) = C12_GND_VIA
    pad = pad_xy(g, 'C12', 2)
    assert pad == (134.0, 91.525), pad
    old = [b for b in p.blocks if Pcb.net(b) == 'GND' and (
        (Pcb.kind(b) == 'via' and Pcb.geom(b)[:2] == (ox, oy)) or
        (Pcb.kind(b) == 'segment' and {Pcb.geom(b)[:2], Pcb.geom(b)[2:4]} == {pad, (ox, oy)}))]
    assert len(old) == 2, old
    p.blocks = [b for b in p.blocks if b not in old]
    p.add_track('GND', 'F.Cu', *pad, nx, ny, 0.4)
    p.add_via('GND', nx, ny)
    return len(old)


# ---------------------------------------------------------------- the stage
def power_integrity(p, Router, placement_only=False):
    p.sync()
    motor_before = {Pcb.geom(b) for b in p.blocks if Pcb.net(b) in MOTOR}
    assert devkit._at(p, 'U1') == (162.7, 157.98, 180.0)
    assert '(property "Reference" "U6"' not in p.text
    a, b = p.footprint_span('R17')
    assert '2.2kOhm 1%' in p.text[a:b]

    # ---- every footprint and text edit first (pcbedit drops pending copper edits)
    a, b = p.footprint_span('U1')
    assert '"Pixy-M2:ESP32-S3-DevKitC-1_SMD_Sockets"' in p.text[a:b]
    for ref in ('R17', 'R18'):
        set_fields(p, ref, CURRENT_FIELDS)
    for (ref, num), net in DRIVER_NETS.items():
        devkit.set_pad_net(p, ref, num, '/' + net)
    for ref, num in BUCK_PADS:
        devkit.set_pad_net(p, ref, num, '/BUCK_3V3')
    devkit.set_pad_net(p, 'U1', '21', '/DEVKIT_5V')
    old_pads = {}
    g0 = Router(p).g
    for ref, (_lib, old_at, new_at) in PCB_MOVES.items():
        assert devkit._at(p, ref) == old_at, (ref, devkit._at(p, ref))
        old_pads[ref] = [dict(pd) for pd in g0.byref[ref]['pads']]
    added = ''.join(footprint(ref, d, symbol_uuid(ref)) for ref, d in PARTS.items())
    p.text = p.head + added + ''.join(p.blocks) + p.tail
    p._split()
    for ref, d in PARTS.items():
        if d['pcb'][2]:
            p.move_footprint(ref, *d['pcb'])
    for ref, (_lib, old_at, new_at) in PCB_MOVES.items():
        p.move_footprint(ref, *new_at)
    # designators on silkscreen: every new part except the test pads, which
    # (like TP1-TP4/TP9) carry a board text instead
    import silk_refs
    for ref in [r for r in PARTS if r.startswith('TP')]:
        silk_refs.set_ref_text(p, ref, *PARTS[ref]['pcb'][:2], 0, hide=True)
    for text, at in OLD_TP_TEXTS.items():
        silk_refs.drop_text(p, text, at)
    n_refs = silk_refs.place(p, [r for r in PARTS if not r.startswith('TP')] + ['C11', 'R19', 'R20', 'R21', 'C1', 'C2'],
                             labels=TP_LABELS, keep={'C11', 'R19', 'R20', 'R21', 'C1', 'C2'},
                             ics={'U6', 'U7', 'U8', 'Q2', 'Q3'})
    p.sync()

    # ---- copper: partition the old supply and control nets
    removed = 0
    new = []
    oldfb = []
    for b in p.blocks:
        net = Pcb.net(b)
        target = None
        if net in OLD_INPUTS:
            if inside(b, devkit.MOTOR_CORNER):
                target = OLD_INPUTS[net]
            else:
                removed += 1
                continue
        elif net == '/ESP_3V3' and inside(b, (130, 93, 148, 103)):
            target = '/BUCK_3V3'
            geom = Pcb.geom(b)
            if Pcb.kind(b) == 'segment' and abs(geom[4] - .2) < 1e-6 and math.dist(geom[:2], geom[2:4]) > .15:
                oldfb.append(geom)
        elif net == '/ESP_3V3' and inside(b, (100, 104, 128, 130)):
            if inside(b, devkit.MOTOR_CORNER):
                target = '/MOTOR_VREF'
            else:
                removed += 1
                continue
        elif net == '/ESP_3V3' and Pcb.kind(b) == 'segment':
            g_ = Pcb.geom(b)
            # the two old feeds to J8.4 straddle the motor-corner boundary
            if min(g_[0], g_[2]) < 128 and 104 < min(g_[1], g_[3]) and max(g_[1], g_[3]) < 130:
                removed += 1
                continue
        if target:
            b = b.replace('(net "' + net + '")', '(net "' + target + '")')
        new.append(b)
    p.blocks = new
    p.sync()
    r = devkit.make_router(Router, p)
    # C7/C11 lose their 3V3 plane taps (now one-layer BUCK_3V3 holes) and the
    # moved test pads their old taps
    gone = set()
    for ref in ('C7', 'C11'):
        gone |= set(taps_of(p, _pad(r.g, ref, '1')))
    for ref, pads in old_pads.items():
        for pd in pads:
            gone |= set(taps_of(p, pd))
    p.blocks = [b for b in p.blocks if b not in gone]
    removed += len(gone)

    for rule in NEW_RULES:
        if rule not in devkit.WIDE_RULES:
            devkit.WIDE_RULES.append(rule)
    p.sync()
    r = devkit.make_router(Router, p)
    count, hit = rip_conflicts(p, r.g, list(PARTS) + list(PCB_MOVES))
    seg_ends = {(round(x, 3), round(y, 3)) for b in p.blocks if Pcb.kind(b) == 'segment'
                for x, y in (Pcb.geom(b)[:2], Pcb.geom(b)[2:4])}
    bare = [b for b in p.blocks if Pcb.kind(b) == 'via' and Pcb.net(b) == 'GND'
            and (round(Pcb.geom(b)[0], 3), round(Pcb.geom(b)[1], 3)) not in seg_ends
            and any(touches(b, box) for box in CLUSTERS.values())]
    p.blocks = [b for b in p.blocks if b not in bare]
    count += len(bare)
    count += devkit.drop_vias_under(p, r.g, list(PARTS) + list(PCB_MOVES))
    # whole-net rip of every re-routable net the clusters displace
    for b in p.blocks:
        n = Pcb.net(b)
        if (n in REROUTABLE or n in PARTIAL) and any(touches(b, box, 0.3) for box in CLUSTERS.values()):
            hit.add(n)
    hit |= I2C                    # SCL takes the lane C12's moved GND via opens
    ripped = set()
    for n in sorted(hit):
        if n in REROUTABLE:
            removed += p.drop(lambda b, n=n: Pcb.net(b) == n)
            ripped.add(n)
        elif n in PARTIAL:
            removed += p.drop(lambda b, n=n: Pcb.net(b) == n and not inside(b, devkit.MOTOR_CORNER))
            ripped.add(n)
    p.sync()
    r = devkit.make_router(Router, p)
    removed += c12_gnd_via(p, r.g)
    hand_copper(p, r.g)
    p.sync()
    print('  power integrity:', len(PARTS), 'parts;', removed, 'old copper items removed;',
          n_refs, 'reference texts placed; ripped whole:', sorted(ripped))
    if placement_only:
        return True

    ok = True
    def route(net, w=0.2, label=None):
        nonlocal ok
        r_ = devkit.make_router(Router, p)
        res = devkit.route_net(r_, net, w)
        print(' ', label or net, res, flush=True)
        ok &= res
        return res

    # 1. the clusters' own nets, short and local
    for net in ('/BUCK_3V3', '/BUCK_PASS', '/BUCK_GATE', '/BUCK_ENABLE', '/USB_PRIORITY',
                '/MOTOR_UVLO'):
        route(net)
    # 2. the long new runs: reference to the drivers, enable to the switch,
    #    GPIO39-42 to the switch, its outputs to the drivers, the sense feeds
    route('/MOTOR_VREF', 0.25)
    route('/MOTOR_OK')
    for net in ('/GPIO39', '/GPIO40', '/GPIO41', '/GPIO42',
                '/DRV_A_IN1', '/DRV_A_IN2', '/DRV_B_IN1', '/DRV_B_IN2'):
        route(net)
    r = devkit.make_router(Router, p)
    res = r.route('/VBAT', 0.3, [r.pad_group('R24', '1', 0.3), r.pad_group('R10', '1', 0.3)])
    print('  /VBAT R10.1 -> R24', res, flush=True)
    ok &= res
    route('/DEVKIT_5V')
    # 3. the displaced signals, in the devkit stage's order
    for net in [n for n in devkit.ORDER if n in ripped] + sorted(ripped - set(devkit.ORDER)):
        route(net)
    # 4. plane taps for every new or moved part, then any original pad whose tap went
    # (U8's GND pin is tapped by hand, between its pad columns)
    r = devkit.make_router(Router, p)
    ok &= devkit.plane_taps(r, [ref for ref in list(PARTS) + list(PCB_MOVES) + ['J8'] if ref != 'U8'])
    r = devkit.make_router(Router, p)
    ok &= devkit.plane_taps(r, [ref for ref in r.g.byref if ref not in ('U4', 'U5', 'U8')])
    p.sync()
    r = devkit.make_router(Router, p)
    nets = ripped | {Pcb.net(b) for b in p.blocks} - devkit.PLANE_NETS - MOTOR - SW
    nets = {n for n in nets if n and n not in ('/REG_EN', '/VSYS', '/VBAT_SENSE')}
    print('  pruned', devkit.prune_strict(p, r.g, nets), 'dangling items')
    print('  removed', drop_unused_signal_vias(p, r.g), 'unused signal vias')
    print('  pruned', devkit.prune_strict(p, r.g, nets), 'tails of removed vias')
    p.sync()
    if debug_path := os.environ.get('PIXY_POWER_CHECKPOINT'):
        p.write(debug_path)
    if not ok:
        p.write(str(Path(tempfile.gettempdir()) / 'pixy-power-integrity-failed.kicad_pcb'))
        raise RuntimeError('power-integrity routing failed')
    assert motor_before == {Pcb.geom(b) for b in p.blocks if Pcb.net(b) in MOTOR}
    for geom in oldfb:
        assert any(Pcb.net(b) == '/BUCK_3V3' and Pcb.geom(b) == geom for b in p.blocks), geom
    return True


def main(src, dst, placement_only=False):
    import rework
    p = Pcb(src)
    power_integrity(p, rework.Router, placement_only)
    p.write(dst)
    print('wrote', dst)


if __name__ == '__main__':
    args = sys.argv[1:]
    only = '--placement-only' in args
    if only:
        args.remove('--placement-only')
    main(*(args or [str(ROOT / 'Pixy-M2.kicad_pcb')] * 2), placement_only=only)
