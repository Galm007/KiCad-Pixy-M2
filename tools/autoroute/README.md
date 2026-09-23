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
11. lays the USB pair (`usb_pair.py`, review issue 7).  It rips the four USB
    nets and CC1/CC2, turns U2 to rot 90 so its flow-through pins face J1 and
    U1, hand-places the 0.25 / 0.15 mm pair J1 → U2 → U1 on F.Cu with no vias,
    takes U2's GND and VBUS out under the body, then A*-routes CC1/CC2 with the
    pair inflated 0.15 mm so they cross it on B.Cu and keep their vias clear.
    It runs last so that every stage before it replays unchanged; the U2 move
    therefore goes through `Pcb.sync()` (below) rather than the up-front MOVES;
12. lays the copper the issue-8 rule set requires (`issue8.py`): widens the five
    nets the router left at 0.15 mm to 0.2 mm outside the DRV8231A pin fields,
    re-routes the USB supply (`Net-(F2-Pad1)`, `/VBUS`) at 0.6 mm with the D3 tap
    pinned to its old corridor, and the R14 tap on `/VBAT_FUSED` at 0.8 mm;
13. moves J8/J9 to JST SH in the Pololu encoder pin order (`pololu_conn.py`,
    2026-09-23).  It swaps the two PH footprints for SH clones of J4, rips the
    motor trunks back to the driver escapes, drops other-net copper under the
    new pad rows, prunes what that leaves dangling *within 2 mm of the new
    pads only*, then re-routes: 0.6 mm fan-in stubs and paired 0.8 mm trunks on
    M1/M2, 0.2 mm reconnections for the cut signals, plane stitches for GND,
    VCC and the MP pads, and U4's VREF feed (its B.Cu run to the old
    through-hole J8 pin was the only 3V3 path under the In2 VBAT island).
    It also sets R17/R18 to 2.2 kΩ.  `! no stitch via for GND near …` for
    J8.1, J8's west MP and J9.1 is **expected**: those pads are then tied to
    the nearest stitched pad or GND via;
14. points U1 at the project footprint `Pixy-M2:ESP32-S3-WROOM-1_AntennaOverhang`
    (`Pcb.set_fpid`), matching the schematic, so the placed copy matches its
    library (see `layout/drc-clean/`);
15. adds the F.Cu `GND pour motor region` zone, the two `Motor pin escape` rule
   areas and the `Power pin escape` rule area that `Pixy-M2.kicad_dru` conditions
   on, and the `Dwgs.User` fab note;
16. serializes a temporary candidate and runs `via_openings.py` before replacing
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
| `pcbedit.py` | text-level surgery on the `.kicad_pcb`: add/drop segments and vias, move footprints, their pads' and texts' angles and board-level labels, append zones. **A footprint or text edit re-splits the file from `self.text` and drops any track/via edit not yet in it** — which is why `rework.py` does its moves first; a late move must call `sync()` first to fold pending block edits back in. **Rotating a footprint must rotate every `(at …)` inside it** — pads included, since each stores its angle in the board frame. Miss them and DRC reports `lib_footprint_mismatch`, which reads like a library problem rather than a bad edit |
| `issue8.py` | review issue 8: the copper the Power/Battery/signal-width rules require. Two router caveats live here: `Router.route_waypoints` offers each waypoint on both layers, so consecutive legs can meet on different layers with no via between them (pin waypoints to one layer); and `G.smd_block` keeps via *centres* only 0.15 mm off SMD pads, which lets a drill touch the mask opening — `issue8.py` rebuilds it at drill radius + 0.10 mm for its own stage |
| `usb_pair.py` | review issue 7: U2 rotation, the hand-placed USB pair, and the CC1/CC2 reroute around it. Geometry constants (`WIDTH`, `GAP`, `U2_AT`, `GND_VIA`) are at the top; the impedance behind them is `../impedance/zdiff.py` |
| `pololu_conn.py` | the J8/J9 connector swap (step 13).  Its `prune()` subtracts a baseline taken before the swap, because on plane nets every bare stitching via looks dangling, and it only trims near the new pads: pruning a cut GPIO40 all the way back ate the 0.15 mm DRV8231A pin escape, which the router cannot re-create.  Its dangling test counts a T onto a segment only if that segment does not share an end with the one tested, because the router's 0.05 mm staircase steps each lie within half a width of the next |
| `loop.py` | enclosed loop area of each motor output pair, the metric review issue 4 turns on. Run it on two boards to compare. The connector end of each pair is looked up by net, so it measures boards from before and after the J8/J9 re-pin alike. Chains track endpoints by BFS over a node graph — a greedy nearest-endpoint walk takes shortcuts through via branches and silently reports the straight-line quadrilateral between the four pads no matter how the board is routed, which is a convincing-looking wrong answer |
