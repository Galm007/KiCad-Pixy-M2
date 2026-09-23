# Issue 7 — USB routed as a coupled pair — 2026-09-22

REVIEW.md finding 7: USB D+/D− were ordinary 0.2 mm traces with varying
separation, a D+ detour around U2, and D− changing to B.Cu and back through
vias while D+ stayed on F.Cu. The 2026-09-22 audit found the issue-6 via pass
had made D− worse (4 vias, 8 mm on B.Cu).

Both polarities now run as one pair from J1 to U1, on F.Cu over the In1 ground
plane, with **no vias anywhere on the USB path**.

## What changed

- **U2 turned 90°**, (154, 148) rot 0 → (153.5, 149.5) rot 90. USBLC6-2SC6
  carries each line in on one side of the package and out of the other. At
  rot 0 that ran west→east while the signal runs J1 (south) → U1 (north-west),
  so D+ had to wrap round the package. At rot 90 the connector pins (1, 2, 3)
  face J1 and the module pins (6, 5, 4) face U1, with D− on the west in both
  rows. The pair goes straight through the part and never crosses itself.
- **U2's middle pins leave under the body**, through the 1 mm gap between the
  pin rows, so neither crosses the pair. GND (2) goes to a plane via under the
  package, 0.71 mm of copper from the pin; the old return was 1.11 mm. VBUS (5)
  goes east to the existing feed from F2.
- **J1's alternating pads** (B7 D−, A6 D+, A7 D−, B6 D+) are joined on F.Cu:
  a D+ bridge over the top of A7 and a D− loop under the bottom of A6. The old
  D− loop used a via to B.Cu. Both joins are short stubs, about 1.4 mm each.
- **The pair**: 0.25 mm lines with a 0.15 mm gap, 13.75 mm coupled on the module
  side. It splits only where U2's 1.9 mm pin pitch and U1's 1.27 mm pitch force
  it to.
- **CC1/CC2 re-routed** around the pair by the A* router. They were ripped
  because their vias sat where the pair now runs. They cross under the pair on
  B.Cu, with the In1 plane between. The router kept their F.Cu copper and vias
  an extra 0.15 mm off the pair, except in J1's pad field.
- **Silkscreen**: U2's reference sits upright east of its module-side pins. J1's
  reference was moved off U2's connector-side pins.

The stage is `tools/autoroute/usb_pair.py`, run by `rework.py` after the
issue-6 via repairs. Nothing earlier in the replay changes.

## Impedance

`tools/impedance/zdiff.py` is a 2D field solver for the odd mode of
edge-coupled microstrip with conformal solder mask. It was run against this
board's F.Cu → In1 stackup: 35 µm copper on 7628 prepreg with εr 4.4. KiCad's
stackup uses 0.200 mm prepreg; JLCPCB's JLC04161H-7628 quotes 0.2104 mm. Mask
is 10–25 µm with εr 3.8. For 0.25 / 0.15 mm the results are:

| prepreg | mask 10 µm | mask 25 µm |
|---|---:|---:|
| 0.200 mm | 93.0 Ω | 89.5 Ω |
| 0.2104 mm | 94.2 Ω | 90.6 Ω |

At a 5 µm mesh the solver reads about 1.5 Ω high against 2.5 µm (91.5 Ω for the
first cell). The IPC-2141 closed form gives 90.4 Ω with no mask. The spread
across stackup, mask and method is **about 88–94 Ω**, inside Espressif's
90 Ω ± 10 % (81–99 Ω). **This is a calculation, not a fabricator figure:**
confirm with JLCPCB's impedance calculator, or order impedance control, before
fabrication. Raw output: `impedance.txt`.

## Measurements (`measurements.json`, from `measure.py`)

Before is commit `0c70856`; after is this board.

| | before | after |
|---|---:|---:|
| USB vias | 4 (all on D−) | **0** |
| USB copper on B.Cu | 8.01 mm | **0** |
| line width | 0.20 mm | **0.25 mm** |
| end-to-end path, J1 pad → U2 → U1 pad: D+ / D− | 24.54 / 32.62 mm | **20.15 / 19.11 mm** |
| end-to-end skew | 8.08 mm | **1.04 mm** (≈ 6 ps) |
| module-side pair gap | 0.25–0.35 mm | **0.15 mm** coupled |
| closest other-net F.Cu copper to a USB line | 0.22 mm (VBUS) | 0.275 mm (CC1, in J1's pad field) |
| board vias | 247 | 243 |
| CC1 / CC2 track | 4.92 / 13.57 mm | 5.81 / 8.53 mm |

The remaining 1.04 mm of skew comes from the pair's two 45° bends, where D− is
the inner line, and from D+'s climb into U1 pin 14. It is below the 1.25 mm
(50 mil) figure commonly used as a *High* Speed matching target. The ESP32-S3
PHY is Full Speed only.

The connector-side pair is 1.13 mm coupled at 0.25 mm. That spacing is J1's
0.5 mm pad pitch, not a routing choice.

## Rules

- `Pixy-M2.kicad_pro` has a new **`USB` netclass**: 0.25 mm width, 0.15 mm
  diff-pair gap, 0.15 mm clearance *within* the class. Clearance to every other
  net stays 0.2 mm. It is matched by `/USB_D*` and `Net-(J1-D*`.
- `Pixy-M2.kicad_dru` gains three rules:
  - USB line width must be 0.24–0.26 mm.
  - USB nets may not have tracks or vias on B.Cu.
  - For `/USB_D±`, the pair gap must be 0.14–0.16 mm and no more than 4 mm may
    be uncoupled. As routed, 3.4 mm is uncoupled, forced by the two pin pitches.
- KiCad treats only `/USB_D+` / `/USB_D-` as a differential pair, because the
  connector-side net names do not end in ±. The coupling rule therefore covers
  the module side only. The width and layer rules cover all four nets.
- **Negative test** (`negative-tests.json`). Each case is a deliberately broken
  copy, and each rule fires:
  - A 0.20 mm segment raises `track_width`.
  - The J1 D− loop moved to B.Cu raises `items_not_allowed`.
  - A /USB_D− segment moved 0.10 mm away raises `diff_pair_gap_out_of_range`.

## Validation

- `kicad-cli pcb drc --schematic-parity --refill-zones` shows 0 unconnected
  items and 0 parity issues (`drc.json`). The only violations are the four
  pre-existing J1 `hole_clearance` errors and the U1 `lib_footprint_mismatch`
  warning, the same verdict as before this change.
- `via_openings.py` reports 0 violations, 243 vias, a 0.10 mm minimum
  ordinary gap, and 0 unintended overlaps (`aperture-audit.json`).
  `test_via_openings.py` passes.
- **Nothing else moved.** A track/via diff against `0c70856` touches only these
  nets: the four USB nets, CC1, CC2, U2's GND stub and via, and U2's VBUS
  fan-in. Every motor, buck, encoder and issue-6 via is byte-for-byte the same
  geometry. Motor loop areas are unchanged at 103.3 / 83.4 mm² (`loop.py`).
- A full `rework.py` replay from `base-routed.kicad_pcb` reproduces this board
  exactly. It also reproduced `0c70856` exactly before the USB stage was added.

Figures: `usb-before.png`, `usb-after.png` (F.Cu red, B.Cu blue, silkscreen
black).

## Not done here

- The **shield return** (J1 shell → C8/R5), which REVIEW.md lists as a separate
  observation, still takes its long B.Cu path behind U2. It is untouched.
- No signal-integrity simulation or hardware eye measurement was performed.
