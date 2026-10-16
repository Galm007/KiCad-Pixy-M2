#!/usr/bin/env python3
"""Apply the motor UVLO/current reference and USB priority schematic revision.

One-shot conversion; all old fields/connections are asserted. New nets partition
the existing circuits; existing connector pins and named board rails stay intact.
"""
import copy
import re
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from power_integrity_data import PARTS, CURRENT_FIELDS, ROOT, SCH_ROOT
from schlib import Sch, parse, kid, kids, sval, fmt, translate
from devkit import label, wire, no_connect, text_item
from clusters import clusters

def uid(): return str(uuid.uuid4())
def q(s): return '"' + s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n') + '"'
def dump(n, depth=0):
    if isinstance(n, tuple): return q(n[1])
    if not isinstance(n, list): return n
    # Small atom-only expressions stay on one line.
    if not any(isinstance(c,list) for c in n): return '('+' '.join(dump(c,depth+1) for c in n)+')'
    out='('+dump(n[0],depth+1)
    for c in n[1:]:
        out += ('\n'+'\t'*(depth+1) if isinstance(c,list) else ' ')+dump(c,depth+1)
    return out+'\n'+'\t'*depth+')'

LIBS={}
def stock_symbol(libid):
    lib,name=libid.split(':')
    if lib not in LIBS:
        tree,_=parse(Path('/usr/share/kicad/symbols',lib+'.kicad_sym').read_text())
        LIBS[lib]={sval(s[1]):s for s in kids(tree,'symbol')}
    def resolve(name):
        s=copy.deepcopy(LIBS[lib][name]); ext=kid(s,'extends')
        if ext:
            parent=sval(ext[1]); base=resolve(parent)
            props={sval(p[1]) for p in kids(s,'property')}
            inherited=[c for c in base[2:] if isinstance(c,list) and c[0]!='extends'
                       and not (c[0]=='property' and sval(c[1]) in props)]
            for c in inherited:
                if c[0]=='symbol': c[1]=('STR',sval(c[1]).replace(parent+'_',name+'_',1))
            s=[s[0],s[1]]+[c for c in s[2:] if c is not ext]+inherited
        return s
    s=resolve(name);s[1]=('STR',libid)
    return s

def custom_symbol(name, pins, halfwidth, halfheight):
    out=f'''(symbol {q(name)}
      (pin_names (offset 0.635)) (exclude_from_sim no) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 0 0) (effects (font (size 1.27 1.27))))
      (property "Value" {q(name)} (at 0 0 0) (effects (font (size 1.27 1.27))))
      (symbol {q(name+'_0_1')}
        (rectangle (start {-halfwidth} {halfheight}) (end {halfwidth} {-halfheight})
          (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol {q(name+'_1_1')}'''
    for num,pname,kind,x,y,angle,hidden in pins:
        out+=f'''(pin {kind} line (at {x} {y} {angle}) (length 2.54) {'(hide yes)' if hidden else ''}
          (name {q(pname)} (effects (font (size 1.0 1.0))))
          (number {q(str(num))} (effects (font (size 1.0 1.0)))))'''
    return parse(out+'))')[0]

CUSTOM = {
    'TLV3012BDBV':custom_symbol('TLV3012BDBV',[
        (1,'OUT','output',7.62,2.54,180,False),(2,'GND','power_in',0,-7.62,90,False),
        (3,'IN+','input',-7.62,2.54,0,False),(4,'IN-','input',-7.62,-2.54,0,False),
        (5,'REF','output',7.62,-2.54,180,False),(6,'VCC','power_in',0,7.62,270,False)],5.08,5.08),
    'SN74LV4066APW':custom_symbol('SN74LV4066APW',[
        (1,'1A','bidirectional',-10.16,7.62,0,False),(2,'1B','bidirectional',10.16,7.62,180,False),
        (4,'2A','bidirectional',-10.16,2.54,0,False),(3,'2B','bidirectional',10.16,2.54,180,False),
        (8,'3A','bidirectional',-10.16,-2.54,0,False),(9,'3B','bidirectional',10.16,-2.54,180,False),
        (11,'4A','bidirectional',-10.16,-7.62,0,False),(10,'4B','bidirectional',10.16,-7.62,180,False),
        (13,'EN','input',-10.16,-12.7,0,False),(5,'~','input',-10.16,-12.7,0,True),
        (6,'~','input',-10.16,-12.7,0,True),(12,'~','input',-10.16,-12.7,0,True),
        (14,'VCC','power_in',0,15.24,270,False),(7,'GND','power_in',0,-15.24,90,False)],7.62,12.7),
}

def prop(name,value,x,y,hide=False,angle=0):
    return f'''(property {q(name)} {q(value)} (at {fmt(x)} {fmt(y)} {angle})
       {'(hide yes)' if hide else ''} (effects (font (size 1.0 1.0))))'''

def placed(ref,data,lib):
    x,y,rot=data['sch'];suid=str(uuid.uuid5(uuid.NAMESPACE_URL,'pixy-power-integrity/symbol/'+ref))
    s=f'''(symbol (lib_id {q(data['lib'])}) (at {x} {y} {rot}) (unit 1)
      (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid {q(suid)})'''
    if ref=='U6':
        s+=prop('Reference',ref,x-6.35,y-10.16)
        s+=prop('Value',data['fields']['Value'],x,y,True)
    elif ref=='U8':
        s+=prop('Reference',ref,x,y-10.16)
        s+=prop('Value',data['fields']['Value'],x,y-7.62)
    elif ref=='U7':
        s+=prop('Reference',ref,x+8.89,y-12.7)
        s+=prop('Value',data['fields']['Value'],x,y,True)
    elif ref=='Q3':
        s+=prop('Reference',ref,x+8.89,y+2.54)
        s+=prop('Value',data['fields']['Value'],x+8.89,y+5.08)
    elif ref.startswith('Q'):
        s+=prop('Reference',ref,x+8.89,y-2.54)
        s+=prop('Value',data['fields']['Value'],x+8.89,y)
    elif rot==90:
        s+=prop('Reference',ref,x,y-3.81,angle=90)
        s+=prop('Value',data['fields']['Value'],x+(7.62 if ref=='R26' else 0),y+3.81,angle=90)
    elif ref.startswith('TP'):
        s+=prop('Reference',ref,x,y-6.858)
        s+=prop('Value',data['fields']['Value'],x,y-5.08)
    elif ref=='C30':
        s+=prop('Reference',ref,x+8.89,y-1.27)
        s+=prop('Value',data['fields']['Value'],x+8.89,y+1.27)
    elif ref=='C23':
        s+=prop('Reference',ref,x-5.715,y-1.27)
        s+=prop('Value',data['fields']['Value'],x-5.715,y+1.27)
    else:
        s+=prop('Reference',ref,x+6.35,y-1.27)
        s+=prop('Value',data['fields']['Value'],x+6.35,y+1.27)
    for k,v in data['fields'].items():
        if k!='Value':s+=prop(k,v,x,y,True)
    def walk(n):
        for c in n:
            if isinstance(c,list):
                if c and c[0]=='pin':yield sval(kid(c,'number')[1])
                else:yield from walk(c)
    for n in walk(lib):
        puid=str(uuid.uuid5(uuid.NAMESPACE_URL,'pixy-power-integrity/pin/'+ref+'/'+n))
        s+=f'(pin {q(n)} (uuid {q(puid)}))'
    return s+f'''(instances (project "Pixy-M2" (path {q(SCH_ROOT)} (reference {q(ref)}) (unit 1)))))'''

def set_props(text,fields):
    for k,v in fields.items():
        pat=r'(\(property '+re.escape(q(k))+r' )"(?:[^"\\]|\\.)*"'
        text,n=re.subn(pat,lambda m:m[1]+q(v),text,count=1)
        if not n:
            i=text.index('(instances');text=text[:i]+prop(k,v,0,0,True)+text[i:]
    return text

def main(src,dst):
    s=Sch(src);syms={it.ref:it for it in s.items if it.kind=='symbol'}
    assert 'U6' not in syms and syms['R17'].prop('Value')=='2.2kOhm 1%'
    edits={};add=[];drop=set()
    for ref in ('R17','R18'):edits[id(syms[ref])]=set_props(syms[ref].text,CURRENT_FIELDS)
    # Retag only the labels physically wired to the affected pins.
    def pin_labels(ref,pin):
        point=next((x,y) for n,x,y in s.pin_positions(syms[ref]) if n==pin)
        seen={point}
        changed=True
        while changed:
            changed=False
            for it in s.items:
                if it.kind!='wire':continue
                pts=s.points(it)
                if any(pt in seen for pt in pts):
                    for pt in pts:
                        if pt not in seen:seen.add(pt);changed=True
        return [it for it in s.items if it.kind=='label' and s.points(it)[0] in seen]
    for ref,pin,new in [('U4','3','DRV_A_IN1'),('U4','2','DRV_A_IN2'),
                        ('U5','3','DRV_B_IN1'),('U5','2','DRV_B_IN2'),
                        ('U4','4','MOTOR_VREF'),('U5','4','MOTOR_VREF'),('U3','1','BUCK_3V3')]:
        ls=pin_labels(ref,pin);assert len(ls)==1,(ref,pin,len(ls))
        it=ls[0];edits[id(it)]=re.sub(r'^\(label "[^"]+"','(label '+q(new),it.text)
    x,y=next((x,y) for n,x,y in s.pin_positions(syms['U1']) if n=='21')
    nc=[it for it in s.items if it.kind=='no_connect' and s.points(it)[0]==(x,y)]
    assert len(nc)==1;drop.add(id(nc[0]))
    add += [wire(x,y,x,y-2.54),wire(x,y-2.54,x-5.08,y-2.54),label('DEVKIT_5V',x-5.08,y-2.54,180)]
    for it in s.items:
        if it.kind!='text':continue
        txt=sval(it.tree[1]);new=None
        if txt.startswith('With USB plugged in,'):new='USB priority: U8/Q2 disconnect the buck from ESP_3V3 when devkit USB is present.'
        elif txt.startswith('current, so the two share'):new='The devkit LDO supplies the logic during USB use; the buck has its own BUCK_3V3 rail.'
        elif txt.startswith('mutually exclusive. USB'):new='U1.21 (DEVKIT_5V) is voltage sensing only: no feed into VSYS or REG_EN.'
        elif txt.startswith('see only the pack,'):new='U6/U7 coast both motors below 6.35V (enable 6.75V), even with USB attached.'
        elif txt.startswith('Power: the AP63203'):new='Power: AP63203 -> U8/Q2 isolation -> ESP_3V3 -> devkit 3V3 pins.'
        elif txt.startswith('DRV8231A VM abs max'):
            ch='GPIO2' if 'GPIO2 (' in txt else 'GPIO10'
            new=f'DRV8231A VM abs max 35V clears D6. U6 reference and 1k RIPROPI set\n0.828A nominal; IPROPI 1.5 V/A on {ch} (ADC1). U7 hardware inhibit.'
        if new is not None:
            edits[id(it)]=re.sub(r'^(\(text )"(?:[^"\\]|\\.)*"',lambda m:m[1]+q(new),it.text,count=1)
    # New project library symbols have explicit, datasheet-checked pin numbers.
    (ROOT/'Pixy-M2.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "pixy-m2")\n'+
        '\n'.join(dump(v,1) for v in CUSTOM.values())+'\n)\n')
    (ROOT/'sym-lib-table').write_text('(sym_lib_table\n  (lib (name "Pixy-M2") (type "KiCad") (uri "${KIPRJMOD}/Pixy-M2.kicad_sym") (options "") (descr "Project power integrity symbols"))\n)\n')
    cache={}
    for d in PARTS.values():
        libid=d['lib']
        if libid in s.libs:continue
        if libid.startswith('Pixy-M2:'):
            lib=copy.deepcopy(CUSTOM[libid.split(':')[1]]);lib[1]=('STR',libid)
        else:lib=stock_symbol(libid)
        cache[libid]=lib
    temp=Sch(text=s.text)
    temp.libs.update(cache)
    from schlib import Item
    for ref,d in PARTS.items():
        lib=temp.libs[d['lib']];txt=placed(ref,d,lib);it=Item(txt,0,len(txt));add.append(txt)
        seen=set()
        for num,px,py in temp.pin_positions(it):
            if (px,py) in seen:continue
            seen.add((px,py));net=d['nets'][num]
            if net is None:
                add.append(no_connect(px,py));continue
            if (ref,num) in {('R24','2'),('R25','1'),('U6','3'),('R27','1'),('R28','2'),('R29','1'),('R30','2'),('Q3','1')}:
                continue
            # Pin labels are deliberately local stubs: no crossing-wire junctions.
            pin=next(p for unit in kids(lib,'symbol') for p in kids(unit,'pin') if sval(kid(p,'number')[1])==num)
            angle=(float(kid(pin,'at')[3])+d['sch'][2])%360
            dx,dy={0:(-2.54,0),180:(2.54,0),90:(0,2.54),270:(0,-2.54)}[angle]
            ex,ey=round(px+dx,3),round(py+dy,3)
            labangle=180 if dx<0 or (ref=='R31' and dy) or (ref,num)==('C25','1') else 0
            if (ref,num)==('U6','4'):ex=round(px-1.27,3)
            lab=label(net,ex,ey,labangle)
            if (ref,num)==('U6','4'):lab=lab.replace('(size 1.27 1.27)','(size 0.8 0.8)')
            if (ref,num)==('C27','1'):lab=lab.replace('(size 1.27 1.27)','(size 1 1)')
            add.extend([wire(px,py,ex,ey),lab])
    # Draw the two divider connections instead of overlapping repeated labels.
    add += [wire(140.97,31.75,140.97,41.91),wire(140.97,33.02,149.86,33.02),
            label('MOTOR_UVLO',140.97,33.02,0).replace('(size 1.27 1.27)','(size 0.9 0.9)'),
            wire(181.61,53.34,181.61,52.07),wire(181.61,52.07,190.5,52.07),
            '(junction (at 140.97 33.02) (diameter 0) (color 0 0 0 0) (uuid '+q(uid())+'))',
            wire(233.68,53.34,233.68,57.15),label('USB_PRIORITY',233.68,55.88,0),
            wire(250.19,57.15,250.19,58.42),wire(250.19,58.42,265.43,58.42),label('BUCK_ENABLE',251.46,58.42,0)]
    # The buck output is a new isolated rail; its inductor hides its source from ERC.
    flg=copy.deepcopy(next(it for it in s.items if it.kind=='symbol' and it.lib_id=='power:PWR_FLAG'))
    txt=flg.text
    ox,oy,_=flg.at();txt=translate(txt,233.68-ox,78.74-oy)
    txt=re.sub(r'\(uuid "[^"]+"\)',lambda m:'(uuid '+q(uid())+')',txt)
    txt=txt.replace(flg.ref,'#FLG05')
    ft,_=parse(txt)
    for pp in kids(ft,'property'):
        if sval(pp[1])=='Value':pp.append(['hide','yes'])
    txt=dump(ft)
    add += [txt,label('BUCK_3V3',233.68,78.74,0)]
    txt2=txt.replace('#FLG05','#FLG06')
    txt2=translate(txt2,44.45,0)
    txt2=re.sub(r'\(uuid "[^"]+"\)',lambda m:'(uuid '+q(uid())+')',txt2)
    add += [txt2,label('DEVKIT_5V',278.13,78.74,0)]
    for a,b,title in [((135.89,13.97),(226.06,64.77),'MOTOR HARDWARE CUTOFF / CURRENT REFERENCE'),
                       ((228.6,13.97),(299.72,88.9),'USB PRIORITY / BUCK ISOLATION')]:
        add.append(f'(rectangle (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (stroke (width 0) (type dash)) (fill (type none)) (uuid {q(uid())}))')
        add.append(text_item(title,a[0]+1.27,a[1]+2.54))
    add.append(text_item('U8 and Q2 have opposing body diodes for off-state isolation.\\nC30 bridges the ~40 us handover; verify on hardware.',229.87,83.82))
    add.append(text_item('TLV3012B',151.13,19.05))
    add.append(text_item('SN74LV4066APWR',194.31,19.05))
    # U4/U5 with every pin label and power symbol touching them move 7.62 mm
    # right: DRV_x_INn and MOTOR_VREF are longer than GPIO39-42/ESP_3V3 were
    groups=clusters(s)
    for ref in ('U4','U5'):
        grp=next(g for g in groups if any(it.kind=='symbol' and it.ref==ref for it in g))
        assert [it.ref for it in grp if it.kind=='symbol' and not it.ref.startswith('#')]==[ref]
        for it in grp:
            edits[id(it)]=translate(edits.get(id(it),it.text),7.62,0)
    changes=[]
    for it in s.items:
        if id(it) in drop:changes.append((it.s,it.e,''))
        elif id(it) in edits:changes.append((it.s,it.e,edits[id(it)]))
    text=s.text
    for a,b,t in sorted(changes,reverse=True):text=text[:a]+t+text[b:]
    i=text.index('(lib_symbols')
    _,end=parse(text,i)
    text=text[:end-1]+'\n'+ '\n'.join(dump(v,2) for v in cache.values())+'\n\t'+text[end-1:]
    end=text.rfind(')');text=text[:end]+'\n\t'+'\n\t'.join(add)+'\n'+text[end:]
    Path(dst).write_text(re.sub(r'(?m)^[\t ]+$','',text))
    print('wrote',dst,'with',len(PARTS),'new parts')

if __name__=='__main__':main(*(sys.argv[1:] or [str(ROOT/'Pixy-M2.kicad_sch')]*2))
