"""Text-level surgery on Pixy-M2.kicad_pcb: delete/add segments+vias, move footprints."""
import re, uuid, math

PCB = '/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/Pixy-M2.kicad_pcb'

def fx(v):
    return f'{round(v, 4):.4f}'.rstrip('0').rstrip('.')

def uid(): return str(uuid.uuid4())

class Pcb:
    def __init__(self, path=PCB):
        self.path = path
        self.text = open(path).read()
        self._split()

    def _split(self):
        t = self.text
        # region of top-level (segment / (via blocks
        first = min(i for i in (t.find('\n\t(segment\n'), t.find('\n\t(via\n')) if i >= 0)
        # end = start of first top-level zone after that
        end = t.find('\n\t(zone\n', first)
        assert end > first
        self.head = t[:first + 1]
        self.mid = t[first + 1:end + 1]
        self.tail = t[end + 1:]
        self.blocks = self._parse_blocks(self.mid)

    @staticmethod
    def _parse_blocks(mid):
        out, i = [], 0
        while i < len(mid):
            j = mid.find('\n\t)\n', i)
            if j < 0: break
            out.append(mid[i:j + 4])
            i = j + 4
        assert ''.join(out) == mid, 'block split mismatch'
        return out

    # ---------- queries ----------
    @staticmethod
    def kind(b): return 'segment' if b.startswith('\t(segment') else ('via' if b.startswith('\t(via') else '?')

    @staticmethod
    def net(b):
        m = re.search(r'\(net "([^"]*)"\)', b)
        return m.group(1) if m else None

    @staticmethod
    def geom(b):
        """segment -> (x1,y1,x2,y2,w,layer); via -> (x,y,size,drill,layers)"""
        if b.startswith('\t(segment'):
            s = re.search(r'\(start ([-\d.]+) ([-\d.]+)\)', b)
            e = re.search(r'\(end ([-\d.]+) ([-\d.]+)\)', b)
            w = re.search(r'\(width ([-\d.]+)\)', b)
            l = re.search(r'\(layer "([^"]+)"\)', b)
            return (float(s[1]), float(s[2]), float(e[1]), float(e[2]), float(w[1]), l[1])
        a = re.search(r'\(at ([-\d.]+) ([-\d.]+)\)', b)
        sz = re.search(r'\(size ([-\d.]+)\)', b)
        dr = re.search(r'\(drill ([-\d.]+)\)', b)
        return (float(a[1]), float(a[2]), float(sz[1]), float(dr[1]))

    # ---------- edits ----------
    def drop(self, pred):
        keep, n = [], 0
        for b in self.blocks:
            if pred(b): n += 1
            else: keep.append(b)
        self.blocks = keep
        return n

    def add_track(self, net, layer, x1, y1, x2, y2, w):
        if abs(x1 - x2) < 1e-9 and abs(y1 - y2) < 1e-9: return
        self.blocks.append('\t(segment\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(width %s)\n'
                           '\t\t(layer "%s")\n\t\t(net "%s")\n\t\t(uuid "%s")\n\t)\n'
                           % (fx(x1), fx(y1), fx(x2), fx(y2), fx(w), layer, net, uid()))

    def add_via(self, net, x, y, size=0.6, drill=0.3, layers=('F.Cu', 'B.Cu')):
        self.blocks.append('\t(via\n\t\t(at %s %s)\n\t\t(size %s)\n\t\t(drill %s)\n'
                           '\t\t(layers "%s" "%s")\n\t\t(net "%s")\n\t\t(uuid "%s")\n\t)\n'
                           % (fx(x), fx(y), fx(size), fx(drill), layers[0], layers[1], net, uid()))

    # ---------- footprints ----------
    def footprint_span(self, ref):
        """(start,end) indices in self.text for the footprint block whose Reference is ref"""
        for m in re.finditer(r'\n\t\(footprint ', self.text):
            i = m.start() + 1
            # find matching close at same indent
            j = self.text.find('\n\t)\n', i)
            blk = self.text[i:j + 4]
            r = re.search(r'\(property "Reference"\s*\n?\s*"([^"]+)"', blk)
            if r and r.group(1) == ref:
                return i, j + 4
        raise KeyError(ref)

    def move_footprint(self, ref, x, y, rot=None):
        i, j = self.footprint_span(ref)
        blk = self.text[i:j]
        m = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\n', blk)
        assert m, 'no footprint (at ...)'
        oldrot = float(m.group(3) or 0.0)
        r = oldrot if rot is None else float(rot)
        new = f'\n\t\t(at {fx(x)} {fx(y)}' + (f' {fx(r)}' if fx(r) else '') + ')\n'
        blk2 = blk[:m.start()] + new + blk[m.end():]
        delta = (r - oldrot) % 360
        if delta:
            # Every text and pad inside a footprint stores its angle in the board
            # frame; KiCad turns them all with the footprint and DRC compares the
            # result against the library copy.  Rotate the parent alone and the
            # pads keep the old angle — a 0.9x0.95 pad silently stays 0.95x0.9,
            # and the footprint reads as "does not match copy in library".
            def turn(mm):
                ang = fx((float(mm.group('ang') or 0.0) + delta) % 360)
                tail = f" {ang})" if ang else ")"
                return f"{mm.group('head')}{mm.group('x')} {mm.group('y')}{tail}"
            blk2 = re.sub(r'(?P<head>\n\t\t\t\(at )(?P<x>[-\d.]+) (?P<y>[-\d.]+)'
                          r'(?: (?P<ang>[-\d.]+))?\)', turn, blk2)
        self.text = self.text[:i] + blk2 + self.text[j:]
        self._split()

    def move_property(self, ref, prop, dx, dy):
        """set a footprint text field's offset in the footprint's own frame"""
        i, j = self.footprint_span(ref)
        blk = self.text[i:j]
        m = re.search(r'\(property "%s" "[^"]*"\s*\n\s*\(at (?P<a>[-\d.]+ [-\d.]+)' % prop, blk)
        assert m, f'{ref}: no {prop} (at ...)'
        blk2 = blk[:m.start('a')] + f'{fx(dx)} {fx(dy)}' + blk[m.end('a'):]
        self.text = self.text[:i] + blk2 + self.text[j:]
        self._split()

    def move_text(self, text, x, y):
        """move a board-level (gr_text "...") to an absolute position"""
        m = re.search(r'\(gr_text "%s"\s*\n\s*\(at (?P<a>[-\d.]+ [-\d.]+)' % re.escape(text), self.text)
        assert m, f'no gr_text {text!r}'
        self.text = self.text[:m.start('a')] + f'{fx(x)} {fx(y)}' + self.text[m.end('a'):]
        self._split()

    def add_zone(self, s):
        self.tail = s + self.tail

    def write(self, path=None):
        open(path or self.path, 'w').write(self.head + ''.join(self.blocks) + self.tail)
