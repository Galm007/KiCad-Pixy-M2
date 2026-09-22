# autoroute — the grid router used to wire Pixy-M2 on 2026-09-21

Not a general tool. It was written for this board and hard-codes its net names,
widths and the In2.Cu VBAT island.

    python3 wire.py      # reads base.kicad_pcb, writes ../../Pixy-M2.kicad_pcb
    python3 check.py     # per-net length / width / via report on the routed board

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
