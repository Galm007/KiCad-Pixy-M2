# Issue 8 — the rule set encodes the routing requirements — 2026-09-22

REVIEW.md finding 8: the project had only the Default netclass, no netclass
assignments and a global 0.15 mm minimum track width. Nothing stopped narrow
copper on motor, USB or supply paths. The motor part was closed with finding 1
(`Motor` netclass and trunk rule), and the USB part with finding 7 (`USB`
netclass, width, layer and coupling rules). This pass covers the rest:

- the general signal minimum;
- the supply paths;
- the "keep away" constraints in CLAUDE.md.

Turning the rules on exposed real copper that failed them, and that copper was
fixed in the same pass.

## Rules added

`Pixy-M2.kicad_pro` adds two netclasses:

| class | nets | default width |
|---|---|---:|
| `Battery` | `/VBAT_RAW`, `/VBAT_FUSED` | 1.0 mm |
| `Power` | `/VBUS`, `/VSYS`, `Net-(F2-Pad1)` | 0.6 mm |

`Pixy-M2.kicad_dru` adds these rules:

| rule | constraint | exception |
|---|---|---|
| Signal minimum width | every track ≥ 0.2 mm | inside the `Motor pin escape` areas (DRV8231A pin fields) |
| Power path width | `Power` ≥ 0.5 mm | inside the new `Power pin escape` area (U2's VBUS pin, which leaves under the package) |
| Battery path width | `Battery` ≥ 0.8 mm | none |
| REG_EN clear of the switch node | ≥ 0.35 mm to `U3-SW`/`U3-BST` | — |
| Sense nodes clear of motor and switch copper | `REG_EN` ≥ 5 mm to motor copper. `VBAT_SENSE` ≥ 5 mm to motor, SW and BST copper | — |
| IPROPI clear of motor outputs | `GPIO2`/`GPIO10` ≥ 0.25 mm to motor copper | — |

Three KiCad behaviours shaped how these are written. All three were checked,
not assumed:

- **Board-setup minimums are absolute.** A custom rule cannot relax them. With
  the board minimum raised to 0.2 mm, a 0.15 mm rule inside the pin-field areas
  was ignored. So the board floor stays 0.15 mm, the pin fields' need, and a
  custom rule raises everything else.
- **When two rules set the same constraint, the later one wins.** The generic
  0.2 mm rule is therefore the *first* rule in the file. The motor, USB, power
  and battery rules below it still override it; see the motor case in the
  negative tests.
- **`enclosedByArea` tests the whole track outline, round caps included.** A
  segment clipped exactly at an area edge pokes out by half its width. The
  widening clips at the areas shrunk by 0.1 mm.

`/VBAT` is in neither supply class, deliberately. Its current runs in the In2
island. Its tracks are stubs from pads to plane vias, and the pin pitch sets
their width, not the current.

The clearance rules are **floors set just under what the board achieves**. They
stop erosion; they do not certify the constraint. Two are well below what
CLAUDE.md asks for, and are recorded as such rather than hidden:

- **REG_EN**: 0.40 mm. U3's EN via under the package sits 0.40 mm from the SW
  pin. The standing fix is to re-place R8/C13 next to U3.2.
- **IPROPI**: 0.29 mm. A GPIO2 via sits beside a MOT_A_2 B.Cu trunk near U4.
  Validate the current reading on hardware.

## Copper the rules required (`tools/autoroute/issue8.py`)

The stage runs in `rework.py` straight after `usb_pair.py`.

| | before | after |
|---|---:|---:|
| track narrower than 0.2 mm | 219.4 mm, on five nets end to end | **8.7 mm**, all inside the DRV8231A pin fields |
| `/VBUS` F2 → D1 | 50.7 mm at 0.24 mm, **105.4 mΩ** | 0.6 mm, **44.4 mΩ** |
| USB input J1.A9 → F2 | 0.24 mm, 9.7 mΩ | 0.6 mm, 4.0 mΩ |
| USB input J1.A4 → F2 | 0.2–0.25 mm, 32.7 mΩ | 0.6 mm, 8.2 mΩ |
| `/VBAT_FUSED` R14 tap | 0.2 mm | 0.8 mm |
| vias | 243 | 243 |

Resistance is DC at 20 °C in 35 µm copper, from `measure.py`. At F2's 0.5 A hold
current the VBUS run drops 22 mV instead of 53 mV.

- **Signals.** `GPIO39/40/41` (motor IN1/IN2) and `GPIO2/10` (IPROPI) had been
  routed at 0.15 mm for their whole 40–52 mm, because the router used one width
  per net. They are now 0.2 mm everywhere outside the pin fields. B.Cu copper
  under the drivers had room, so it is 0.2 mm too. One GPIO41 corner doglegs
  0.3 mm to clear the GPIO47 via issue 6 moved beside it; widened in place it
  would have been 0.18 mm from that via.
- **USB supply.** It carries the whole board on USB. `CLAUDE.md`'s width table
  said 0.6 mm; the copper was 0.24 mm. It is now re-routed at 0.6 mm:
  - The D3 tap (VBUS → D3 → R9 → REG_EN) is 0.5 mm, pinned by F.Cu waypoints
    to its old corridor along the top edge. Unpinned, A* sent it through the
    buck block, 0.5 mm from C6's switch-node pad, straight into the enable
    divider.
  - The pinning found a bug in `Router.route_waypoints`: it offers each
    waypoint on both layers, so consecutive legs can meet on different layers
    with no via. Its only existing caller, the MOT_B_2 pairing, happens not to
    trigger it. `issue8.py` routes its own legs instead.
- **Vias near pads.** The router bars via *centres* from 0.15 mm round a pad. A
  0.3 mm drill can then touch the mask opening; it missed by 0.04 mm at both
  J1 VBUS pads on the first try. For this stage only, the bar is drill
  radius + 0.10 mm + one grid step, matching issue 6's floor. Earlier stages
  keep the old bar so they replay unchanged.

## Validation

- **DRC.** `--schematic-parity --refill-zones` gives 0 unconnected and 0 parity
  issues (`drc.json`). The only violations are the four pre-existing J1
  `hole_clearance` errors and the U1 `lib_footprint_mismatch` warning, the same
  verdict as before.
- **Aperture audit.** `via_openings.py`: 0 violations, 243 vias, 0.10 mm
  minimum (`aperture-audit.json`).
- **Negative tests.** `negative-tests.json` has one deliberately broken copy
  per rule, and each rule fires:

  | case | edit | fires |
  |---|---|---|
  | signal | a GPIO21 segment at 0.15 mm | Signal minimum width |
  | motor | a MOT_B_1 trunk at 0.4 mm | Motor trunk minimum width (still wins over the generic rule) |
  | usb | a USB_D+ segment at 0.2 mm | USB line width and pair gap |
  | power | a VBUS run at 0.3 mm | Power path width |
  | battery | a VBAT_FUSED trunk at 0.6 mm | Battery path width |
  | reg_en | the EN via 0.1 mm closer to SW | REG_EN clear of the switch node |
  | ipropi | the GPIO2 via 0.06 mm closer to MOT_A_2 | IPROPI clear of motor outputs |
- **Nothing else moved.** A track/via diff against the issue-7 board touches
  only `GPIO2/10/39/40/41`, `/VBUS`, `Net-(F2-Pad1)` and `/VBAT_FUSED`.
  - Motor, USB, buck and issue-6 copper are unchanged.
  - Motor loops are unchanged at 103.3 / 83.4 mm².
  - Exact clearances before and after (`clearances.json`, `clearmin.py`) are
    identical. VBUS/VSYS copper stays 1.11 mm from the switch node, the
    spacing U3's own pins set, so the new supply routes come no closer to it.
- **Replay.** A full `rework.py` replay reproduces the board exactly.

Figures: `supply-top-before.png` / `supply-top.png` (D1, the D3 tap, the buck
block) and `supply-connector.png` (J1 → F2).

## Corrections to earlier notes

- CLAUDE.md issue 5 said `REG_EN` copper passes **0.99 mm** from switching
  copper. Measured exactly, it is **0.40 mm**, from the EN via to the SW pin.
- The first measurement in this pass used a single 20 mm DRC threshold. It
  reported 0.95 mm for REG_EN and 0.75 mm for IPROPI, both wrong; see
  `clearmin.py`.

## Not done

- `REG_EN` and IPROPI are not moved; see above.
- D6's single ground via and narrow VBAT stub (a REVIEW.md side observation) are
  untouched. The width rule does not cover `/VBAT`.
