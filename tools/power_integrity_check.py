#!/usr/bin/env python3
"""Audit the intentional netlist change and conservative DC design corners.

Usage: python3 tools/power_integrity_check.py before.net after.net
Pins outside the explicit transition must keep their exact net and part fields.
The numerical bounds are engineering calculations, not transient simulations.
"""
import itertools
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'schematic'))
from schlib import parse, kids, kid, sval
from power_integrity_data import PARTS, DRIVER_NETS, BUCK_PADS, CURRENT_FIELDS


def load(path):
    t = Path(path).read_text()
    tree, _ = parse(t, t.index('('))
    pins, comps = {}, {}
    for n in kids(kid(tree, 'nets'), 'net'):
        name = sval(kid(n, 'name')[1])
        for m in kids(n, 'node'):
            pins[sval(kid(m, 'ref')[1]), sval(kid(m, 'pin')[1])] = name
    for c in kids(kid(tree, 'components'), 'comp'):
        f = {}
        for p in kids(kid(c, 'fields') or [], 'field'):
            f[sval(kid(p, 'name')[1])] = sval(p[-1]) if len(p) > 2 else ''
        f['Value'] = sval(kid(c, 'value')[1])
        f['Footprint'] = sval(kid(c, 'footprint')[1])
        ds = kid(c, 'datasheet')
        if ds:
            f['Datasheet'] = sval(ds[1])
        comps[sval(kid(c, 'ref')[1])] = f
    return pins, comps


def electrical(before, after):
    old, oc = load(before)
    actual, ac = load(after)
    expected = dict(old)
    for pin, net in DRIVER_NETS.items():
        expected[pin] = '/' + net
    for pin in BUCK_PADS:
        expected[pin] = '/BUCK_3V3'
    expected['U1', '21'] = '/DEVKIT_5V'
    for ref, d in PARTS.items():
        for num, net in d['nets'].items():
            expected[ref, num] = ('unconnected-(%s-NC-Pad%s)' % (ref, num) if net is None
                                  else net if net == 'GND' else '/' + net)
    bad = [(p, expected.get(p), actual.get(p)) for p in sorted(set(expected) | set(actual))
           if expected.get(p) != actual.get(p)]
    assert not bad, ('unexpected pin connectivity', bad)
    assert set(ac) == set(oc) | set(PARTS)
    for ref, f in oc.items():
        want = dict(f)
        if ref in ('R17', 'R18'):
            want.update(CURRENT_FIELDS)
        assert ac[ref] == want, (ref, want, ac[ref])
    for ref, d in PARTS.items():
        for k, v in d['fields'].items():
            assert ac[ref].get(k) == v, (ref, k, v, ac[ref].get(k))
    return {'nets': len(set(actual.values())), 'parts': len(ac), 'pins_checked': len(actual),
            'unexpected_changes': 0}


def ohms(ref):
    v = PARTS[ref]['fields']['Value'].split()[0]
    m = re.fullmatch(r'([\d.]+)([kM]?)', v)
    return float(m[1]) * {'': 1, 'k': 1e3, 'M': 1e6}[m[2]]


def farads(ref):
    v = PARTS[ref]['fields']['Value'].split()[0]
    m = re.fullmatch(r'([\d.]+)([pnu])F', v)
    return float(m[1]) * {'p': 1e-12, 'n': 1e-9, 'u': 1e-6}[m[2]]


def corners():
    top, bot, fb = ohms('R24'), ohms('R25'), ohms('R26')
    # -40..+125 C: at most 100 C from the 25 C specification point.
    # TLV3012B: REF 1.223-1.260 V, 100 ppm/C; the full 8 mV hysteresis on
    # either side, 9 mV Vos, 5 mV for common-mode/supply effects (54 dB CMRR,
    # 1 mV/V PSRR), 0.5 mV reference loading and 0.25 mV line regulation.
    ref_lo = 1.223 * (1 - .01) - .0005 - .00025
    ref_hi = 1.260 * (1 + .01) + .0005 + .00025
    err = .009 + .008 + .005
    rerr = .001 + 25e-6 * 100                  # 0.1 %, 25 ppm/C thin film
    ranges = [[v * (1 - rerr), v * (1 + rerr)] for v in (top, bot, fb)]
    off, on = [], []
    for t, b, f in itertools.product(*ranges):
        factor = 1 + t / b + t / f
        for ref in (ref_lo - err, ref_hi + err):
            # output low 0-0.2 V when off; high from 2.8 V to the 3.3 V rail
            on += [ref * factor - v * t / f for v in (0, .2)]
            off += [ref * factor - v * t / f for v in (3.0 - .2, 3.3495)]
    nom_on = 1.242 * (1 + top / bot + top / fb)
    nom_off = nom_on - 3.3 * top / fb
    # DRV gain: +/-6 % only specified at 1 A, VM >= 6.5 V, VIPROPI <= 3 V.
    # 1 % resistor with <=100 ppm/C, reference initial+drift, plus DRV VREF
    # input loading (2 x 1 uA absolute upper allowance, 1 mV/mA regulation).
    ipropi_min_at_1A = .0015 * .94 * 1000 * (1 - .01 - .01)
    current_estimate = (ref_hi + .000002) / ipropi_min_at_1A
    # AP63203 +/-1 %, selector resistors +/-1 %; USB post-diode rail >= 4.0 V.
    # 1 % initial + 100 ppm/C drift on the selector divider, and the absolute
    # CE leakage maximum through the larger Thevenin resistance.
    r28, r29 = ohms('R28'), ohms('R29')
    k_min = r29 * .98 / (r28 * 1.02 + r29 * .98)
    k_max = r29 * 1.02 / (r28 * .98 + r29 * 1.02)
    leak_shift = .000000610 * (r28 * r29 / (r28 + r29)) * 1.02
    usb_off_margin = 4.0 * k_min - (3.333 + .080) - leak_shift
    battery_on_margin = 3.267 - .250 - 3.333 * k_max - leak_shift
    # TLV3012B REF is stable with up to 10 nF: C25 at U6 + C28 at the drivers,
    # +10 % X7R tolerance
    vref_c_max = (farads('C25') + farads('C28')) * 1.1
    # USB unplug: U8 turns on ~40 us (typ, VIN 3.6 V; no maximum given) after
    # CE drops below VIN.  C30 (100 uF X5R 1206, ~45 % left at 3.3 V bias,
    # -20 %) plus C1 and C15 (10 uF 0805, ~60 % left) carry the rail meanwhile;
    # the devkit's own 3V3 capacitance is not counted.
    c_hold = farads('C30') * .45 * .8 + 2 * 10e-6 * .6
    sag_500mA = .5 * 40e-6 / c_hold
    assert min(off) - .005 >= 6.0, (min(off), 'cutoff would drain the pack below 3.0 V/cell')
    assert max(on) <= 7.2, (max(on), 'a pack at storage charge must enable the motors')
    assert nom_on - nom_off >= .3, 'hysteresis'
    assert ipropi_min_at_1A > ref_hi + .000002
    assert usb_off_margin > 0 and battery_on_margin > 0
    assert vref_c_max <= 10e-9, vref_c_max
    return dict(motor_enable_nominal_V=nom_on, motor_cutoff_nominal_V=nom_off,
                motor_enable_DC_envelope_V=[min(on), max(on)],
                motor_cutoff_DC_envelope_V=[min(off), max(off)],
                driver_VM_DC_floor_with_5mV_copper_budget_V=min(off) - .005,
                current_limit_nominal_A=1.242 / 1.5, current_estimate_with_1A_gain_bound_A=current_estimate,
                trip_comparator_margin_at_1A_V=ipropi_min_at_1A - ref_hi - .000002,
                ipropi_nominal_V_per_A=1.5, usb_disable_margin_V=usb_off_margin,
                battery_enable_margin_V=battery_on_margin,
                vref_capacitance_max_nF=vref_c_max * 1e9,
                usb_handover_holdup_uF=c_hold * 1e6, usb_handover_sag_at_500mA_40us_V=sag_500mA,
                qualifications=[
                    'DRV gain bound is specified at 1 A, not a guaranteed limit at every current/PWM edge.',
                    'Below VM 6.5 V the DRV8231A current mirror still regulates; TI does not specify its accuracy there.',
                    'Comparator delay, input filtering, motor ripple and source handover require oscilloscope tests.',
                    'U8 turn-on has no datasheet maximum: scope ESP_3V3 at USB unplug under load.',
                    'USB LDO thermal capability and complete rail dropout require bench qualification.'])


if __name__ == '__main__':
    out = {'electrical': electrical(*sys.argv[1:]), 'DC_corners': corners()}
    print(json.dumps(out, indent=2))
