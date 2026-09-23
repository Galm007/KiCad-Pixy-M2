#!/usr/bin/env python3
"""Differential impedance of an edge-coupled microstrip — REVIEW.md issue 7.

2D finite-difference Laplace solve of the odd mode: two traces on a prepreg of
height h over a ground plane, covered by a conformal solder mask.  Codd comes
from the field energy with and without dielectric; Zdiff = 2 / (c sqrt(Codd Codd_air)).

Defaults are this board's F.Cu -> In1.Cu stackup (Pixy-M2.kicad_pcb): 35 um
copper on 0.2 mm 7628 prepreg, er 4.4.  JLCPCB's JLC04161H-7628 quotes the same
prepreg as 0.2104 mm; solder mask is 10-25 um, er ~3.8.

Accuracy: the energy converges slowly with the mesh (field singularity at the
copper edges); d = 5 um reads ~1.5 ohm high against d = 2.5 um.  Treat the result
as +/- 3 ohm and confirm with the fabricator's calculator when ordering.

    python3 zdiff.py 0.25 0.15            # width, gap (mm)
    python3 zdiff.py 0.25 0.15 --sweep    # prepreg 0.200/0.2104 x mask 10/25 um
"""
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as sla, sys
C0=299792458.0; E0=8.854187817e-12
def solve(w,s,h,t=0.035,er=4.4,mask=0.015,erm=3.8,d=0.005,air_eps=False):
    W=max(4.0, 2*w+s+12*h); Ht=h+t+2.5
    nx=int(round(W/d)); ny=int(round(Ht/d))
    xs=(np.arange(nx)+0.5)*d-W/2; ys=(np.arange(ny)+0.5)*d   # cell centres; y up from ground
    X,Y=np.meshgrid(xs,ys)
    eps=np.ones((ny,nx))
    if not air_eps:
        eps[Y<h]=er
        # conformal-ish mask: layer of thickness mask above dielectric and over the traces
        x1a,x1b=-s/2-w,-s/2; x2a,x2b=s/2,s/2+w
        near=((X>=x1a-mask)&(X<=x1b+mask))|((X>=x2a-mask)&(X<=x2b+mask))
        m=(Y>=h)&(Y<h+mask)&~near
        m|=near&(Y>=h)&(Y<h+t+mask)
        eps[m]=erm
    V=np.full((ny,nx),np.nan)
    tr1=(X>=-s/2-w)&(X<=-s/2)&(Y>=h)&(Y<=h+t)
    tr2=(X>=s/2)&(X<=s/2+w)&(Y>=h)&(Y<=h+t)
    V[tr1]=1; V[tr2]=-1
    # ground at y=0 face: handled as Dirichlet boundary below row 0; open boundary = 0 far away
    idx=-np.ones((ny,nx),int); free=np.isnan(V); idx[free]=np.arange(free.sum())
    N=free.sum(); rows=[];cols=[];vals=[]; b=np.zeros(N)
    def face(e1,e2): return 2*e1*e2/(e1+e2)
    J,I=np.nonzero(free)
    diag=np.zeros(N)
    for dj,di in ((1,0),(-1,0),(0,1),(0,-1)):
        j2=J+dj; i2=I+di
        inb=(j2>=0)&(j2<ny)&(i2>=0)&(i2<nx)
        e1=eps[J,I]
        e2=np.where(inb,eps[np.clip(j2,0,ny-1),np.clip(i2,0,nx-1)],e1)
        f=face(e1,e2)
        # boundary: bottom (j2<0) is ground at distance d/2 -> coefficient 2*e1
        f=np.where(~inb & (j2<0), 2*e1, f)
        f=np.where(~inb & (j2>=0), 2*e1, f)   # other boundaries at 0 V too
        diag+=f
        k=idx[J,I]
        ok=inb.copy()
        j2c=np.clip(j2,0,ny-1); i2c=np.clip(i2,0,nx-1)
        nb_free=ok & free[j2c,i2c]
        rows+=list(k[nb_free]); cols+=list(idx[j2c,i2c][nb_free]); vals+=list(-f[nb_free])
        fixed=ok & ~free[j2c,i2c]
        np.add.at(b,k[fixed],f[fixed]*V[j2c,i2c][fixed])
    A=sp.csr_matrix((vals+list(diag),(rows+list(range(N)),cols+list(range(N)))),shape=(N,N))
    x=sla.spsolve(A,b); Vf=V.copy(); Vf[free]=x
    # energy via face sums
    Wn=0.0
    ex=face(eps[:,1:],eps[:,:-1]); Wn+=np.sum(ex*(Vf[:,1:]-Vf[:,:-1])**2)
    ey=face(eps[1:,:],eps[:-1,:]); Wn+=np.sum(ey*(Vf[1:,:]-Vf[:-1,:])**2)
    Wn+=np.sum(2*eps[0,:]*Vf[0,:]**2)
    return 0.5*E0*Wn  # = Codd per line (F/m)
def zdiff(w,s,h,**k):
    C=solve(w,s,h,**k); Ca=solve(w,s,h,air_eps=True,**{kk:v for kk,v in k.items() if kk in('t','d')})
    zo=1/(C0*np.sqrt(C*Ca)); return 2*zo, np.sqrt(C/Ca)
if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('width', type=float); ap.add_argument('gap', type=float)
    ap.add_argument('--h', type=float, default=0.2)
    ap.add_argument('--mask', type=float, default=0.01)
    ap.add_argument('--d', type=float, default=0.005, help='mesh step, mm')
    ap.add_argument('--sweep', action='store_true')
    a = ap.parse_args()
    cases = ([(h, m) for h in (0.2, 0.2104) for m in (0.01, 0.025)] if a.sweep
             else [(a.h, a.mask)])
    for h, m in cases:
        z, e = zdiff(a.width, a.gap, h, mask=m, d=a.d)
        print(f'w={a.width} s={a.gap} h={h} mask={m}  Zdiff={z:5.1f} ohm  eeff={e * e:.2f}')
