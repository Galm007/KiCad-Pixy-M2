"""Exact minimum copper clearance between net groups, by DRC descent — issue 8.

    python3 layout/issue8-rules/clearmin.py BOARD.kicad_pcb BOARD.kicad_pro [OUT.json]

Method:
run a clearance rule at threshold T; if violated at actual a < T, rerun at a;
stop when nothing violates.  Several starting thresholds are tried and the
smallest result kept: with a large T, DRC reports the first violating shape pair
it meets, not the closest one, and for some pairs reports nothing at all.  The
first attempt at these numbers used a single 20 mm threshold and was wrong by
up to 0.5 mm."""
import json, re, shutil, subprocess, sys, os, tempfile
PAIRS = {
 'REG_EN-SW':      ("A.NetName == '/REG_EN'", "(B.NetName == 'Net-(U3-SW)' || B.NetName == 'Net-(U3-BST)')"),
 'REG_EN-motor':   ("A.NetName == '/REG_EN'", "B.NetClass == 'Motor'"),
 'VBAT_SENSE-SW':  ("A.NetName == '/VBAT_SENSE'", "(B.NetName == 'Net-(U3-SW)' || B.NetName == 'Net-(U3-BST)')"),
 'VBAT_SENSE-motor': ("A.NetName == '/VBAT_SENSE'", "B.NetClass == 'Motor'"),
 'IPROPI-motor':   ("(A.NetName == '/GPIO2' || A.NetName == '/GPIO10')", "B.NetClass == 'Motor'"),
 'USB-other':      ("A.NetClass == 'USB'", "B.NetClass != 'USB'"),
 'VBUS-SW':        ("(A.NetName == '/VBUS' || A.NetName == '/VSYS')", "(B.NetName == 'Net-(U3-SW)' || B.NetName == 'Net-(U3-BST)')"),
}
def run(board, pro, rules):
    d = tempfile.mkdtemp()
    shutil.copy(board, d + '/b.kicad_pcb'); shutil.copy(pro, d + '/b.kicad_pro')
    open(d + '/b.kicad_dru', 'w').write('(version 1)\n' + '\n'.join(rules) + '\n')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', d + '/o.json', d + '/b.kicad_pcb'],
                   capture_output=True)
    out = json.load(open(d + '/o.json')); shutil.rmtree(d)
    return out
def measure(board, pro, start=12.0):
    T = {k: start for k in PAIRS}; best = {k: None for k in PAIRS}; live = set(PAIRS)
    while live:
        rules = [f'(rule "M {k}" (constraint clearance (min {T[k]:.4f}mm)) (condition "{a} && {b}"))'
                 for k, (a, b) in PAIRS.items() if k in live]
        d = run(board, pro, rules); hit = {}
        for v in d['violations']:
            m = re.search(r"rule 'M ([^']+)'.*actual ([\d.]+) mm", v['description'])
            if m:
                k, a = m.group(1), float(m.group(2))
                if k not in hit or a < hit[k][0]:
                    hit[k] = (a, [(i['description'][:36], i['pos']['x'], i['pos']['y']) for i in v['items']])
        for k in list(live):
            if k in hit and (best[k] is None or hit[k][0] < best[k][0] - 1e-6):
                best[k] = hit[k]; T[k] = hit[k][0] - 1e-4
            else:
                live.discard(k)
    return best
def measure_all(board, pro, starts=(0.6, 1.2, 2.5, 5.0, 10.0, 20.0)):
    best = {k: None for k in PAIRS}
    for s in starts:
        for k, v in measure(board, pro, s).items():
            if v and (best[k] is None or v[0] < best[k][0]): best[k] = v
    return best
if __name__ == '__main__':
    res = measure_all(sys.argv[1], sys.argv[2])
    for k, v in res.items(): print(f'  {k:18s}', v if v else '> 20 mm')
    if len(sys.argv) > 3: json.dump(res, open(sys.argv[3], 'w'), indent=1)
