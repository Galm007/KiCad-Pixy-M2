"""post-route sanity report: per-net track length, layer use, via count"""
import sys, collections, math
sys.path.insert(0,'/tmp/claude-1000/-home-galm-Workspace-KiCad-Pixy-M2-Pixy-M2/0d540b1f-73cf-4064-b688-c76203191bc7/scratchpad')
from sexp import parse, children, child, val
t=open('/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/Pixy-M2.kicad_pcb').read()
pcb=parse(t)
L=collections.Counter(); W=collections.defaultdict(set); V=collections.Counter(); layer=collections.Counter()
for s in children(pcb,'segment'):
    net=val(child(s,'net')[1]); a=child(s,'start'); b=child(s,'end')
    d=math.dist((float(a[1]),float(a[2])),(float(b[1]),float(b[2])))
    L[net]+=d; W[net].add(float(child(s,'width')[1])); layer[val(child(s,'layer')[1])]+=d
for v in children(pcb,'via'): V[val(child(v,'net')[1])]+=1
print(f"{'net':24s} {'mm':>7s} {'vias':>5s}  widths")
for n in sorted(L, key=lambda n:-L[n]):
    print(f"{n:24s} {L[n]:7.1f} {V[n]:5d}  {sorted(W[n])}")
print('vias only:', {n:c for n,c in V.items() if n not in L})
print('total track mm', round(sum(L.values()),1), 'vias', sum(V.values()))
print('per layer mm', {k:round(v,1) for k,v in layer.items()})
