"""J8/J9 -> JST SH in the Pololu encoder's own pin order (2026-09-23).

Runs after issue8.py.  The schematic moved J8/J9 from 2.0 mm JST PH
(M1 GND A B VCC M2) to SM06B-SRSS-TB, the same 1.0 mm SH part as J4-J7, wired
in the order of the Pololu 12 CPR encoder board that ships on the micro metal
gearmotors (#4760/#4761, #5153-#5165):

    1 GND   2 OUT B   3 OUT A   4 VCC   5 M2   6 M1      MP GND

so the motor plugs in with Pololu's own SH-SH cable (#4766-#4769) and no
re-pinning.  This stage makes the board match:

  1  swaps the two PH footprints for SH ones cloned from J4, keeping each
     connector's rotation (the cable still leaves toward its motor) and
     sitting inside the old connector's courtyard;
  2  rips the motor trunks back to the driver escapes, then drops every
     other copper item the new SMD pads land on (the PH part was through-hole,
     so GPIO2/39/40 ran between its pins) and prunes whatever that leaves
     dangling, back to the nearest pad, via or junction;
  3  lays 0.6 mm fan-in stubs on M1/M2: the pins are 1.0 mm apart, so two
     0.8 mm trunks cannot both reach them, and 0.6 mm is the Motor rule floor;
  4  routes the motor trunks at 0.8 mm, M1 first and M2 paired along it --
     the two pins are now adjacent, so both channels pair (review issue 4);
  5  reconnects every other net it cut, component to component, at 0.2 mm;
  6  stitches GND (pin 1 and both MP pads) and VCC (pin 4) into the planes.
"""
import math, os, re, sys, uuid
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board import ROUTE, disc_mask, seg_disc_stamp, stamp
from pcbedit import Pcb, fx
from loop import polyline

TRUNK, FAN, SIGNAL = 0.8, 0.6, 0.2
PLANE_NETS = {'GND', '/ESP_3V3', '/VBAT'}
MOTOR_NETS = {'/MOT_A_1', '/MOT_A_2', '/MOT_B_1', '/MOT_B_2'}
PAD_CLEAR = 0.2          # copper of another net closer than this to a new pad is ripped

# (x, y, rot): rot kept from the PH part so each cable still exits toward its
# motor.  Both sit inside the old PH courtyard.  J9's x is the eastmost that
# stays clear of the 0.6 mm /VBUS run along x = 160.
PLACE = {'J8': (110.0, 125.5, 180), 'J9': (160.0, 103.4, 90)}
PINS = {
    'J8': {'1': 'GND', '2': '/GPIO48', '3': '/GPIO47', '4': '/ESP_3V3',
           '5': '/MOT_A_2', '6': '/MOT_A_1', 'MP': 'GND'},
    'J9': {'1': 'GND', '2': '/GPIO38', '3': '/GPIO21', '4': '/ESP_3V3',
           '5': '/MOT_B_2', '6': '/MOT_B_1', 'MP': 'GND'},
}
DESC = ('Motor {m} + encoder (Pololu micro metal gearmotor, 12 CPR encoder). Pololu pin order: '
        '1=GND 2=OUTB 3=OUTA 4=VCC 5=M2 6=M1. Straight SH-SH cable (Pololu #4766-4769).')
# driver escape end points (rework.escapes): OUT1 -> pin 6 (M1), OUT2 -> pin 5 (M2)
BREAKOUTS = {'J8': {'/MOT_A_1': (112.45, 114.25), '/MOT_A_2': (110.3, 112.4)},
             'J9': {'/MOT_B_1': (120.45, 114.25), '/MOT_B_2': (118.3, 112.4)}}


# ---------------------------------------------------------------- footprints
def _clone(p, ref, x, y, rot):
    """J4's placed SH footprint, re-linked to `ref`'s schematic symbol"""
    i, j = p.footprint_span('J4')
    tmpl = p.text[i:j]
    oi, oj = p.footprint_span(ref)
    old = p.text[oi:oj]
    path = re.search(r'\n\t\t\(path "[^"]+"\)', old).group(0)
    blk = re.sub(r'\n\t\t\(path "[^"]+"\)', lambda _: path, tmpl, count=1)
    blk = re.sub(r'\(uuid "[^"]+"\)', lambda _: f'(uuid "{uuid.uuid4()}")', blk)
    blk = blk.replace('(property "Reference" "J4"', f'(property "Reference" "{ref}"')
    blk = re.sub(r'\(property "Description" "[^"]*"',
                 lambda _: '(property "Description" "%s"' % DESC.format(m='A' if ref == 'J8' else 'B'),
                 blk, count=1)

    def pad_net(m):
        num = m.group(1)
        return re.sub(r'\(net "[^"]*"\)', f'(net "{PINS[ref][num]}")', m.group(0), count=1)
    blk = re.sub(r'\t\t\(pad "(\w+)" .*?\n\t\t\)\n', pad_net, blk, flags=re.S)
    assert blk.count('(pad "') == 8
    p.text = p.text[:oi] + blk + p.text[oj:]
    p._split()
    p.move_footprint(ref, x, y, rot)


# ---------------------------------------------------------------- geometry
def _pads(g, net=None):
    for f in g.fps:
        for pd in f['pads']:
            if net is None or pd['net'] == net:
                yield f['ref'], pd


def _in_pad(pd, x, y, margin=0.0):
    dx, dy = x - pd['x'], y - pd['y']
    if pd['shape'] == 'circle':
        return math.hypot(dx, dy) <= pd['w'] / 2 + margin
    a = math.radians(pd['rot'])
    u = dx * math.cos(a) - dy * math.sin(a)
    v = dx * math.sin(a) + dy * math.cos(a)
    return abs(u) <= pd['w'] / 2 + margin and abs(v) <= pd['h'] / 2 + margin


def _pad_seg_gap(pd, x1, y1, x2, y2, hw):
    """copper gap between a pad (as a rotated rect) and a track of half-width hw"""
    n = max(2, int(math.hypot(x2 - x1, y2 - y1) / 0.02))
    a = math.radians(pd['rot'])
    best = 1e9
    for i in range(n + 1):
        t = i / n
        dx, dy = x1 + (x2 - x1) * t - pd['x'], y1 + (y2 - y1) * t - pd['y']
        u = dx * math.cos(a) - dy * math.sin(a)
        v = dx * math.sin(a) + dy * math.cos(a)
        best = min(best, math.hypot(max(abs(u) - pd['w'] / 2, 0), max(abs(v) - pd['h'] / 2, 0)))
    return best - hw


def _pt_seg(px, py, x1, y1, x2, y2):
    L2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / L2))
    return math.hypot(px - x1 - t * (x2 - x1), py - y1 - t * (y2 - y1))


def _layers(pd):
    return [l for l in ROUTE if l in pd['layers'] or '*.Cu' in pd['layers']]


# ---------------------------------------------------------------- rip + prune
def dangling(p, g, nets):
    """segments with a free end, and vias with too little on them.  A free end
    touches no pad, via or other track of its net.  On the plane nets this also
    matches every bare stitching via, which is why prune() subtracts a baseline."""
    out = set()
    for net in nets:
        sg = [(b, Pcb.geom(b)) for b in p.blocks if Pcb.kind(b) == 'segment' and Pcb.net(b) == net]
        vg = [(b, Pcb.geom(b)) for b in p.blocks if Pcb.kind(b) == 'via' and Pcb.net(b) == net]
        pads = [pd for _, pd in _pads(g, net)]
        for b, (x1, y1, x2, y2, w, l) in sg:
            for (px, py) in ((x1, y1), (x2, y2)):
                # an end whose copper overlaps a pad or via is connected: the
                # router can finish a 0.8 mm track 0.36 mm from a 0.6 mm via
                ov = w / 2 - 0.02
                if any(l in _layers(pd) and _in_pad(pd, px, py, ov) for pd in pads): continue
                if any(math.hypot(px - vx, py - vy) <= s / 2 + ov for _, (vx, vy, s, d) in vg): continue
                # a shared end, or a T onto a segment that is not this one's
                # neighbour: the router's 0.05 mm staircase steps each lie within
                # half a width of the next, so a looser test calls a dead spur live
                ends = {(x1, y1), (x2, y2)}
                if any(o is not b and ol == l and (
                        math.dist((px, py), (ox1, oy1)) < 1e-3 or math.dist((px, py), (ox2, oy2)) < 1e-3 or
                        (not ends & {(ox1, oy1), (ox2, oy2)} and
                         _pt_seg(px, py, ox1, oy1, ox2, oy2) <= ow / 2 + 1e-3))
                       for o, (ox1, oy1, ox2, oy2, ow, ol) in sg): continue
                out.add(b)
                break
        for b, (vx, vy, s, d) in vg:
            touched = {l for _, (x1, y1, x2, y2, w, l) in sg
                       if _pt_seg(vx, vy, x1, y1, x2, y2) <= s / 2 + w / 2}
            touched |= {l for pd in pads for l in _layers(pd) if _in_pad(pd, vx, vy)}
            # a plane via needs one track; a signal via has to join two layers
            if len(touched) < (1 if net in PLANE_NETS else 2):
                out.add(b)
    return out


ZONE_MARGIN = 2.0


def _zone(g, ref):
    """the footprint's pad extent plus ZONE_MARGIN -- pad edges, not centres,
    or a 7 mm pad (F1) leaves a track under its own edge outside the zone"""
    pads = g.byref[ref]['pads']
    r = [max(q['w'], q['h']) / 2 for q in pads]
    return (min(q['x'] - e for q, e in zip(pads, r)) - ZONE_MARGIN,
            min(q['y'] - e for q, e in zip(pads, r)) - ZONE_MARGIN,
            max(q['x'] + e for q, e in zip(pads, r)) + ZONE_MARGIN,
            max(q['y'] + e for q, e in zip(pads, r)) + ZONE_MARGIN)


def _near(b, zones):
    g = Pcb.geom(b)
    pts = [(g[0], g[1]), (g[2], g[3])] if Pcb.kind(b) == 'segment' else [(g[0], g[1])]
    return any(z[0] <= x <= z[2] and z[1] <= y <= z[3] for z in zones for x, y in pts)


def prune(p, g, nets, baseline, zones):
    """drop what this stage left dangling, repeatedly, but only near the new
    connectors: a spur cut under a pad row is trimmed back to the zone edge and
    reconnected from there, instead of eaten back to a 0.5 mm pin field the
    router cannot escape again.  `baseline` is what already matched dangling()
    before the stage started (zone-fed stubs, bare plane vias)."""
    total = 0
    while True:
        drop = {b for b in dangling(p, g, nets) - baseline if _near(b, zones)}
        if not drop:
            return total
        p.blocks = [b for b in p.blocks if b not in drop]
        total += len(drop)


def rip_conflicts(p, g, refs):
    """drop other-net copper that overlaps (or crowds) the new SMD pads"""
    new = [pd for r in refs for pd in g.byref[r]['pads']]
    hit, nets = set(), set()
    for b in p.blocks:
        n = Pcb.net(b)
        if Pcb.kind(b) == 'segment':
            x1, y1, x2, y2, w, l = Pcb.geom(b)
            if l != 'F.Cu': continue
            if any(pd['net'] != n and _pad_seg_gap(pd, x1, y1, x2, y2, w / 2) < PAD_CLEAR for pd in new):
                hit.add(b); nets.add(n)
        elif Pcb.kind(b) == 'via':
            vx, vy, s, d = Pcb.geom(b)
            if any(pd['net'] != n and _pad_seg_gap(pd, vx, vy, vx, vy, s / 2) < PAD_CLEAR for pd in new):
                hit.add(b); nets.add(n)
    p.blocks = [b for b in p.blocks if b not in hit]
    return len(hit), nets


# ---------------------------------------------------------------- reconnect
def components(p, g, net):
    """connected groups of a signal net's pads, tracks and vias, as Router groups"""
    items = []   # (kind, geom)
    for ref, pd in _pads(g, net):
        items.append(('pad', pd))
    for b in p.blocks:
        if Pcb.net(b) != net: continue
        items.append((Pcb.kind(b), Pcb.geom(b)))
    n = len(items)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def touch(a, b):
        ka, ga = a; kb, gb = b
        if ka == 'segment' and kb == 'segment':
            if ga[5] != gb[5]: return False
            return min(_pt_seg(ga[0], ga[1], *gb[:4]), _pt_seg(ga[2], ga[3], *gb[:4]),
                       _pt_seg(gb[0], gb[1], *ga[:4]), _pt_seg(gb[2], gb[3], *ga[:4])) <= max(ga[4], gb[4]) / 2
        if ka == 'pad' and kb == 'pad': return False
        if kb == 'pad': a, b, ka, kb, ga, gb = b, a, kb, ka, gb, ga
        if ka == 'pad':
            if kb == 'segment':
                return gb[5] in _layers(ga) and (_in_pad(ga, gb[0], gb[1]) or _in_pad(ga, gb[2], gb[3]))
            return bool(_layers(ga)) and _in_pad(ga, gb[0], gb[1], gb[2] / 2)
        if ka == 'via' and kb == 'via':
            return math.hypot(ga[0] - gb[0], ga[1] - gb[1]) <= (ga[2] + gb[2]) / 2
        if ka == 'via': a, b, ka, kb, ga, gb = b, a, kb, ka, gb, ga
        return _pt_seg(gb[0], gb[1], *ga[:4]) <= ga[4] / 2 + gb[2] / 2
    for i in range(n):
        for j in range(i + 1, n):
            if touch(items[i], items[j]):
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(items[i])
    return list(groups.values())


def _group(g, members):
    from board import NX, NY
    m = {l: np.zeros((NY, NX), bool) for l in ROUTE}
    pts = []
    for k, gm in members:
        if k == 'pad':
            sel = g.pad_sel(gm, -0.15)
            if sel is None or not sel[4].any():
                sel = disc_mask(gm['x'], gm['y'], 0.05)
            for l in _layers(gm):
                iy0, iy1, ix0, ix1, mm = sel
                m[l][iy0:iy1 + 1, ix0:ix1 + 1] |= mm
            pts.append((gm['x'], gm['y'], 0.1))
        elif k == 'segment':
            x1, y1, x2, y2, w, l = gm
            if l in m:
                seg_disc_stamp(m[l].view(np.int8), x1, y1, x2, y2, min(w / 2, 0.1), 1)
                pts += [(x1, y1, 0.1), (x2, y2, 0.1)]
        else:
            x, y, s, d = gm
            for l in ROUTE:
                stamp(m[l].view(np.int8), disc_mask(x, y, min(s / 2, 0.15)), 1)
            pts.append((x, y, 0.1))
    return dict(m=m, pts=pts)


def reconnect(r, net, w=SIGNAL):
    comps = components(r.p, r.g, net)
    if len(comps) < 2:
        return True
    return r.route(net, w, [_group(r.g, c) for c in comps])


# ---------------------------------------------------------------- motor copper
def _pad(g, ref, num):
    return next(pd for pd in g.byref[ref]['pads'] if pd['num'] == num)


def fan_in(r, ref):
    """0.6 mm stubs out of pins 5 (M2) and 6 (M1), splayed to 1.3 mm centres so
    two 0.8 mm trunks fit.  Returns {net: stub end}."""
    g = r.g
    p5, p6 = _pad(g, ref, '5'), _pad(g, ref, '6')
    fx_, fy_, rot = PLACE[ref]
    a = math.radians(rot)
    # outward = away from the housing = local -y, turned into the board frame
    ux, uy = -math.sin(a), -math.cos(a)
    vx, vy = p6['x'] - p5['x'], p6['y'] - p5['y']
    L = math.hypot(vx, vy); vx, vy = vx / L, vy / L
    ends = {}
    x, y = p5['x'], p5['y']
    e5 = (x + 1.3 * ux, y + 1.3 * uy)
    r.track(p5['net'], 'F.Cu', x, y, *e5, FAN)
    x, y = p6['x'], p6['y']
    k6 = (x + 1.0 * ux, y + 1.0 * uy)
    e6 = (x + 1.3 * ux + 0.3 * vx, y + 1.3 * uy + 0.3 * vy)
    r.track(p6['net'], 'F.Cu', x, y, *k6, FAN)
    r.track(p6['net'], 'F.Cu', *k6, *e6, FAN)
    ends[p5['net']], ends[p6['net']] = e5, e6
    return ends, (ux, uy)


def motor(r, ref, pair_waypoints):
    ends, _ = fan_in(r, ref)
    m1, m2 = sorted(BREAKOUTS[ref])          # *_1 = M1 = pin 6, *_2 = M2 = pin 5
    res = {}
    start = r.point_group(*BREAKOUTS[ref][m1], ['F.Cu'], r=0.2)
    res[m1] = r.route(m1, TRUNK, [start, r.point_group(*ends[m1], ['F.Cu'], r=0.2)])
    wps = []
    if res[m1]:
        pts = polyline(r.p, m1, BREAKOUTS[ref][m1], ends[m1])
        side = (ends[m2][0] - ends[m1][0], ends[m2][1] - ends[m1][1])
        wps = pair_waypoints(pts, side)
    start = r.point_group(*BREAKOUTS[ref][m2], ['F.Cu'], r=0.2)
    end = r.point_group(*ends[m2], ['F.Cu'], r=0.2)
    # waypoints pinned to F.Cu: Router.route_waypoints offers each one on both
    # layers, so two legs can meet on different layers with no via (issue8.py)
    prev, used = start, 0
    for (x, y) in wps:
        if r.route(m2, TRUNK, [prev, r.point_group(x, y, ['F.Cu'], r=0.2)], quiet=True):
            prev, used = r.point_group(x, y, ['F.Cu'], r=0.2), used + 1
    res[m2] = r.route(m2, TRUNK, [prev, end])
    return res, used


# ---------------------------------------------------------------- stage
# The In2 VBAT island (x 100.5-127, y 88-122) sits under U4, so U4's VREF has
# no 3V3 plane beneath it; it was fed by a B.Cu run to the old through-hole
# J8 pin 5.  Any /ESP_3V3 piece left with no via outside the island is routed
# to the new J8 pin 4 instead.
VBAT_ISLAND = (100.5, 88.0, 127.0, 122.0)
RIPROPI = {'R17': 'GPIO2 (ADC1_CH1)', 'R18': 'GPIO10 (ADC1_CH9)'}


def _set_prop(p, ref, prop, value):
    i, j = p.footprint_span(ref)
    blk, n = re.subn(r'(\(property "%s" )"[^"]*"' % prop, lambda m: m.group(1) + '"%s"' % value,
                     p.text[i:j], count=1)
    assert n == 1, (ref, prop)
    p.text = p.text[:i] + blk + p.text[j:]
    p._split()


def plane_vias(p, net, x, y, radius, avoid=None):
    """existing vias of a plane net near (x, y): any of them already reaches the
    plane, so a pad or a cut-off piece can be tied to the nearest one instead of
    routed across the board to a particular pad"""
    out = []
    for b in p.blocks:
        if Pcb.kind(b) != 'via' or Pcb.net(b) != net: continue
        vx, vy, sz, dr = Pcb.geom(b)
        if math.hypot(vx - x, vy - y) > radius: continue
        if avoid and avoid[0] <= vx <= avoid[2] and avoid[1] <= vy <= avoid[3]: continue
        out.append(('via', (vx, vy, sz, dr)))
    return out


def orphan_3v3(r):
    net = '/ESP_3V3'
    x0, y0, x1, y1 = VBAT_ISLAND
    ok = True
    for c in components(r.p, r.g, net):
        feeds = [gm for k, gm in c if (k == 'via' and not (x0 <= gm[0] <= x1 and y0 <= gm[1] <= y1))
                 or (k == 'pad' and gm['drill'])]
        if feeds or not any(k != 'pad' for k, _ in c):
            continue
        cx = sum(gm['x'] if k == 'pad' else gm[0] for k, gm in c) / len(c)
        cy = sum(gm['y'] if k == 'pad' else gm[1] for k, gm in c) / len(c)
        feeds = plane_vias(r.p, net, cx, cy, 15.0, avoid=VBAT_ISLAND)
        res = r.route(net, 0.3, [_group(r.g, c), _group(r.g, feeds + [('pad', _pad(r.g, 'J8', '4'))])])
        print(f'  /ESP_3V3 island piece -> J8.4 {"ok" if res else "FAILED"}')
        ok &= res
    return ok


def pololu_conn(p, Router, pair_waypoints, drill_bar):
    p.sync()
    # ITRIP = 3.3 / (1500e-6 * 2200) = 1.00 A: the JST SH contacts' rating
    for ref in RIPROPI:
        _set_prop(p, ref, 'Value', '2.2kOhm 1%')
        _set_prop(p, ref, 'Description', 'RIPROPI. ITRIP = VREF/(AIPROPI*R) = 3.3/(1500u*2200) = '
                  '1.00A (JST SH contact rating 1A); sense scale 3.3 V/A.')
    # every net the swap can touch: the connectors' own, and anything whose
    # top copper or vias run through the new pad rows
    baseline = dangling(p, Router(p).g, {n for b in p.blocks if (n := Pcb.net(b))})
    for ref, (x, y, rot) in PLACE.items():
        _clone(p, ref, x, y, rot)
    # motor trunks go whole; the driver escapes (all under 0.6 mm) stay
    n = p.drop(lambda b: Pcb.net(b) in MOTOR_NETS and
               (Pcb.kind(b) == 'via' or Pcb.geom(b)[4] >= 0.6))
    r = Router(p)
    k, hit_nets = rip_conflicts(p, r.g, PLACE)
    cut = ({v for ref in PINS for v in PINS[ref].values()} | hit_nets) - MOTOR_NETS
    zones = [_zone(r.g, ref) for ref in PLACE]
    pr = prune(p, r.g, cut, baseline, zones)
    print(f'  ripped {n} motor trunk items, {k} items under the new pads '
          f'({", ".join(sorted(hit_nets))}), pruned {pr} dangling')
    r = Router(p)
    drill_bar(r)
    ok = True
    for ref in PLACE:
        res, nw = motor(r, ref, pair_waypoints)
        print(f'  {ref}: ' + ', '.join(f'{k_} {"ok" if v else "FAILED"}' for k_, v in res.items())
              + (f' (paired, {nw} waypoints)' if nw else ''))
        ok &= all(res.values())
    for net in sorted(cut - PLANE_NETS):
        res = reconnect(r, net)
        print(f'  {net} reconnected' if res else f'  {net} FAILED')
        ok &= res
    for ref in PLACE:
        g = r.g
        fx_, fy_, rot = PLACE[ref]
        a = math.radians(rot)
        ux, uy = -math.sin(a), -math.cos(a)
        vcc = _pad(g, ref, '4')
        ok &= r.stitch(vcc['net'], vcc['x'] + 0.5 * ux, vcc['y'] + 0.5 * uy, (ux, uy),
                       w=0.3, maxr=4.0) is not None
        # GND is pin 1 plus both MP pads: give each its own via where one fits,
        # then tie any that got none to those that did
        gnd = [q for q in g.byref[ref]['pads'] if q['net'] == 'GND']
        fed, unfed = [], []
        for pd in gnd:
            if pd['num'] == 'MP':
                spot = r.stitch('GND', pd['x'], pd['y'], (0, 0), w=0.3, maxr=6.0)
            else:     # inside the 1.55 mm pad, heading away from the housing
                spot = r.stitch('GND', pd['x'] + 0.5 * ux, pd['y'] + 0.5 * uy, (ux, uy), w=0.3, maxr=4.0)
            (fed if spot else unfed).append(pd)
        if not fed:
            ok = False
        for pd in unfed:
            tgt = _group(r.g, [('pad', q) for q in fed] + plane_vias(r.p, 'GND', pd['x'], pd['y'], 8.0))
            res = r.route('GND', 0.3, [_group(r.g, [('pad', pd)]), tgt])
            print(f"    {ref}.{pd['num']} ({pd['x']:.1f},{pd['y']:.1f}) tied to the nearest stitched pad or GND via"
                  if res else f"    {ref}.{pd['num']} GND FAILED")
            ok &= res
            if res:
                fed.append(pd)
    ok &= orphan_3v3(r)
    extra = prune(p, r.g, cut | MOTOR_NETS, baseline, zones)
    if extra:
        print(f'  pruned {extra} spurs left after routing')
    return ok
