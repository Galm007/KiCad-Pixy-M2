#!/usr/bin/env python3
"""The battery bay between the axles (2026-09-24).

The underside reservation drawn at placement (40 x 30 x 15 mm at board
x 13-53, y 5-35) predates the pack.  The chosen OVONIC 2S 450 mAh is
61.5 x 15.77 x 13.48 mm by its listing and 62 x 17 x 14 mm by its maker, so
it fits neither way round.  Across the front strip it fits, but that puts
31 g, about 30 % of the robot, 36 mm ahead of the front axle: the estimated
CG lands about 6 mm ahead of the front wheels and the robot rests on its nose.

It goes across the board between the two motors instead, centred on the
rotation centre's y.  Board frame (mm from the front-left corner, +y to the
rear; KiCad = board + (100, 60)):

  battery body   x 0.5-62.5, y 57.5-74.5   62 x 17, the maker's envelope
  lead exit      x 62.5-66 at its right end; the rule area runs to the edge
  motor A        y 40-56 (was 44-60)       4 mm encoder allowance now faces
  motor B        y 76-92 (was 72-88)       outboard, not into the battery

Pololu's 12 CPR encoder board stands 3 mm (side connector) or 4 mm (back
connector) proud of the gearmotor on one face, at the encoder end.  That is
what the 4 mm side allowance of each 38 x 16 mm motor envelope is for, and
it used to face the middle of the board.  Each motor now has to be mounted
with that face outboard (or toward the floor), and its brackets may only
use the outboard side: the inboard attachment bands are deleted and the
outboard ones follow their envelope out by 4 mm.  Motor B's outboard band
stops either side of J1's shell tabs.

The XT30 and balance leads leave the pack's right-hand (+x) end, turn
forward in the 3.5 mm left before the edge, run forward on the underside
along x = 64.5 to y = 29.5, cross the front strip and wrap the left edge
between J6 and BT1 to reach BT1 on top.  That is about 13 cm of lead, more
than a stock pack lead.  The route is drawn on User.2.

On B.SilkS it prints the pack's outline and what it is, an arrow at the
end its leads leave from, and the lead route as a dashed line to the left
edge.  assembly_marks.py puts the motors' part names in their (now
outboard) encoder allowance, with ENC CONN SIDE over the encoder.

Runs after assembly_marks.py in rework.py.  Standalone, it converts an
existing board once, moving the motor names on a board marked before
2026-09-24, and checks every drilled pad against the new envelopes:

    /usr/bin/python3 tools/autoroute/battery_bay.py [board.kicad_pcb]
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcbedit import Pcb, fx, uid
from assembly_marks import Marks, MOTORS, GEARBOX, MOTOR, ENCODER

# every coordinate below is KiCad's: board frame + (100, 60)
PACK = (100.5, 117.5, 162.5, 134.5)             # battery body, 62 x 17
BAY = (100.5, 117.5, 166.0, 134.5)              # + lead exit to the edge

# rule-area name: (placement-era rectangle, new rectangle)
RULE_AREAS = {
    'Battery underside reservation': ((113, 65, 153, 95), BAY),
    'Left motor underside reservation': ((100, 104, 138, 120), (100, 100, 138, 116)),
    'Right motor underside reservation': ((128, 132, 166, 148), (128, 136, 166, 152)),
}

# User.1 body envelopes: old rectangle -> new (None = delete)
USER1 = [((113, 65, 153, 95), PACK),
         ((100, 104, 138, 120), (100, 100, 138, 116)),
         ((128, 132, 166, 148), (128, 136, 166, 152))]

# User.2 attachment bands.  Motor B's outboard band would cross J1's shell tabs
# (x 148.9-159.1, from y 153.57) and the notch the connector body sits in, so it
# is split either side of J1's courtyard (x 147.1-160.9).
USER2 = [((110, 65, 113, 89), None),                    # battery bracket L
         ((153, 65, 156, 95), None),                    # battery bracket R
         ((100, 120, 120, 123), None),                  # motor A, inboard
         ((128, 129, 166, 132), None),                  # motor B, inboard
         ((100, 101, 138, 104), (100, 97, 138, 100)),   # motor A, outboard
         ((128, 148, 166, 151), (128, 152, 146.5, 155))]
USER2_ADD = [(161.5, 152, 166, 155)]                    # motor B, outboard east of J1

# (layer, old text, old at) -> (new text, new at), new text None = delete.
# The empty User.2 texts are placement-era anchors, one per attachment band.
TEXTS = [('User.1', r'BATTERY (bottom)\n40 x 30 x 15', (133, 80),
          r'BATTERY (bottom)\n62 x 17 x 14', (111, 126)),  # clear of IMU (top)
         ('User.2', '', (111.5, 77), None, None),
         ('User.2', '', (154.5, 80), None, None),
         ('User.2', '', (110, 121.5), None, None),
         ('User.2', '', (147, 130.5), None, None),
         ('User.2', '', (119, 102.5), '', (119, 98.5)),
         ('User.2', '', (147, 149.5), '', (137.25, 153.5))]

# the pack's leads: out of its right end, forward, across the front strip and
# round the left edge between J6 (courtyard to y 88.33) and BT1 (from 90.45)
LEAD = [(162.5, 126), (164.5, 124), (164.5, 89.5), (100, 89.5)]
LEAD_TEXT = ('BATTERY LEAD: XT30 around the left edge to BT1', (132, 88))

MARKER = 'BATTERY  2S LiPo 450 mAh'     # present once the silkscreen marks are
# the motor names' placement-era spot, inside what is now the battery envelope
OLD_MOTOR_TEXT = {'MOTOR A': (116, 118), 'MOTOR B': (150, 134)}


def _items(text):
    """(start, end, block) for every top-level item of a .kicad_pcb"""
    for m in re.finditer(r'(?m)^\t\(', text):
        i = m.start()
        j = text.find('\n\t)\n', i) + 4
        yield i, j, text[i:j]


def _num(s): return float(s)


def _close(a, b): return all(abs(u - v) < 1e-6 for u, v in zip(a, b))


def _edges(r):
    x0, y0, x1, y1 = r
    return [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
            ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]


def _is_edge(s, e, r):
    return any((_close(s, a) and _close(e, b)) or (_close(s, b) and _close(e, a))
               for a, b in _edges(r))


def _line(layer, x1, y1, x2, y2, dash=False):
    return (f'\t(gr_line\n\t\t(start {fx(x1)} {fx(y1)})\n\t\t(end {fx(x2)} {fx(y2)})\n'
            f'\t\t(stroke\n\t\t\t(width 0.15)\n\t\t\t(type {"dash" if dash else "default"})\n\t\t)\n'
            f'\t\t(layer "{layer}")\n\t\t(uuid "{uid()}")\n\t)\n')


def _rect(layer, r):
    return ''.join(_line(layer, *a, *b) for a, b in _edges(r))


def _text(layer, s, x, y):
    return (f'\t(gr_text "{s}"\n\t\t(at {fx(x)} {fx(y)} 0)\n\t\t(layer "{layer}")\n'
            f'\t\t(uuid "{uid()}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1 1)\n'
            f'\t\t\t\t(thickness 0.15)\n\t\t\t)\n\t\t)\n\t)\n')


def _pts(r):
    x0, y0, x1, y1 = r
    return f'(xy {fx(x0)} {fx(y0)}) (xy {fx(x1)} {fx(y0)}) (xy {fx(x1)} {fx(y1)}) (xy {fx(x0)} {fx(y1)})'


def reserved(p):
    """True once the battery rule area already has the bay's outline"""
    return f'(name "Battery underside reservation")' in p.text and _pts(BAY) in p.text


def reserve(p):
    """move the three underside reservations and redraw User.1 / User.2"""
    p.sync()
    t = p.text
    edits = []          # (start, end, replacement)
    seen = {k: 0 for k in RULE_AREAS}
    lines = {('User.1', r): 0 for r, _ in USER1}
    lines.update({('User.2', r): 0 for r, _ in USER2})
    texts = [0] * len(TEXTS)
    for i, j, b in _items(t):
        if b.startswith('\t(zone'):
            m = re.search(r'\(name "([^"]+)"\)', b)
            if m and m[1] in RULE_AREAS:
                old, new = RULE_AREAS[m[1]]
                assert _pts(old) in b, f'{m[1]}: not the placement-era outline'
                edits.append((i, j, b.replace(_pts(old), _pts(new))))
                seen[m[1]] += 1
        elif b.startswith('\t(gr_line'):
            layer = re.search(r'\(layer "([^"]+)"\)', b)[1]
            table = USER1 if layer == 'User.1' else USER2 if layer == 'User.2' else ()
            s = re.search(r'\(start ([-\d.]+) ([-\d.]+)\)', b)
            e = re.search(r'\(end ([-\d.]+) ([-\d.]+)\)', b)
            s, e = (_num(s[1]), _num(s[2])), (_num(e[1]), _num(e[2]))
            for old, _ in table:
                if _is_edge(s, e, old):
                    edits.append((i, j, ''))
                    lines[layer, old] += 1
                    break
        elif b.startswith('\t(gr_text'):
            for k, (layer, old, at, new, nat) in enumerate(TEXTS):
                head = f'\t(gr_text "{old}"\n\t\t(at {fx(at[0])} {fx(at[1])} 0)\n\t\t(layer "{layer}")\n'
                if b.startswith(head):
                    rep = '' if new is None else b.replace(
                        head, f'\t(gr_text "{new}"\n\t\t(at {fx(nat[0])} {fx(nat[1])} 0)\n'
                              f'\t\t(layer "{layer}")\n', 1)
                    edits.append((i, j, rep))
                    texts[k] += 1
                    break
    assert all(n == 1 for n in seen.values()), seen
    assert all(n == 4 for n in lines.values()), 'an old envelope or band is missing an edge'
    assert all(n == 1 for n in texts), texts
    for i, j, rep in sorted(edits, reverse=True):
        t = t[:i] + rep + t[j:]
    p.text = t
    p._split()

    add = ''.join(_rect('User.1', new) for _, new in USER1)
    add += ''.join(_rect('User.2', new) for _, new in USER2 if new)
    add += ''.join(_rect('User.2', r) for r in USER2_ADD)
    add += ''.join(_line('User.2', *a, *b, dash=True) for a, b in zip(LEAD, LEAD[1:]))
    add += _text('User.2', LEAD_TEXT[0], *LEAD_TEXT[1])
    p.add_zone(add)
    return len(edits)


def marks(p):
    """the battery's B.SilkS outline, lead arrow and dashed lead route"""
    L = 'B.SilkS'
    m = Marks()
    m.group('Battery 2S LiPo')
    x0, y0, x1, y1 = PACK
    m.rect(L, *PACK)
    m.text(L, MARKER, (x0 + x1) / 2, 121.0)
    m.text(L, '62 x 17 face on board, hook-and-loop', (x0 + x1) / 2, 123.5)
    (lx, ly) = LEAD[0]
    m.arrow(L, lx - 6.5, ly, lx - 0.3, ly, head=0.8)     # leads leave this end
    m.text(L, 'XT30 + balance leads', lx - 11.5, ly + 2.5)
    route = LEAD[:-1] + [(LEAD[-1][0] + 0.8, LEAD[-1][1])]   # silk stays off the edge
    for a, b in zip(route, route[1:]):
        m.line(L, *a, *b, dash=True)
    m.arrow(L, route[-1][0] + 2.0, route[-1][1], *route[-1], head=0.8)
    m.text(L, 'XT30 LEAD: ROUND LEFT EDGE TO BT1 (TOP)', *LEAD_TEXT[1])
    p.add_zone(m.sexpr())
    return len(m.items)


def motor_labels(p):
    """one-off: a board marked before 2026-09-24 has each motor's name in the
    inboard allowance.  Move it outboard and add ENC CONN SIDE to the group, as
    assembly_marks.py now draws them."""
    p.sync()
    t, new = p.text, ''
    for name, side, conn, face, d, axle, ty in MOTORS:
        mo, e = face + d * (GEARBOX + MOTOR), face + d * (GEARBOX + MOTOR + ENCODER)
        ox, oy = OLD_MOTOR_TEXT[name]
        old = f'\t(gr_text "Pololu HP 6V N20"\n\t\t(at {fx(ox)} {fx(oy)} 0)\n\t\t(layer "B.SilkS")\n'
        assert t.count(old) == 1, f'{name}: label not at its placement-era spot'
        t = t.replace(old, f'\t(gr_text "Pololu HP 6V N20"\n\t\t(at {fx((face + mo) / 2)} {fx(ty)} 0)\n'
                           '\t\t(layer "B.SilkS")\n')
        m = Marks()
        m.group('')
        m.text('B.SilkS', 'ENC CONN SIDE', (mo + e) / 2, ty)
        g = t.index(f'\t(group "{name} {side.lower()}"\n')
        k = t.index('\n\t\t)\n\t)\n', g)          # end of its member list
        t = t[:k] + f'\n\t\t\t"{m.members[0]}"' + t[k:]
        new += m.items[0]
    p.text = t
    p._split()
    p.add_zone(new)


def battery_bay(p):
    """the whole stage, as rework.py runs it"""
    return reserve(p) + marks(p)


def check(path):
    """every drilled pad clear of every underside envelope and band"""
    import pcbnew
    b = pcbnew.LoadBoard(path)
    boxes = [(n, RULE_AREAS[n][1]) for n in RULE_AREAS]
    boxes += [('band', r) for _, r in USER2 if r] + [('band', r) for r in USER2_ADD]
    clashes, n = [], 0
    for f in b.GetFootprints():
        for pad in f.Pads():
            if not pad.HasHole():
                continue
            n += 1
            q = pad.GetBoundingBox()
            a = [pcbnew.ToMM(v) for v in (q.GetLeft(), q.GetTop(), q.GetRight(), q.GetBottom())]
            for name, (x0, y0, x1, y1) in boxes:
                if a[0] < x1 and a[2] > x0 and a[1] < y1 and a[3] > y0:
                    clashes.append((f.GetReference(), pad.GetNumber(), name))
    print(f'{n} drilled pads checked against {len(boxes)} underside envelopes/bands:',
          clashes or 'no clashes')
    return not clashes


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..', 'Pixy-M2.kicad_pcb')
    p = Pcb(path)
    if reserved(p):
        print(f'{path}: battery bay already reserved')
    else:
        print(f'reservations and drawings: {reserve(p)} items edited')
    if '(gr_text "ENC CONN SIDE"' not in p.text:
        motor_labels(p)
        print('motor names moved to the outboard allowance')
    if f'(gr_text "{MARKER}"' in p.text:
        print(f'{path}: battery marks already present')
    else:
        print(f'battery silkscreen: {marks(p)} items')
    p.write()
    sys.exit(0 if check(path) else 1)
