"""Obstacle raster of the CURRENT board (pads + tracks + vias + holes), per-net."""
import sys, math, numpy as np
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy import ndimage
from board import *
from sexp import parse, children, child, val
from load import fp_info
from pcbedit import Pcb

CL = 0.26
VIA_D, VIA_DRILL = 0.6, 0.3
H2H = 0.45
NONET = 30000

class G:
    def __init__(self, pcb_obj=None, ignore_nets=(), moved=None):
        """moved: {ref: (x,y,rot)} footprint overrides applied before rasterising"""
        self.p = pcb_obj or Pcb()
        self.pcb = parse(self.p.text)
        self.fps = [fp_info(f) for f in children(self.pcb, 'footprint')]
        self.byref = {f['ref']: f for f in self.fps}
        loops = board_polygon(edge_segments(self.pcb))
        self.inside = fill_polygon(loops)
        self.dist_edge = ndimage.distance_transform_edt(self.inside) * H
        self.keepout = np.zeros((NY, NX), bool)
        for z in children(self.pcb, 'zone'):
            ko = child(z, 'keepout')
            if not ko: continue
            rules = {c[0]: c[1] for c in ko[1:]}
            if rules.get('tracks') != 'not_allowed': continue
            for pg in children(z, 'polygon'):
                pts = [(float(q[1]), float(q[2])) for q in children(child(pg, 'pts'), 'xy')]
                self.keepout |= fill_polygon([pts])
        self.nets = {}
        for f in self.fps:
            for pd in f['pads']:
                if pd['net']: self.nets.setdefault(pd['net'], []).append((f['ref'], pd))
        allnets = set(self.nets) | {Pcb.net(b) for b in self.p.blocks if Pcb.net(b)}
        self.netid = {n: i for i, n in enumerate(sorted(n for n in allnets if n))}
        self.cu = {l: np.full((NY, NX), -1, np.int16) for l in ROUTE}
        self.holes = []
        self.ignore = set(ignore_nets)
        for f in self.fps:
            for pd in f['pads']:
                nid = self.netid.get(pd['net'], NONET)
                lay = pd['layers']
                sel = self.pad_sel(pd, 0.0)
                for l in ROUTE:
                    if l in lay or '*.Cu' in lay: stamp(self.cu[l], sel, nid)
                if pd['drill']:
                    self.holes.append((pd['x'], pd['y'], pd['drill'] / 2, nid if pd['net'] else NONET))
        for b in self.p.blocks:
            n = Pcb.net(b)
            if n in self.ignore: continue
            nid = self.netid.get(n, NONET)
            if Pcb.kind(b) == 'segment':
                x1, y1, x2, y2, w, l = Pcb.geom(b)
                if l in self.cu: seg_disc_stamp(self.cu[l], x1, y1, x2, y2, w / 2, nid)
            else:
                x, y, sz, dr = Pcb.geom(b)
                for l in ROUTE: stamp(self.cu[l], disc_mask(x, y, sz / 2), nid)
                self.holes.append((x, y, dr / 2, nid))
        # SMD pads: searched vias must not land in one (solder wicking)
        self.smd_block = np.zeros((NY, NX), bool)
        for f in self.fps:
            for pd in f['pads']:
                if pd['drill'] or not any(l in pd['layers'] for l in ROUTE): continue
                sel = self.pad_sel(pd, 0.15)
                if sel:
                    iy0, iy1, ix0, ix1, m = sel
                    self.smd_block[iy0:iy1 + 1, ix0:ix1 + 1] |= m
        self.hole_block = np.zeros((NY, NX), bool)
        for (hx, hy, hr, hn) in self.holes:
            sel = disc_mask(hx, hy, VIA_DRILL / 2 + H2H + hr)
            if sel:
                iy0, iy1, ix0, ix1, m = sel
                self.hole_block[iy0:iy1 + 1, ix0:ix1 + 1] |= m

    def pad_sel(self, pd, margin):
        if pd['shape'] == 'circle':
            return disc_mask(pd['x'], pd['y'], pd['w'] / 2 + margin)
        return rect_mask(pd['x'], pd['y'], pd['w'], pd['h'], pd['rot'], margin)

    def dist(self, net):
        nid = self.netid[net]
        out = {}
        hmask = np.zeros((NY, NX), bool)
        for (hx, hy, hr, hn) in self.holes:
            if hn == nid: continue
            sel = disc_mask(hx, hy, hr + 0.06)
            if sel:
                iy0, iy1, ix0, ix1, mm = sel
                hmask[iy0:iy1 + 1, ix0:ix1 + 1] |= mm
        for l in ROUTE:
            other = ((self.cu[l] >= 0) & (self.cu[l] != nid)) | hmask
            own = (self.cu[l] == nid) & (~hmask)
            out[l] = (ndimage.distance_transform_edt(~other) * H,
                      ndimage.distance_transform_edt(own) * H)
        return out

    def ok_masks(self, d, w):
        req = CL + w / 2
        out = {}
        for l in ROUTE:
            dd, own = d[l]
            out[l] = (((dd >= req) | (own >= w / 2 + H)) & (self.dist_edge >= req)) & self.inside & (~self.keepout)
        return out

    def via_mask(self, d, via_d=VIA_D):
        r = CL + via_d / 2
        m = ((self.dist_edge >= r) & (~self.hole_block) & (~self.keepout)
             & (~self.smd_block) & self.inside)
        for l in ROUTE:
            m &= (d[l][0] >= r) | (d[l][1] >= via_d / 2 + H / 2)
        return m
