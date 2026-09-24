"""Functional blocks of the Pixy-M2 sheet, built from wire-connected clusters."""
from schlib import *
from clusters import clusters

# block -> refs / labels that identify its clusters, and note-text prefixes
BLOCKS = {
    'mcu':     dict(refs=['U1']),
    'reset':   dict(refs=['R2', 'SW1', 'SW2']),
    'debug':   dict(refs=['J11', 'TP5', 'TP6', 'TP7', 'TP8', 'TP9'],
                    notes=['DEBUG / PROGRAMMING', 'J11 pins', 'auto-reset', 'ever disables', 'header: U1',
                           'TP5-TP8', 'GPIO35/36/37']),
    'tof':     dict(refs=['J4', 'J5', 'J6', 'J7', 'R15', 'R16', 'C15', 'C16'],
                    notes=['VL53L0X', '1 VCC', 'The module pulls', 'Firmware must pull', 'Drive GPIO4-7',
                           'Module VIN', 'R15/R16', 'C15/C16', 'INT']),
    'battery': dict(refs=['BT1', 'D6'], flags=['#FLG04'],
                    notes=['OFF', 'ON', 'F1:', 'SW3 switches', 'D6:', 'VBAT is fed']),
    'buck':    dict(refs=['U3']),
    'uvlo':    dict(refs=['R7']),
    'usb':     dict(refs=['J1']),
    'sense':   dict(refs=['R10']),
    'leds':    dict(refs=['D4', 'D5', 'TP1', 'TP2', 'TP3']),
    'motor_a': dict(refs=['U4', 'J8', 'C18', 'C19', 'R17', 'R19', 'R20'],
                    notes=['MOTOR A', "DRV8231A VM abs max 35V clears D6's 15.4V clamp. R17"]),
    'motor_b': dict(refs=['U5', 'J9', 'C20', 'C21', 'R18', 'R21', 'R22'],
                    notes=['MOTOR B', "DRV8231A VM abs max 35V clears D6's 15.4V clamp. R18"]),
    'imu':     dict(refs=['J10', 'R23', 'C22'], notes=['IMU', 'SPI:', 'Jumper PS1']),
}


def blocks(s):
    gs = clusters(s)
    out = {k: [] for k in BLOCKS}
    used = set()
    for name, spec in BLOCKS.items():
        keys = set(spec.get('refs', [])) | set(spec.get('flags', []))
        for g in gs:
            if any(it.kind == 'symbol' and it.ref in keys for it in g):
                out[name] += g
                used.add(id(g))
        for t in s.items:
            if t.kind == 'text':
                v = sval(t.tree[1])
                for n in spec.get('notes', []):
                    if v == n or (len(n) >= 3 and v.startswith(n)):
                        out[name].append(t)
                        used.add(id(t))
                        break
    left = [g for g in gs if id(g) not in used] + \
        [t for t in s.items if t.kind == 'text' and id(t) not in used]
    return out, left


def block_box(s, items, text=True):
    return union([b for it in items for b in extents(s, it, text)])


if __name__ == '__main__':
    import sys
    s = Sch(sys.argv[1] if len(sys.argv) > 1 else '../../Pixy-M2.kicad_sch')
    bl, left = blocks(s)
    for k, v in bl.items():
        b = block_box(s, v)
        print('%-8s n=%3d  (%6.1f,%6.1f)-(%6.1f,%6.1f)  %5.1f x %5.1f' % (k, len(v), *b, b[2] - b[0], b[3] - b[1]))
    print('unassigned:', left)
