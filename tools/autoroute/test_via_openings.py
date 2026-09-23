"""Regression cases missed by the original via-centre-only check."""
import math
import unittest
import pcbnew as pcb
from via_openings import point_gap, apertures, audit, THERMAL


def shape(w=1, h=1, angle=0, radius=0):
    return dict(x=0, y=0, w=w, h=h, angle=angle, radius=radius)


class OpeningTests(unittest.TestCase):
    def test_center_outside_still_overlaps(self):
        self.assertGreater(point_gap(.6, 0, shape()), 0)
        self.assertAlmostEqual(point_gap(.6, 0, shape()) - .15, -.05)

    def test_tangency_is_not_positive_clearance(self):
        self.assertAlmostEqual(point_gap(.65, 0, shape()) - .15, 0)
        self.assertAlmostEqual(point_gap(.75, 0, shape()) - .15, .1)

    def test_rotated_rectangle(self):
        self.assertAlmostEqual(point_gap(.9, 0, shape(2, 1, 90)), .4)
        self.assertAlmostEqual(point_gap(0, .9, shape(2, 1, 90)), -.1)

    def test_round_corner_and_oval(self):
        self.assertAlmostEqual(point_gap(.6, .6, shape(radius=.2)), math.sqrt(.18)-.2)
        self.assertAlmostEqual(point_gap(1.1, 0, shape(2, 1, radius=.5)), .1)

    def test_paste_only_and_required_thermal_process(self):
        b = pcb.BOARD()
        net = pcb.NETINFO_ITEM(b, 'GND')
        b.Add(net)
        for x, ref in ((109, 'U4'), (117, 'U5')):
            f = pcb.FOOTPRINT(b)
            f.SetReference(ref)
            b.Add(f)
            # The exposed pad has mask but no paste. Independent unnumbered
            # paste-only pads are the actual apertures above the two holes.
            for num, y, size, layers in [('9',114,(.9,1.6),[pcb.F_Cu,pcb.F_Mask]),
                    ('',113.6,(.73,.64),[pcb.F_Paste]), ('',114.4,(.73,.64),[pcb.F_Paste])]:
                p = pcb.PAD(f)
                p.SetNumber(num)
                p.SetShape(pcb.PAD_SHAPE_RECT)
                p.SetSize(pcb.VECTOR2I(pcb.FromMM(size[0]),pcb.FromMM(size[1])))
                p.SetPosition(pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y)))
                ls = pcb.LSET()
                for layer in layers:
                    ls.AddLayer(layer)
                p.SetLayerSet(ls)
                p.SetNet(net)
                f.Add(p)
        vias = []
        for x, y in THERMAL:
            v = pcb.PCB_VIA(b)
            v.SetPosition(pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y)))
            v.SetWidth(pcb.FromMM(.45))
            v.SetDrill(pcb.FromMM(.25))
            v.SetNet(net)
            v.SetFillingMode(pcb.FILLING_MODE_FILLED)
            v.SetCappingMode(pcb.CAPPING_MODE_CAPPED)
            b.Add(v)
            vias.append(v)
        self.assertEqual(sum(a['layer']=='F.Paste' for a in apertures(b)),4)
        self.assertEqual(audit(b)['violations'],[])
        vias[0].SetCappingMode(pcb.CAPPING_MODE_FROM_BOARD)
        self.assertTrue(any('explicit fill and cap' in v['reason'] for v in audit(b)['violations']))


if __name__ == '__main__':
    unittest.main()
