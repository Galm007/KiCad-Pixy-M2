# Pixy-M2 — Micromouse Controller PCB

Context for a Claude Code session working on this KiCad project via the KiCad MCP server.

Single-board micromouse controller, KiCad 10. It carries an ESP32-S3-WROOM-1-N16,
two DRV8231A motor drivers, a 2S LiPo power path (fuse, P-FET switch, TVS, UVLO),
an AP63203 3.3 V buck and USB-C. JST-SH connectors lead to off-board parts: four
VL53L0X ToF sensors, a BNO085 IMU and two Pololu N20 gearmotors with encoders.

**Where things live.** This file holds the working rules: invariants, "do not"
items and checks. Other sources:

- `README.md`: design rationale, pin and connector tables, firmware bring-up notes.
- `BOM.md`: parts.
- `tools/autoroute/README.md`: the layout pipeline.
- `tools/schematic/README.md`: the sheet re-layout tooling.
- `layout/*/README.md`: per-fix measurements and evidence.
- The git history of this file: the full issue-by-issue narrative (pruned 2026-09-24).

## Status (2026-09-24)

- **Schematic complete.** `Pixy-M2.kicad_sch`, a single flat A3 sheet with 13
  dashed, titled block frames. Keep new parts inside their block's frame. 66 nets,
  78 parts. ERC 0/0.
- **PCB placed and fully routed.** 66 × 100 mm, 4 layers, 254 vias. DRC gives 0
  violations, 0 unconnected and 0 parity issues. The aperture audit passes.
- **Open:**
  - **Mechanical design.** There are no mounting holes, drivetrain or brackets
    yet.
  - **Motor gear ratio.** 12 CPR before gearing is low, so check the ratio gives
    enough encoder edges for the control loop.
  - **Hardware measurements.** F1 and U4/U5 temperatures under hard acceleration
    and stall. IPROPI readings and the 1.00 A limit under PWM.
  - **USB impedance.** Confirm with the fab's calculator, or order impedance
    control.
  - **Antenna performance** with the mechanics fitted.
  - **Silkscreen gaps.** No text yet for "pin 1 = VCC" at J4–J7, the `-R8`
    PSRAM caveat by TP6–TP8, or a BOOT strapping note at J11.
  - `docs/images/pcb-3d-iso.png` is stale. It shows R8/C13 in their old
    positions, and its camera settings were not recorded.
- **A clean ERC is the floor, not evidence.** ERC does not check footprints,
  ratings, saturation current or whether a pin goes anywhere useful.

## Checks and workflow

```sh
kicad-cli sch export netlist --format kicadsexpr -o /tmp/after.net Pixy-M2.kicad_sch
python3 tools/schematic/netdiff.py /tmp/before.net /tmp/after.net   # exit 1 on any electrical change
kicad-cli sch erc -o /tmp/erc.rpt Pixy-M2.kicad_sch
kicad-cli pcb drc --schematic-parity --refill-zones --save-board --format json -o /tmp/drc.json Pixy-M2.kicad_pcb
/usr/bin/python3 tools/autoroute/via_openings.py Pixy-M2.kicad_pcb --output /tmp/apertures.json
kicad-cli sch export svg --exclude-drawing-sheet --black-and-white -o /tmp/svg Pixy-M2.kicad_sch
rsvg-convert -z 8 -b white /tmp/svg/Pixy-M2.svg -o /tmp/sheet.png   # ~30 px/mm
```

- **Close KiCad before editing files on disk.** A `~Pixy-M2.*.lck` file means the
  GUI has the project open, and whichever side saves last wins.
- **After any structural schematic edit, diff the netlist.** Then render the sheet
  and look at it. A netlist diff cannot see overlapping text, or a wire crossing
  a point where two other wires meet end to end. KiCad treats that point as a
  junction, so the crossing silently shorts two nets.
- **Change a component's Value, Footprint, Datasheet and MPN together.**
  Half-updated parts are how the wrong part gets ordered.
- **DRC needs `--refill-zones`.** Without it, every plane-connected pad reports
  as unconnected. `--save-board` writes the fills back. Read `unconnected_items`
  as well as `violations`.
- **Ask before deleting connector pins or renaming nets.** First make sure every
  net has somewhere else to go. Keep `VBAT`, `VBUS` and `VSYS` as explicit labels.
- Symbol fields inherit the symbol's rotation. On a 90°-rotated symbol:
  - give the field its own 90° angle so it renders horizontally;
  - write `justify right` to get left-justified text. `justify left` renders
    right-justified, so the text grows into the symbol.
- **Renders** (`docs/images/`):
  - `pcb-3d-top.png`, `pcb-3d-bottom.png`:
    `kicad-cli pcb render --side top|bottom -w 1408 -h 2024 --background opaque --quality high`.
  - `pcb-copper-top.png`:
    `kicad-cli pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet --layers F.Cu,Edge.Cuts`,
    then `rsvg-convert -w 1000 -b white`.

### Library edits that "Update from library" silently reverts

- **U4/U5, `Driver_Motor:DRV8231ADSG`.** The cached symbol has OUT2 (pin 8)
  retyped from `power_in` to `output`, fixing a stock-library bug. Never run
  "Update Symbols from Library" on them. If two `power_pin_not_driven` errors
  appear on the motor nets, re-apply the fix. Do not add PWR_FLAGs.
  `#FLG04` on `VBAT` is legitimate: ERC cannot see a source through BT1 → F1 → Q1.
- **U1** uses `Pixy-M2:ESP32-S3-WROOM-1_AntennaOverhang` (project library
  `Pixy-M2.pretty`, registered in `fp-lib-table`). It is Espressif's footprint
  with the antenna silkscreen moved to F.Fab, because the antenna overhangs the
  rear edge.
  - Never update it back to `PCM_Espressif`.
  - The cached *symbol* still names `PCM_Espressif` as its default footprint,
    deliberately. Editing the cache raises `lib_symbol_mismatch`.
- **Q1** borrows `Transistor_FET:IRF7404` for its SO-8 pin map. The fitted part is
  **AO4407A**. Never order IRF7404.
- `USB_C_Receptacle_Amazon.kicad_mod` in the repo root is unused. J1 is the stock
  `Connector_USB:USB_C_Receptacle_Amphenol_12401948E412A`.

## Verified correct — do not re-flag

Each was checked against the extracted netlist. A review that "finds" one of these is wrong.

- **Buck.** AP63203WU is the fixed-3.3 V variant. FB (U3.1) senses `ESP_3V3`
  directly, with no divider. C6 (BST cap) sits across U3.6/U3.5. EN (U3.2) is on
  `REG_EN`, not tied to IN; `VSYS` is C12, C17, D1.K, D2.K and U3.3.
- **Input capacitance.** One C12 (22 µF 25 V 1206) meets the datasheet's 10 µF
  *effective* input. It keeps ~11–13 µF at 8.4 V bias. The datasheet's 2 × 22 µF
  is the *output*, which C7 ‖ C11 match. C17 (0.1 µF) is the HF bypass.
- **USB-C.** R6 (CC1, J1.A5) and R1 (CC2, J1.B5) are 5.1 k to GND, each
  independently.
  - U2 is in-line: pins 1/6 on D−, 3/4 on D+, 5 on VBUS, 2 on GND.
  - The shield goes through R5 (1 M) ‖ C8 to GND.
  - All four VBUS and all four GND pins of J1 are tied together.
  - **No D± series resistors.** They were deleted deliberately; the S3 PHY is
    matched. Do not re-add them "just in case".
- **Module pins.** All 41 are accounted for. GPIO45 (U1.26) and GPIO46 (U1.16)
  carry explicit no-connect flags.
  - Both are strapping pins. GPIO45 high at reset sets the flash rail to 1.8 V,
    and the board will not boot. GPIO46 high with GPIO0 low is an invalid
    combination.
  - External pulldowns were rejected: the internal ~45 k suffices.
  - In layout they are floating pads. Give them no trace, test point or pour
    island.
- **Seven no-connect flags, all deliberate:** U1.26, U1.16, J4.5–J7.5 (the ToF
  interrupt pins) and SW3.1.
- **D2 feeds only `VSYS`.** Motor current on `VBAT` never passes through it. D2
  dissipates ~140 mW worst case, so an ideal-diode controller is unnecessary. Do
  not re-propose it unless a real load moves onto `VSYS`.
- **The DRV8231A thermal pad (pin 9) is on GND.** It sits at the same symbol
  coordinate as pin 7, and the netlist confirms it.
- **Boot and reset.** SW1 pulls `CHIP_PU` low (R2 10 k pull-up, C3 1 µF, C4 0.1 µF).
  SW2 pulls GPIO0 low (C5).
- **No JTAG header.** USB-Serial-JTAG over J1 provides flashing, console and debug.

## Power path

```
 BT1+ ─ F1 ─ VBAT_FUSED ─ Q1 (S→D) ─ VBAT ─┬─ D2 ─┐
               R14 ─ G ─ SW3 (gate only)    ├─ U4/U5 VM, C18–C21
                                            ├─ R7/R8 UVLO, R10/R11 sense, TP1
                                            └─ D6 TVS → GND
                                                   ├─ VSYS ─ U3 buck ─ ESP_3V3
 J1 VBUS ─ F2 ─ VBUS ─ D1 ─────────────────────────┘
                 ├─ D3 ─ R9 → REG_EN
                 └─ U2.5
```

- **F1: Littelfuse `0885005.DR`** (`Device:Fuse`, `Fuse:Fuse_Littelfuse-NANO2-885`).
  5 A fast-acting, breaks 1500 A at 125 VDC, one-time.
  - Why: the pack (OVONIC 2S 450 mAh 100C) could short at an estimated 200–400 A.
    The old PPTC (40 A) and NANO2 451/453 (300–400 A) were rejected for that.
  - Worst normal load is ~2.4 A: both motors at the limit plus the buck.
  - **If F1 nuisance-blows, do not fit a bigger fuse.** Lower ITRIP or tighten
    the firmware duty cap first.
- **F2** stays a PPTC, Bourns MF-MSMF050-2 (0.5 A hold).
- **Q1: AO4407A.**
  - Pins: source 1–3 on `VBAT_FUSED`, drain 5–8 on `VBAT`, gate 4.
  - R14 (100 k, G–S) defaults it OFF. SW3 switches only the gate. Give all seven
    S/D pads adequate copper.
  - Both dividers and D6 sit downstream of it, so OFF leaves only Q1's leakage on
    the pack. That is low, not zero.
  - Its body diode means it is **not** reverse-polarity protection.
  - SW3 OFF with USB present does not guarantee a 0 V `VBAT`: R7 and D2 leakage
    bias it. The drivers' pulldowns keep them disabled.
- **D6: SMBJ9.0A** (Vishay, SMB). It clamps `VBAT` at up to **15.4 V**. Every
  part on `VBAT` or `VSYS` must survive that:
  - DRV8231A: 35 V.
  - C19/C21: 25 V.
  - D1/D2 (onsemi **MBRA340T3G**, SMA): 40 V. Beware "SS34": Vishay's SS34 is
    SMC, not SMA.
  - DRV8833 (11.8 V) and TB6612FNG (15 V) are rejected for this reason.
- **UVLO.** R7 120 k (from `VBAT`) and R8 24 k to GND, plus C13, on U3's EN
  comparator. It has built-in switched hysteresis.
  - Thresholds: on at 6.90 V, off at 5.94 V (3.45 / 2.97 V/cell).
  - **R7/R8 must be 1 %**, and the Value field says so.
  - The USB path VBUS → D3 (BAT54W) → R9 39 k holds EN up with no pack.
  - **D3 is required.** Without it, an unpowered USB host pulls EN down and the
    board will not start. No R9 value satisfies both cases.
  - EN is rated to 35 V abs max, so no clamp.
  - **With USB present, the hardware UVLO is defeated.** Firmware must cut off a
    low pack.
- **Battery sense.** `VBAT` → R10 470 k / R11 220 k (1 %) → GPIO1 (ADC1_CH0).
  - **C14 (100 nF) is required.** The source is 150 kΩ, too high for the SAR
    ADC's sample-and-hold. Its 15 ms RC means allowing ~50 ms to settle.
  - Keep it on ADC1: ADC2 is unusable while Wi-Fi runs.
  - No gate FET. A low-side gate floats the node into the GPIO clamp, and a
    high-side gate needs 4 parts to save 12 µA.
- **L1: Bourns SRP5030T-4R7M** (Isat 6 A, 53 mΩ, `Inductor_SMD:L_Bourns_SRP5030T`).
  The Sunlord SWPA4030S is the rejected smaller option. Its land pattern differs,
  so switching means changing both fields together.
- **Capacitor ratings.** Every capacitor states its rating in its Value field.
  - C6 (BST) sees ≤ 6 V.
  - **C8 is 4.7 nF 1 kV 1206**, because an 8 kV ESD strike puts ~250 V across it.
- **LEDs.**
  - **D4 (power) is a high-efficiency red LED on 10 k**, about 150 µA. Do not
    substitute blue, white or pure green: they would not light. D4 dominates
    deep-sleep current.
  - **D5 (status) is green**, on GPIO3 → R13 2.2 k → anode. It is active-high,
    which keeps the strapping pin low at reset.
- **U1 is `-N16`, with no PSRAM**, so GPIO35–37 are free. A `-R8` part turns
  TP6–TP8 into PSRAM signals.

## Motor drive

- **U4/U5: DRV8231A (DSG, WSON-8).**
  - Chosen for its 35 V abs max over the TVS clamp and its 4.5 V minimum VM,
    which covers the whole pack range.
  - **Internal 100 k pulldowns on IN1/IN2** keep both motors off while the GPIOs
    float at reset. Add no external pulldowns.
  - No nSLEEP or nFAULT pins are needed.
  - Alternatives:
    - DRV8874: better R_DS(on), but no stock KiCad symbol.
    - The DDA (HSOP-8) package of the same die: RθJA 42.8 °C/W against 66.5.
      This is the move if thermals are tight.
- **Current limit.** `VREF` = 3.3 V, and R17/R18 are 2.2 k 1 %.
  - ITRIP = 3.3 / (1500 µA/A × 2.2 k) = **1.00 A**. IPROPI reads 3.3 V/A on
    GPIO2/GPIO10 (ADC1). The ADC clips at ~0.94 A, so a stall reads as full
    scale.
  - **The 1 A is set by the JST SH contacts and Pololu's cable.** Do not lower
    R17/R18 (raising the limit) without re-checking both.
  - IPROPI tracks only the low-side current and is off in coast.
- **Local capacitance.** C18/C20 (0.1 µF 50 V) at each VM pin. C19/C21 (22 µF
  25 V 1206) are the bulk. Recirculation goes through the H-bridge body diodes.
- **Motors.** Pololu Micro Metal Gearmotor HP 6V with a 12 CPR encoder:
  1.6 A stall at 6 V, 100 mA free-run.
  - They are over-volted on 8.4 V, so firmware caps PWM at about 71 % duty.
  - J8 is motor A (left); J9 is motor B (right).

## Pinout

| GPIO | Use | GPIO | Use |
|---|---|---|---|
| 0 | BOOT: SW2, J11.5 | 19 / 20 | USB D− / D+ |
| 1 | `VBAT_SENSE` (ADC1_CH0) | 21 / 38 | encoder B OUT A / OUT B (J9.3 / J9.2) |
| 2 / 10 | IPROPI motor A / B (ADC1) | 39 / 40 | motor A IN1 / IN2 |
| 3 | status LED D5 | 41 / 42 | motor B IN1 / IN2 |
| 4–7 | XSHUT J4–J7 | 43 / 44 | UART0 TX / RX (J11.3 / J11.4) |
| 8 / 9 | I²C SDA / SCL, R15/R16 2.2 k | 45, 46 | no-connect (strapping) |
| 11–17 | IMU MOSI, SCK, MISO, CS, INT, RST, WAKE | 47 / 48 | encoder A OUT A / OUT B (J8.3 / J8.2) |
| 18, 35–37 | spares on TP5–TP8 | | |

All GPIOs are allocated. GPIO11/12/13 are the native FSPI D/CLK/Q pins.

| Conn | Part | Pins |
|---|---|---|
| J4–J7 | SM06B-SRSS-TB, GY-VL53L0XV2 order | **1 VCC (3V3)**, 2 GND, 3 SCL, 4 SDA, 5 INT (NC), 6 XSHUT. J4 FL/GPIO4, J5 FR/GPIO5, J6 look-left/GPIO6, J7 look-right/GPIO7 |
| J8, J9 | SM06B-SRSS-TB, Pololu encoder order | 1 GND, 2 OUT B, 3 OUT A, 4 VCC (3V3), 5 M2, 6 M1, MP GND |
| J10 | SM09B-SRSS-TB | 1 VIN, 2 GND, 3 SCK, 4 MOSI, 5 MISO, 6 CS, 7 INT, 8 RST, 9 WAKE/PS0, MP GND |
| J11 | SM06B-SRSS-TB | 1 3V3 (reference only), 2 GND, 3 U0TXD, 4 U0RXD, 5 GPIO0, 6 CHIP_PU. An esptool auto-reset interface |
| TP1–TP9 | 1.5 mm pads | VBAT, 3V3, GND, SW, GPIO18, GPIO35, GPIO36, GPIO37, GND |

- **ToF sensors.**
  - Every VL53L0X wakes at address 0x29, and the address is volatile, so each
    sensor needs its own XSHUT.
  - GPIO4–7 float at reset, and the module pulls XSHUT up to 2.8 V. Firmware
    drives them open-drain. Add no pulldown on this board.
  - 3.3 V is within spec, so no level shifter.
  - R15/R16 are the only bus pull-ups. If the modules add 10 k each, the bus
    sees about 1.2 k in total, which is still legal.
  - C15 (10 µF) and C16 (0.1 µF) serve the pulsed VCSEL load.
- **IMU.**
  - SPI was chosen over the shared I²C bus for **latency jitter**, not
    throughput.
  - INT and RST are required in SPI mode. R23 (10 k) holds RST high.
  - WAKE is the same pin as PS0. **The module needs PS1 jumpered high.**
  - C22 (0.1 µF) is the only decoupling it needs.
- **Encoders.** R19–R22 (10 k) pull the outputs up, for open-drain Hall sensors.
- **Pololu cable risk.** A non-Pololu motor plugged into J8/J9 with a 1:1 cable
  can put motor voltage on its encoder.

## PCB

**Coordinates.** KiCad = board + (100, 60). The board origin is the front-left
corner, with +Y toward the rear. The rotation centre is board (33, 66), which is
KiCad (133, 126). Mechanical reservations are in `layout/README.md`.

### Stackup and zones

JLC04161H-7628, 1.6 mm, with ~0.2 mm prepreg between L1 and L2. Outer copper is
1 oz. The AP63203 datasheet asks for 2 oz, but at its full 2 A; this rail draws
~0.7 A.

| Layer | Use |
|---|---|
| F.Cu | Components, the USB pair, the SW island and the driver loops. Zone `GND pour motor region`, x 104.2–123.2, y 104.6–120.2 |
| In1.Cu | **Solid GND plane. Never split it, cut it or route through it.** |
| In2.Cu | `ESP_3V3` pour, plus a `VBAT` island (priority 1) at x 100.5–127, y 88–122 |
| B.Cu | Secondary routing, plus a GND pour stitched to In1 |

- All zones use solid pad connections, with island removal on.
- **Noise is controlled by placement, not plane splits.** The motor drivers,
  bulk capacitors, D6, F1/Q1 and the battery entry share the left corner. U1,
  the ADC nodes and I²C stay away from it.
- The antenna overhangs the rear edge. A board-level all-layer copper keep-out
  covers it.
- The `IMU module and bracket reservation` keepout (x 120.5–145.5,
  y 113.5–138.5) forbids footprints. Tracks and vias are allowed.

### Rules (`Pixy-M2.kicad_pro`, `Pixy-M2.kicad_dru`)

**Netclasses:**

| Class | Width | Nets |
|---|---|---|
| Default | 0.2 | everything else |
| Battery | 1.0 | `/VBAT_RAW`, `/VBAT_FUSED` |
| Motor | 0.8 | `/MOT_*` |
| Power | 0.6 | `/VBUS`, `/VSYS`, `Net-(F2-Pad1)` |
| USB | 0.25 | `/USB_D*`, `Net-(J1-D*` |

`/VBAT` is deliberately in no class. Its current runs in the In2 island, and its
tracks are only pad-to-plane stubs.

**Custom rules, in file order:**

| Rule | Constraint |
|---|---|
| Signal minimum width | ≥ 0.2 mm, except inside the `Motor pin escape` areas |
| Motor trunk minimum width | ≥ 0.6 mm outside `Motor pin escape` |
| Via drill to solder pad | 0.10 mm |
| Filled capped driver thermal vias | the exception for U4/U5's in-pad vias |
| USB line width | 0.24–0.26 mm |
| USB lines stay on F.Cu | no USB track or via on B.Cu |
| USB pair coupling | gap 0.14–0.16 mm, ≤ 4 mm uncoupled |
| Power path width | ≥ 0.5 mm, except inside `Power pin escape` |
| Battery path width | ≥ 0.8 mm |
| REG_EN clear of the switch node | ≥ 0.9 mm from SW and BST |
| Sense nodes clear of motor and switch copper | 5 mm: `REG_EN` to motor copper; `VBAT_SENSE` to motor, SW and BST copper |
| IPROPI clear of motor outputs | ≥ 0.75 mm |
| Hole clearance | 0.30 mm, except J1's own pads against J1's own NPTH holes (JLCPCB allows 0.20) |

**KiCad behaviours these rules depend on:**

- **Board-setup minimums are absolute**, and custom rules cannot relax them.
  Track width therefore stays at 0.15 mm and hole clearance at 0.20 mm in board
  setup, and the higher floors are custom rules.
- **When two rules set the same constraint, the later one wins.** "Signal minimum
  width" must stay the **first** rule. Moved lower, it relaxes the motor, USB,
  power and battery rules to 0.2 mm.
- **Use `enclosedByArea`, never `intersectsArea`.**
  - With `intersectsArea`, a track that merely starts inside the area is exempt
    along its whole length.
  - `enclosedByArea` tests the whole outline, round caps included, so a segment
    ending exactly on the area edge is *not* enclosed.
- **KiCad pairs nets by a trailing ±.** So `Net-(J1-D±…)` gets the USB width
  and layer rules but not the coupling rule.
- **DRC with a large threshold reports the first violating pair, not the
  closest.** To measure a clearance, descend through several thresholds
  (`layout/issue8-rules/clearmin.py`).
- **Test every new rule by breaking a copy of the board** and confirming that
  DRC fires. Every existing rule was verified this way.

### Layout pipeline

- **The board is generated.** `tools/autoroute/rework.py` rebuilds
  `Pixy-M2.kicad_pcb` from `tools/autoroute/base-routed.kicad_pcb` through a
  fixed sequence of stages (listed in `tools/autoroute/README.md`).
  - It **discards hand edits** to the board.
  - It writes zones unfilled, so always follow it with the DRC command above.
  - A run takes minutes; run it in the background. Do not watch it with
    `pgrep -f "python3 rework.py"`: the pattern matches the watching shell and
    the loop never exits.
- **New layout work is a new stage script.**
  - Assert the old geometry it replaces, and let it also convert an existing
    board standalone.
  - Hook it into `rework.py` in order, and document it in
    `tools/autoroute/README.md`.
  - Put the evidence in `layout/<topic>/README.md`.
  - Confirm that a full replay reproduces the board.
- **Expected messages, not failures:**
  - `! no neck+via for GND from (109.0,114.8)` and the same for (117.0,114.8);
  - `! no stitch via for GND near …` for J8.1, J8's west MP pad and J9.1.
- **`pcbedit` traps:**
  - A footprint or text edit re-splits the file and drops pending track and via
    edits. Do moves first, or call `sync()`.
  - Rotating a footprint must turn every `(at …)` inside it, pads and texts
    included. A missed one shows up as `lib_footprint_mismatch`, which reads like
    a library problem rather than a bad edit.
- **Router traps:**
  - `Router.route_waypoints` can leave consecutive legs on different layers with
    no via between them. Pin waypoints to one layer.
  - `G.smd_block` keeps via centres only 0.15 mm off pads. Rebuild it at drill
    radius + 0.10 mm.
  - Lay tracks before stitching vias. A stitching via dropped first once shorted
    SW to GND.
  - Stitch fine-pitch parts after their signals.
- **In tight spots, hand-placed copper beats A\*.** The buck, the USB pair,
  REG_EN and IPROPI are all hand-placed, because A* failed or wandered on each.
- **New vias** go ≥ 1.35 mm from any other non-plane via, so their antipads do
  not merge into one void in In1/In2.
- **No ordinary via drill within 0.10 mm of any mask or paste opening.**
  `via_openings.py` checks this. The only exceptions are the four thermal vias.

### Placement and routing invariants — do not undo

- **USB.**
  - **U2 sits at (153.5, 149.5), rot 90.** Its flow-through pins face J1 and U1.
    Do not rotate it back without re-routing the pair.
  - The pair is 0.25 / 0.15 mm on F.Cu, J1 → U2 → U1, with no vias.
  - The 1.04 mm skew is geometric. **Do not add a serpentine.**
  - `tools/impedance/zdiff.py` solves it at 88–94 Ω. That is a calculation,
    not a fab figure.
  - CC1/CC2 cross under the pair on B.Cu.
- **Buck.**
  - **C17 straddles U3.3 (IN) and U3.4 (GND)** under the package.
  - The SW node is 3.57 mm² of F.Cu with **no vias**.
  - **L1's courtyard is 0.45 mm from U3's.** That is why C6 sits above the
    package. Do not move L1 east.
  - TP4 is a single 3.2 mm top-layer stub. If the island ever grows marginal,
    drop TP4. TP3 (GND) is 4.4 mm away.
  - `/VSYS` is pinned by a waypoint to the corridor north of the buck.
  - U3.4, C7, C11 and C17 each have their own GND via.
- **FB.** A dedicated via-free top-layer trace runs U3.1 → C11.1 (26.3 mm),
  round the outside of R8/C13. Its closest approach is TP4, at 1.35 mm.
  **Never put a via on FB**: it would bond to the In2 3V3 pour beside U3.
- **REG_EN.**
  - C13 (136.18, 97.0) and R8 (134.47, 97.175) sit beside U3.2, and
    EN → C13.1 → R8.1 is one top-layer run.
  - The long leg to R7/R9 crosses under FB on B.Cu.
  - Nothing of REG_EN's runs under U3. Its closest approach, 0.95 mm, is U3's
    own EN-to-SW pin gap.
- **IPROPI.**
  - R17 sits at (104.5, 120.3), west of U4's IN escapes. R18 sits at
    (118.5, 118.6), east of U5's pair. **Keep them on those sides.**
  - GPIO2 stays ≥ 1.30 mm and GPIO10 ≥ 0.80 mm from motor copper; GPIO10's
    limit is its escape via.
- **Motor copper.**
  - 0.8 mm trunks. The only narrower copper is in the `Motor pin escape` areas.
  - M1/M2 route as pairs. `tools/autoroute/loop.py` measures the loop areas:
    A 23.9 mm², B 9.8 mm².
  - **Do not move U5 toward J9.** It would be off the VBAT island (x ≤ 127),
    into the buck output, and it would split the motor region.
- **Driver exposed pads.**
  - Two in-pad 0.45/0.25 mm vias per pad. The hole-to-hole rule allows no more
    in a 0.9 × 1.6 mm pad.
  - All four are **filled and capped (IPC-4761 type VII)**. The note on
    `Dwgs.User` says so, and the fab order must include it; tenting is no
    substitute.
  - Each pad also has a 0.8 mm neck up to a further via, four GND vias within
    3 mm and the F.Cu pour.
  - There is no neck out of the lower end: the VREF feed blocks it.
- **Bypass loops.**
  - C18/C20 sit 1.33 mm from VM, across pins 5/7, with the loop closed in top
    copper. The 0.5 mm pin pitch caps those runs at 0.3–0.35 mm.
  - C21 is at (119.3, 109.4), rot 90.
- **Battery input.**
  - F1 is at (110.2, 100.7) and BT1 at (105, 93.6). Keep unfused copper short.
  - U4's VREF feed, a B.Cu run to J8.4's stitch via, is the only 3V3 path under
    the VBAT island.
- **Connectors.**
  - J8 is at (110, 125.5), rot 180; J9 at (160, 103.4), rot 90. Each cable exits
    toward its motor.
  - **J9's x** is the eastmost that clears the 0.6 mm `/VBUS` run.
- **Battery bay.**
  - The pack lies across the underside, between the motors: board
    X 0.5–62.5, Y 57.5–74.5.
  - Each motor's 4 mm encoder allowance faces outboard, and brackets fasten on
    the outboard side only. Hook-and-loop tape holds the pack.
  - The front strip was rejected: the pack there moves the CG ahead of the
    front axle.
  - The lead to BT1 is about 13 cm, so plan an XT30 extension. Do not move BT1
    to the pack's end: that would drag unfused copper out of the motor corner.
- **Silkscreen.** `assembly_marks.py` and `battery_bay.py` print the ToF mounts,
  the IMU outline, the motors and the battery. Test points, spare GPIOs,
  `BAT ON/OFF` and `PS1 HIGH = SPI` are labelled.

### Still checked by eye (DRC cannot see these)

- C14 hard against U1.39, with R10/R11 behind it.
- C15 among J4–J7, and C16 against the connector furthest from C15.
- D4/D5 visible past the mechanics.
- J11 and TP5–TP9 reachable by hand and probe.
- The J10 cable not run alongside the motor outputs.
