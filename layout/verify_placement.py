import pcbnew as p,xml.etree.ElementTree as E,json,math
from pathlib import Path
import subprocess,tempfile,os
os.chdir(Path(__file__).resolve().parent.parent)
with tempfile.TemporaryDirectory(prefix='pixy-placement-check-') as tmp:
 path=str(Path(tmp)/'schematic.xml')
 subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',path,'Pixy-M2.kicad_sch'],check=True)
 net=E.parse(path).getroot()
b=p.LoadBoard('Pixy-M2.kicad_pcb');fps={f.GetReference():f for f in b.GetFootprints()}
expected={}
for n in net.findall('nets/net'):
 for v in n.findall('node'):expected[(v.get('ref'),v.get('pin'))]=n.get('name')
errors=[]
for c in net.findall('components/comp'):
 f=fps[c.get('ref')]
 assert f.GetFPID().GetUniStringLibId()==c.findtext('footprint')
 assert f.GetPath().AsString().endswith(c.findtext('tstamps'))
 for pad in f.Pads():
  k=(f.GetReference(),pad.GetNumber());actual=pad.GetNetname()
  if actual!=expected.get(k,''):errors.append([k,actual,expected.get(k,'')])
reservations=[('battery',13,5,53,35),('motor L',0,44,38,60),('motor R',28,72,66,88),('battery bracket L',10,5,13,29),('battery bracket R',53,5,56,35),('motor L bracket 1',0,41,38,44),('motor L bracket 2',0,60,20,63),('motor R bracket 1',28,69,66,72),('motor R bracket 2',28,88,66,91)]
clashes=[];through=0
for f in fps.values():
 for pad in f.Pads():
  if pad.GetDrillSize().x==0:continue
  through+=1;q=pad.GetBoundingBox();a=[p.ToMM(q.GetLeft())-100,p.ToMM(q.GetTop())-60,p.ToMM(q.GetRight())-100,p.ToMM(q.GetBottom())-60]
  for name,x,y,X,Y in reservations:
   if a[0]<X and a[2]>x and a[1]<Y and a[3]>y:clashes.append([f.GetReference(),pad.GetNumber(),name])
assert not errors,errors
print('Mechanical pad-envelope clashes:',clashes)
assert not clashes,clashes
assert len(fps)==78
assert len(b.GetTracks())==0
assert all(z.GetIsRuleArea() for z in b.Zones())
result={'footprints':len(fps),'schematic_nets':len(net.findall('nets/net')),'pad_net_mismatches':errors,'through_hole_pads_checked':through,'underside_pad_envelope_clashes':clashes,'tracks_and_vias':len(b.GetTracks()),'copper_pours':0,'outline_size_mm':[66,100],'assembled_width_target_mm':90}
open('layout/verification.json','w').write(json.dumps(result,indent=2)+'\n');print(result)
