"""Span-preserving reader for a flat KiCad schematic.

Keeps every top-level item as its original text so edits are coordinate
rewrites only: nothing KiCad wrote is re-serialised.
"""
import math
import re

TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')


def parse(text, start=0):
    """Parse one s-expression starting at text[start] == '('. Returns (tree, end)."""
    stack = []
    for m in TOK.finditer(text, start):
        t = m.group()
        if t == '(':
            stack.append([])
        elif t == ')':
            n = stack.pop()
            if not stack:
                return n, m.end()
            stack[-1].append(n)
        else:
            if t.startswith('"'):
                t = ('STR', t[1:-1].replace('\\"', '"').replace('\\\\', '\\'))
            stack[-1].append(t)
    raise ValueError('unbalanced')


def kids(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def kid(node, name):
    c = kids(node, name)
    return c[0] if c else None


def sval(x):
    return x[1] if isinstance(x, tuple) else x


class Item:
    def __init__(self, text, s, e):
        self.s, self.e = s, e
        self.text = text[s:e]
        self.tree, _ = parse(self.text)
        self.kind = self.tree[0]

    def at(self):
        a = kid(self.tree, 'at')
        return (float(a[1]), float(a[2]), float(a[3]) if len(a) > 3 else 0.0)

    def prop(self, name):
        for p in kids(self.tree, 'property'):
            if sval(p[1]) == name:
                return sval(p[2])
        return None

    @property
    def lib_id(self):
        return sval(kid(self.tree, 'lib_id')[1])

    @property
    def ref(self):
        return self.prop('Reference')

    @property
    def uuid(self):
        return sval(kid(self.tree, 'uuid')[1])


class Sch:
    def __init__(self, path=None, text=None):
        self.path = path
        self.text = text if text is not None else open(path).read()
        self.items = []
        self.libs = {}
        depth = 0
        i = 0
        # walk the top level: find each "\n\t(" child of the root
        root_open = self.text.index('(')
        pos = root_open + 1
        while True:
            m = re.compile(r'\(|\)').search(self.text, pos)
            if self.text[m.start()] == ')':
                break
            tree_end = parse(self.text, m.start())[1]
            it = Item(self.text, m.start(), tree_end)
            if it.kind == 'lib_symbols':
                for ls in kids(it.tree, 'symbol'):
                    self.libs[sval(ls[1])] = ls
            else:
                self.items.append(it)
            pos = tree_end

    # ---- geometry -------------------------------------------------------
    def lib_pins(self, lib_id):
        """[(number, x, y)] in symbol coordinates (y up, as stored)."""
        out = []
        lib = self.libs[lib_id]

        def walk(n):
            for c in n:
                if isinstance(c, list) and c:
                    if c[0] == 'pin':
                        a = kid(c, 'at')
                        num = sval(kid(c, 'number')[1])
                        out.append((num, float(a[1]), float(a[2])))
                    else:
                        walk(c)
        walk(lib)
        return out

    def pin_positions(self, it):
        """Schematic coordinates of every pin of a placed symbol."""
        x, y, r = it.at()
        mirror = kid(it.tree, 'mirror')
        mir = mirror[1] if mirror else None
        out = []
        for num, px, py in self.lib_pins(it.lib_id):
            py = -py                      # library y is up, sheet y is down
            a = math.radians(-r)        # KiCad rotates counter-clockwise on screen
            qx = px * math.cos(a) - py * math.sin(a)
            qy = px * math.sin(a) + py * math.cos(a)
            if mir == 'x':              # mirroring is applied after rotation
                qy = -qy
            elif mir == 'y':
                qx = -qx
            out.append((num, round(x + qx, 3), round(y + qy, 3)))
        return out

    def points(self, it):
        """Connection points an item offers or needs."""
        if it.kind == 'symbol':
            return [(px, py) for _, px, py in self.pin_positions(it)]
        if it.kind == 'wire':
            return [(float(p[1]), float(p[2])) for p in kids(kid(it.tree, 'pts'), 'xy')]
        if it.kind in ('label', 'junction', 'no_connect', 'text'):
            x, y, _ = it.at()
            return [(x, y)]
        return []

    def bbox(self, it):
        pts = self.points(it)
        if it.kind == 'symbol':
            x, y, _ = it.at()
            pts = pts + [(x, y)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)


NUM = r'(-?\d+(?:\.\d+)?)'
AT = re.compile(r'\((at|xy) ' + NUM + ' ' + NUM)


def fmt(v):
    v = round(v, 4)
    if v == int(v):
        return str(int(v))
    return ('%.4f' % v).rstrip('0').rstrip('.')


def translate(text, dx, dy):
    """Shift every (at x y …) and (xy x y) inside one item's text."""
    return AT.sub(lambda m: '(%s %s %s' % (m.group(1), fmt(float(m.group(2)) + dx),
                                            fmt(float(m.group(3)) + dy)), text)


# ---- approximate extents, for layout and overlap checks ---------------------
CHAR_W = 0.80          # stroke-font advance, as a fraction of the font size


def _xform(it, px, py):
    x, y, r = it.at()
    mirror = kid(it.tree, 'mirror')
    mir = mirror[1] if mirror else None
    py = -py
    a = math.radians(-r)
    qx = px * math.cos(a) - py * math.sin(a)
    qy = px * math.sin(a) + py * math.cos(a)
    if mir == 'x':
        qy = -qy
    elif mir == 'y':
        qx = -qx
    return x + qx, y + qy


def _lib_points(lib, unit=None):
    pts = []

    def walk(n):
        for c in n:
            if not (isinstance(c, list) and c):
                continue
            if c[0] == 'pin':
                a = kid(c, 'at')
                ln = float(kid(c, 'length')[1])
                x, y, ang = float(a[1]), float(a[2]), math.radians(float(a[3]))
                pts.append((x, y))
                pts.append((x + ln * math.cos(ang), y + ln * math.sin(ang)))
            elif c[0] in ('xy', 'start', 'end', 'mid'):
                pts.append((float(c[1]), float(c[2])))
            elif c[0] == 'circle':
                cx, cy = map(float, kid(c, 'center')[1:3])
                r = float(kid(c, 'radius')[1])
                pts.extend([(cx - r, cy - r), (cx + r, cy + r)])
            elif c[0] == 'property':
                continue
            else:
                walk(c)
    walk(lib)
    return pts


def text_box(x, y, ang, s, size, justify):
    """Box of a single-line string anchored at (x, y)."""
    w = sum(size * (0.95 if c.isupper() or c.isdigit() else 0.55 if c in ' .,:;|il1!()' else 0.78)
            for c in s)
    h = size * 1.2
    horiz = 'left' if 'left' in justify else 'right' if 'right' in justify else 'center'
    vert = 'bottom' if 'bottom' in justify else 'top' if 'top' in justify else 'center'
    x0 = {'left': 0, 'right': -w, 'center': -w / 2}[horiz]
    y0 = {'bottom': -h, 'top': 0, 'center': -h / 2}[vert]
    if int(round(ang)) % 180 == 90:          # vertical text reads bottom-to-top
        return (x + y0, y - x0 - w, x + y0 + h, y - x0)
    return (x + x0, y + y0, x + x0 + w, y + y0 + h)


def _effects(node):
    e = kid(node, 'effects')
    size = float(kid(kid(e, 'font'), 'size')[1]) if e and kid(e, 'font') else 1.27
    j = kid(e, 'justify') if e else None
    hidden = (kid(node, 'hide') is not None and kid(node, 'hide')[1] == 'yes') or \
        (e is not None and kid(e, 'hide') is not None)
    return size, (j[1:] if j else []), hidden


def extents(s, it, text=True):
    """List of boxes covering an item's graphics and visible text."""
    boxes = []
    if it.kind == 'symbol':
        pts = [_xform(it, px, py) for px, py in _lib_points(s.libs[it.lib_id])]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
        if text:
            for p in kids(it.tree, 'property'):
                size, just, hidden = _effects(p)
                v = sval(p[2])
                if hidden or not v:
                    continue
                a = kid(p, 'at')
                srot = it.at()[2]
                fa = (float(a[3]) if len(a) > 3 else 0) + srot
                if int(round(srot)) % 180 == 90:
                    # a field's justification turns with its symbol and reads flipped
                    swap = {'left': 'right', 'right': 'left', 'top': 'bottom', 'bottom': 'top'}
                    just = [swap.get(j, j) for j in just]
                boxes.append(text_box(float(a[1]), float(a[2]), fa % 180, v, size, just))
    elif it.kind == 'wire':
        (ax, ay), (bx, by) = s.points(it)
        boxes.append((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)))
    elif it.kind in ('junction', 'no_connect'):
        x, y, _ = it.at()
        boxes.append((x - 0.6, y - 0.6, x + 0.6, y + 0.6))
    elif it.kind in ('label', 'text'):
        x, y, a = it.at()
        size, just, _ = _effects(it.tree)
        v = sval(it.tree[1])
        if it.kind == 'label':
            # a label's anchor is its connection point; KiCad writes the
            # justification already resolved for the angle it is drawn at
            pass
        if text:
            lines = v.split('\n')
            for k, line in enumerate(lines):
                boxes.append(text_box(x, y + k * size * 1.6, a, line, size, just))
    elif it.kind == 'rectangle':
        (ax, ay), (bx, by) = [tuple(map(float, kid(it.tree, n)[1:3])) for n in ('start', 'end')]
        boxes.append((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)))
    return boxes


def union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


# ---- editing ------------------------------------------------------------------
import uuid as _uuid


class Editor:
    """Collects item replacements, deletions and additions, then rebuilds the file.

    Items keep their original text and position in the file unless changed.
    """

    def __init__(self, text):
        self.s = Sch(text=text)
        self.by_uuid = {it.uuid: it for it in self.s.items if it.kind in DRAWN}
        self.new_text = {}          # uuid -> replacement text (None = delete)
        self.added = []

    def item(self, uid):
        hits = [u for u in self.by_uuid if u.startswith(uid)]
        assert len(hits) == 1, (uid, hits)
        return self.by_uuid[hits[0]]

    def sym(self, ref):
        hits = [it for it in self.s.items if it.kind == 'symbol' and it.ref == ref]
        assert len(hits) == 1, ref
        return hits[0]

    def cur(self, it):
        return self.new_text.get(it.uuid, it.text)

    def delete(self, uid):
        self.new_text[self.item(uid).uuid] = None

    def translate(self, it, dx, dy):
        self.new_text[it.uuid] = translate(self.cur(it), dx, dy)

    def move_to(self, it, x, y):
        x0, y0, _ = it.at()
        self.translate(it, x - x0, y - y0)

    def set_field(self, it, name, x, y, justify):
        txt = self.cur(it)
        i = txt.index('(property "%s"' % name)
        j = parse(txt, i)[1]
        blk = txt[i:j]
        blk = re.sub(r'\(at \S+ \S+ (\S+)\)', lambda m: '(at %s %s %s)' % (fmt(x), fmt(y), m.group(1)), blk, count=1)
        if '(justify' in blk:
            blk = re.sub(r'\(justify[^)]*\)', '(justify %s)' % justify, blk)
        else:
            blk = blk.replace('\t\t\t\t)\n\t\t\t)', '\t\t\t\t)\n\t\t\t\t(justify %s)\n\t\t\t)' % justify, 1)
        self.new_text[it.uuid] = txt[:i] + blk + txt[j:]

    def move_label(self, uid, x, y, angle=0, justify='left bottom'):
        it = self.item(uid)
        txt = self.cur(it)
        txt = re.sub(r'\(at \S+ \S+ \S+\)', '(at %s %s %s)' % (fmt(x), fmt(y), fmt(angle)), txt, count=1)
        txt = re.sub(r'\(justify[^)]*\)', '(justify %s)' % justify, txt)
        self.new_text[it.uuid] = txt

    def wire(self, *pts):
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            self.added.append(
                '(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n'
                '\t\t\t(type default)\n\t\t)\n\t\t(uuid "%s")\n\t)'
                % (fmt(ax), fmt(ay), fmt(bx), fmt(by), _uuid.uuid4()))

    def label(self, name, x, y, angle=0, justify='left bottom'):
        self.added.append(
            '(label "%s"\n\t\t(at %s %s %s)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n'
            '\t\t\t)\n\t\t\t(justify %s)\n\t\t)\n\t\t(uuid "%s")\n\t)'
            % (name, fmt(x), fmt(y), fmt(angle), justify, _uuid.uuid4()))

    def junction(self, x, y):
        self.added.append(
            '(junction\n\t\t(at %s %s)\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n\t\t(uuid "%s")\n\t)'
            % (fmt(x), fmt(y), _uuid.uuid4()))

    def raw(self, text):
        self.added.append(text)

    def build(self):
        src = self.s.text
        out = []
        pos = 0
        for it in self.s.items:
            gap = src[pos:it.s]
            if it.kind == 'sheet_instances':
                # additions go after the last drawn item
                out.append(''.join('\n\t' + a for a in self.added))
            out.append(gap)
            nt = self.new_text.get(it.uuid, it.text) if it.kind in DRAWN else it.text
            if nt is None:
                out.pop()
                out.append(gap[:-2] if gap.endswith('\n\t') else gap)
            else:
                out.append(nt)
            pos = it.e
        return ''.join(out) + src[pos:]


DRAWN = ('symbol', 'wire', 'label', 'junction', 'no_connect', 'text', 'rectangle', 'polyline')
