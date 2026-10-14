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
14. replaces F1 with a Littelfuse 885 fuse (`f1_fuse.py`, 2026-09-23): builds
    the footprint from the stock library file, moves BT1 0.4 mm north so its
    courtyard fits, drops the stubs left on the old 2920 pads, and re-routes
    `/VBAT_RAW` and `/VBAT_FUSED` at 1.0 mm;
15. points U1 at the project footprint `Pixy-M2:ESP32-S3-WROOM-1_AntennaOverhang`
    (`Pcb.set_fpid`), matching the schematic, so the placed copy matches its
    library (see `layout/drc-clean/`);
16. prints the assembly marks on the silkscreen (`assembly_marks.py`,
    2026-09-23): the four ToF mount outlines with aim arrows and connector
    names, the Adafruit BNO085 outline with its holes, chip centre and X/Y
    axes on F.SilkS, and both Pololu N20 bodies on their wheel axles on
    B.SilkS.  It nudges the C20 and R15 reference fields clear of the IMU
    outline.  Standalone, it adds the marks to an existing board once;
17. moves the battery bay between the axles (`battery_bay.py`, 2026-09-24):
    the underside battery rule area goes to board x 0.5-66, y 57.5-74.5 (the
    62 x 17 mm pack plus its lead exit), both motor reservations turn their
    4 mm encoder allowance outboard, and User.1 / User.2 are redrawn to match,
    with the pack's lead route to BT1.  On B.SilkS it prints the pack
    outline, its lead arrow and the route as a dashed line (the motor names
    and `ENC CONN SIDE` come from `assembly_marks.py`).  Every edit asserts
    the placement-era geometry it replaces.  Standalone, it converts an
    existing board once, moving the motor names on a board marked before
    2026-09-24, and checks every drilled pad against the new envelopes and
    bands;
18. moves the UVLO enable network beside U3.2 (`reg_en.py`, 2026-09-24).
    C13 and R8 stand vertical in a row just west of U3, so EN -> C13.1 ->
    R8.1 is one straight top-layer run.  The FB sense trace keeps its
    via-free top-layer route to C11.1, but it now turns south round the
    outside of the new parts.  REG_EN's long leg to R7/R9 crosses under it on
    B.Cu.  The VSYS hop from C12 to C17 moves its upper via north of FB.
    Everything is hand-placed, and every old item is asserted before it is
    replaced.  Standalone, it converts an existing board once;
19. clears the IPROPI sense runs of motor and drive copper (`ipropi.py`,
    2026-09-24).  R17 moves west of U4's IN1/IN2 escapes.  GPIO2 then never
    crosses them: it runs down between C19 and the escapes, through R17 and
    on down x = 105, 1.7 mm from MOT_A_1.  R18 moves east of U5's GPIO41/42
    pair.  GPIO10 crosses the pair once, under U5's own pins, rises to R18
    and drops to its old diagonal to U1 just past the VBAT island.  The
    channel beside MOT_A_2 is left empty.  Standalone, it converts an
    existing board once;
20. puts U1 on an ESP32-S3-DevKitC-1-N8R8 plug-in daughterboard (`devkit.py`,
    branch `devkit-daughterboard`, 2026-10-13).  It deletes the 21 footprints
    the schematic dropped (USB-C input, D1/D3/R9, reset/boot, J11, TP5-TP8),
    closes the rear edge J1's footprint notch left open, and swaps U1 for
    `Pixy-M2:ESP32-S3-DevKitC-1_SMD_Sockets` along the right edge, antenna
    over the rear edge.  It moves the IMU reservation, its marks and the
    antenna exclusion, and 19 parts: J8/SW3 clear of the IMU's new column, J9
    to the front of the right edge, J10/C22 behind the IMU, the LEDs to the
    rear-left corner, the sense chain against GPIO1.  It then rips every net
    that ran to the old module or a moved part, keeping the motor-corner copper
    of the driver inputs and IPROPI runs, and re-routes: both motor pairs (J8's
    stubs fan in under its own housing; M1 to J9 follows layer-pinned
    waypoints), the plane pins that need their spot first, every signal in a
    fixed order, then the plane taps and one GND via in each piece of the B.Cu
    pour that has none (`stitch_islands`), so island removal keeps the piece.
    A* sees the custom clearance floors (IPROPI 0.75 mm, REG_EN and VBAT_SENSE
    5 mm), keeps signal vias 1.35 mm apart, and puts no 3V3 via over the In2
    VBAT island.  `prune_strict()` removes dead ends the way KiCad's
    `track_dangling` check sees them, and `drop_via_only_gnd()` the F.Cu GND
    stubs of removed or moved pads that are left joining only vias.
    Standalone, it converts an existing board once.  Evidence in
    `layout/devkit/README.md`;
21. straightens the copper into 0/45/90 degree runs (`octilinear.py`,
    2026-10-13).  The A* router turns for free on its 0.05 mm grid, so any
    other angle came out as a staircase of 0.05-0.3 mm steps that renders as a
    curve.  The stage first joins pieces that only overlap (`_heal`), then
    rebuilds each chain between pads, vias, junctions and width changes as the
    fewest clear legs, preferring 45 degree turns and chamfering the 90 degree
    ones.  It tests clearance with the router's raster and the custom floors,
    plus 0.02 mm (0.85 mm between IPROPI and motor copper), and keeps each
    motor output within 1.5 mm of its partner so a pair straightens together.  It leaves the hand-placed buck block (SW, BST, REG_EN, and
    chains touching U3, L1, C6, R8, C13) and the piece on each U4/U5 pin as
    they are, keeps necks inside their `Motor pin escape` area, and repeats
    until a round changes nothing.  Evidence in `layout/octilinear/README.md`;
22. adds the F.Cu `GND pour motor region` zone, the two `Motor pin escape` rule
    areas that `Pixy-M2.kicad_dru` conditions on, and the `Dwgs.User` fab note
    (issue 8's `Power pin escape` area fenced U2, which is gone);
23. serializes a temporary candidate and runs `via_openings.py` before replacing
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
| `f1_fuse.py` | the F1 swap (step 14).  Reuses `pololu_conn.py`'s rip / prune / reconnect helpers; its pruning zone is the pads' *extent* plus 2 mm, since F1's pads are 7.3 mm tall and a zone built from pad centres missed a track under the pad's own edge |
| `assembly_marks.py` | silkscreen marks for the off-board parts (step 16). Every dimension is a constant at the top: the ToF reservations, Adafruit's BNO085 board geometry (from `Adafruit_BNO08x.brd`) and Pololu's gearbox / motor / encoder lengths (drawing 0J949). Each part's marks are one KiCad group, so they move together in the GUI |
| `battery_bay.py` | the battery bay (step 17). Its constants are KiCad coordinates, old and new side by side, so a changed board fails an assertion instead of being half-edited. `check()` repeats `layout/verify_placement.py`'s drilled-pad test against the new envelopes on a routed board, which that script cannot load |
| `reg_en.py` | the enable network beside U3.2 (step 18). FB could not drop to B.Cu to make room: a via on it bonds to the In2 3V3 pour beside U3, which is the plane pickup review finding 5 removed. So FB stays on top and REG_EN's long leg, a signal-only net, takes the two vias. The new vias sit at least 1.35 mm from any other non-plane via, so their antipads never merge into one void in In1 or In2 |
| `devkit.py` | the DevKitC-1 daughterboard (step 20). Its constants are KiCad coordinates and every old position is asserted, so a changed board fails instead of being half-edited. All text-level edits (footprints, fields, texts, zones) come before any track edit, because each one re-splits the file. `make_router()` wraps `rework.Router` with three things the plain router does not know: the custom clearance floors as extra distance in `G.dist`, a 1.35 mm keep-off between non-plane vias, and no 3V3 vias over the VBAT island. `prune_strict()` replaces `pololu_conn.dangling()` for the nets it re-routes: a track end counts as connected only if it meets another track end exactly, lies in a pad, via or pour, or T-joins a track that is not within ten segments of its own chain. The staircase steps of one route all overlap their neighbours, so the looser test kept dead tails that KiCad flags, and it pruned stubs that carried another route's T-joint |
| `devkit_footprint.py` | writes `Pixy-M2.pretty/ESP32-S3-DevKitC-1_SMD_Sockets.kicad_mod`: two copies of KiCad's Harwin M20-786 SMD socket land pattern 22.86 mm apart, numbered as Espressif's symbol, the devkit outline on F.Fab and a USB-end arrow on F.SilkS. Courtyard = the socket bodies only, since the devkit stands ~10 mm up |
| `octilinear.py` | the straightening pass (step 21). `_heal()` joins every loose end that lies inside another piece of its net to that piece exactly, by splitting the host and adding a link no wider than either, because the router's pieces often meet only by overlapping. `chains()` then cuts each net and layer into chains between real nodes, and `simplify()` jumps from each vertex to the farthest chain point one leg, or a 45 degree leg plus an orthogonal one, reaches in the clear. A cell on the chain's own old centreline always counts as clear, since that copper passed DRC. The old segment stays wherever nothing else fits, so the result is never worse than the input |
| `ipropi.py` | the IPROPI sense runs (step 19). A* with the aggressors fattened was tried first and routed GPIO10 across J8 and through the encoder field, so both runs are hand-placed. For motor A, the pin order at U4 matches the order at U1's west column, so only R17's old position forced a crossing. For motor B, GPIO10 lands east of GPIO41/42 and must cross them. It does so once, under U5's pins, where the pair is still on F.Cu |
| `loop.py` | enclosed loop area of each motor output pair, the metric review issue 4 turns on. Run it on two boards to compare. The connector end of each pair is looked up by net, so it measures boards from before and after the J8/J9 re-pin alike. Chains track endpoints by BFS over a node graph — a greedy nearest-endpoint walk takes shortcuts through via branches and silently reports the straight-line quadrilateral between the four pads no matter how the board is routed, which is a convincing-looking wrong answer |
