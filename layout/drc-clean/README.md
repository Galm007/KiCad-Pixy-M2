# DRC clean: J1 hole clearance and the U1 footprint warning (2026-09-23)

Five DRC items had been carried since placement (`layout/README.md`, "Five
retained DRC findings"): four J1 `hole_clearance` errors and one U1
`lib_footprint_mismatch` warning. Neither was a routing fault. Both are now
resolved without changing any copper. KiCad reports **0 violations, 0
unconnected items, and 0 schematic-parity issues** (`drc.json`), and ERC still
reports 0 (`erc.json`).

## J1: four hole-clearance errors

J1 uses the stock KiCad footprint `Connector_USB:USB_C_Receptacle_Amphenol_12401948E412A`.
The earlier CLAUDE.md note named `USB_C_Receptacle_Amazon`. That was wrong: the
`.kicad_mod` of that name in the repository root is unused.

The footprint's four GND pads (A1/B12 and A12/B1, 0.8 × 1.4 mm) end at
y = −4.40 mm. Its 0.6 mm locating holes start at y = −4.15 mm. That leaves
**0.25 mm**, against the project's 0.30 mm hole-clearance rule. The four reports
are duplicate pad numbers over two physical gaps.

**This is the manufacturer's land pattern, so the land pattern stays.** The
footprint cites Amphenol drawing c12401948. KiCad's librarians merged it against
that drawing in kicad-footprints MR !3540. Amphenol's own site blocks automated
download, so I could not re-measure the drawing myself. Shortening the GND
pads would move the part off its recommended layout to satisfy a rule the
fabricator doesn't need. JLCPCB's capabilities page gives **0.20 mm**
NPTH-to-track.

**How the rule changed.** KiCad's board-setup hole clearance is absolute: a
custom rule cannot relax it, the same as the minimum track width (issue 8). So:

- the board setup `min_hole_clearance` is **0.30 → 0.20 mm**, the fab floor;
- a new custom rule, **"Hole clearance"**, restores **0.30 mm for every pair
  except J1's own pads against J1's own holes**.

Everything else on the board is held to exactly what it was before.

**Negative tests** (`negative-tests.json`):

| edit | fires |
|---|---|
| a track 0.25 mm from an SW3 locating hole (not J1) | "Hole clearance", 0.30 mm |
| J1's hole moved to 0.15 mm from its own GND pads | the 0.20 mm board-setup floor |

## U1: library-footprint mismatch warning

U1's board copy differed from `PCM_Espressif:ESP32-S3-WROOM-1` in exactly five
items: the four antenna-area outline lines and the "Antenna Area" label, moved
from F.SilkS to F.Fab. The module's antenna deliberately overhangs the board
edge, so the silkscreen would print off the board. The change was intentional
and recorded in `layout/README.md`. Pads, courtyard, antenna keepout and 3D
model are identical to Espressif's.

"Update footprint from library" would have undone the change, so that was not
the fix. Instead the variant is now a real library footprint:

- `Pixy-M2.pretty/ESP32-S3-WROOM-1_AntennaOverhang.kicad_mod` is Espressif's
  file with those five layer changes, a new name, and a description saying why.
  `diff` against the Espressif original shows nothing else.
- `fp-lib-table` (project) adds library `Pixy-M2` at `${KIPRJMOD}/Pixy-M2.pretty`.
- U1 points at `Pixy-M2:ESP32-S3-WROOM-1_AntennaOverhang` in both files:
  - the board, as a one-line change;
  - the schematic's **placed U1 instance only**. Changing the cached library
    symbol as well produced an ERC `lib_symbol_mismatch`, so it was left as
    Espressif's.
- `rework.py` sets the same footprint id when it regenerates the board
  (`Pcb.set_fpid`). A full replay reproduces HEAD's tracks and vias exactly.
  The board file itself was edited in one line rather than regenerated, to
  keep the diff free of UUID churn.

## Not changed

No copper, footprint geometry or placement changed. The committed board differs
from the previous commit only in U1's footprint id.
