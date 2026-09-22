import sys, math, re
sys.path.insert(0,'/tmp/claude-1000/-home-galm-Workspace-KiCad-Pixy-M2-Pixy-M2/0d540b1f-73cf-4064-b688-c76203191bc7/scratchpad')
from sexp import *
PCB='/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/Pixy-M2.kicad_pcb'
def load():
    return parse(open(PCB).read())
def fp_info(fp):
    at=child(fp,'at'); x,y=float(at[1]),float(at[2]); rot=float(at[3]) if len(at)>3 else 0.0
    ref=None
    for p in children(fp,'property'):
        if val(p[1])=='Reference': ref=val(p[2])
    lib=val(fp[1]); layer=val(child(fp,'layer')[1])
    pads=[]
    for pad in children(fp,'pad'):
        num=val(pad[1]); ptype=pad[2]; shape=pad[3]
        pat=child(pad,'at'); px,py=float(pat[1]),float(pat[2])
        prot=float(pat[3]) if len(pat)>3 else rot
        sz=child(pad,'size'); w,h=float(sz[1]),float(sz[2])
        lay=[val(z) for z in child(pad,'layers')[1:]]
        netn=child(pad,'net'); net=val(netn[1]) if netn else None
        drill=None
        dr=child(pad,'drill')
        if dr:
            dn=[float(x) for x in dr[1:] if re.match(r'^-?[\d.]+$',str(x))]
            if dn: drill=max(dn)
        a=math.radians(rot)
        gx=x+px*math.cos(a)+py*math.sin(a)
        gy=y-px*math.sin(a)+py*math.cos(a)
        pads.append(dict(num=num,type=ptype,shape=shape,x=gx,y=gy,rot=prot%360,w=w,h=h,layers=lay,net=net,drill=drill))
    return dict(ref=ref,lib=lib,x=x,y=y,rot=rot,layer=layer,pads=pads)
