"""F1: 2920 PPTC -> Littelfuse 885 fuse, for the pack's short-circuit current (2026-09-23).

Runs after pololu_conn.py.  The chosen pack (OVONIC 2S 450 mAh 100C) can put an
estimated 200-400 A into a dead short; the 2920L300/15DR PPTC was rated to
interrupt 40 A.  F1 is now a one-time Littelfuse 0885005.DR: 5 A, 1500 A
interrupting at 125 VDC.  It is a larger part (land pattern 16.1 x 7.3 mm), so
it moves east into the free area between BT1 and Q1, pad 1 under BT1's + pin.
Its courtyard is 7.76 mm tall and the gap between BT1's and D6's was 7.65 mm,
so BT1 moves 0.4 mm north (J6 is 2.6 mm above it; its holes still clear the
underside battery attachment band) rather than D6, which sits in the tuned
motor region.

  1  builds the footprint from the stock library file and swaps it in,
     keeping F1's schematic link;
  2  drops other-net top copper under the new pads, then prunes the old
     /VBAT_RAW and /VBAT_FUSED trunks back from the old pad positions;
  3  re-routes both at 1.0 mm, the Battery netclass width.
"""
import os, re, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcbedit import Pcb, fx
from pololu_conn import dangling, prune, rip_conflicts, reconnect, _set_prop, _zone, _in_pad

LIB = '/usr/share/kicad/footprints/Fuse.pretty/Fuse_Littelfuse-NANO2-885.kicad_mod'
FPID = 'Fuse:Fuse_Littelfuse-NANO2-885'
AT = (110.2, 100.7, 0)
BT1_AT = (105.0, 93.6)                          # was (105, 94)
REF_AT = {'F1': (0.0, 0.0), 'D6': (2.2, 3.0)}   # F1's between its pads; D6's off F1 pad 2 and C21
NETS = {'1': '/VBAT_RAW', '2': '/VBAT_FUSED'}
BATTERY_W = 1.0
# must match the schematic's F1 fields, or parity reports a field mismatch
FIELDS = {
    'Value': '5A 1500A@125VDC',
    'Datasheet': 'https://www.littelfuse.com/assetdocs/littelfuse-fuse-885-datasheet?assetguid=f4426cf6-2a53-41b3-b8da-211f7a44fad1',
    'Description': 'Battery fuse, one-time: Littelfuse 885 series 5A, breaks 1500A @ 125VDC. Sized for the '
                   'pack short-circuit current (OVONIC 2S 450mAh 100C, est. 200-400A); the old 2920 PPTC was '
                   'rated for 40A max fault. 200% opens in 2 min max; max normal load ~2.4A.',
    'MPN': '0885005.DR',
}
MPN_PROP = '''		(property "MPN" "{v}"
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


def library_block(ref, path, x, y):
    """the stock footprint, re-indented as a board item at rotation 0"""
    lib = open(LIB).read()
    lines = [l for l in lib.splitlines(True)
             if not re.match(r'\t\((version|generator|generator_version) ', l)]
    blk = ''.join('\t' + l if l.strip() else l for l in lines)
    blk = blk.replace('\t(footprint "Fuse_Littelfuse-NANO2-885"\n',
                      f'\t(footprint "{FPID}"\n', 1)
    blk = blk.replace('\t\t(layer "F.Cu")\n',
                      f'\t\t(layer "F.Cu")\n\t\t(uuid "{uuid.uuid4()}")\n\t\t(at {fx(x)} {fx(y)})\n', 1)
    blk = blk.replace('(property "Reference" "REF**"', f'(property "Reference" "{ref}"', 1)
    blk = re.sub(r'\(uuid "[^"]+"\)', lambda _: f'(uuid "{uuid.uuid4()}")', blk)
    i = blk.index('\t\t(attr smd)')
    blk = blk[:i] + MPN_PROP.format(v=FIELDS['MPN'], u=uuid.uuid4()) + path + blk[i:]

    def pad_net(m):
        return m.group(0).replace('\t\t\t(uuid', f'\t\t\t(net "{NETS[m.group(1)]}")\n\t\t\t(uuid', 1)
    blk = re.sub(r'\t\t\(pad "(\d)" .*?\n\t\t\)\n', pad_net, blk, flags=re.S)
    assert blk.count('(net "') == 2
    return blk


def f1_fuse(p, Router):
    p.sync()
    baseline = dangling(p, Router(p).g, {n for b in p.blocks if (n := Pcb.net(b))})
    old = [(pd, pd['net']) for pd in Router(p).g.byref['F1']['pads']]
    p.move_footprint('BT1', *BT1_AT)
    i, j = p.footprint_span('F1')
    path = re.search(r'\t\t\(path "[^"]+"\)\n', p.text[i:j]).group(0)
    p.text = p.text[:i] + library_block('F1', path, AT[0], AT[1]) + p.text[j:]
    p._split()
    for k, v in FIELDS.items():
        if k != 'MPN':
            _set_prop(p, 'F1', k, v)
    for ref, (dx, dy) in REF_AT.items():
        p.move_property(ref, 'Reference', dx, dy)
    r = Router(p)
    # stubs that ended on the old 2920 pads: several overlap each other there,
    # which dangling() reads as a T, so they are dropped explicitly
    new = r.g.byref['F1']['pads']

    def stub(b):
        if Pcb.kind(b) != 'segment': return False
        x1, y1, x2, y2, w, l = Pcb.geom(b)
        net = Pcb.net(b)
        for (px, py) in ((x1, y1), (x2, y2)):
            if any(n == net and _in_pad(pd, px, py) for pd, n in old) and \
                    not any(q['net'] == net and _in_pad(q, px, py) for q in new):
                return True
        return False
    stubs = p.drop(stub)
    k, hit = rip_conflicts(p, r.g, ['F1'])
    nets = set(NETS.values()) | hit
    pr = prune(p, r.g, nets, baseline, [_zone(r.g, 'F1')])
    print(f'  F1 -> {FPID} at {AT[:2]}: ripped {k} items under its pads'
          f'{" (" + ", ".join(sorted(hit)) + ")" if hit else ""}, {stubs} stubs on the old pads,'
          f' pruned {pr} dangling')
    r = Router(p)
    ok = True
    for net in sorted(nets):
        w = BATTERY_W if net in NETS.values() else 0.2
        res = reconnect(r, net, w)
        print(f'  {net} {"reconnected" if res else "FAILED"} at {w} mm')
        ok &= res
    return ok
