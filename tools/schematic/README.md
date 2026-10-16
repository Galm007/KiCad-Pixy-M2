# schematic — the 2026-09-24 sheet re-layout

Re-arranged `Pixy-M2.kicad_sch` into framed functional blocks without changing
a single net, pin or part.

    python3 relayout.py OLD.kicad_sch OUT.kicad_sch   # one-shot, see below
    python3 netdiff.py before.net after.net           # exit 1 on any electrical change
    python3 blocks.py [sheet]                         # block extents on a sheet

- `schlib.py` reads the sheet span-preservingly: every item keeps KiCad's own
  text, and edits are coordinate rewrites, deletions or appended items.
- `clusters.py` groups items that touch by wire geometry. A cluster moved as a
  whole cannot lose a connection; clusters join each other only through labels.
- `relayout.py` phase 1 redraws two blocks (USB CC resistors off the D± pair;
  UVLO split from the buck on its existing `REG_EN` label). Phase 2 moves every
  cluster into its frame. It addresses items by UUID and old coordinates, so it
  only runs on the pre-re-layout sheet (`git show a0b645a:Pixy-M2.kicad_sch`).
- `netdiff.py` compares two `kicadsexpr` netlists: net names and members, and
  each part's value, footprint and fields.

Verified: 66 nets, 78 parts, 0 differences; ERC 0/0; PCB DRC with schematic
parity 0/0/0.

## devkit.py — U1 becomes a plug-in DevKitC-1 (branch `devkit-daughterboard`)

    python3 devkit.py ../../Pixy-M2.kicad_sch ../../Pixy-M2.kicad_sch   # one-shot

Converts the 2026-09-24 sheet, span-preserving like `relayout.py`:

- U1 keeps its UUID (so the PCB footprint keeps its link) and becomes Espressif's
  `PCM_Espressif:ESP32-S3-DevKitC` symbol, placed so its 3V3 pins land on the old
  `ESP_3V3` wire. Every pin carries a label or a no-connect flag.
- Deletes whole wire clusters made only of the removed parts: the USB-C input
  (J1, U2, F2, R1, R5, R6, C8), D1, the reset/boot network (R2, C3–C5, SW1, SW2),
  J11 and TP5–TP8. In the UVLO block it removes only the USB leg (D3, R9, the
  `VBUS` label and three wire stubs); R7/R8/C13 and their junction stay.
- Relabels encoder B's OUT B from `GPIO38` to `GPIO18` at R22 and J9.2 (the v1.1
  devkit's RGB LED is on GPIO38) and moves TP9 under TP3.
- Drops the RESET/BOOT and DEBUG frames, retitles the USB-C frame as the
  daughterboard notes, and removes symbols nothing uses from the cache.

Every item it touches is asserted first, so it only runs on the pre-devkit sheet.
`netdiff.py` against the old netlist shows exactly the intended changes: the
removed parts and nets, U1's pin numbering, `/GPIO38` → `/GPIO18`, and `/VBUS`
gone from `VSYS` and `REG_EN`.

## power_integrity.py — motor cutoff and isolated supplies

    python3 power_integrity.py BEFORE.kicad_sch OUT.kicad_sch

One-shot conversion of the 2026-10-13 devkit sheet. Adds U6/U7 for a motor
cutoff independent of USB and firmware, uses U6's reference with 1 kΩ R17/R18
(decoupled by C25 at U6 and C28 at the drivers), and adds U8/Q2/Q3 for
USB-priority isolation of the buck, with C30 holding ESP_3V3 through the
handover. TP10/TP11 bring out MOTOR_OK and MOTOR_VREF. U1.21 becomes voltage
sensing only. Existing connector pins and named rails remain. U4 and U5 move
7.62 mm right with their pin labels, so the longer DRV_x_INn and MOTOR_VREF
names stay inside their frames. The two new custom symbols live in
`Pixy-M2.kicad_sym`; pin maps, values, part numbers and sheet positions come
from `tools/power_integrity_data.py`, also consumed by the PCB stage. New
symbols take a uuid5 of their reference, so the PCB stage can link footprints
without reading the sheet.

Export netlists before and after. Run `netdiff.py` to see the full intentional
change, then `python3 tools/power_integrity_check.py before.net after.net`
from the project root to assert every pin's expected connection and every
original part's fields. This also calculates DC tolerance envelopes; it does
not certify motor transients or USB LDO thermals. Evidence in
`layout/power-integrity/README.md`.
