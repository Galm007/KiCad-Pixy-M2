#!/usr/bin/env python3
"""Before/after evidence for the straightening stage (tools/autoroute/octilinear.py).

    python3 layout/octilinear/compare.py BEFORE.kicad_pcb AFTER.kicad_pcb [--json OUT] [--png OUT]

Counts per board: segments, segments under 0.3 mm (the router's staircase
steps), and segments at an angle other than 0/45/90 degrees, with the nets
that hold most of them.  With --png, draws the motor corner and the whole board
side by side at true track width (F.Cu red, B.Cu blue, pads amber).
"""
import collections
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools', 'autoroute'))
from pcbedit import Pcb          # noqa: E402
from sexp import parse, children  # noqa: E402
from load import fp_info          # noqa: E402

CORNER = (101.0, 106.0, 133.0, 130.0)      # KiCad box round U4/U5 and J8
WHOLE = (100.0, 60.0, 166.0, 160.0)


def stats(path):
    p = Pcb(path)
    n, short, off = 0, collections.Counter(), collections.Counter()
    for b in p.blocks:
        if Pcb.kind(b) != 'segment':
            continue
        x1, y1, x2, y2, w, layer = Pcb.geom(b)
        n += 1
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        if math.hypot(dx, dy) < 0.3:
            short[Pcb.net(b)] += 1
        if not (dx < 1e-4 or dy < 1e-4 or abs(dx - dy) < 1e-4):
            off[Pcb.net(b)] += 1
    return {'segments': n,
            'short_under_0.3mm': sum(short.values()),
            'short_by_net': dict(short.most_common(8)),
            'off_45': sum(off.values()),
            'off_45_by_net': dict(off.most_common(8))}


def draw(ax, path, box, title):
    import matplotlib.transforms as mt
    from matplotlib.patches import Polygon, Circle, Rectangle
    p = Pcb(path)
    x0, y0, x1, y1 = box
    for f in (fp_info(x) for x in children(parse(p.text), 'footprint')):
        for pd in f['pads']:
            if not (x0 - 3 < pd['x'] < x1 + 3 and y0 - 3 < pd['y'] < y1 + 3):
                continue
            if not any(l in pd['layers'] for l in ('F.Cu', '*.Cu')):
                continue
            ax.add_patch(Rectangle((pd['x'] - pd['w'] / 2, pd['y'] - pd['h'] / 2), pd['w'], pd['h'],
                                   color='#e8b04a', alpha=0.8,
                                   transform=mt.Affine2D().rotate_deg_around(pd['x'], pd['y'], -pd['rot'])
                                   + ax.transData))
    for b in p.blocks:
        if Pcb.kind(b) == 'segment':
            xa, ya, xb, yb, w, layer = Pcb.geom(b)
            c, al = ('#c83737', 0.85) if layer == 'F.Cu' else ('#3a6fc8', 0.55)
            L = math.dist((xa, ya), (xb, yb))
            if L > 1e-9:
                nx, ny = -(yb - ya) / L * w / 2, (xb - xa) / L * w / 2
                ax.add_patch(Polygon([(xa + nx, ya + ny), (xb + nx, yb + ny), (xb - nx, yb - ny),
                                      (xa - nx, ya - ny)], color=c, alpha=al, lw=0))
            for q in ((xa, ya), (xb, yb)):
                ax.add_patch(Circle(q, w / 2, color=c, alpha=al, lw=0))
        elif Pcb.kind(b) == 'via':
            x, y, s, d = Pcb.geom(b)[:4]
            ax.add_patch(Circle((x, y), s / 2, color='#999', lw=0))
            ax.add_patch(Circle((x, y), d / 2, color='k', lw=0))
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)
    ax.set_aspect('equal')
    ax.set_facecolor('#1d2330')
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=10)


def main():
    argv = sys.argv[1:]
    opts = {}
    for k in ('--json', '--png'):
        if k in argv:
            i = argv.index(k)
            opts[k] = argv[i + 1]
            argv = argv[:i] + argv[i + 2:]
    before, after = argv
    res = {'before': stats(before), 'after': stats(after)}
    print(json.dumps(res, indent=1))
    if '--json' in opts:
        json.dump(res, open(opts['--json'], 'w'), indent=1)
    if '--png' in opts:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axs = plt.subplots(2, 2, figsize=(13, 16.5),
                                gridspec_kw={'height_ratios': [CORNER[3] - CORNER[1], 0.8 * (WHOLE[3] - WHOLE[1])]})
        for col, (path, name) in enumerate(((before, 'before'), (after, 'after'))):
            n = res[name]['segments']
            draw(axs[0][col], path, CORNER, f'{name}: motor corner (U4, U5, J8)')
            draw(axs[1][col], path, WHOLE, f'{name}: whole board, {n} segments')
        fig.tight_layout()
        fig.savefig(opts['--png'], dpi=90)


if __name__ == '__main__':
    main()
