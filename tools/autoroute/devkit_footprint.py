#!/usr/bin/env python3
"""Footprint for the ESP32-S3-DevKitC-1 on two 1x22 SMD female headers.

Writes ../../Pixy-M2.pretty/ESP32-S3-DevKitC-1_SMD_Sockets.kicad_mod.

Two copies of KiCad's `PinSocket_1x22_P2.54mm_Vertical_SMD_Pin1Left` (the
Harwin M20-786 land pattern) 22.86 mm apart, numbered as Espressif's
`ESP32-S3-DevKitC` symbol and footprint: J1 (3V3 ... 5V, GND) is pads 1-22 at
x = 0, J3 is pads 44 (GND, top) down to 23 at x = 22.86.  The origin is pad 1
and the antenna end of the devkit is toward -y, as in Espressif's footprint.

SMD sockets, not through-hole: the devkit's footprint on Pixy-M2 lies over the
underside battery bay and motor B, and through-hole tails would stand into both.

The courtyard is the two socket bodies only.  The devkit itself stands about
10 mm up (7.5 mm socket body + the 2.5 mm spacer of its own male headers), so
the low parts and copper between and in front of the rows are legal; the devkit
outline, its antenna overhang and USB ports are drawn on F.Fab.  F.SilkS marks
which end the USB ports go, because a devkit plugged in turned round puts the
3V3 rail onto GND pins.

There is no DevKitC 3D model, so the render stands Espressif's WROOM-1 model at
the module's real position and height above the two socket models.
"""
import os
import re
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'Pixy-M2.pretty', 'ESP32-S3-DevKitC-1_SMD_Sockets.kicad_mod')
SOCKET = ('/usr/share/kicad/footprints/Connector_PinSocket_2.54mm.pretty/'
          'PinSocket_1x22_P2.54mm_Vertical_SMD_Pin1Left.kicad_mod')
NAME = 'ESP32-S3-DevKitC-1_SMD_Sockets'

ROW = 22.86             # J1 to J3, Espressif drawing DXF_ESP32-S3-DevKitC-1_V1.1
PITCH = 2.54
SOCK_CY = 10.5 * PITCH  # socket centre: pads 1..22 at y 0 .. 53.34
# devkit PCB, Espressif dimension drawing (v1.1, 2022-04-29): 25.40 x 62.74 mm,
# pin rows 1.27 mm in from each long edge and the first pins 1.27 mm from the
# antenna end.  The module's antenna overhangs that end; the drawing shows about
# 6.5 mm, Espressif's own footprint 5.74 mm, so 6.5 is used.
KIT_X = (-1.27, ROW + 1.27)
KIT_Y = (-1.27, -1.27 + 62.74)
ANT = (2.43, 20.43, -1.27 - 6.5)          # module 18 mm wide, centred on the kit
USB = [(4.8, 'UART'), (17.68, 'USB')]     # port centres, x from the J1 edge
MODULE_Z = 7.5 + 2.5 + 1.6                # socket + male-header spacer + kit PCB


def fx(v):
    return ('%.4f' % round(v, 4)).rstrip('0').rstrip('.')


def line(x1, y1, x2, y2, layer, w):
    return ('\t(fp_line\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(stroke\n\t\t\t(width %s)\n'
            '\t\t\t(type solid)\n\t\t)\n\t\t(layer "%s")\n\t\t(uuid "%s")\n\t)\n'
            % (fx(x1), fx(y1), fx(x2), fx(y2), fx(w), layer, uuid.uuid4()))


def rect(x1, y1, x2, y2, layer, w):
    return (line(x1, y1, x2, y1, layer, w) + line(x2, y1, x2, y2, layer, w) +
            line(x2, y2, x1, y2, layer, w) + line(x1, y2, x1, y1, layer, w))


def text(s, x, y, layer, size=1.0, rot=0):
    return ('\t(fp_text user "%s"\n\t\t(at %s %s %s)\n\t\t(layer "%s")\n\t\t(uuid "%s")\n'
            '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size %s %s)\n\t\t\t\t(thickness 0.15)\n'
            '\t\t\t)\n\t\t)\n\t)\n' % (s, fx(x), fx(y), fx(rot), layer, uuid.uuid4(),
                                       fx(size), fx(size)))


def model(path, x, y, z, rz=0):
    return ('\t(model "%s"\n\t\t(offset\n\t\t\t(xyz %s %s %s)\n\t\t)\n\t\t(scale\n'
            '\t\t\t(xyz 1 1 1)\n\t\t)\n\t\t(rotate\n\t\t\t(xyz 0 0 %s)\n\t\t)\n\t)\n'
            % (path, fx(x), fx(-y), fx(z), fx(rz)))


def socket_items():
    """the stock socket's lines and pads, in its own frame"""
    s = open(SOCKET).read()
    lines = [(float(a), float(b), float(c), float(d), lay, float(w)) for a, b, c, d, w, lay in
             re.findall(r'\(fp_line\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)'
                        r'\s*\(stroke\s*\(width ([-\d.]+)\).*?\(layer "([^"]+)"\)', s, re.S)]
    pads = [(int(n), float(x), float(y), float(w), float(h)) for n, x, y, w, h in
            re.findall(r'\(pad "(\d+)" smd rect\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+) ([-\d.]+)\)', s)]
    assert len(pads) == 22 and pads[0][:3] == (1, -1.65, -26.67), pads[0]
    return lines, pads


def build():
    lines, pads = socket_items()
    out = ['(footprint "%s"\n\t(version 20260206)\n\t(generator "pixy-m2-devkit_footprint")\n'
           '\t(layer "F.Cu")\n'
           '\t(descr "ESP32-S3-DevKitC-1 (v1.1) plugged into two 1x22 2.54 mm vertical SMD female '
           'headers (Harwin M20-786 land pattern, pin 1 left). Pads numbered as Espressif\'s '
           'ESP32-S3-DevKitC symbol. Courtyard = the two socket bodies; the devkit stands ~10 mm '
           'above the board, outline on F.Fab.")\n'
           '\t(tags "ESP32-S3 DevKitC socket daughterboard")\n' % NAME]
    out.append('\t(property "Reference" "REF**"\n\t\t(at %s %s 0)\n\t\t(layer "F.SilkS")\n'
               '\t\t(uuid "%s")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n'
               '\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n'
               % (fx(10.7), fx(33.0), uuid.uuid4()))
    out.append('\t(property "Value" "%s"\n\t\t(at %s %s 90)\n\t\t(layer "F.Fab")\n'
               '\t\t(uuid "%s")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n'
               '\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n'
               % (NAME, fx(ROW / 2 - 2), fx(SOCK_CY), uuid.uuid4()))
    out.append('\t(attr smd)\n\t(duplicate_pad_numbers_are_jumpers no)\n')

    # both sockets: silkscreen, courtyard and fab as the stock footprint draws them
    for cx in (0.0, ROW):
        for x1, y1, x2, y2, lay, w in lines:
            # J1's pin-1 tick points off the board's outer edge, into the R3
            # corner on Pixy-M2; the 3V3 label below marks pin 1 instead
            if cx == 0.0 and lay == 'F.SilkS' and min(x1, x2) < -1.4:
                continue
            out.append(line(x1 + cx, y1 + SOCK_CY, x2 + cx, y2 + SOCK_CY, lay, w))

    # the devkit itself, on F.Fab
    fab = 'F.Fab'
    out.append(rect(KIT_X[0], KIT_Y[0], KIT_X[1], KIT_Y[1], fab, 0.1))
    out.append(rect(ANT[0], ANT[2], ANT[1], KIT_Y[0], fab, 0.1))
    out.append(text('ANTENNA (overhangs)', ROW / 2, (ANT[2] + KIT_Y[0]) / 2, fab, 0.8))
    for x, name in USB:
        out.append(rect(x - 4.0, KIT_Y[1] - 5.6, x + 4.0, KIT_Y[1] + 0.8, fab, 0.1))
        out.append(text(name, x, KIT_Y[1] - 2.6, fab, 0.8))
    out.append(text('${REFERENCE}', ROW / 2 + 2, SOCK_CY, fab, 1.0, 90))

    # F.SilkS orientation mark between the rows: an arrow toward the end that
    # takes the devkit's USB ports (the end itself lies over the buck block)
    silk = 'F.SilkS'
    ax = 6.2
    out.append(line(ax, 41.8, ax, 45.4, silk, 0.15))
    out.append(line(ax, 45.4, ax - 0.7, 44.4, silk, 0.15))
    out.append(line(ax, 45.4, ax + 0.7, 44.4, silk, 0.15))
    out.append(text('DEVKIT', ROW / 2, 44.2, silk, 1.0))
    out.append(text('USB END', ROW / 2, 42.5, silk, 1.0))
    out.append(text('3V3', 4.6, 0, silk, 1.0))
    out.append(text('GND', ROW - 4.6, 0, silk, 1.0))

    # pads: socket A is J1 (1..22), socket B is J3 (44..23), both pin 1 at the top
    for cx, number in ((0.0, lambda j: j), (ROW, lambda j: 45 - j)):
        for j, x, y, w, h in pads:
            out.append('\t(pad "%d" smd rect\n\t\t(at %s %s)\n\t\t(size %s %s)\n'
                       '\t\t(layers "F.Cu" "F.Mask" "F.Paste")\n\t\t(uuid "%s")\n\t)\n'
                       % (number(j), fx(x + cx), fx(y + SOCK_CY), fx(w), fx(h), uuid.uuid4()))
    out.append('\t(embedded_fonts no)\n')
    sock = ('${KICAD10_3DMODEL_DIR}/Connector_PinSocket_2.54mm.3dshapes/'
            'PinSocket_1x22_P2.54mm_Vertical_SMD_Pin1Left.step')
    out.append(model(sock, 0, SOCK_CY, 0))
    out.append(model(sock, ROW, SOCK_CY, 0))
    # the STEP's origin is the module's left corner at its pin end (Espressif's
    # WROOM-1 footprint offsets it by (-9, -9.75)); the module is 18 x 25.5 mm
    wroom = ('${KICAD10_3RD_PARTY}/3dmodels/com_github_espressif_kicad-libraries/'
             'espressif.3dshapes/ESP32-S3-WROOM-1.STEP')
    out.append(model(wroom, ANT[0], ANT[2] + 25.5, MODULE_Z))
    out.append(')\n')
    return ''.join(out)


if __name__ == '__main__':
    open(OUT, 'w').write(build())
    print('wrote', os.path.normpath(OUT))
