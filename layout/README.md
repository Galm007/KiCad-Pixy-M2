# Pixy-M2 initial placement — 2026-09-21

This is an **unrouted, provisional chassis layout**, not fabrication-ready mechanical design.

## Geometry and reservations

The PCB is 66 × 100 mm with R3 corners and a single closed perimeter. J1's stock mid-mount USB-C footprint requires a rear-edge notch; its Edge.Cuts geometry is integrated into the perimeter. There are no additional mounting holes or drivetrain cutouts. Existing connector locating holes remain part of their assigned footprints.

Coordinates in `placement.json` are millimetres from the board's front-left corner, +X right and +Y rear; the KiCad origin for this corner is (100, 60) mm. Angles follow KiCad footprint rotation conventions. The front is at the top of the preview.

| Reservation | Position relative to PCB front-left | Size / meaning |
|---|---|---|
| Complete width allowance | X = −12…78 | 90 mm including wheels, gears, brackets and cable protrusions |
| Side drive lanes | X = −12…0 and 66…78 | 12 mm each; illustrative 8 mm tire + 4 mm gear/clearance allocation |
| Wheel axes | Y = 50 and 82 | Ø30 mm wheels, 32 mm wheelbase |
| Left underside motor | X = 0…38, Y = 44…60 | 38 × 16 × 16 mm including encoder/cable allowance; shaft toward left |
| Right underside motor | X = 28…66, Y = 72…88 | 38 × 16 × 16 mm including encoder/cable allowance; shaft toward right |
| Underside battery | X = 13…53, Y = 5…35 | 40 × 30 × 15 mm |
| Top-side IMU | X = 20.5…45.5, Y = 53.5…78.5 | 25 × 25 mm around nominal rotation centre (33, 66) |
| Four top sensor mounts | X = 1…15, 17…31, 35…49, 51…65; Y = 1…20 | 14 × 19 mm provisional mount/module envelope each |
| Antenna | Rear-centre; module reaches Y = 105.75 | Overhang, all-layer copper keepout and additional no-metal drawing |

`Dwgs.User` shows top reservations, drive lanes, wheels, axes, aim directions and dimensions. `User.1` shows underside body envelopes. `User.2` shows provisional attachment bands and RF clearance. These bands are reserved space, not final bolt patterns. The left battery attachment band ends at Y = 29 to avoid the battery connector's through-hole pads.

Board-level placement keepouts cover top modules and underside bodies. The antenna has a board-level all-layer copper keepout; the footprint also retains its original antenna rule area. The board-level antenna area permits U1 itself to overlap the area, while the footprint's own keepout protects against other footprints.

J4 = forward left / GPIO4, J5 = forward right / GPIO5, J6 = look-ahead left / GPIO6, J7 = look-ahead right / GPIO7. The latter two start at 45° outward, with 30–60° adjustment reserved. Rays show aiming adjustment, **not optical field of view**. The connectors face the sensor mounts; J10 faces the central IMU reservation.

## Electrical placement and verification

- All 78 schematic components, 66 exported nets, footprint assignments and schematic paths are preserved. Every footprint pad's net was compared against a fresh schematic netlist: zero mismatches.
- Zero tracks, vias or copper pours. Rule areas are not copper pours. Ratsnest connectivity is retained.
- All electronics are on F.Cu. All 22 existing drilled pads clear the underside body and attachment envelopes by their full pad bounds.
- No courtyard overlaps, pad shorts, malformed outline, placement-keepout violations or silkscreen collisions remain in DRC.
- Schematic parity: **zero issues**. DRC reports **220 expected unconnected items** for the unrouted board.
- The original project rules and four-layer/1.6 mm stackup are preserved; the schematic is unchanged.

## Five retained DRC findings

> **Resolved 2026-09-23** without changing the land patterns: see
> `layout/drc-clean/README.md`. J1's gap is allowed at JLCPCB's 0.20 mm by a rule
> scoped to J1's own pads and holes; U1's variant is now the project library
> footprint `Pixy-M2:ESP32-S3-WROOM-1_AntennaOverhang`.

1. **Four J1 pad-to-hole clearance errors:** the assigned stock Amphenol footprint has 0.25 mm between its locator holes and adjacent GND pads, versus the project's 0.30 mm minimum. These are intrinsic footprint geometry, not overlaps between placed components. Verify the connector drawing and fabricator capability before routing/fabrication; the rule has not been weakened and the findings have not been excluded. The original 0.20 mm board-edge clearance rule is satisfied.
2. **One U1 library-footprint mismatch warning:** antenna silkscreen segments crossing or crowding the rear edge were moved to F.Fab. Pads, electrical mapping, courtyard, antenna geometry and keepout remain unchanged. Updating this footprint from its library would restore those silkscreen segments.

`drc.json` contains the complete, unsuppressed report; `verification.json` records the net/mechanical checks.

## Mechanical limits before committing to hardware

The selected motor bracket, encoder protrusion, shafts, wheel hubs, gear mesh, fasteners, battery, sensor breakout and IMU dimensions must fit these allowances. In particular, the staggered motor shafts do not define a finished gear train: idlers, axle supports and gear ratios remain unspecified. Mount rigidity, PCB bending, screw access, ground clearance and actual wheel/gear tolerances need mechanical design validation. Top-side assemblies may lie above underside reservations because they occupy opposite sides; verify their real Z clearances and fastening method.

The 90 mm target gives 24 mm total nominal clearance in the stated 114 mm corridor. This does not prove diagonal transition clearance. The rigid module overhang brings the nominal component envelope to about 106 mm long before final brackets/cables; validate the complete swept shape and next-cell sensor visibility. Antenna performance also needs checking with the final battery, motors, gears and mounts installed.

## Previews

- `placement-preview.svg` / `.png`: dimensioned assembly overview, with actual top copper/silkscreen beneath the mechanical overlay.
- `top.svg` / `.png`: detailed top placement.
- `bottom.svg` / `.png`: mirrored bottom copper with underside and attachment reservations. Drawing-layer text is naturally mirrored in this bottom view.

No files are fabrication exports.
