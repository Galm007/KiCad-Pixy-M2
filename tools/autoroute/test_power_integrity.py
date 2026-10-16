"""Regression: removing a one-layer drill must preserve its copper junction."""
import unittest
from types import SimpleNamespace
from pcbedit import Pcb
from pololu_conn import components
from power_integrity import drop_unused_signal_vias

class ViaJunctionTest(unittest.TestCase):
    def board(self):
        p=Pcb.__new__(Pcb);p.blocks=[]
        return p,SimpleNamespace(fps=[])

    def test_one_layer_via_bridges_offset_trace_ends(self):
        p,g=self.board()
        p.add_track('/TEST','F.Cu',-1,0,-.25,0,.2)
        p.add_track('/TEST','F.Cu',.25,0,1,0,.2)
        p.add_via('/TEST',0,0)
        self.assertEqual(len(components(p,g,'/TEST')),1)
        self.assertEqual(drop_unused_signal_vias(p,g),1)
        self.assertFalse(any(Pcb.kind(b)=='via' for b in p.blocks))
        self.assertEqual(len(components(p,g,'/TEST')),1)

    def test_two_layer_via_is_retained(self):
        p,g=self.board()
        p.add_track('/TEST','F.Cu',-1,0,0,0,.2)
        p.add_track('/TEST','B.Cu',0,0,1,0,.2)
        p.add_via('/TEST',0,0)
        self.assertEqual(drop_unused_signal_vias(p,g),0)
        self.assertEqual(len(components(p,g,'/TEST')),1)

    def test_plane_stitch_is_retained(self):
        p,g=self.board();p.add_via('GND',0,0)
        self.assertEqual(drop_unused_signal_vias(p,g),0)

class ClosedLoopTest(unittest.TestCase):
    def test_redundant_closed_loop_does_not_crash_straightening(self):
        from octilinear import simplify
        clear=SimpleNamespace(path=lambda points: True)
        self.assertEqual(simplify([(0,0),(1,0),(1,1),(0,0)],clear),[(0,0)])

if __name__=='__main__':unittest.main()
