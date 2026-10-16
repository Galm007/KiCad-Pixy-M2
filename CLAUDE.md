# Pixy-M2 — Micromouse Controller PCB

Context for a Claude Code session working on this KiCad project via the KiCad MCP server.

Single-board micromouse controller, KiCad 10. **Branch `devkit-daughterboard`:**
U1 is an ESP32-S3-DevKitC-1-N8R8 that plugs into two 1×22 SMD female headers.
The board also carries two DRV8231A motor drivers, a 2S LiPo power path (fuse,
P-FET switch, TVS, UVLO) and an AP63203 3.3 V buck. USB, BOOT/RESET and the
USB-UART bridge are on the devkit. JST-SH connectors lead to off-board parts:
four VL53L0X ToF sensors, a BNO085 IMU and two Pololu N20 gearmotors with
encoders.

**Where things live.** This file holds the working rules: invariants, "do not"
items and checks. Other sources:

- `README.md`: design rationale, pin and connector tables, firmware bring-up notes.
- `BOM.md`: parts.
- `tools/autoroute/README.md`: the layout pipeline.
- `tools/schematic/README.md`: the sheet re-layout tooling.
- `layout/*/README.md`: per-fix measurements and evidence.
- The git history of this file: the full issue-by-issue narrative (pruned 2026-09-24).

## Status (2026-10-15, branch `devkit-daughterboard`)

- **Schematic complete.** `Pixy-M2.kicad_sch`, a single flat A3 sheet with 13
  dashed, titled block frames. Keep new parts inside their block's frame.
  72 nets, 79 parts. ERC 0/0. `tools/schematic/power_integrity.py` adds the
  independent motor cutoff, the driver reference and USB isolation.
- **PCB placed and fully routed.** 66 × 100 mm, 4 layers, 233 vias. DRC gives 0
  violations, 0 unconnected and 0 parity issues. The aperture audit passes.
  `tools/autoroute/devkit.py` (rework stage 20) made the devkit change; evidence
  in `layout/devkit/README.md`. Stage 21 (`power_integrity.py`) adds the motor
  inhibit, reference and supply isolation; evidence in
  `layout/power-integrity/README.md`. Stage 22 (`octilinear.py`) straightens
  the router's staircases into 0/45/90° runs; evidence in
  `layout/octilinear/README.md`.
- **Open:**
  - **Mechanical design.** There are no mounting holes, drivetrain or brackets
    yet.
  - **Motor gear ratio.** 12 CPR before gearing is low, so check the ratio gives
    enough encoder edges for the control loop.
  - **Hardware measurements.** F1 and U4/U5 temperatures under hard acceleration
    and stall. IPROPI readings and the 0.828 A nominal limit under PWM.
    The independent cutoff (trip, release, filter delay), ESP_3V3 at USB
    unplug under load (C30's ride-through), and the devkit LDO's temperature.
  - **Socket part number.** The land pattern is Harwin M20-786 (KiCad's
    `PinSocket_1x22_P2.54mm_Vertical_SMD_Pin1Left`); no 22-way M20-786 part
    number was confirmed. Two 11-way strips per row fit the same pads.
  - **Antenna performance** with the devkit, mechanics and battery fitted.
  - **IMU off the rotation centre.** Its chip is 8.6 mm left of and 7.5 mm
    behind it: the only 25 mm column left beside the devkit. Fine for the gyro;
    the accelerometer sees centripetal acceleration in turns.
  - **Silkscreen gaps.** No text yet for "pin 1 = VCC" at J4–J7.
  - **The 3D view has no DevKitC model.** The footprint stands Espressif's
    WROOM-1 model at the module's real height (11.6 mm) with no devkit PCB,
    headers or USB ports under it, so it floats above the sockets in renders.
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
  net has somewhere else to go. Keep `VBAT` and `VSYS` as explicit labels.
- Symbol fields inherit the symbol's rotation. On a 90°-rotated symbol:
  - give the field its own 90° angle so it renders horizontally;
  - write `justify right` to get left-justified text. `justify left` renders
    right-justified, so the text grows into the symbol.
- **Renders** (`docs/images/`):
  - `pcb-3d-top.png`, `pcb-3d-bottom.png`:
    `kicad-cli pcb render --side top|bottom -w 1408 -h 2024 --background opaque --quality high`.
  - `pcb-3d-iso.png`:
    `kicad-cli pcb render --perspective --rotate '-50,0,-30' --zoom 0.95 --pan '0,1,0' -w 1320 -h 1088 --background opaque --quality high`.
  - `pcb-copper-top.png`:
    `kicad-cli pcb export svg --mode-single --page-size-mode 2 --exclude-drawing-sheet --layers F.Cu,Edge.Cuts`,
    then `rsvg-convert -w 1000 -b white`.
  - `schematic.png`: `kicad-cli sch export svg --exclude-drawing-sheet` (colour),
    then `rsvg-convert -w 3200`.

### Library edits that "Update from library" silently reverts

- **U4/U5, `Driver_Motor:DRV8231ADSG`.** The cached symbol has OUT2 (pin 8)
  retyped from `power_in` to `output`, fixing a stock-library bug. Never run
  "Update Symbols from Library" on them. If two `power_pin_not_driven` errors
  appear on the motor nets, re-apply the fix. Do not add PWR_FLAGs.
  `#FLG04` on `VBAT` is legitimate: ERC cannot see a source through BT1 → F1 → Q1.
- **U1** is the symbol `PCM_Espressif:ESP32-S3-DevKitC` on the footprint
  `Pixy-M2:ESP32-S3-DevKitC-1_SMD_Sockets` (project library `Pixy-M2.pretty`,
  registered in `fp-lib-table`). `tools/autoroute/devkit_footprint.py` writes
  the footprint: regenerate it rather than editing it by hand.
  - Never update U1's footprint back to `PCM_Espressif:ESP32-S3-DevKitC`: that is
    a through-hole footprint, and its tails would stand into the underside
    battery bay and motor B.
  - The cached *symbol* names `PCM_Espressif:ESP32-S3-DevKitC` as its default
    footprint, deliberately. Editing the cache raises `lib_symbol_mismatch`.
  - `Pixy-M2:ESP32-S3-WROOM-1_AntennaOverhang` is unused on this branch.
- **Q1** borrows `Transistor_FET:IRF7404` for its SO-8 pin map. The fitted part is
  **AO4407A**. Never order IRF7404.
- `USB_C_Receptacle_Amazon.kicad_mod` in the repo root is unused. There is no
  USB connector on this branch's board.

## Verified correct — do not re-flag

Each was checked against the extracted netlist. A review that "finds" one of these is wrong.

- **Buck.** AP63203WU is the fixed-3.3 V variant. FB (U3.1) senses `BUCK_3V3`
  directly, with no divider. C6 (BST cap) sits across U3.6/U3.5. EN (U3.2) is on
  `REG_EN`, not tied to IN; `VSYS` is C12, C17, D2.K and U3.3.
- **Input capacitance.** One C12 (22 µF 25 V 1206) meets the datasheet's 10 µF
  *effective* input. It keeps ~11–13 µF at 8.4 V bias. The datasheet's 2 × 22 µF
  is the *output*, which C7 ‖ C11 match. C17 (0.1 µF) is the HF bypass.
- **No USB on the main board.** The devkit's own ports (USB-UART and native
  USB, each behind a 1N5819 to its 5 V rail) replace J1, U2, F2 and the CC and
  shield parts. Do not re-add a USB-C connector wired to GPIO19/20: the
  devkit's native-USB port is already on them.
- **Devkit pins.** All 44 are accounted for. 12 carry no-connect flags:
  CHIP_PU (U1.3), GPIO0 (U1.31), GPIO19/20 (U1.25/26),
  GPIO43/44 (U1.43/42), GPIO35–38 (U1.32–35) and GPIO45/46 (U1.30/14).
  - The devkit uses them itself: its BOOT and RESET buttons, its USB ports,
    its USB-UART bridge, the N8R8's octal PSRAM (GPIO35–37) and the v1.1
    board's RGB LED (GPIO38).
  - GPIO45/46 are strapping pins. GPIO45 high at reset sets the flash rail to
    1.8 V, and the board will not boot. GPIO46 high with GPIO0 low is an
    invalid combination. External pulldowns were rejected: the internal ~45 k
    suffices.
  - In layout the no-connect pads are floating pads. Give them no trace, test
    point or pour island.
- **18 no-connect flags, all deliberate:** the 12 on U1, J4.5–J7.5 (the ToF
  interrupt pins), SW3.1 and U8.4. U1.21 senses DEVKIT_5V only.
- **D2 feeds only `VSYS`.** Motor current on `VBAT` never passes through it. D2
  dissipates ~140 mW worst case, so an ideal-diode controller is unnecessary. Do
  not re-propose it unless a real load moves onto `VSYS`.
- **The DRV8231A thermal pad (pin 9) is on GND.** It sits at the same symbol
  coordinate as pin 7, and the netlist confirms it.
- **Boot and reset** are the devkit's own BOOT and RESET buttons and CHIP_PU RC.
- **No JTAG or UART header.** The devkit's native-USB port (USB-Serial-JTAG)
  and its USB-UART port provide flashing, console and debug.

## Power path

```
 BT1+ ─ F1 ─ VBAT_FUSED ─ Q1 (S→D) ─ VBAT ─┬─ D2 ─ VSYS ─ U3 buck ─ BUCK_3V3 ─ U8/Q2 ─ ESP_3V3 ─ U1 3V3 pins
               R14 ─ G ─ SW3 (gate only)    ├─ U4/U5 VM, C18–C21                   │
                                            ├─ R7/R8 UVLO, R10/R11 sense, TP1      │
                                            └─ D6 TVS → GND       devkit USB ─ 1N5819 ─ SGM2212 LDO (USB priority)
```

- **The devkit's 3V3 pins are an input here**, which Espressif's user guide lists
  as a supported supply ("3V3 and G pins"). Its 5V pin is used only for USB-priority voltage sensing.
- **USB has priority**, sensed from U1.21 through R28/R29 into U8 CE. U8
  (LM66100) and Q2 (AO3401A, source BUCK_PASS/drain ESP_3V3) have opposing
  body diodes. Q3 follows U8 ST, so a disabled U8 also opens Q2. Never remove
  Q2: the LM66100 alone still conducts through its forward body diode.
- **BUCK_3V3 is separate from ESP_3V3.** U3.1, L1.2 and C7/C11 stay together
  upstream of U8. Do not connect them to the In2 ESP_3V3 pour. The feedback
  trace keeps its original geometry and no vias.
- **USB with the pack off** powers logic from the devkit LDO, with the buck
  isolated. U6/U7 inhibit both motors regardless of USB or firmware. USB LDO
  thermals and rail dropout require hardware qualification. Begin USB bench
  work with RF off.
- **USB unplug with the pack on** leaves ESP_3V3 unfed for U8's turn-on
  (~40 µs typical, no datasheet maximum). C30 (100 µF X5R 1206, ~45 µF at
  3.3 V) with C1/C15 carries it: about 0.42 V sag at 0.5 A, 0.2 V at 0.25 A,
  not counting the devkit's own capacitance. Scope ESP_3V3 at unplug under load.

- **F1: Littelfuse `0885005.DR`** (`Device:Fuse`, `Fuse:Fuse_Littelfuse-NANO2-885`).
  5 A fast-acting, breaks 1500 A at 125 VDC, one-time.
  - Why: the pack (OVONIC 2S 450 mAh 100C) could short at an estimated 200–400 A.
    The old PPTC (40 A) and NANO2 451/453 (300–400 A) were rejected for that.
  - The old ~2.4 A normal-load allowance is conservative after lowering ITRIP.
    Measure PWM peaks; do not increase F1 to compensate for nuisance blowing.
  - **If F1 nuisance-blows, do not fit a bigger fuse.** Lower ITRIP or tighten
    the firmware duty cap first.
- **Q1: AO4407A.**
  - Pins: source 1–3 on `VBAT_FUSED`, drain 5–8 on `VBAT`, gate 4.
  - R14 (100 k, G–S) defaults it OFF. SW3 switches only the gate. Give all seven
    S/D pads adequate copper.
  - Both dividers and D6 sit downstream of it, so OFF leaves only Q1's leakage on
    the pack. That is low, not zero.
  - Its body diode means it is **not** reverse-polarity protection.
  - SW3 OFF leaves `VBAT` at only Q1's leakage. USB no longer back-feeds the buck output. U6/U7 and the drivers'
    pulldowns keep the motors disabled.
- **D6: SMBJ9.0A** (Vishay, SMB). It clamps `VBAT` at up to **15.4 V**. Every
  part on `VBAT` or `VSYS` must survive that:
  - DRV8231A: 35 V.
  - C19/C21: 25 V.
  - D2 (onsemi **MBRA340T3G**, SMA): 40 V. Beware "SS34": Vishay's SS34 is
    SMC, not SMA.
  - DRV8833 (11.8 V) and TB6612FNG (15 V) are rejected for this reason.
- **UVLO.** R7 120 k (from `VBAT`) and R8 24 k to GND, plus C13, on U3's EN
  comparator. It has built-in switched hysteresis.
  - Thresholds: on at 6.90 V, off at 5.94 V (3.45 / 2.97 V/cell).
  - **R7/R8 must be 1 %**, and the Value field says so.
  - EN is rated to 35 V abs max, so no clamp.
  - **USB does not reach EN.** This UVLO disables only the buck. U6/U7
    provide the independent motor cutoff even when USB powers the ESP32.
  - **Never feed the devkit's 5V pin back into VSYS or REG_EN.** With USB
    absent, the 3V3 rail back-feeds the devkit's LDO through its body diode to
    ~2.9 V on that pin. Through an R9-style path that would hold EN above its
    threshold down to a ~3 V pack.
- **Motor cutoff (U6/U7).** U6 (TLV3012B) compares VBAT through R24/R25, with
  R26 hysteresis from its output, against its 1.242 V reference; below the
  threshold U7 opens GPIO39–42 from the drivers and their pulldowns coast both
  motors.
  - Nominal: coast at **6.35 V**, enable at **6.75 V** (3.17 / 3.37 V/cell).
    R24/R25/R26 = 100 k / 23.2 k / 825 k, **0.1 %, ≤25 ppm/°C** (Yageo
    RT0805BRD07100KL / 0723K2L / 07825KL). C27 filters the node (~1.8 ms).
  - DC envelopes over −40…125 °C: coast 6.01–6.74 V, enable 6.39–7.08 V
    (`tools/power_integrity_check.py`). A pack resting at 3.6 V/cell always
    enables.
  - It is a **backstop under firmware's cutoff**: firmware stops at about
    6.8 V under load and latches the stop, so pack rebound cannot restart a
    stalled motor.
  - Below VM 6.5 V the DRV8231A's current mirror still regulates; TI only
    specifies its ±6 % at VM ≥ 6.5 V. The 2026-10-14 thresholds (6.92 / 7.39 V)
    kept VM inside that condition at the cost of the bottom third of the pack
    and were lowered on 2026-10-15.
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
- **LEDs.**
  - **D4 (power) is a high-efficiency red LED on 10 k**, about 150 µA. Do not
    substitute blue, white or pure green: they would not light. The devkit's
    own red power LED (5.1 k on 3V3, ~0.3 mA) now dominates deep-sleep current.
  - **D5 (status) is green**, on GPIO3 → R13 2.2 k → anode. It is active-high,
    which keeps the strapping pin low at reset.
- **U1 is a DevKitC-1-N8R8 (v1.1).** Its octal PSRAM takes GPIO35–37, and its
  RGB LED takes GPIO38 (through 0 Ω R17 on the devkit). A v1.0 devkit puts the
  LED on GPIO48 instead (encoder A OUT B): remove that LED's feed resistor or
  use v1.1. An `R8V`/`R16V` variant runs GPIO47/48 at 1.8 V and must not be
  fitted.

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
- **Current limit.** U6 TLV3012B supplies `MOTOR_VREF` = 1.242 V, and R17/R18
  are **1 kΩ 1 %, ≤100 ppm/°C** (RC0805FR-071KL).
  - ITRIP = 1.242 / (1500 µA/A × 1 kΩ) = **0.828 A nominal**. IPROPI reads
    **1.5 V/A** on GPIO2/GPIO10 (ADC1), about 1.242 V at nominal trip.
  - The 1 A contact/cable rating requires margin. The audit checks reference,
    resistor and temperature corners against TI's specified gain at 1 A and
    VM ≥6.5 V. It does not guarantee every PWM peak; measure ripple and stalls.
  - U7 SN74LV4066A disconnects all four inputs while MOTOR_OK is low. The
    drivers' own 100 k pulldowns then command coast; keep those input escapes.
  - **VREF decoupling.** `MOTOR_VREF` runs ~74 mm from U6 (rear of the socket
    rows) to the drivers, past motor copper in the corner. C25 (2.2 nF) sits at
    U6 and C28 (4.7 nF) where the feed splits to U4.4 and U5.4. Together they
    stay under the TLV3012B REF's 10 nF stability limit: never enlarge either
    without checking the sum.
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
| 0 | devkit BOOT button (NC here) | 19 / 20 | devkit USB D− / D+ (NC here) |
| 1 | `VBAT_SENSE` (ADC1_CH0) | 21 / 18 | encoder B OUT A / OUT B (J9.3 / J9.2) |
| 2 / 10 | IPROPI motor A / B (ADC1) | 39 / 40 | motor A IN1 / IN2 |
| 3 | status LED D5 | 41 / 42 | motor B IN1 / IN2 |
| 4–7 | XSHUT J4–J7 | 43 / 44 | devkit USB-UART (NC here) |
| 8 / 9 | I²C SDA / SCL, R15/R16 2.2 k | 45, 46 | no-connect (strapping) |
| 11–17 | IMU MOSI, SCK, MISO, CS, INT, RST, WAKE | 47 / 48 | encoder A OUT A / OUT B (J8.3 / J8.2) |
| 35–37, 38 | N8R8 octal PSRAM, v1.1 RGB LED (NC here) | | |

All usable GPIOs are allocated; none is spare. GPIO11/12/13 are the native FSPI
D/CLK/Q pins.

| Conn | Part | Pins |
|---|---|---|
| J4–J7 | SM06B-SRSS-TB, GY-VL53L0XV2 order | **1 VCC (3V3)**, 2 GND, 3 SCL, 4 SDA, 5 INT (NC), 6 XSHUT. J4 FL/GPIO4, J5 FR/GPIO5, J6 look-left/GPIO6, J7 look-right/GPIO7 |
| J8, J9 | SM06B-SRSS-TB, Pololu encoder order | 1 GND, 2 OUT B, 3 OUT A, 4 VCC (3V3), 5 M2, 6 M1, MP GND |
| J10 | SM09B-SRSS-TB | 1 VIN, 2 GND, 3 SCK, 4 MOSI, 5 MISO, 6 CS, 7 INT, 8 RST, 9 WAKE/PS0, MP GND |
| U1 | 2 × 1×22 2.54 mm SMD female header | the DevKitC-1, USB ports toward the front (silkscreen arrow between the rows). Turned round, it puts 3V3 on GND pins |
| TP1–TP4, TP9–TP11 | 1.5 mm pads | VBAT, 3V3, GND, SW, GND, MOTOR_OK, MOTOR_VREF. BUCK_3V3 is probed at L1.2 or C26, both in front of the devkit |

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
| F.Cu | Components, the SW island and the driver loops. Zone `GND pour motor region`, x 104.2–123.2, y 104.6–120.2 |
| In1.Cu | **Solid GND plane. Never split it, cut it or route through it.** |
| In2.Cu | `ESP_3V3` pour, plus a `VBAT` island (priority 1) at x 100.5–127, y 88–122 |
| B.Cu | Secondary routing, plus a GND pour stitched to In1 |

- All zones use solid pad connections, with island removal on.
- **Noise is controlled by placement, not plane splits.** The motor drivers,
  bulk capacitors, D6, F1/Q1 and the battery entry share the left corner. U1,
  the ADC nodes and I²C stay away from it.
- The devkit's antenna overhangs the rear edge by ~6.5 mm, about 10 mm above
  the board. The devkit's own PCB ends 0.75 mm inside the board edge. A
  board-level all-layer copper keep-out covers x 143.5–159.5, y ≥ 158.8.
- The `IMU module and bracket reservation` keepout (x 112.1–136.7,
  y 121–146) forbids footprints. Tracks and vias are allowed.
- **B.Cu GND pour stitching.** Long B.Cu signal runs cut the pour into pieces,
  and island removal drops any piece with no GND via. Rework stage 20 finishes
  with `stitch_islands`: one GND via, at the legal spot deepest inside, in each
  piece of 2 mm² or more that has none.

### Rules (`Pixy-M2.kicad_pro`, `Pixy-M2.kicad_dru`)

**Netclasses:**

| Class | Width | Nets |
|---|---|---|
| Default | 0.2 | everything else |
| Battery | 1.0 | `/VBAT_RAW`, `/VBAT_FUSED` |
| Motor | 0.8 | `/MOT_*` |
| Power | 0.6 | `/VSYS` |

`/VBAT` is deliberately in no class. Its current runs in the In2 island, and its
tracks are only pad-to-plane stubs.

**Custom rules, in file order:**

| Rule | Constraint |
|---|---|
| Signal minimum width | ≥ 0.2 mm, except inside the `Motor pin escape` areas |
| Motor trunk minimum width | ≥ 0.6 mm outside `Motor pin escape` |
| Via drill to solder pad | 0.10 mm |
| Filled capped driver thermal vias | the exception for U4/U5's in-pad vias |
| Power path width | ≥ 0.5 mm |
| Battery path width | ≥ 0.8 mm |
| REG_EN clear of the switch node | ≥ 0.9 mm from SW and BST |
| Sense nodes clear of motor and switch copper | 5 mm: `REG_EN` to motor copper; `VBAT_SENSE` to motor, SW and BST copper |
| Motor UVLO clear of switching copper | MOTOR_UVLO ≥ 5 mm from motor, SW and BST copper |
| SPI clear of motor and switch copper | GPIO11–17 ≥ 5 mm from motor, SW and BST copper (closest: GPIO14, 10.0 mm) |
| Encoders clear of the switch node | GPIO18/21/47/48 ≥ 5 mm from SW and BST copper (closest: GPIO21, 9.7 mm) |
| I2C clear of the switch node | GPIO8/9 ≥ 3 mm from SW and BST copper (closest: SCL to BST, 4.4 mm) |
| IPROPI clear of motor outputs | ≥ 0.75 mm |
| Hole clearance | 0.30 mm everywhere (the board-setup floor stays at JLCPCB's 0.20 mm) |

**KiCad behaviours these rules depend on:**

- **Board-setup minimums are absolute**, and custom rules cannot relax them.
  Track width therefore stays at 0.15 mm and hole clearance at 0.20 mm in board
  setup, and the higher floors are custom rules.
- **When two rules set the same constraint, the later one wins.** "Signal minimum
  width" must stay the **first** rule. Moved lower, it relaxes the motor,
  power and battery rules to 0.2 mm.
- **Use `enclosedByArea`, never `intersectsArea`.**
  - With `intersectsArea`, a track that merely starts inside the area is exempt
    along its whole length.
  - `enclosedByArea` tests the whole outline, round caps included, so a segment
    ending exactly on the area edge is *not* enclosed.
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
  - Hook it into `rework.py` in order, before stage 22 (`octilinear.py`) if
    it lays copper, and document it in `tools/autoroute/README.md`.
  - Put the evidence in `layout/<topic>/README.md`.
  - Confirm that a full replay reproduces the board.
- **Expected messages, not failures:**
  - `! no neck+via for GND from (109.0,114.8)` and the same for (117.0,114.8);
  - `! no stitch via for GND near …` for J8.1, J8's west MP pad and J9.1
    (stage 13, before the devkit stage moves J8/J9 and re-taps them);
  - `(waypoint … skipped)` and `(M1 waypoint … skipped)` lines;
  - `no clear silkscreen position, hidden on F.SilkS: R28, R29` (stage 21: the
    front cluster has no room left for two more 1 mm designators; F.Fab
    still names them).
- **Stage 21 (`power_integrity.py`) traps:**
  - Any re-routable net (`devkit.FULL`, and GPIO2/GPIO10 outside the motor
    corner) that a new part or cluster displaces is **ripped whole and routed
    again**. Ripping only the conflicting pieces once made A* patch the loose
    ends around the new parts: SPI ran along motor B's trunk and GPIO21 past
    the switch node.
  - Keep the clusters out of the existing corridors: the SPI diagonal between
    the socket rows, GPIO21's run south of motor B's trunk, and the I²C and
    XSHUT runs along the right row.
  - SCL and SDA are always ripped and routed again, with a 3 mm router floor
    from SW/BST. SCL's lane past the buck runs under C15, between C15 and C12.
  - `silk_refs.py` places the designators before any copper; it needs the
    board's measured text extents (0.9 mm a character at 1 mm) to agree with
    DRC.
- **Stage 20 (`devkit.py`) traps:**
  - It reads only routed copper; every hand edit to the board is discarded with
    the rest of the replay.
  - Do every text-level edit (footprints, fields, texts, zones) before the
    first track edit. One `drop_text` after the rip once threw the rip away
    silently.
  - A regex with nested repetition and `re.S` across the 2 MB board text
    backtracks for good. Locate items by uuid and `rindex` instead.
  - `pkill -f`/`pgrep -f` with a pattern from your own command line kills or
    matches the calling shell. Use a bracket, e.g. `pgrep -f "devki[t].py"`.
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
  - A* turns for free on its 0.05 mm grid, so any angle other than 0/45/90
    comes out as a staircase of 0.05–0.3 mm steps that renders as a curve.
- **Traces are straight 0/45/90° runs with 45° turns.** The user rejected the
  router's curvy staircases on sight. Stage 22 (`octilinear.py`) straightens
  every chain it may touch. It must stay the last copper stage: a stage added
  after it brings the staircases back. Before reporting layout work done, look
  at the copper, not only the DRC counts.
  - It joins pieces that meet only by overlapping (`_heal`) before cutting
    chains. Without that, most motor and signal runs had loose ends and stayed
    frozen.
  - It never moves the buck block (SW, BST, REG_EN, chains on U3, L1, C6, R8,
    C13) or the piece on each U4/U5 pin. Necks below the class minimum move
    only inside their `Motor pin escape` area.
- **In tight spots, hand-placed copper beats A\*.** The buck, REG_EN and
  IPROPI near the drivers are all hand-placed, because A* failed or wandered on
  each. Stage 20 re-routes the IPROPI runs only beyond the motor corner.
- **New vias** go ≥ 1.35 mm from any other non-plane via, so their antipads do
  not merge into one void in In1/In2.
- **No ordinary via drill within 0.10 mm of any mask or paste opening.**
  `via_openings.py` checks this. The only exceptions are the four thermal vias.

### Placement and routing invariants — do not undo

- **Devkit (U1).**
  - **At (162.7, 157.98), rot 180**: pad 1 (3V3) at the rear right, socket rows
    at x 139.84 and 162.7. Pad 1 clears the R3 corner by 0.27 mm. The antenna
    end is to the rear, and the USB ports face the front at y ≈ 96.5.
  - **SMD sockets, not through-hole.** U1's area lies over the underside
    battery bay and motor B.
  - **The courtyard is the two socket bodies only.** The devkit stands ~10 mm up
    (7.5 mm socket + 2.5 mm header spacer). Parts under it must stay below
    ~8 mm, and nothing under it is reachable once it is fitted. TP4 sits under
    its USB end; C1/C2, R15/R16, R19–R23 and the motor-cutoff cluster sit
    between the rows.
  - **It fits nowhere else** at 25.4 × 62.7 mm. The left corner is the motor
    and power region, and the middle is too narrow beside the IMU.
- **Power-integrity clusters** (stage 21; part data in
  `tools/power_integrity_data.py`).
  - **Front, in front of the devkit's USB end:** U8, Q2, Q3, R28–R31, C26.
    BUCK_3V3 goes straight from L1.2 into U8 VIN (0.4 mm, no via), U8 VOUT to
    Q2's source is 1.4 mm, the gate drive stays within the cluster. Motor B's
    trunk (MOT_B_1 on B.Cu, MOT_B_2 on F.Cu, stacked) walls this area off from
    the socket rows, so DEVKIT_5V arrives under J9. U8's GND pin is tapped
    between its pad columns to a via below the package: a via under an SC70
    body does not fit.
  - **Rear, between the socket rows:** U7 with the 2026-10-14 escape pattern (every
    signal pin to its own staggered via) and C24; below it U6, R24–R27,
    C23/C25/C27 with the MOTOR_UVLO node held to 5 mm of copper, and C30.
    VBAT is taken from R10.1.
  - **C28** at (115.0, 120.2), on the MOTOR_VREF diagonal where it splits to
    U4.4 and U5.4. **TP11** (MOTOR_VREF) at (124.9, 117.0) beside the corner;
    **TP10** (MOTOR_OK) at (132.0, 156.6), rear-left, outside the devkit.
  - **TP2/TP3** moved to (148.4, 86.6) / (151.8, 86.6), between J5 and J7,
    labelled `3V3` and `GND`.
- **Buck.**
  - **C17 straddles U3.3 (IN) and U3.4 (GND)** under the package.
  - The SW node is 3.57 mm² of F.Cu with **no vias**.
  - **L1's courtyard is 0.45 mm from U3's.** That is why C6 sits above the
    package. Do not move L1 east.
  - TP4 is a single 3.2 mm top-layer stub. If the island ever grows marginal,
    drop TP4.
  - `/VSYS` is pinned by a waypoint to the corridor north of the buck.
  - U3.4, C7, C11 and C17 each have their own GND via.
  - C12's GND via sits east of its GND pad, at (135.55, 91.53). North of the
    pad it closed SCL's lane under C15, and SCL ran past C6's BST pad at 0.45 mm.
- **FB (BUCK_3V3).** A dedicated via-free top-layer trace runs U3.1 → C11.1 (26.3 mm),
  round the outside of R8/C13. Its closest approach is TP4, at 1.35 mm.
  **Never put a via on FB**: it would risk bonding BUCK_3V3 to the In2 ESP_3V3 pour beside U3.
- **REG_EN.**
  - C13 (136.18, 97.0) and R8 (134.47, 97.175) sit beside U3.2, and
    EN → C13.1 → R8.1 is one top-layer run.
  - The leg to R7 crosses under FB on B.Cu.
  - Nothing of REG_EN's runs under U3. Its closest approach, 0.95 mm, is U3's
    own EN-to-SW pin gap.
- **IPROPI.**
  - R17 sits at (104.5, 120.3), west of U4's IN escapes. R18 sits at
    (118.5, 118.6), east of U5's pair. **Keep them on those sides.**
  - GPIO2 stays ≥ 1.20 mm and GPIO10 ≥ 0.80 mm from motor copper. GPIO2's
    limit is its via by J8, against the MOT_A_1 diagonal (1.30 mm on main,
    before stage 20 moved J8). GPIO10's limit is its escape via.
    `octilinear.py` holds new legs to 0.85 mm (raster) from IPROPI copper.
- **Motor copper.**
  - 0.8 mm trunks. The only narrower copper is in the `Motor pin escape` areas.
  - M1/M2 route as pairs. `tools/autoroute/loop.py` measures the loop areas:
    A 25.9 mm², B 24.3 mm² (main: 23.9 / 9.8). `loop.py`'s area is signed,
    and B's pair crosses itself, so opposite lobes cancel. On main they nearly
    balanced; `layout/devkit/measure.py` reports the lobes.
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
  - U4/U5 VREF now uses MOTOR_VREF from U6, not J8.4's ESP_3V3 feed.
    J8.4 has its own 3V3 stitch outside the VBAT island. Never rejoin them.
- **Connectors.**
  - J8 is at (106.6, 125.5), rot 180; J9 at (162.3, 97.3), rot 90. Each cable
    exits toward its motor, as before.
  - **J8's motor pins fan in north, under its own housing.** At J8's new x the
    old corridor along the board edge is gone. `devkit.fan_in_j8` lays the
    stubs; M2's steps 1.6 mm east over pin 4 so the pair can leave
    north-east.
  - **J9 is in front of the devkit**, so the motor B trunks keep their old
    corridor. MOT_B_1 follows layer-pinned waypoints that pass 5 mm south of
    REG_EN and cross under the left socket on B.Cu.
  - **J10 sits behind the IMU, rot 180, facing it**, with C22 beside its pins
    1/2. In front of the IMU it blocked the motor B trunks' exit from U5 and
    put the SPI bus beside motor copper.
- **IMU.** Chip centre (124.4, 133.5), 8.6 mm left of and 7.5 mm behind the
  rotation centre. The reservation is x 112.1–136.7, 0.04 mm off the left
  socket's courtyard. J8 and SW3 moved 3.4 / 0.4 mm west to clear it.
- **Battery bay.**
  - The pack lies across the underside, between the motors: board
    X 0.5–62.5, Y 57.5–74.5.
  - Each motor's 4 mm encoder allowance faces outboard, and brackets fasten on
    the outboard side only. Hook-and-loop tape holds the pack.
  - The right motor's attachment band on User.2 is still split either side of
    where J1 stood. With J1 gone it could be continuous.
  - The front strip was rejected: the pack there moves the CG ahead of the
    front axle.
  - The lead to BT1 is about 13 cm, so plan an XT30 extension. Do not move BT1
    to the pack's end: that would drag unfused copper out of the motor corner.
- **Silkscreen.** `assembly_marks.py` and `battery_bay.py` print the ToF mounts,
  the IMU outline, the motors and the battery. Test points, `BAT ON/OFF` and
  `PS1 HIGH = SPI` are labelled. The devkit footprint prints an arrow and
  `DEVKIT USB END` between the socket rows, plus `3V3`/`GND` at pins 1/44.
  Every stage-21 part except R28/R29 carries a designator (`silk_refs.py`).

### Still checked by eye (DRC cannot see these)

- C14 hard against U1.41 (GPIO1), with R10/R11 either side of it.
- C15 among J4–J7, and C16 against the connector furthest from C15.
- D4/D5 visible past the mechanics (rear-left corner).
- TP1–TP3 and TP9–TP11 reachable by hand and probe; TP4 sits under the
  devkit's USB end.
- The SPI bus (GPIO11–17) keeps its diagonal corridor between the socket rows
  (DRC checks only the 5 mm floor, not the route).
- The devkit's USB ports reachable with a cable plugged in from the front.
- The J10 cable not run alongside the motor outputs.
