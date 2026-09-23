"""Copper that the issue-8 rule set requires — REVIEW.md issue 8.

Runs after usb_pair.py.  The rules themselves live in Pixy-M2.kicad_pro (the
Power/Battery netclasses) and Pixy-M2.kicad_dru; this stage makes the board meet
them, and it is the only thing that changes when they are introduced.

  signals   The global minimum was 0.15 mm, and the router had used it for the
            whole length of five nets that only need it inside the DRV8231A's
            0.5 mm pin field: IN1/IN2 (GPIO39-41) and IPROPI (GPIO2, GPIO10).
            Every segment is split at the 'Motor pin escape' rule areas and
            widened to 0.2 mm outside them.  One corner of GPIO41 doglegs 0.3 mm
            to clear the GPIO47 via issue 6 moved beside it.

  USB power The whole USB supply, connector -> F2 -> D1, was 0.24 mm: 50 mm of
            /VBUS and every Net-(F2-Pad1) branch.  It carries the board's entire
            load on USB (F2 holds 0.5 A, trips at 1 A).  Re-routed at 0.6 mm.
            The D3 tap (VBUS -> D3 -> R9 -> REG_EN) is 0.5 mm and pinned to its old
            corridor along the top edge: left to itself A* takes it through the
            buck block, 0.5 mm from C6's switch-node pad, which would couple the
            SW node straight into the enable divider.

  battery   The R14 gate pull-up tap on /VBAT_FUSED was 0.2 mm.  Re-routed at
            0.8 mm, the Battery netclass minimum.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcbedit import Pcb

SIGNAL_MIN = 0.2
PIN_FIELDS = [(107.0, 112.0, 112.9, 116.0), (115.0, 112.0, 120.9, 116.0)]  # = rework.ESCAPE_AREAS
NARROW_NETS = ('/GPIO2', '/GPIO10', '/GPIO39', '/GPIO40', '/GPIO41')
# GPIO41's diagonal passed 0.18 mm from the GPIO47 via at (117.875, 132.05)
# once widened; turning 0.3 mm earlier leaves 0.4 mm.
GPIO41_OLD = ((118.7, 132.05), (116.05, 129.4))
GPIO41_NEW = [(118.7, 132.05), (118.7, 131.75), (116.35, 129.4), (116.05, 129.4)]

POWER_W, TAP_W, BATTERY_W = 0.6, 0.5, 0.8
VIA_PAD_MARGIN = 0.15 + 0.10 + 0.05     # drill radius + issue-6 floor + grid step
U2_BOX = (153.4, 147.8, 156.7, 149.7)      # usb_pair's VBUS stubs under/beside U2
U2_VBUS_TAIL = ((155.4, 149.45), (156.65, 148.05))
D3_CORRIDOR = [(150.0, 89.3), (136.0, 89.3)]
# only place a Power-class track may be narrower than 0.5 mm: U2's VBUS pin
# (5) leaves under the package between the two pin rows (usb_pair.py)
POWER_ESCAPE = (152.9, 148.5, 155.7, 150.1)


def _in(box, x, y):
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _clip(x1, y1, x2, y2, areas):
    """split a segment at the area edges -> [((x1,y1,x2,y2), inside), ...]"""
    ts = {0.0, 1.0}
    for a in areas:
        for k, v in ((0, a[0]), (0, a[2]), (1, a[1]), (1, a[3])):
            p1, p2 = (x1, y1)[k], (x2, y2)[k]
            if p1 != p2 and 0 < (v - p1) / (p2 - p1) < 1:
                ts.add(round((v - p1) / (p2 - p1), 9))
    ts = sorted(ts)
    out = []
    for t0, t1 in zip(ts, ts[1:]):
        tm = (t0 + t1) / 2
        xm, ym = x1 + (x2 - x1) * tm, y1 + (y2 - y1) * tm
        out.append(((x1 + (x2 - x1) * t0, y1 + (y2 - y1) * t0,
                     x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1),
                    any(_in(a, xm, ym) for a in areas)))
    return out


# DRC's enclosedByArea tests a track's whole outline, round caps included, so a
# segment clipped exactly at an area edge sticks out by half its width.  Clip at
# the areas shrunk by more than that.  The areas are on F.Cu only; B.Cu copper
# under the drivers has room for 0.2 mm and is widened everywhere.
CLIP_INSET = 0.1
PIN_FIELDS_INNER = [(a + CLIP_INSET, b + CLIP_INSET, c - CLIP_INSET, d - CLIP_INSET)
                    for a, b, c, d in PIN_FIELDS]


def widen_signals(p):
    def is_old41(b):
        if Pcb.net(b) != '/GPIO41' or Pcb.kind(b) != 'segment': return False
        g = Pcb.geom(b)
        return {(g[0], g[1]), (g[2], g[3])} == set(GPIO41_OLD)
    assert p.drop(is_old41) == 1, 'GPIO41 corner moved; re-check the dogleg'
    for a, b in zip(GPIO41_NEW, GPIO41_NEW[1:]):
        p.add_track('/GPIO41', 'F.Cu', *a, *b, SIGNAL_MIN)
    narrow = [b for b in p.blocks if Pcb.kind(b) == 'segment' and Pcb.net(b) in NARROW_NETS
              and Pcb.geom(b)[4] < SIGNAL_MIN]
    drop = set(narrow)
    p.blocks = [b for b in p.blocks if b not in drop]
    n = 0
    for b in narrow:
        x1, y1, x2, y2, w, layer = Pcb.geom(b)
        areas = PIN_FIELDS_INNER if layer == 'F.Cu' else []
        for seg, inside in _clip(x1, y1, x2, y2, areas):
            p.add_track(Pcb.net(b), layer, *seg, w if inside else SIGNAL_MIN)
            n += not inside
    return n


def _drill_clear_of_pads(r, margin=VIA_PAD_MARGIN):
    """G bars via centres from 0.15 mm round each SMD pad, which lets a 0.3 mm
    drill touch the mask opening.  Issue 6 set a 0.10 mm drill-to-opening floor
    (via_openings.py); rebuild the bar at drill radius + 0.10 mm + one grid step
    for this stage only, so earlier stages still replay unchanged."""
    import numpy as np
    r.g.smd_block = np.zeros_like(r.g.smd_block)
    for f in r.g.fps:
        for pd in f['pads']:
            if pd['drill'] or not any(l in pd['layers'] for l in ('F.Cu', 'B.Cu')): continue
            sel = r.g.pad_sel(pd, margin)
            if sel:
                iy0, iy1, ix0, ix1, m = sel
                r.g.smd_block[iy0:iy1 + 1, ix0:ix1 + 1] |= m


def power_paths(p, Router):
    def ripped(b):
        n = Pcb.net(b)
        if n == 'Net-(F2-Pad1)': return True
        g = Pcb.geom(b)
        pts = [(g[0], g[1]), (g[2], g[3])] if Pcb.kind(b) == 'segment' else [(g[0], g[1])]
        if n == '/VBUS':
            return not all(_in(U2_BOX, x, y) for x, y in pts) or \
                (Pcb.kind(b) == 'segment' and {pts[0], pts[1]} == set(U2_VBUS_TAIL))
        if n == '/VBAT_FUSED':   # the R14 tap is the only sub-1.0 mm copper
            return Pcb.kind(b) == 'segment' and g[4] < 0.5
        return False
    n = p.drop(ripped)
    p.add_track('/VBUS', 'F.Cu', *U2_VBUS_TAIL[0], *U2_VBUS_TAIL[1], TAP_W)
    r = Router(p)
    _drill_clear_of_pads(r)
    res = {}
    res['VBUS F2 -> D1'] = r.route('/VBUS', POWER_W, [
        r.pad_group('F2', '2', POWER_W), r.pad_group('D1', '2', POWER_W),
        r.point_group(*U2_VBUS_TAIL[1], ['F.Cu'], r=0.15)])
    # waypoints pinned to F.Cu: Router.route_waypoints offers each one on both
    # layers, so a leg can end on F.Cu and the next start on B.Cu at the same
    # point with no via between them
    prev, ok = r.pad_group('D1', '2', TAP_W), True
    for (x, y) in D3_CORRIDOR:
        ok &= r.route('/VBUS', TAP_W, [prev, r.point_group(x, y, ['F.Cu'], r=0.2)])
        prev = r.point_group(x, y, ['F.Cu'], r=0.2)
    res['VBUS tap -> D3'] = ok and r.route('/VBUS', TAP_W, [prev, r.pad_group('D3', '2', TAP_W)])
    res['connector -> F2'] = r.route('Net-(F2-Pad1)', POWER_W, [
        r.pad_group('F2', '1', POWER_W), r.pad_group('J1', 'A9', POWER_W),
        r.pad_group('J1', 'A4', POWER_W)])
    res['VBAT_FUSED tap -> R14'] = r.route('/VBAT_FUSED', BATTERY_W, [
        r.pad_group('Q1', '3', BATTERY_W), r.pad_group('R14', '1', BATTERY_W)])
    return n, res


RULE_AREA = '''	(zone
		(layer "F.Cu")
		(uuid "{uuid}")
		(name "Power pin escape")
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
				(xy {x0} {y0}) (xy {x1} {y0}) (xy {x1} {y1}) (xy {x0} {y1})
			)
		)
	)
'''


def issue8(p, Router):
    print('  signals widened to 0.2 mm outside the driver pin fields:', widen_signals(p), 'segments')
    n, res = power_paths(p, Router)
    print('  power paths: ripped', n, '|', ', '.join(f"{k} {'ok' if v else 'FAILED'}" for k, v in res.items()))
    if not all(res.values()):
        raise RuntimeError('issue 8 power routing failed')


def rule_areas():
    import uuid
    x0, y0, x1, y1 = POWER_ESCAPE
    return [RULE_AREA.format(uuid=uuid.uuid4(), x0=x0, y0=y0, x1=x1, y1=y1)]
