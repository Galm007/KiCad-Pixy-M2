"""Check drill edges against actual pad mask/paste openings, including paste-only pads.

Run with KiCad's Python: /usr/bin/python3 tools/autoroute/via_openings.py BOARD
The 0.10 mm margin is this board's design allowance, not a JLCPCB process limit.
Only the four explicitly filled/capped DRV8231A thermal vias are exempt, and only
for their own exposed-pad mask and paste apertures. Unknown pad shapes fail closed.
"""
import argparse
import json
import math
import pcbnew as pcb

MARGIN = 0.10
TOL = 0.000002  # KiCad stores integer nanometres.
THERMAL = {(109.0, 113.6): 'U4', (109.0, 114.4): 'U4',
           (117.0, 113.6): 'U5', (117.0, 114.4): 'U5'}


def point_gap(x, y, shape):
    """Signed distance to a circle, oval, rectangle or rounded rectangle."""
    dx, dy = x - shape['x'], y - shape['y']
    a = math.radians(shape['angle'])
    u = abs(math.cos(a) * dx - math.sin(a) * dy)
    v = abs(math.sin(a) * dx + math.cos(a) * dy)
    r = shape['radius']
    qx, qy = u - shape['w'] / 2 + r, v - shape['h'] / 2 + r
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r


def pad_shape(pad, ref, layer=None):
    w, h = pcb.ToMM(pad.GetSize().x), pcb.ToMM(pad.GetSize().y)
    kind = pad.GetShape()
    if kind not in (pcb.PAD_SHAPE_CIRCLE, pcb.PAD_SHAPE_OVAL,
                    pcb.PAD_SHAPE_RECT, pcb.PAD_SHAPE_ROUNDRECT):
        raise ValueError(f'Unsupported pad shape: {ref}.{pad.GetNumber()} ({kind})')
    radius = (min(w, h) / 2 if kind in (pcb.PAD_SHAPE_CIRCLE, pcb.PAD_SHAPE_OVAL)
              else pcb.ToMM(pad.GetRoundRectCornerRadius()) if kind == pcb.PAD_SHAPE_ROUNDRECT else 0)
    mx = my = 0
    if layer in (pcb.F_Mask, pcb.B_Mask):
        mx = my = pcb.ToMM(pad.GetSolderMaskExpansion(layer))
    elif layer in (pcb.F_Paste, pcb.B_Paste):
        m = pad.GetSolderPasteMargin(layer)
        mx, my = pcb.ToMM(m.x), pcb.ToMM(m.y)
    if abs(mx - my) > TOL:
        raise ValueError(f'Anisotropic aperture expansion needs polygon checking: {ref}.{pad.GetNumber()}')
    w, h = w + 2 * mx, h + 2 * my
    if w <= 0 or h <= 0:
        raise ValueError(f'Nonpositive aperture: {ref}.{pad.GetNumber()}')
    radius = min(w / 2, h / 2, max(0, radius + mx))
    return dict(ref=ref, number=pad.GetNumber(), uuid=pad.m_Uuid.AsString(),
                layer=pcb.LayerName(layer) if layer is not None else None,
                x=pcb.ToMM(pad.GetPosition().x), y=pcb.ToMM(pad.GetPosition().y),
                w=w, h=h, angle=pad.GetOrientationDegrees(), radius=radius,
                net=pad.GetNetname())


def apertures(board):
    out = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            for layer in (pcb.F_Mask, pcb.B_Mask, pcb.F_Paste, pcb.B_Paste):
                if pad.IsOnLayer(layer):
                    out.append(pad_shape(pad, fp.GetReference(), layer))
    return out


def thermal_pair(via, opening):
    ref = THERMAL.get((round(via['x'], 6), round(via['y'], 6)))
    return (ref == opening['ref'] and opening['number'] in ('9', '')
            and opening['layer'] in ('F.Mask', 'F.Paste')
            and via['net'] == 'GND' and abs(via['drill'] - 0.25) < TOL
            and abs(via['size'] - 0.45) < TOL)


def audit(board):
    openings = apertures(board)
    result = dict(margin_mm=MARGIN, via_count=0, thermal=[], violations=[], nearest=[])
    for v in board.GetTracks():
        if not isinstance(v, pcb.PCB_VIA):
            continue
        result['via_count'] += 1
        d = dict(uuid=v.m_Uuid.AsString(), x=pcb.ToMM(v.GetPosition().x),
                 y=pcb.ToMM(v.GetPosition().y), size=pcb.ToMM(v.GetWidth(pcb.F_Cu)),
                 drill=pcb.ToMM(v.GetDrillValue()), net=v.GetNetname(),
                 filled=v.GetFillingMode() == pcb.FILLING_MODE_FILLED,
                 capped=v.GetCappingMode() == pcb.CAPPING_MODE_CAPPED)
        ordinary = []
        for a in openings:
            gap = point_gap(d['x'], d['y'], a) - d['drill'] / 2
            row = dict(**d, opening=a, gap_mm=round(gap, 9))
            if thermal_pair(d, a):
                if not d['filled'] or not d['capped']:
                    result['violations'].append(dict(**row, reason='thermal via needs explicit fill and cap'))
                continue
            ordinary.append(row)
        nearest = min(ordinary, key=lambda r: r['gap_mm'])
        result['nearest'].append(nearest)
        if nearest['gap_mm'] < MARGIN - TOL:
            result['violations'].append(dict(**nearest, reason='drill too close to pad opening'))
        if (round(d['x'], 6), round(d['y'], 6)) in THERMAL:
            result['thermal'].append(d)
    if len(result['thermal']) != 4:
        result['violations'].append(dict(reason='expected exactly four designated thermal vias'))
    result['minimum_ordinary_gap_mm'] = min(r['gap_mm'] for r in result['nearest'])
    result['unintended_overlapping_vias'] = sum(r['gap_mm'] < -TOL for r in result['nearest'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board')
    parser.add_argument('--output')
    args = parser.parse_args()
    result = audit(pcb.LoadBoard(args.board))
    output = json.dumps(result, indent=2) + '\n'
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
    else:
        print(output)
    raise SystemExit(bool(result['violations']))


if __name__ == '__main__':
    main()
