"""Apply the local, DRC-verified issue-6 repairs to the issue-1..6 layout.

No net is ripped up. Each via keeps its diameter and drill; short connections
retain the widths checked on both sides. Coordinates also make this replayable
when rework.py generates fresh UUIDs. Unexpected routing fails closed.
"""
import re
from pcbedit import Pcb, fx

# net, old position, new position, connecting layers and widths (millimetres).
MOVES = [
    ('/VBAT', (111.5, 115.65), (110.7, 115.625), {'F.Cu': 0.25}),
    ('/VBAT', (126.5, 95.35), (126.65, 95.45), {'F.Cu': 0.25}),
    ('/VBAT', (119.65, 115.65), (119.675, 115.7), {'F.Cu': 0.25}),
    ('/VBAT', (126.5, 97.9), (126.675, 97.925), {'F.Cu': 0.25}),
    ('/VBAT', (126.5, 96.65), (126.625, 96.75), {'F.Cu': 0.25}),
    ('/REG_EN', (138.7, 96.1), (138.775, 96.1), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/REG_EN', (135.95, 99.7), (135.95, 99.65), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/ESP_3V3', (145.4, 98.8), (145.3, 98.8), {'F.Cu': 0.25}),
    ('/ESP_3V3', (145.4, 101.5), (145.3, 101.5), {'F.Cu': 0.2}),
    ('GND', (141.1, 104.0), (141.0, 104.0), {'F.Cu': 0.25}),
    ('GND', (135.0, 150.55), (135.2, 150.625), {'F.Cu': 0.25}),
    ('GND', (133.6, 151.95), (133.8, 151.95), {'F.Cu': 0.25}),
    ('GND', (135.0, 151.95), (135.2, 151.9), {'F.Cu': 0.25}),
    ('GND', (138.4, 103.0), (138.475, 103.0), {'F.Cu': 0.25}),
    ('GND', (148.6, 99.0), (148.7, 99.0), {'F.Cu': 0.25}),
    ('GND', (111.9, 113.45), (111.975, 113.45), {'F.Cu': 0.25}),
    ('GND', (135.0, 149.15), (135.2, 149.15), {'F.Cu': 0.25}),
    ('GND', (138.2, 101.15), (138.275, 101.15), {'F.Cu': 0.25}),
    ('GND', (135.55, 149.95), (135.55, 149.84), {'F.Cu': 0.25}),
    ('GND', (133.6, 149.15), (133.8, 149.15), {'F.Cu': 0.25}),
    ('GND', (148.6, 101.3), (148.7, 101.3), {'F.Cu': 0.25}),
    ('GND', (119.65, 107.2), (119.7, 107.1), {'F.Cu': 0.25}),
    ('GND', (111.05, 112.85), (111.05, 112.775), {'F.Cu': 0.25}),
    ('GND', (133.6, 150.55), (133.8, 150.55), {'F.Cu': 0.25}),
    ('/GPIO38', (157.4, 111.7), (157.25, 111.75), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/GPIO7', (140.85, 150.95), (140.75, 150.95), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/GPIO7', (155.5, 87.95), (155.475, 88.025), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/GPIO10', (115.8, 113.05), (114.775, 113.05), {'F.Cu': 0.15, 'B.Cu': 0.15}),
    ('/GPIO47', (118.1, 133.85), (117.875, 132.05), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/GPIO4', (121.5, 87.95), (121.475, 88.025), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/GPIO6', (105.05, 87.55), (104.95, 87.55), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/GPIO6', (140.85, 151.9), (140.75, 151.85), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/GPIO16', (140.85, 147.8), (140.75, 147.8), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/GPIO16', (143.2, 110.4), (143.15, 110.4), {'F.Cu': 0.2, 'B.Cu': 0.2}),
    ('/GPIO17', (137.5, 108.2), (137.55, 108.2), {'F.Cu': 0.2, 'B.Cu': 0.2}),
]
THERMAL = {(109.0, 113.6), (109.0, 114.4), (117.0, 113.6), (117.0, 114.4)}
FAB_NOTE = [
    'FAB NOTE - VIA IN PAD',
    'Resin fill and copper cap the four 0.25 mm thermal vias in U4/U5 pads.',
    'IPC-4761 type VII is required; per-via filling and capping are enabled.',
    'These four vias lie under solder paste. Tenting is not a substitute.',
    'All other via drills clear pad mask and paste openings by >= 0.10 mm.',
    'Fabrication order must include the specified filled/capped process.',
]


def finish_issue6(p):
    for net, old, new, layers in MOVES:
        matches = [(i, b) for i, b in enumerate(p.blocks)
                   if Pcb.kind(b) == 'via' and Pcb.net(b) == net
                   and Pcb.geom(b)[:2] == old]
        if not matches:
            done = [b for b in p.blocks if Pcb.kind(b) == 'via'
                    and Pcb.net(b) == net and Pcb.geom(b)[:2] == new]
            if len(done) == 1:
                continue
        if len(matches) != 1:
            raise ValueError(f'Issue 6 replay needs review: {net} at {old}')
        i, b = matches[0]
        p.blocks[i] = re.sub(r'\(at [-\d.]+ [-\d.]+\)',
                             f'(at {fx(new[0])} {fx(new[1])})', b)
        for layer, width in layers.items():
            p.add_track(net, layer, *old, *new, width)
    found = set()
    for i, b in enumerate(p.blocks):
        if Pcb.kind(b) != 'via':
            continue
        x, y, size, drill = Pcb.geom(b)
        if (x, y) not in THERMAL:
            continue
        if Pcb.net(b) != 'GND' or size != .45 or drill != .25 or (x, y) in found:
            raise ValueError('Unexpected thermal-via geometry')
        found.add((x, y))
        b = re.sub(r'\n\t\t\((?:filling|capping) [^)]*\)', '', b)
        p.blocks[i] = b.replace('\t\t(net ',
                               '\t\t(capping yes)\n\t\t(filling yes)\n\t\t(net ')
    if found != THERMAL:
        raise ValueError('Expected four driver thermal vias')
