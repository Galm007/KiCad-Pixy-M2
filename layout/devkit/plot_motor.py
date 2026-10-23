#!/usr/bin/env python3
"""Motor output pairs before and after the devkit stage, side by side.

    python3 layout/devkit/plot_motor.py BEFORE.kicad_pcb AFTER.kicad_pcb OUT.png

M1 solid colours, M2 lighter; F.Cu solid lines, B.Cu dashed.  Every other track
is drawn faint grey.  Board coordinates (KiCad - (100, 60)), front at the top.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools', 'autoroute'))
from pcbedit import Pcb      # noqa: E402
import loop                  # noqa: E402
import matplotlib            # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt   # noqa: E402

COL = {'/MOT_A_1': '#c0392b', '/MOT_A_2': '#e59866', '/MOT_B_1': '#1f4e9c', '/MOT_B_2': '#5dade2'}


def draw(ax, path, title):
    p = Pcb(path)
    for b in p.blocks:
        if Pcb.kind(b) != 'segment':
            continue
        x1, y1, x2, y2, w, layer = Pcb.geom(b)
        n = Pcb.net(b)
        ls = '-' if layer == 'F.Cu' else '--'
        if n in COL:
            ax.plot([x1 - 100, x2 - 100], [y1 - 60, y2 - 60], color=COL[n], lw=w * 3, ls=ls,
                    solid_capstyle='round')
        else:
            ax.plot([x1 - 100, x2 - 100], [y1 - 60, y2 - 60], color='0.87', lw=0.4, ls=ls)
    areas = loop.report(path)
    ax.set_title(f"{title}\nloop A {areas['motor A']:.1f} mm², B {areas['motor B']:.1f} mm²",
                 fontsize=10)
    ax.set_xlim(0, 66)
    ax.set_ylim(100, 0)
    ax.set_aspect('equal')
    ax.set_xticks(range(0, 67, 10))
    ax.set_yticks(range(0, 101, 10))
    ax.grid(alpha=0.3)


def main():
    before, after, out = sys.argv[1:4]
    fig, axs = plt.subplots(1, 2, figsize=(10, 7.6))
    draw(axs[0], before, 'main (WROOM-1 on board)')
    draw(axs[1], after, 'devkit-daughterboard')
    handles = [plt.Line2D([], [], color=c, lw=2.4, label=n[1:]) for n, c in COL.items()]
    handles += [plt.Line2D([], [], color='k', lw=1, ls='-', label='F.Cu'),
                plt.Line2D([], [], color='k', lw=1, ls='--', label='B.Cu')]
    fig.legend(handles=handles, loc='lower center', ncol=6, fontsize=9, frameon=False)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(out, dpi=110, bbox_inches='tight')


if __name__ == '__main__':
    main()
