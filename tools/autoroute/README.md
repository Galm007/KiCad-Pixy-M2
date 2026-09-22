# autoroute — the grid router used to wire Pixy-M2 on 2026-09-21

Not a general tool. It was written for this board and hard-codes its net names,
widths and the In2.Cu VBAT island.

    python3 wire.py      # reads base.kicad_pcb, writes ../../Pixy-M2.kicad_pcb
    python3 rework.py    # reads base-routed.kicad_pcb, writes ../../Pixy-M2.kicad_pcb
    python3 check.py     # per-net length / width / via report on the routed board

## wire.py — the original routing pass

`wire.py` expects an *unrouted* copy of the board as `base.kicad_pcb` in its working
directory, and rewrites the project file from scratch every run — it never edits
existing tracks. Re-running it discards all hand edits made since, so copy the board
aside first.

How it works: pads and holes are rasterised onto a 0.05 mm grid; per net a Euclidean
distance transform gives the legal region for that net's width (0.26 mm clearance
target against a 0.2 mm rule); A* over F.Cu + B.Cu with a via cost routes each net,
growing a connected group at a time. Plane nets get one stitching via per SMD pad
instead of being routed. A final pass widens power tracks wherever clearance allows.

Two tracks in the committed board were hand-corrected afterwards and are not
reproduced by a re-run: one ESP_3V3 segment at U4 narrowed 0.4 → 0.2 mm, and a short
segment added so MOT_B_2 lands on J9 pad 6's annulus rather than its rounded corner.

## rework.py — the motor-region second pass (review issues 1–3)

`rework.py` reads **`base-routed.kicad_pcb`**, a snapshot of `wire.py`'s output, and
writes the reworked board. Like `wire.py` it never edits the file it reads, so it is
re-runnable — but it also discards any hand edits made to `Pixy-M2.kicad_pcb` since,
and it emits the board with *unfilled* zones. Always follow it with:

    kicad-cli pcb drc --schematic-parity --refill-zones --save-board \
        --format json -o /tmp/drc.json ../../Pixy-M2.kicad_pcb

What it does, in order — the order matters:

1. moves C18, C20, C21 and four silkscreen reference fields (footprint moves must
   come before any track edit: they re-split the file and drop pending block edits);
2. rips the four motor nets, `/GPIO6`, and the VBAT/GND stubs in five boxes around
   the old capacitor and driver positions;
3. lays the hand-computed copper — driver pin escapes, the VM/GND runs across to each
   bypass cap, and the in-pad thermal vias — all of it clearance-checked by hand
   against the 0.5 mm pin pitch rather than searched;
4. routes the four motor trunks at 0.8 mm with A*;
5. *then* searches for the plane stitching vias, so they cannot land on a trunk;
6. re-routes `/GPIO6`, which had to be ripped to free C20's new position;
7. adds the F.Cu `GND pour motor region` zone and the two `Motor pin escape` rule
   areas that `Pixy-M2.kicad_dru` conditions on.

`! no neck+via for GND from (109.0,114.8)` and the same for `(117.0,114.8)` are
**expected output**, not failures: the ESP_3V3 VREF feed blocks a wide neck out of the
lower end of each exposed pad. Nothing is emitted when that search fails.

## supporting modules

| file | role |
|---|---|
| `sexp.py` | minimal s-expression reader |
| `load.py` | footprint / pad extraction with rotation applied |
| `board.py` | 0.05 mm raster helpers, board outline fill, keepout zones |
| `grid.py` | obstacle raster of the **current** board — pads *and* existing tracks, vias and holes — with per-net distance fields. This is what lets `rework.py` route against a board that is already wired, which `wire.py` could not do |
| `pcbedit.py` | text-level surgery on the `.kicad_pcb`: add/drop segments and vias, move footprints and their text fields, append zones |
