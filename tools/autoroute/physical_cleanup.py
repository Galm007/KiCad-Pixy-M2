"""Finish signal connectivity using KiCad's physical connectivity report.

The router's raster connectivity and short overlapping trace ends can disagree
with KiCad.  octilinear(finish=True) calls finish() last: KiCad's DRC is run on
a temporary copy, each reported dangling track or one-layer via is removed and
each reported unconnected pair is joined and straightened, until KiCad reports
none.  Only the low-current signal nets below are touched; a report on any
other net (a plane, a supply, a motor output) stops the replay for manual
review rather than deleting or re-routing protected copper.
"""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from pcbedit import Pcb
import devkit

ROOT = Path(__file__).resolve().parents[2]
SIGNALS = {'/MOTOR_UVLO', '/MOTOR_VREF', '/MOTOR_OK', '/USB_PRIORITY', '/DEVKIT_5V',
           '/BUCK_ENABLE', '/BUCK_GATE'}


def repairable(net):
    return net in SIGNALS or net.startswith('/GPIO') or net.startswith('/DRV_')


def _net_of(item):
    m = re.search(r'\[([^\]]+)\]', item['description'])
    return m[1] if m else None


def finish(p, Router, straighten):
    rule = ({'/MOTOR_UVLO'}, devkit.MOTOR_NETS | devkit._SW, 5.0)
    if rule not in devkit.WIDE_RULES:
        devkit.WIDE_RULES.append(rule)
    repairs = tails = holes = 0
    with tempfile.TemporaryDirectory(prefix='pixy-connectivity-') as tmp:
        board = Path(tmp) / 'Pixy-M2.kicad_pcb'
        report = Path(tmp) / 'drc.json'
        for ext in ('.kicad_pro', '.kicad_dru'):
            shutil.copy2(ROOT / ('Pixy-M2' + ext), board.with_suffix(ext))
        for attempt in range(6):
            p.sync()
            p.write(board)
            subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--format', 'json',
                            '-o', str(report), str(board)], capture_output=True, check=True)
            data = json.loads(report.read_text())
            dead = [v for v in data['violations'] if v['type'] == 'track_dangling']
            unused = [v for v in data['violations'] if v['type'] == 'via_dangling']
            missing = data['unconnected_items']
            if not dead and not unused and not missing:
                return dict(passes=attempt + 1, connections_repaired=repairs,
                            dangling_tracks_removed=tails, unused_holes_removed=holes)
            for v in dead + unused:
                for it in v['items']:
                    net = _net_of(it)
                    if net and not repairable(net):
                        raise RuntimeError('dangling copper needs manual review: ' + it['description'])
            uuids = {it['uuid'] for v in dead for it in v['items']}
            tails += p.drop(lambda b: any('(uuid "' + u + '")' in b for u in uuids))
            if unused:
                from power_integrity import drop_unused_signal_vias
                p.sync()
                r = devkit.make_router(Router, p)
                holes += drop_unused_signal_vias(p, r.g)
            if dead or unused:
                # a missing-pair report can refer to the orphan just removed:
                # ask KiCad again before choosing endpoints
                continue
            changed = set()
            for pair in missing:
                a, b = pair['items']
                net = _net_of(a)
                assert net, pair
                if not repairable(net):
                    raise RuntimeError('physical connection requires manual review: ' + str(pair))

                def target(r, it):
                    d = it['description']
                    pos = it['pos']
                    pad = re.match(r'Pad (\S+) .* of (\S+) on ', d)
                    if pad:
                        return r.pad_group(pad[2], pad[1], 0.2)
                    layers = [l for l in ('F.Cu', 'B.Cu') if l in d]
                    assert layers, it
                    return r.point_group(pos['x'], pos['y'], layers, r=.1)
                p.sync()
                r = devkit.make_router(Router, p)
                if not r.route(net, 0.2, [target(r, a), target(r, b)]):
                    raise RuntimeError('cannot repair physical connection: ' + str(pair))
                repairs += 1
                changed.add(net)
            if changed:
                p.sync()
                r = devkit.make_router(Router, p)
                # the repair belongs to the last copper stage, so it is
                # straightened too before the next check
                for _ in range(2):
                    if not straighten(p, r.g, sorted(changed)):
                        break
        raise RuntimeError('physical cleanup did not converge')
