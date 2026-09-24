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
