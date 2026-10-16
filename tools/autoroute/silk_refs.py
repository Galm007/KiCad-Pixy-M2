"""Place reference designators and test-point labels clear of pads and silkscreen.

Used by power_integrity.py while it still edits text (before any copper).  The
new parts sit in clusters, so a library-default reference lands on a neighbour's
pad or outline.  Each text is tried at positions around its part (above,
below, either side, then further out and rotated), the first one clear of every
pad, every silkscreen item and the board edge is kept, and it then blocks the
texts placed after it.  A reference with no clear position is hidden on F.SilkS
(F.Fab still names the part) and reported.

Text boxes follow KiCad's measured stroke-font extents (0.86-0.94 mm a
character at 1 mm); 0.18 mm is kept to pads and silkscreen (DRC asks 0.15),
and DRC's silk checks confirm the result.
"""
import math
import re

from sexp import parse, children, child, val

SIZE = 1.0                 # the board's minimum text height (Pixy-M2.kicad_pro)
THICK = 0.15
GAP = 0.25                 # text box to its own part
PAD_CLEAR = 0.18
SILK_CLEAR = 0.18       # DRC: 0.15


def _xf(fx, fy, rot, px, py):
    a = math.radians(rot)
    return fx + px * math.cos(a) + py * math.sin(a), fy - px * math.sin(a) + py * math.cos(a)


def _box(pts, m=0.0):
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    return (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def text_box(cx, cy, s, angle, size=SIZE):
    w = len(s) * 0.9 * size + 0.05       # measured: 0.86-0.94 mm a character
    h = size * 1.15 + THICK              # measured: 1.15-1.25 mm
    if round(angle) % 180 == 90:
        w, h = h, w
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _seg_box(a, b, w, m):
    return _box([a, b], w / 2 + m)


def _fp_items(f):
    at = child(f, 'at')
    fx, fy = float(at[1]), float(at[2])
    rot = float(at[3]) if len(at) > 3 else 0.0
    ref = next((val(pr[2]) for pr in children(f, 'property') if val(pr[1]) == 'Reference'), '?')
    pads, silk, texts = [], [], []
    for pad in children(f, 'pad'):
        lay = [val(l) for l in child(pad, 'layers')[1:]]
        if not any(l in ('F.Cu', '*.Cu') for l in lay):
            continue
        pa = child(pad, 'at')
        px, py = float(pa[1]), float(pa[2])
        pr = float(pa[3]) if len(pa) > 3 else 0.0
        sz = child(pad, 'size')
        w, h = float(sz[1]), float(sz[2])
        cx, cy = _xf(fx, fy, rot, px, py)
        a = math.radians(pr)
        corners = [(cx + u * math.cos(a) + v * math.sin(a), cy - u * math.sin(a) + v * math.cos(a))
                   for u, v in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
        pads.append(_box(corners))
    for g in children(f, 'fp_line') + children(f, 'fp_rect') + children(f, 'fp_poly') + \
            children(f, 'fp_circle') + children(f, 'fp_arc'):
        ly = child(g, 'layer')
        if not ly or val(ly[1]) != 'F.SilkS':
            continue
        st = child(g, 'stroke')
        w = float(child(st, 'width')[1]) if st and child(st, 'width') else 0.12
        if g[0] in ('fp_line', 'fp_rect'):
            a_, b_ = child(g, 'start'), child(g, 'end')
            a = _xf(fx, fy, rot, float(a_[1]), float(a_[2]))
            b = _xf(fx, fy, rot, float(b_[1]), float(b_[2]))
            if g[0] == 'fp_line':
                silk.append(_seg_box(a, b, w, 0))
            else:
                c = _xf(fx, fy, rot, float(a_[1]), float(b_[2]))
                d = _xf(fx, fy, rot, float(b_[1]), float(a_[2]))
                for p, q in ((a, c), (c, b), (b, d), (d, a)):
                    silk.append(_seg_box(p, q, w, 0))
        elif g[0] == 'fp_circle':
            c_, e_ = child(g, 'center'), child(g, 'end')
            c = _xf(fx, fy, rot, float(c_[1]), float(c_[2]))
            r = math.hypot(float(e_[1]) - float(c_[1]), float(e_[2]) - float(c_[2]))
            silk.append((c[0] - r - w / 2, c[1] - r - w / 2, c[0] + r + w / 2, c[1] + r + w / 2))
        elif g[0] == 'fp_arc':
            pts = [_xf(fx, fy, rot, float(child(g, k)[1]), float(child(g, k)[2])) for k in ('start', 'mid', 'end')]
            silk.append(_box(pts, w / 2))
        else:
            pts = [_xf(fx, fy, rot, float(q[1]), float(q[2])) for q in children(child(g, 'pts'), 'xy')]
            for p, q in zip(pts, pts[1:] + pts[:1]):
                silk.append(_seg_box(p, q, w, 0))
    for t in children(f, 'property') + children(f, 'fp_text'):
        ly = child(t, 'layer')
        if not ly or val(ly[1]) != 'F.SilkS' or child(t, 'hide') is not None:
            continue
        name = val(t[1]) if t[0] == 'property' else val(t[1])
        s = val(t[2])
        if t[0] == 'fp_text' and val(t[1]) == 'reference':
            name = 'Reference'
        at_ = child(t, 'at')
        cx, cy = _xf(fx, fy, rot, float(at_[1]), float(at_[2]))
        ang = float(at_[3]) if len(at_) > 3 else 0.0
        eff = child(t, 'effects')
        size = SIZE
        if eff and child(eff, 'font') and child(child(eff, 'font'), 'size'):
            size = float(child(child(eff, 'font'), 'size')[1])
        texts.append((name, s, text_box(cx, cy, s, ang, size)))
    return ref, (fx, fy, rot), pads, silk, texts


def _board_obstacles(t, moving_refs, moving_texts):
    obst = []
    parts = {}
    for f in children(t, 'footprint'):
        ref, at, pads, silk, texts = _fp_items(f)
        parts[ref] = (at, pads, silk)
        obst += [_box([(b[0], b[1]), (b[2], b[3])], PAD_CLEAR) for b in pads]
        obst += [_box([(b[0], b[1]), (b[2], b[3])], SILK_CLEAR) for b in silk]
        for name, s, b in texts:
            if not (name == 'Reference' and ref in moving_refs):
                obst.append(_box([(b[0], b[1]), (b[2], b[3])], SILK_CLEAR))
    for g in children(t, 'gr_text'):
        if val(child(g, 'layer')[1]) != 'F.SilkS' or val(g[1]) in moving_texts:
            continue
        at = child(g, 'at')
        ang = float(at[3]) if len(at) > 3 else 0.0
        b = text_box(float(at[1]), float(at[2]), val(g[1]), ang)
        obst.append(_box([(b[0], b[1]), (b[2], b[3])], SILK_CLEAR))
    for kind in ('gr_line', 'gr_rect', 'gr_circle', 'gr_arc', 'gr_poly'):
        for g in children(t, kind):
            ly = child(g, 'layer')
            if not ly or val(ly[1]) != 'F.SilkS':
                continue
            st = child(g, 'stroke')
            w = float(child(st, 'width')[1]) if st and child(st, 'width') else 0.15
            if kind == 'gr_line':
                a_, b_ = child(g, 'start'), child(g, 'end')
                obst.append(_seg_box((float(a_[1]), float(a_[2])), (float(b_[1]), float(b_[2])), w, SILK_CLEAR))
            elif kind == 'gr_rect':
                a_, b_ = child(g, 'start'), child(g, 'end')
                x0, y0, x1, y1 = float(a_[1]), float(a_[2]), float(b_[1]), float(b_[2])
                for p, q in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
                    obst.append(_seg_box(p, q, w, SILK_CLEAR))
            elif kind == 'gr_circle':
                c_, e_ = child(g, 'center'), child(g, 'end')
                r = math.hypot(float(e_[1]) - float(c_[1]), float(e_[2]) - float(c_[2]))
                cx, cy = float(c_[1]), float(c_[2])
                # a ring: only its outline is silk; model it as 16 short chords
                pts = [(cx + r * math.cos(k * math.pi / 8), cy + r * math.sin(k * math.pi / 8)) for k in range(16)]
                for p, q in zip(pts, pts[1:] + pts[:1]):
                    obst.append(_seg_box(p, q, w, SILK_CLEAR))
            elif kind == 'gr_arc':
                pts = [(float(child(g, k)[1]), float(child(g, k)[2])) for k in ('start', 'mid', 'end')]
                obst.append(_box(pts, w / 2 + SILK_CLEAR))
            else:
                pts = [(float(q[1]), float(q[2])) for q in children(child(g, 'pts'), 'xy')]
                for p, q in zip(pts, pts[1:] + pts[:1]):
                    obst.append(_seg_box(p, q, w, SILK_CLEAR))
    return obst, parts


BOARD = (100.0, 60.0, 166.0, 160.0)


def _inside_board(b, m=0.5):
    return b[0] >= BOARD[0] + m and b[1] >= BOARD[1] + m and b[2] <= BOARD[2] - m and b[3] <= BOARD[3] - m


def _candidates(anchor, s, near=None, centre=None):
    """text centres and angles around an anchor box, nearest first"""
    x0, y0, x1, y1 = anchor
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    out = []
    if centre:                       # on the part's own body (ICs)
        out += [(centre[0], centre[1], 90), (centre[0], centre[1], 0)]
    for extra in (0.0, 0.5, 1.0, 1.6):          # further reads as a neighbour's
        for ang in (0, 90):
            w0 = text_box(0, 0, s, ang)
            hw, hh = (w0[2] - w0[0]) / 2, (w0[3] - w0[1]) / 2
            g = GAP + extra
            for d in (0, -0.6, 0.6, -1.2, 1.2, -2.0, 2.0, -3.0, 3.0):
                out.append((cx + d, y0 - g - hh, ang))       # above
                out.append((cx + d, y1 + g + hh, ang))       # below
                out.append((x0 - g - hw, cy + d, ang))       # left
                out.append((x1 + g + hw, cy + d, ang))       # right
    if near:
        out[2 if centre else 0:] = sorted(out[2 if centre else 0:],
                                          key=lambda c: math.hypot(c[0] - near[0], c[1] - near[1]))
    return out


def set_ref_text(p, ref, cx, cy, ang, hide=False):
    """write a footprint's Reference position (board coordinates, absolute angle)"""
    i, j = p.footprint_span(ref)
    blk = p.text[i:j]
    m = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\n', blk)
    fx, fy, rot = float(m.group(1)), float(m.group(2)), float(m.group(3) or 0.0)
    a = math.radians(rot)
    bx, by = cx - fx, cy - fy
    lx = bx * math.cos(a) - by * math.sin(a)
    ly = bx * math.sin(a) + by * math.cos(a)
    m = re.search(r'(\(property "Reference" "[^"]*"\s*\n\s*\(at )([-\d.]+ [-\d.]+(?: [-\d.]+)?)\)', blk)
    assert m, ref
    blk = blk[:m.start(2)] + '%.4g %.4g %g' % (lx, ly, ang) + blk[m.end(2):]
    k = m.end(2)
    e = blk.index('(effects', k)
    head, tail = blk[:e], blk[e:]
    head = head.replace('\t\t\t(hide yes)\n', '')
    if hide:
        head = head.rstrip('\t') + '\t\t\t(hide yes)\n\t\t\t'
    head = re.sub(r'\(layer "[^"]*"\)', '(layer "F.SilkS")', head, count=1)
    blk = head + tail
    p.text = p.text[:i] + blk + p.text[j:]
    p._split()


GR_TEXT = '''\t(gr_text "{s}"
\t\t(at {x:.4g} {y:.4g} {a:g})
\t\t(layer "F.SilkS")
\t\t(uuid "{u}")
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1 1)
\t\t\t\t(thickness 0.15)
\t\t\t)
\t\t)
\t)
'''


def drop_text(p, s, near):
    """delete the board text s nearest to `near` (another text may share it)"""
    best = None
    for m in re.finditer(r'\n\t\(gr_text "%s"\s*\n\s*\(at ([-\d.]+) ([-\d.]+)' % re.escape(s), p.text):
        d = math.hypot(float(m.group(1)) - near[0], float(m.group(2)) - near[1])
        if best is None or d < best[0]:
            best = (d, m.start())
    assert best and best[0] < 1.0, (s, near)
    i = best[1] + 1
    j = p.text.index('\n\t)\n', i) + 4
    p.text = p.text[:i] + p.text[j:]
    p._split()


def place(p, refs, labels=None, keep=(), ics=()):
    """refs: footprints whose Reference should be shown and placed clear.
    labels: {board text: test-point ref}: board-level texts added beside that
    pad.  keep: refs whose current position is tried first.  ics: refs that
    may carry their reference on their own body.  Returns the number placed."""
    import uuid
    labels = labels or {}
    t = parse(p.text)
    obst, parts = _board_obstacles(t, set(refs), set(labels))
    placed = 0
    hidden = []
    current = {}
    for f in children(t, 'footprint'):
        ref, at, pads, silk, texts = _fp_items(f)
        for name, s, b in texts:
            if name == 'Reference':
                current[ref] = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    def cands_of(s, ref, tp):
        owner = ref or tp
        (fx, fy, rot), pads, silk = parts[owner]
        anchor = _box([(b[0], b[1]) for b in pads + silk] + [(b[2], b[3]) for b in pads + silk])
        cands = _candidates(anchor, s, near=(fx, fy), centre=(fx, fy) if owner in ics else None)
        if ref in keep and ref in current:
            cands.insert(0, (current[ref][0], current[ref][1], 0))
        return [c for c in cands if _inside_board(text_box(c[0], c[1], s, c[2]))
                and not any(_hit(text_box(c[0], c[1], s, c[2]), o) for o in obst)]
    # test-pad labels first (a probe needs them more than assembly needs a
    # designator), then the designators with the fewest clear positions
    todo = [(s, None, tp) for s, tp in labels.items()]
    todo += sorted([(r, r, None) for r in refs], key=lambda e: (len(cands_of(*e)), e[0]))
    for s, ref, tp in todo:
        owner = ref or tp
        fx, fy = parts[owner][0][:2]
        for cx, cy, ang in cands_of(s, ref, tp):
            b = text_box(cx, cy, s, ang)
            if _inside_board(b) and not any(_hit(b, o) for o in obst):
                obst.append(_box([(b[0], b[1]), (b[2], b[3])], SILK_CLEAR))
                if ref:
                    set_ref_text(p, ref, cx, cy, ang)
                else:
                    i = p.text.index('\n\t(gr_')
                    p.text = p.text[:i + 1] + GR_TEXT.format(s=s, x=cx, y=cy, a=ang, u=uuid.uuid4()) + p.text[i + 1:]
                    p._split()
                placed += 1
                break
        else:
            if ref:
                set_ref_text(p, ref, fx, fy, 0, hide=True)
            hidden.append(s)
    if hidden:
        print('    no clear silkscreen position, hidden on F.SilkS:', ', '.join(hidden))
    return placed
