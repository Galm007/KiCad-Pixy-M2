#!/usr/bin/env python3
"""ESP32-S3-DevKitC-1-N8R8 as a plug-in daughterboard (branch devkit-daughterboard).

One-shot conversion of the 2026-09-24 sheet:

  * U1 becomes the DevKitC-1 (Espressif's `ESP32-S3-DevKitC` symbol, 44 pins in
    the board's two 1x22 headers).  Its UUID is kept, so the PCB footprint keeps
    its schematic link.  Its 3V3 pins take ESP_3V3 from the AP63203, which
    Espressif's user guide lists as a supported input ("3V3 and G pins").
  * The parts the devkit duplicates go: the USB-C input (J1, U2, F2, R1, R5, R6,
    C8), the USB supply path into VSYS and REG_EN (D1, D3, R9), the reset/boot
    network (R2, C3, C4, C5, SW1, SW2) and the J11 programming header.
  * GPIO35/36/37 are the N8R8's octal PSRAM bus and GPIO38 drives the v1.1
    board's RGB LED, so TP6-TP8 go and encoder B's OUT B moves from GPIO38 to
    GPIO18, the last spare (TP5 goes with it).  TP9 moves to the test-point block.
  * Every devkit pin that carries nothing gets a no-connect flag.

Items are addressed by reference, label text and old coordinates, and every one
is asserted before it is touched, so the script only runs on the old sheet:

    python3 devkit.py ../../Pixy-M2.kicad_sch ../../Pixy-M2.kicad_sch
"""
import re
import sys
import uuid

from schlib import Sch, kid, kids, sval, parse, translate, fmt
from clusters import clusters

LIB = ('/home/galm/.local/share/kicad/10.0/3rdparty/symbols/'
       'com_github_espressif_kicad-libraries/Espressif.kicad_sym')
LIB_NAME, LIB_ID = 'ESP32-S3-DevKitC', 'PCM_Espressif:ESP32-S3-DevKitC'
ROOT = '/fefb2c5c-cd05-4562-bf27-32a51f81fd04'

REMOVE = {'J1', 'U2', 'F2', 'R1', 'R5', 'R6', 'C8',      # USB-C input
          'D1', 'D3', 'R9',                              # USB supply into VSYS / REG_EN
          'R2', 'C3', 'C4', 'C5', 'SW1', 'SW2',          # reset / boot
          'J11', 'TP5', 'TP6', 'TP7', 'TP8'}             # debug header, spare-GPIO pads

# the new U1: placed so its 3V3 pins (1, 2) land on the old ESP_3V3 wire at x 73.66
U1_AT = (72.39, 83.82)
U1_FIELDS = [
    ('Reference', 'U1', (76.2, 36.83), False),
    ('Value', 'ESP32-S3-DevKitC-1-N8R8', (76.2, 39.37), False),
    ('Footprint', 'Pixy-M2:ESP32-S3-DevKitC-1_SMD_Sockets', (72.39, 137.16), True),
    ('Datasheet', 'https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/'
                  'esp32-s3-devkitc-1/user_guide_v1.1.html', (72.39, 139.7), True),
    ('Description', 'ESP32-S3-DevKitC-1 v1.1, N8R8 (8 MB flash, 8 MB octal PSRAM), plugged into '
                    'two 1x22 2.54 mm SMD female headers. Fed on its 3V3 pins from the AP63203.',
     U1_AT, True),
    ('MPN', 'ESP32-S3-DevKitC-1-N8R8', U1_AT, True),
]
# pin number -> label (None = no-connect flag)
U1_NETS = {
    '1': '3V3', '2': '3V3', '21': None, '22': 'GND', '23': 'GND', '24': 'GND', '44': 'GND',
    '3': None,                                    # CHIP_PU: the devkit's own RC + RESET
    '8': 'GPIO15', '9': 'GPIO16', '36': 'GPIO39', '37': 'GPIO40', '38': 'GPIO41', '39': 'GPIO42',
    '43': None, '42': None,                       # U0TXD/U0RXD: the devkit's USB-UART bridge
    '26': None, '25': None,                       # USB D+/D-: the devkit's USB port
    '41': 'VBAT_SENSE', '40': 'GPIO2', '31': None, '13': 'GPIO3',
    '4': 'GPIO4', '5': 'GPIO5', '6': 'GPIO6', '7': 'GPIO7', '12': 'GPIO8', '15': 'GPIO9',
    '16': 'GPIO10', '17': 'GPIO11', '18': 'GPIO12', '19': 'GPIO13', '20': 'GPIO14',
    '10': 'GPIO17', '11': 'GPIO18', '27': 'GPIO21',
    '32': None, '33': None, '34': None,           # octal PSRAM on the N8R8
    '35': None,                                   # RGB LED on the v1.1 board
    '30': None, '14': None,                       # GPIO45/46 strapping pins
    '28': 'GPIO47', '29': 'GPIO48',
}

TP9_MOVE = (200.66 - 265.43, 120.65 - 73.66)     # under TP3 in INDICATORS / TEST POINTS

TEXT_EDITS = {
    'MCU — ESP32-S3-WROOM-1-N16': 'MCU — ESP32-S3-DevKitC-1-N8R8 (plug-in daughterboard)',
    'USB-C INPUT': 'DEVKITC-1 DAUGHTERBOARD — NOTES',
    'SW3 switches battery only; USB can still power the controller.':
        "SW3 switches the battery only. USB reaches only the devkit's own LDO (see notes, left).",
}
TEXT_DROP = ('RESET / BOOT', 'DEBUG / PROGRAMMING', 'J11 pins 3-6', 'auto-reset (DTR',
             'ever disables the native', 'header: U1.13/14', 'TP5-TP8:', 'GPIO35/36/37 are free')
FRAME_DROP = [((135.89, 13.97), (210.82, 64.77)),      # RESET / BOOT
              ((213.36, 13.97), (299.72, 88.9))]       # DEBUG / PROGRAMMING

NOTES_AT = (16.51, 144.78)
NOTES = [
    'U1 is an ESP32-S3-DevKitC-1-N8R8 (v1.1) on two 1x22 2.54 mm SMD female headers.',
    'Its own USB-UART and native-USB ports, BOOT/RESET buttons and CHIP_PU RC replace the',
    'removed USB-C input, J11 and SW1/SW2. Flash and debug through the devkit\'s USB ports.',
    '',
    'Power: the AP63203 feeds ESP_3V3 into the devkit\'s 3V3 pins; its 5V pin is unused.',
    'With USB plugged in, the devkit\'s SGM2212 LDO also drives 3V3. Neither source sinks',
    'current, so the two share the rail harmlessly, but Espressif calls the inputs',
    'mutually exclusive. USB no longer reaches VSYS or REG_EN: the motors and the UVLO',
    'see only the pack, and the hardware UVLO now holds with USB attached.',
    '',
    'Unusable pins: GPIO35/36/37 (octal PSRAM on N8R8), GPIO38 (v1.1 RGB LED),',
    'GPIO19/20 (devkit USB), GPIO43/44 (devkit USB-UART), GPIO0 and CHIP_PU (devkit',
    'buttons), GPIO45/46 (strapping). Encoder B OUT B is on GPIO18 for that reason.',
    'No spare GPIOs remain.',
]


def new_uuid():
    return str(uuid.uuid4())


def lib_symbol_text():
    """Espressif's symbol, verbatim, renamed into the project cache"""
    s = open(LIB).read()
    i = s.index('(symbol "%s"' % LIB_NAME)
    _, j = parse(s, i)
    blk = s[i:j]
    assert blk.count('(symbol "%s"' % LIB_NAME) == 1
    return blk.replace('(symbol "%s"' % LIB_NAME, '(symbol "%s"' % LIB_ID, 1)


def prop(name, value, at, hide, rot=0):
    return ('\t\t(property "%s" "%s"\n\t\t\t(at %s %s %s)\n%s\t\t\t(show_name no)\n'
            '\t\t\t(do_not_autoplace no)\n\t\t\t(effects\n\t\t\t\t(font\n'
            '\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n%s\t\t\t)\n\t\t)\n'
            % (name, value.replace('"', '\\"'), fmt(at[0]), fmt(at[1]), rot,
               '\t\t\t(hide yes)\n' if hide else '',
               '' if hide else '\t\t\t\t(justify left)\n'))


def u1_text(u, pins):
    out = ['(symbol\n\t\t(lib_id "%s")\n\t\t(at %s %s 0)\n\t\t(unit 1)\n\t\t(body_style 1)\n'
           '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n'
           '\t\t(in_pos_files yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n'
           % (LIB_ID, fmt(U1_AT[0]), fmt(U1_AT[1]), u)]
    for name, value, at, hide in U1_FIELDS:
        out.append(prop(name, value, at, hide))
    for n in sorted(pins, key=int):
        out.append('\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)\n' % (n, new_uuid()))
    out.append('\t\t(instances\n\t\t\t(project "Pixy-M2"\n\t\t\t\t(path "%s"\n'
               '\t\t\t\t\t(reference "U1")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)'
               % ROOT)
    return ''.join(out)


def label(text, x, y, angle):
    just = 'right bottom' if angle == 180 else 'left bottom'
    return ('(label "%s"\n\t\t(at %s %s %d)\n\t\t(effects\n\t\t\t(font\n'
            '\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify %s)\n\t\t)\n'
            '\t\t(uuid "%s")\n\t)' % (text, fmt(x), fmt(y), angle, just, new_uuid()))


def no_connect(x, y):
    return '(no_connect\n\t\t(at %s %s)\n\t\t(uuid "%s")\n\t)' % (fmt(x), fmt(y), new_uuid())


def wire(x1, y1, x2, y2):
    return ('(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n\t\t(stroke\n'
            '\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "%s")\n\t)'
            % (fmt(x1), fmt(y1), fmt(x2), fmt(y2), new_uuid()))


def text_item(t, x, y):
    return ('(text "%s"\n\t\t(at %s %s 0)\n\t\t(effects\n'
            '\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left)\n'
            '\t\t)\n\t\t(uuid "%s")\n\t)' % (t.replace('"', '\\"'), fmt(x), fmt(y), new_uuid()))


def gnd_symbol(ref, x, y, sheet_text):
    """copy #PWR01 (the old U1 ground) to a new position"""
    m = re.search(r'\(symbol\n\t\t\(lib_id "power:GND"\)\n\t\t\(at 73\.66 125\.73 0\).*?\n\t\)',
                  sheet_text, re.S)
    assert m, '#PWR01 not found'
    t = translate(m.group(0), x - 73.66, y - 125.73)
    t = re.sub(r'\(uuid "[^"]+"\)', lambda _: '(uuid "%s")' % new_uuid(), t)
    assert '"#PWR01"' in t
    return t.replace('"#PWR01"', '"%s"' % ref)


def main(src, dst):
    s = Sch(src)
    text = s.text
    drop, edits, add = set(), {}, []

    sym = {it.ref: it for it in s.items if it.kind == 'symbol'}
    u1 = sym['U1']
    assert u1.lib_id == 'PCM_Espressif:ESP32-S3-WROOM-1' and u1.at() == (73.66, 82.55, 0.0)
    for r in REMOVE | {'TP9'}:
        assert r in sym, r

    # 1. whole clusters made only of removed parts (plus their power symbols)
    groups = clusters(s)
    for g in groups:
        refs = {it.ref for it in g if it.kind == 'symbol' and not it.ref.startswith('#')}
        if refs and refs <= REMOVE:
            drop |= {id(it) for it in g}
        if refs == {'TP9'}:
            for it in g:
                edits[id(it)] = translate(it.text, *TP9_MOVE)

    # 2. the UVLO network keeps R7/R8/C13; only the USB leg (D3, R9, VBUS) goes
    uvlo = next(g for g in groups if any(it.kind == 'symbol' and it.ref == 'R7' for it in g))
    usb_leg = {((353.06, 165.1), (356.87, 165.1)), ((364.49, 165.1), (368.3, 165.1)),
               ((375.92, 165.1), (381.0, 165.1))}
    n = 0
    for it in uvlo:
        if it.kind == 'symbol' and it.ref in ('D3', 'R9'):
            drop.add(id(it)); n += 1
        elif it.kind == 'label' and sval(it.tree[1]) == 'VBUS':
            drop.add(id(it)); n += 1
        elif it.kind == 'wire' and tuple(s.points(it)) in usb_leg:
            drop.add(id(it)); n += 1
    assert n == 6, n                       # D3, R9, VBUS and three wire stubs

    # 3. U1's cluster: keep C1/C2, their ground, the ESP_3V3 label and PWR_FLAG
    mcu = next(g for g in groups if any(it.kind == 'symbol' and it.ref == 'U1' for it in g))
    pins = {(round(x, 2), round(y, 2)) for _, x, y in s.pin_positions(u1)}
    keep_sym = {'C1', 'C2', '#PWR02', '#FLG03'}
    old_3v3 = ((73.66, 33.02), (73.66, 41.91))
    n = 0
    for it in mcu:
        if it.kind == 'symbol':
            if it.ref == '#PWR01':         # U1 itself is replaced in place below
                drop.add(id(it)); n += 1
            else:
                assert it.ref in keep_sym | {'U1'}, it.ref
        elif it.kind in ('label', 'no_connect'):
            x, y, _ = it.at()
            if (round(x, 2), round(y, 2)) in pins or sval(it.tree[1]) in ('CHIP_PU', 'USB_D+', 'USB_D-'):
                drop.add(id(it)); n += 1
        elif it.kind == 'wire':
            pts = tuple(s.points(it))
            if pts == old_3v3:
                # the new 3V3 pins sit at y 38.1: shorten the drop from PWR_FLAG
                edits[id(it)] = it.text.replace('(xy 73.66 41.91)', '(xy 73.66 38.1)')
                assert edits[id(it)] != it.text
            elif any((round(x, 2), round(y, 2)) in pins for x, y in pts) and pts != old_3v3:
                drop.add(id(it)); n += 1
    print('MCU cluster: dropped', n, 'items')

    # 4. the new U1, its labels, flags and ground
    lib = lib_symbol_text()
    s.libs[LIB_ID] = parse(lib)[0]
    lib_pins = {n: (x, y) for n, x, y in s.lib_pins(LIB_ID)}
    assert set(lib_pins) == set(U1_NETS), set(lib_pins) ^ set(U1_NETS)
    edits[id(u1)] = u1_text(u1.uuid, U1_NETS)
    done = set()
    for num, net in U1_NETS.items():
        px, py = lib_pins[num]
        x, y = round(U1_AT[0] + px, 2), round(U1_AT[1] - py, 2)
        if (x, y) in done:                 # stacked pins share one point
            continue
        done.add((x, y))
        if net == '3V3':
            assert (x, y) == (73.66, 38.1)
        elif net == 'GND':
            add.append(gnd_symbol('#PWR01', x, y, text))
        elif net is None:
            add.append(no_connect(x, y))
        else:
            add.append(label(net, x, y, 180 if px < 0 else 0))

    # 5. encoder B OUT B: GPIO38 -> GPIO18 at R22 and J9.2
    n = 0
    for it in s.items:
        if it.kind == 'label' and sval(it.tree[1]) == 'GPIO38' and it.at()[:2] in ((177.8, 254.0), (181.61, 245.11)):
            edits[id(it)] = it.text.replace('(label "GPIO38"', '(label "GPIO18"', 1)
            n += 1
    assert n == 2, n

    # 6. notes and frames
    for it in s.items:
        if it.kind == 'text':
            v = sval(it.tree[1])
            if v in TEXT_EDITS:
                edits[id(it)] = it.text.replace('"%s"' % v, '"%s"' % TEXT_EDITS[v], 1)
            elif v.startswith(TEXT_DROP):
                drop.add(id(it))
        elif it.kind == 'rectangle':
            st, en = kid(it.tree, 'start'), kid(it.tree, 'end')
            key = ((float(st[1]), float(st[2])), (float(en[1]), float(en[2])))
            if key in FRAME_DROP:
                drop.add(id(it))
    for i, line in enumerate(NOTES):
        if line:
            add.append(text_item(line, NOTES_AT[0], NOTES_AT[1] + 2.54 * i))

    gone = {it.ref for it in s.items if it.kind == 'symbol' and id(it) in drop}
    assert REMOVE <= gone, REMOVE - gone

    # stitch the sheet back together
    out, pos = [], 0
    for it in s.items:
        out.append(text[pos:it.s])
        if id(it) not in drop:
            out.append(edits.get(id(it), it.text))
        pos = it.e
    tail = text[pos:]
    body = ''.join(out)
    # new items go before the sheet_instances block
    k = body.rfind('\n\t(sheet_instances')
    if k < 0:
        k = len(body)
    body = body[:k] + ''.join('\n\t' + a for a in add) + body[k:]
    body += tail

    # 7. symbol cache: add the devkit, drop symbols nothing uses any more
    used = set(re.findall(r'\(lib_id "([^"]+)"\)', body))
    cache = re.search(r'\n\t\(lib_symbols\n', body)
    start = cache.end()
    _, cend = parse(body, cache.start() + 2)
    region = body[start:cend]
    pieces, i = [], 0
    for m in re.finditer(r'\t\t\(symbol "([^"]+)"\n', region):
        if m.start() < i:
            continue
        _, e = parse(region, m.start() + 2)
        pieces.append((m.group(1), m.start(), e))
        i = e
    new_region, last = [], 0
    for name, a, e in pieces:
        new_region.append(region[last:a])
        if name in used:
            new_region.append(region[a:e])
        else:
            print('cache: dropped', name)
            # swallow the newline that followed it
            if region[e:e + 1] == '\n':
                e += 1
        last = e
    rest = region[last:]
    devkit = '\t\t' + lib.replace('\n', '\n\t')
    new_region = ''.join(new_region).rstrip('\n') + '\n' + devkit + rest
    body = body[:start] + new_region + body[cend:]
    open(dst, 'w').write(body)
    print('wrote', dst, '| dropped', len(drop), 'items, edited', len(edits), ', added', len(add))


if __name__ == '__main__':
    main(*sys.argv[1:3])
