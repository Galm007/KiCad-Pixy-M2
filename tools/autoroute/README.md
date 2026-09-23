# autoroute — the grid router used to wire Pixy-M2 on 2026-09-21

Not a general tool. It was written for this board and hard-codes its net names,
widths and the In2.Cu VBAT island.

    python3 wire.py      # reads base.kicad_pcb, writes ../../Pixy-M2.kicad_pcb
    python3 rework.py    # reads base-routed.kicad_pcb, writes ../../Pixy-M2.kicad_pcb
    python3 check.py     # per-net length / width / via report on the routed board
    python3 loop.py -v   # motor output pair loop areas (add paths to compare boards)

A full `rework.py` run takes a few minutes: the via-out-of-pad pass recomputes a
per-net distance field for each via it moves. Run it in the background rather than
waiting on it, and **do not watch it with `pgrep -f "python3 rework.py"`** — the
pattern matches the watching shell's own command line, so the loop never exits.

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
4. routes the four motor trunks at 0.8 mm with A*.  `MOT_B_1` goes first; its
   finished polyline is then sampled, each sample offset 1.15 mm toward the side
   `MOT_B_2` has to end up on, and `MOT_B_2` is routed through those points so the
   two run as a pair (review issue 4).  An unreachable waypoint is skipped, not
   fatal.  `U4` is not paired — measured, no gain, see CLAUDE.md;
5. *then* searches for the plane stitching vias, so they cannot land on a trunk;
6. lays the buck block (`buck_block`, review issue 5) — same discipline: every
   track first, every via afterwards.  The first attempt did it the other way and
   dropped a ground stitching via straight into the corridor the switch node
   needed, shorting SW to GND under the package;
7. re-routes `/VSYS` (through a waypoint north of the buck, or A* threads the
   8.4 V input rail between L1 and the output capacitors), `/REG_EN` and
   `/GPIO6`, all of which were ripped to free space;
8. runs the historical centre-based relocation (`unstick_vias`) and its whole-net
   fallback. This stage alone misses drill-edge overlaps and paste-only pads;
   it is retained to reproduce the original routing, then corrected in step 10;
9. restores the verified local GPIO48 route with `encoder48_cleanup` (2026-09-22
   audit P3). The generic via relocation had stretched this encoder net to
   72.36 mm around TP5 and J11; the replacement is 26.03 mm, keeps the J8/R20/U1
   connections, and puts all four via holes at least 0.45 mm clear of SMD mask
   openings. This runs after the generic reroute so regeneration preserves it;
10. applies `finish_issue6.py`: 35 local via moves and their layer connections,
    with per-via fill/cap on the four intentional driver thermal vias;
11. adds the F.Cu `GND pour motor region` zone and the two `Motor pin escape` rule
   areas that `Pixy-M2.kicad_dru` conditions on, and the `Dwgs.User` fab note;
12. serializes a temporary candidate and runs `via_openings.py` before replacing
    the output PCB. Any missing expected via or aperture violation stops the run.

The final aperture check measures drill edges against mask and paste, including
independent paste-only pads, rotated pads and rounded corners. It requires
0.10 mm clearance except for the four explicitly filled/capped driver thermal
vias. To check an edited board without regenerating routing, run from repo root:

    /usr/bin/python3 tools/autoroute/via_openings.py Pixy-M2.kicad_pcb --output /tmp/apertures.json
    /usr/bin/python3 tools/autoroute/test_via_openings.py

The first command exits nonzero on a violation; it complements, not replaces,
KiCad DRC and schematic parity. See `layout/issue6-complete/README.md`.

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
| `pcbedit.py` | text-level surgery on the `.kicad_pcb`: add/drop segments and vias, move footprints, their pads' and texts' angles and board-level labels, append zones. **Rotating a footprint must rotate every `(at …)` inside it** — pads included, since each stores its angle in the board frame. Miss them and DRC reports `lib_footprint_mismatch`, which reads like a library problem rather than a bad edit |
| `loop.py` | enclosed loop area of each motor output pair, the metric review issue 4 turns on. Run it on two boards to compare. Chains track endpoints by BFS over a node graph — a greedy nearest-endpoint walk takes shortcuts through via branches and silently reports the straight-line quadrilateral between the four pads no matter how the board is routed, which is a convincing-looking wrong answer |
