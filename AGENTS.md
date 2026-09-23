# Pixy-M2 — Micromouse Controller PCB

Context for a Codex session working on this KiCad project via the KiCad MCP server.

## What this board is

Controller PCB for a micromouse robot — a **single-board design**. An
**ESP32-S3-WROOM-1** module is soldered directly to it. The board carries the MCU,
USB-C programming/power port, a buck converter, four JST-SH connectors (J4–J7) for
**off-board VL53L0X time-of-flight wall sensors**, and — once the parts are chosen —
the **motor drivers, encoders and IMU on the board itself**.

**There is no daughterboard.** Decided 2026-09-20, before layout started. It replaces
the earlier two-board architecture in which motors, motor drivers and the IMU mated
through two 22-pin headers (J2, J3). **Those headers were deleted on 2026-09-20**
once the motor, IMU and debug blocks that replaced them were built.

Power comes from a **2S LiPo (7.4V nominal, 8.4V full charge)** via an XT30 connector,
F1 battery polyfuse and Q1/SW3 load switch, then is diode-OR'd with fused USB 5V
and down-converted to 3.3V by an AP63203WU buck. `VBAT` is the switched, fused
motor/high-current supply; `VBUS` is downstream of the USB polyfuse F2.
The 2S pack is charged separately; no onboard battery charger is required.

- Schematic: `Pixy-M2.kicad_sch` — single flat sheet, no hierarchy
- KiCad 10.0
- **PCB layout is placed and fully routed (2026-09-21).** 4 layers — see "Board stackup"
  and "Routing" below. Every net is connected; DRC reports no routing errors.

## Current status

The **controller section** of the schematic is complete — MCU, USB, power path,
protection and ToF connectors. **ERC reports 0 errors and 0 warnings** as of
2026-09-20, when issue 12 put no-connect flags on GPIO45/GPIO46 and cleared the last
two `isolated_pin_label` warnings.

**A clean ERC is worth almost nothing here, and is now easier to misread than it was
when it showed 2 warnings.** Most issues below survive it: ERC does not check
footprint assignment, component ratings, saturation current, or whether a labelled
header pin actually goes anywhere. Treat 0/0 as the floor, not as evidence.

Extract the netlist mechanically rather than reading the schematic image:

```
kicad-cli sch export netlist --format kicadsexpr -o /tmp/after.net Pixy-M2.kicad_sch
kicad-cli sch erc -o /tmp/erc.rpt Pixy-M2.kicad_sch
```

Diff the net list against the previous export after every structural edit. Close
KiCad before editing `.kicad_sch` on disk — `~Pixy-M2.kicad_sch.lck` tells you the
GUI has it open, and whichever side saves last wins.

**Netlist last re-extracted: 2026-09-19, after the issue-14 ToF sensor connectors.**
The tables below are current as of that extraction. The schematic sheet was also
changed from A4 to **A3** to make room for the sensor block.

**As of the 2026-09-20 single-board decision the schematic is no longer complete as
a whole.** The motor drivers, encoders and IMU that used to live off-board do not
exist in it yet, and J2/J3 still stand in for them. See issue 15. Expect the sheet
to need more room again — possibly A2, or a move to hierarchical sheets, once the
power stage stops being the only high-part-count block.

**That is now stale too.** As of 2026-09-20 the motor drive, the IMU connector and
the debug header are all built, and J2/J3 are gone. The sheet is still A3: the motor
and IMU blocks went into the empty band below y≈195, and the debug block reuses the
space J2/J3 vacated. What remains open is the **board outline** (issue 15) and
measuring the issue-17 current budget on real hardware.

## Verified correct — do not re-flag these

These were checked against the actual netlist and are right. If a review pass
"finds" one of these, the review is wrong:

- **Buck topology.** C6 (0.1µF) is across U3.6 (BST) and U3.5 (SW). SW also drives
  L1.1. FB (U3.1) senses the 3.3V output directly — AP63203WU is the fixed-3.3V
  variant, so no feedback divider is needed or wanted.
- **Input capacitance exists.** C12 (10µF) is on `VSYS` at U3.3 (IN).
- **USB-C CC termination.** R1 and R6 are 5.1kΩ resistors (`Device:R_US`), one on
  CC1 (J1.A5), one on CC2 (J1.B5), each independently to GND. Correct Rd.
- **ESD protection.** U2 (USBLC6-2SC6) is correctly in-line: pins 1/6 on D−,
  pins 3/4 on D+, pin 5 on VBUS, pin 2 on GND.
- **Shield.** J1.SH via R5 (1M) ‖ C8 (4.7nF) to GND.
- **All four VBUS and all four GND pins of J1 are tied together.**
- **All 41 module pins are accounted for.** 39 land on a real net; `GPIO45` (U1.26)
  and `GPIO46` (U1.16) carry **explicit no-connect flags** and are deliberately
  unconnected — issue 12. Do not "fix" them by attaching anything: both are
  strapping pins and driving either one high at reset is harmful. (`GPIO3` was a
  third dangling pin until the issue-13 status LED took it.)
- **I2C is GPIO8 (SDA) / GPIO9 (SCL)**, pulled up by R15/R16 and shared by the four
  ToF connectors. Each connector also has its own XSHUT line — `GPIO4`–`GPIO7`, one
  per sensor. This is deliberate, not redundant: see issue 14.
- **U3's EN is independently driven** (issue 2). `VSYS` carries U3.3 (IN) only; EN is
  on `REG_EN`. If a review reports EN tied to IN, it is reading a stale netlist.
- **Boot/reset.** SW1 pulls CHIP_PU low (R2 10k pull-up, C3 1µF, C4 0.1µF debounce);
  SW2 pulls GPIO0 low (C5 0.1µF).

## Net map (extracted, authoritative)

| Net | Members |
|---|---|
| `ESP_3V3` | C1.1, C2.1, C7.1, C11.1, C15.1, C16.1, C22.1, J4.1, J5.1, J6.1, J7.1, J10.1, J11.1, L1.2, R2.1, R12.1, R15.1, R16.1, R19–R23.1, TP2.1, U1.2, U3.1(FB), U4.4, U5.4 |
| `VSYS` | C12.1, D1.1(K), D2.1(K), U3.3(IN) |
| `REG_EN` | C13.1, R7.2, R8.1, R9.2, U3.2(EN) |
| `VBAT_RAW` | BT1.1(+), F1.1 |
| `VBAT_FUSED` | F1.2, Q1.1/2/3(S), R14.1 |
| `VBAT` | Q1.5/6/7/8(D), D2.2(A), D6.1(K), C18–C21.1, R7.1, R10.1, TP1.1, U4.5, U5.5, #FLG04 |
| `Net-(Q1-G)` | Q1.4(G), R14.2, SW3.2(common) |
| USB connector (`Net-(F2-Pad1)`) | J1.A4/A9/B4/B9, F2.1 |
| `VBUS` | F2.2, D1.2(A), D3.2(A), U2.5 |
| `CHIP_PU` | C3.1, C4.2, J11.6, R2.2, SW1.1, U1.3(EN) |
| `GPIO0` | C5.2, SW2.1, U1.27 |
| `VBAT_SENSE` | C14.1, R10.2, R11.1, U1.39 (GPIO1/ADC1_CH0) |
| `Net-(D3-K)` | D3.1(K), R9.1 |
| SW node (`Net-(U3-SW)`) | C6.2, L1.1, TP4.1, U3.5 |
| BST (unnamed) | C6.1, U3.6 |
| `GPIO3` | R13.1, U1.15 |
| `Net-(D4-A)` | D4.2(A), R12.2 |
| `Net-(D5-A)` | D5.2(A), R13.2 |

`GND` additionally carries D4.1(K), D5.1(K), TP3.1, D6.2(A), SW3.3(ON), C15.2,
C16.2 and, for each of J4–J7, both pin 2 and the `MP` mounting pegs.
SW3.1 (OFF) is intentionally marked no-connect, as are **J4.5–J7.5** (the modules'
interrupt pin — issue 14) and **U1.26 / U1.16** (GPIO45 / GPIO46 — issue 12).
Seven no-connect flags in total; all seven are deliberate.

The four ToF connector nets (issue 14):

| Net | Members |
|---|---|
| `GPIO9` (SCL, conn. pin 3) | U1.17, J4.3, J5.3, J6.3, J7.3, R16.2 |
| `GPIO8` (SDA, conn. pin 4) | U1.12, J4.4, J5.4, J6.4, J7.4, R15.2 |
| `GPIO4` (XSHUT 1, conn. pin 6) | U1.4, J4.6 |
| `GPIO5` (XSHUT 2, conn. pin 6) | U1.5, J5.6 |
| `GPIO6` (XSHUT 3, conn. pin 6) | U1.6, J6.6 |
| `GPIO7` (XSHUT 4, conn. pin 6) | U1.7, J7.6 |

`VCC_USB_5V` has been **renamed `VSYS`**. It is the diode-OR output and sits at up to
**~8.1V** on a full pack, so the old "5V" name was actively misleading. `VBAT` and
`VBUS` are now explicit labels too, not auto-generated net names — do not let them
revert to `Net-(D1-A)` style names.

**J2 and J3 are gone (2026-09-20).** The two 22-pin headers existed to mate a
daughterboard; with the motor drive, IMU and debug blocks built there was nothing
left for them to carry, and they were the heaviest and tallest parts on the board
after the module. Deleting them is a mass and CG win, which is what a micromouse
trades on. **Every GPIO they carried now terminates on a real part** — that was the
precondition, and it is why the deletion produced no stranded nets.

`GPIO0`, `GPIO3`, `GPIO45` and `GPIO46` are the pins that were never on a header:
`GPIO0` is SW2 and now also J11.5, `GPIO3` drives the issue-13 status LED, and
GPIO45/46 are explicitly no-connect (issue 12).

**`GPIO4`–`GPIO9` are claimed by the ToF sensors (issue 14)** and now go only to
J4–J7 and the bus pull-ups. `GPIO8`/`GPIO9` remain a shared I2C bus with room for
more devices on it.

## Motor drive nets (extracted, authoritative)

Added 2026-09-20. Two identical channels, U4/J8 and U5/J9.

| Net | Members |
|---|---|
| `MOT_A_1` | U4.6 (OUT1), J8.1 |
| `MOT_A_2` | U4.8 (OUT2), J8.6 |
| `MOT_B_1` | U5.6 (OUT1), J9.1 |
| `MOT_B_2` | U5.8 (OUT2), J9.6 |
| `GPIO39` / `GPIO40` | U4.3 (IN1) / U4.2 (IN2) — motor A |
| `GPIO41` / `GPIO42` | U5.3 (IN1) / U5.2 (IN2) — motor B |
| `GPIO47` / `GPIO48` | J8.3 + R19.2 / J8.4 + R20.2 — encoder A |
| `GPIO21` / `GPIO38` | J9.3 + R21.2 / J9.4 + R22.2 — encoder B |
| `GPIO2` (ADC1_CH1) | U4.1 (IPROPI), R17.1 — motor A current sense |
| `GPIO10` (ADC1_CH9) | U5.1 (IPROPI), R18.1 — motor B current sense |

`VBAT` additionally gained U4.5, U5.5 (VM) and C18/C19/C20/C21.1.
`ESP_3V3` gained U4.4, U5.4 (VREF), J8.5, J9.5 and R19–R22.1.
`GND` gained U4.7, U5.7, **U4.9 and U5.9 (the thermal pads)**, C18–C21.2,
R17.2, R18.2, J8.2 and J9.2.

**The drivers' thermal pads are netted.** The KiCad symbol puts pin 9 at the same
coordinate as pin 7, so grounding GND connects the pad automatically — confirmed in
the netlist, not assumed.

## IMU nets (extracted, authoritative)

Added 2026-09-20. The **BNO08x is an off-board module**, like the ToF sensors —
this PCB carries the connector, one pull-up and local decoupling.

| J10 pin | Function | Net |
|---:|---|---|
| 1 | VIN | `ESP_3V3` |
| 2 | GND | `GND` |
| 3 | SCK | `GPIO12` (native FSPICLK) |
| 4 | MOSI | `GPIO11` (native FSPID) |
| 5 | MISO | `GPIO13` (native FSPIQ) |
| 6 | CS | `GPIO14` |
| 7 | INT | `GPIO15` |
| 8 | RST | `GPIO16` (+ R23 10k pull-up to `ESP_3V3`) |
| 9 | WAKE / PS0 | `GPIO17` |
| MP | mounting pegs | `GND` |

C22 (0.1µF 16V) decouples `ESP_3V3` at the connector.

**GPIO budget: 23 were free after the ToF sensors; all 23 are now allocated.**

| Function | Pins | Which |
|---|---:|---|
| Two motor driver channels (IN1/IN2 each) | 4 | GPIO39–42 |
| Two quadrature encoders | 4 | GPIO47, 48, 21, 38 |
| Two IPROPI current-sense inputs | 2 | GPIO2, GPIO10 (both ADC1) |
| BNO08x on SPI | 7 | GPIO11–17 |
| Debug console on J11 | 2 | GPIO43, 44 (UART0) |
| Spare, on test pads TP5–TP8 | 4 | GPIO18, 35, 36, 37 |
| **Total** | **23** | |

**Nothing is uncommitted, but the last four are spares, not users.** TP5–TP8 are
probe pads, so those GPIOs are available for a future peripheral at the cost of a
bodge wire rather than a respin. `GPIO35/36/37` among them are free only on the
fitted `-N16` module — an `-R8` part consumes them for PSRAM (issue 11).

The DRV8231A needs no nSLEEP or nFAULT pin — it sleeps when IN1 = IN2 = 0 and reports
faults by folding back current rather than on a dedicated line — which is why the
budget absorbed a 7-pin IMU and still left four spares.

## Open issues

Ordered by severity. **Resolved since this list was written: 1 (L1 part), 2 (UVLO),
3 (U1 footprint), 4 (dead header pins), 5 (battery sense), 6 (dissolved by the
single-board decision), 7 (switch/fuses/TVS added; battery fuse sizing remains
provisional), 8 (capacitor ratings), 9 (OR-ing diodes), 10 (USB series resistors),
11 (module variant), 12 (strapping pins), 13 (conveniences), 14 (ToF wall sensors).**

**The schematic is complete as of 2026-09-20.** Every block the single-board decision
called for is built: motor drive, IMU connector, debug header and spare pads, and
J2/J3 are deleted. ERC is 0 errors, 0 warnings, and **no net has fewer than two pins
except the seven deliberate no-connects**.

**Still open: 15 and 17, and neither is a schematic change.**

- **Issue 15 is down to the board outline**, which is a mechanical problem, not an
  electrical one — the chassis, the antenna keep-out, four outward-facing ToF
  connectors, J8–J11 and the USB-C port all have to coexist. That is what now gates
  layout.
- **Issue 17 is a measurement task.** The current budget is bounded by the motor
  drivers' 1.47A limit; what is left is confirming it on assembled hardware, and it
  gates *routing* the power path rather than fabrication.

Issue 16 is resolved. The suction fan was dropped from the design.

### 1. L1 — RESOLVED (2026-09-19)

L1 began as `Inductor_SMD:L_0805_2012Metric`, which was the worst problem in the
design. A 4.7µH 0805 part saturates somewhere around 300–700mA with DCR often
>300mΩ; the AP63203 is a 2A converter at ~1.4MHz, so the core would have saturated
under load, current would have run into the IC's cycle-by-cycle limit, and the part
would have overheated. The footprint was then corrected to the Bourns land pattern
while the Value was left naming a Sunlord part — the half-updated state this issue
tracked, which was worse than either end state.

**Both fields now name the same part, and the MPN and datasheet were written with
them:**

| Field | Value |
|---|---|
| Value | `4.7uH SRP5030T-4R7M` |
| Footprint | `Inductor_SMD:L_Bourns_SRP5030T` |
| MPN | `SRP5030T-4R7M` |
| Datasheet | `https://www.bourns.com/docs/product-datasheets/srp5030t.pdf` |

Bourns **SRP5030T-4R7M**, verified against that datasheet rather than from memory:
4.7µH ±20%, DCR 53mΩ max, **Irms 4.6A, Isat 6A**, shielded, 5.0×5.0×3.0mm body.
LCSC C2045677, also stocked at DigiKey/Mouser. (The "4.6A rated current" quoted
in earlier revisions of this file is Irms — the 20%-inductance-drop saturation
figure is 6A.)

**The Sunlord SWPA4030S4R7MT was rejected, not lost.** It works electrically
(~1.6A Isat, ~92mΩ DCR against a ~700mA peak) and `Inductor_SMD:L_Sunlord_SWPA4030S`
exists in the stock library, so reversing this decision is a one-field edit. It was
not taken because the 5×5 part has far more margin and because the layout notes
below are already written around it; the ~1mm-per-side of board area was judged not
worth it. The two land patterns are **not** interchangeable — Bourns is 2.0×1.8mm
pads on a 4.5mm pitch, Sunlord 1.1×3.7mm pads on a 3.0mm pitch — so if the smaller
part is ever chosen, both fields have to move together again.

Operating margin for reference: ripple is roughly 300mA p-p at 8.4V in, steady load
300–500mA, so peak inductor current stays under ~700mA. DCR loss is ~15mW —
negligible next to the ~400mW burned in D2 (issue 9).

*Correction to an earlier spec in this file's history: a "DCR ≤ 60mΩ" target at
4.7µH in a 4×4mm package is not physically achievable. The 5030T meets it because
it is a larger part.*

**Verified:** netlist diff before/after shows only L1's own field text changing —
no net, pin or footprint assignment anywhere else moved. ERC is unchanged at 0
errors and the same two GPIO45/GPIO46 warnings. The sheet was rendered and the new
Value string sits clear of TP4, C6 and the SW wire.

### 2. Undervoltage lockout — RESOLVED (2026-09-19)

U3.2 (EN) and U3.3 (IN) were the same net, so the regulator could never turn itself
off. EN is now driven by a programmed UVLO network and `VSYS` contains `U3.3(IN)`
only.

```
   VBAT ──[R7 120k]──┬──────────────── U3.2 (EN)       net: REG_EN
                     │
   VBUS ──|<|──[R9 39k]                                D3 = BAT54W
           D3        │
                     ├──[R8 24k]── GND
                     └──[C13 100nF]── GND
```

**Why this is not the divider the old note prescribed.** A 220k/47k divider on `VSYS`
would have bricked USB-only operation: USB gives VSYS ≈ 5.0 − 0.35 (D1) = 4.65V, so
EN would sit at 4.65 × 47/267 = **0.82V**, below the 1.15V minimum threshold. The
board could never be programmed or bench-tested without a charged pack. Sensing
`VBAT` directly also avoids smearing the threshold by D2's load-dependent Vf.

**The AP63203 has a purpose-built UVLO input**, so this is not a crude divider. Per
the datasheet (DS41326 Rev 3-2, Fig. 22, Eq. 1/2): a 1.5µA pull-up sits on EN always,
and a **further 4µA switches in once the part is enabled**, giving real, designed
hysteresis. Thresholds are VEN_H 1.15/1.18/1.23V rising, VEN_L 1.05/1.10/1.15V
falling.

| Condition | EN | Result |
|---|---|---|
| Pack rising, no USB | 1.18V at **VBAT = 6.90V** | turns on at 3.45 V/cell |
| Pack falling, no USB | 1.10V at **VBAT = 5.94V** | turns off at 2.97 V/cell |
| USB 4.75V, no pack fitted | 1.74V | runs (+41% over the 1.23V max threshold) |
| USB 4.75V, pack dead at 0V | 1.55V | runs (+26%) |
| Pack 8.4V + USB 5.25V | 2.69V | vs **35V** EN abs max — 13× margin |

Worst-case spread including the threshold tolerance: VON 6.72–7.20V, VOFF
5.64–6.24V (2.82–3.12 V/cell). Hysteresis ≈ 0.96V, which is wide enough that motor
sag on `VBAT` will not chatter the regulator.

**The old "check the EN abs-max rating" caveat is closed.** VEN is rated
**−0.3V to +35.0V** and the datasheet states EN "can be directly connected to VIN".
No clamp is needed and none should be added.

**D3 is not optional.** Without it, R9 becomes a 39k pull-*down* whenever VBUS is 0 —
i.e. any USB cable plugged into a powered-down PC or an unpowered hub. On a full
8.4V pack that drags EN to 0.945V and the board will not start; if it is already
running, EN falls to 0.998V and it shuts down. No value of R9 fixes this: holding EN
up on USB alone requires R9 ≈ R8, while not dragging it down on battery requires
R9 ≥ 94k. The two constraints do not intersect, so the reverse path must be blocked.

**Carry forward:**

- R7 and R8 set a safety threshold and **must be 1%**. At 5% the per-cell cutoff
  smears by roughly ±0.15 V/cell. This is encoded in their Value fields — keep it
  there.
- The divider draws **58µA at 8.4V** continuously (41µA once tripped), ≈42 mAh/month.
  A 500mAh pack survives about a year on that, comparable to self-discharge, so it is
  acceptable during use. **Issue 7 now puts it downstream of Q1/SW3**, so it no
  longer has a direct battery connection with the switch off.
- The table's voltages now refer to **post-switch `VBAT` and post-fuse `VBUS`**.
  Battery terminal thresholds also include F1/Q1 voltage drop under load; USB
  margin must include F2's resistance. Neither source bypasses its fuse through EN.
- **With USB connected, hardware UVLO is intentionally defeated** — D3/R9 hold EN up
  regardless of pack voltage. That is correct (you want to bench-run a flat board),
  but it means a low pack left connected alongside USB can still be pulled down to
  ~4.65V. Firmware must cover that case.
- Primary low-voltage protection is still **firmware**, using the battery sense
  divider from issue 5 — now built. This hardware UVLO is the coarse backstop for
  when firmware is not running; firmware is the accurate mechanism.

### 3. U1 footprint — RESOLVED

U1 is now `ESP32-S3-WROOM-1-N16` with footprint `PCM_Espressif:ESP32-S3-WROOM-1`.
No component in the design is missing a footprint.

### 4. Dead header pins — RESOLVED

The `5V0`, `GPIO19` and `GPIO20` header pins are gone. **Superseded entirely on
2026-09-20: J2 and J3 themselves are gone**, so no header pin can be dead. The
replacement is J11 (6 pins, all used) and TP5–TP9.

Still unconnected, but on the module rather than a header: `GPIO45` (U1.26) and
`GPIO46` (U1.16), both now carrying no-connect flags — issue 12, resolved.
`GPIO3` (U1.15) was the third until the issue-13 status LED took it.

### 5. Battery sense — RESOLVED (2026-09-19)

`VBAT_SENSE` was a label on U1.39 and nothing else. The MCU can now read pack
voltage:

```
   VBAT --[R10 470k]--+--> U1.39   GPIO1 / ADC1_CH0
                      |
                 [R11 220k]   [C14 100nF]
                      |            |
                     GND          GND
```

`GPIO1` is **ADC1**_CH0. Do not move this to an ADC2 pin — ADC2 is unusable while
Wi-Fi is active. Use `ADC_ATTEN_DB_12` (0–3100 mV on the ESP32-S3).

| Pack | V/cell | ADC sees |
|---|---|---|
| 8.4V full | 4.20 | 2.678V |
| 7.4V nominal | 3.70 | 2.359V |
| 6.90V (issue-2 UVLO turn-on) | 3.45 | 2.200V |
| 5.94V (issue-2 UVLO cutoff) | 2.97 | 1.894V |
| 9.5V (overcharge fault) | 4.75 | 3.029V |

422 mV of headroom at a full pack, and even a badly overcharged pack stays inside
the attenuator's range rather than railing — so an over-voltage fault is still
*measurable* instead of just clipping.

**Why 470k/220k rather than the 100k/47k originally specced, and no MOSFET gate.**
The original note called for gating the divider with a small MOSFET. A low-side
MOSFET — the obvious reading — is actively harmful here: it disconnects the bottom
of the divider but leaves the top tied to VBAT, so the sense node floats up until
GPIO1's ESD clamp conducts at ~3.6V, injecting ~46µA into the 3.3V rail through the
pin and still draining the pack. Gating a divider whose top sits above the ADC's
limit has to be done on the **high side**, which needs a P-FET plus an N-FET level
shifter, because a 3.3V GPIO cannot pull a gate up to 8.4V to turn it off.

That is 4 extra parts to save 12µA, on a board where the issue-2 UVLO divider
already draws 58µA ungated and *cannot* be gated — it has to work while the MCU is
off. Raising the divider to 470k/220k gets the drain to **12µA**, five times below
the UVLO divider, which makes the gate pointless. The standing pair is now ~70µA
total; the issue-7 power switch now disconnects both dividers from the battery.
MOSFET off-state leakage remains; this is not a mechanical air gap.

Dropping the gate also keeps `GPIO3` free — the last full-function unused pin — and
removes a failure mode where firmware forgets to assert the gate, reads 0V, and
concludes the pack is flat.

**Carry forward:**

- **C14 is not optional.** Source impedance is 150kΩ, far above what the SAR ADC's
  sample-and-hold can drive directly. C14 is the charge reservoir that makes the
  sample settle; without it readings will be low and load-dependent. RC is 15ms, so
  allow ~50ms after any step change before trusting a reading. That is irrelevant at
  the ~1Hz a battery monitor needs.
- **Calibrate in firmware.** 1% resistors give ±1.37% on the ratio, ±57 mV/cell
  before calibration, and the ESP32-S3 ADC adds its own error on top. One-point
  calibration against a metered pack voltage removes essentially all of it. Even
  uncalibrated this beats the issue-2 UVLO's ±0.15 V/cell.
- After issue 7, sense voltage at **TP1 (`VBAT`)** when calibrating. The divider
  measures the supply after F1/Q1, so motor current causes an additional drop
  relative to the battery terminals. This is conservative for low-voltage cutoff.
- R10 doubles as transient protection. Motor kickback on `VBAT` can only push
  (V−3.6)/470k into GPIO1's clamp — 56µA even at 30V — and C14's 15ms rolls off
  anything fast. No extra clamp is needed.

### 6. Ground pins — DISSOLVED (2026-09-20)

Was: 8 GND pins across the 44 header positions (J2.1/6/12/18, J3.7/12/17/22) carrying
motor and sensor return current between two boards — "improved over the original 4,
still thin". **Both headers were deleted on 2026-09-20**, so the question is not just
dissolved in principle; the pins no longer exist.

**The single-board decision removes the question.** Motor return current now flows in
the L2 ground plane instead of through header pins, which is a change of kind rather
than degree. Nothing to do here.

J11, the debug header that replaced them, has one GND pin (pin 2) next to the console
pair, and TP9 is a dedicated probe ground beside TP5–TP8. Neither carries power
return, so the old concern does not transfer.

### 7. Power switch, fuses and TVS — IMPLEMENTED (2026-09-19)

Six components added. **F1's current rating is provisional:** the intended loads
were unknown when this was written. They are now settled: **two high-speed N20
gearmotors and four VL53L0X wall sensors, and no fan** — see issues 15 and 17, where
the budget is recomputed against real numbers.

```
 BT1+ -- F1 -- VBAT_FUSED -- Q1(S -> D) -- VBAT -- D2 -- VSYS
                    |           |          |-- U4/U5 motor drivers, TP1
                    R14         G          |-- R7/R8 UVLO
                    |           |          |-- R10/R11 battery sense
                    +-----------+          +-- D6(K), D6(A) -> GND
                                |
                           SW3 common(2)
                           /           \
                     OFF(1): NC    ON(3): GND

 J1 VBUS pins -- F2 -- VBUS -- D1 -- VSYS
                        |-- D3/R9 USB enable
                        +-- U2.5 ESD clamp reference
```

| Ref | Fitted part / value | Footprint | Selection |
|---|---|---|---|
| F1 | Littelfuse `2920L300/15DR`, 3A 15V | `Fuse:Fuse_2920_7451Metric` | 3A hold, 5A trip at 20°C; 40A maximum fault current |
| F2 | Bourns `MF-MSMF050-2`, 500mA 15V | `Fuse:Fuse_1812_4532Metric` | 0.5A hold, 1A trip at 23°C |
| Q1 | AOS `AO4407A` | `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` | −30V P-FET, ±25V gate; 17mΩ max at VGS = −6V |
| R14 | 100kΩ | `Resistor_SMD:R_0805_2012Metric` | Gate-to-source pull-up, defaults OFF |
| SW3 | C&K `JS102011SAQN` | `Button_Switch_SMD:SW_SPDT_CK_JS102011SAQN` | Gate control only; 2–3 ON, 2–1 OFF |
| D6 | Vishay `SMBJ9.0A-E3/52` | `Diode_SMD:D_SMB` | Unidirectional TVS, 9V standoff, 600W pulse rating |

Manufacturer references: [F1](https://www.littelfuse.com/assetdocs/2920l_datasheet_update.pdf?assetguid=f237e8c2-1ed9-4c13-a738-dbe0738b3d2c),
[F2](https://www.bourns.com/docs/product-datasheets/mf-msmf.pdf),
[Q1](https://www.aosmd.com/sites/default/files/res/datasheets/AO4407A.pdf),
[SW3](https://www.ckswitches.com/media/1422/js.pdf),
[D6](https://www.vishay.com/docs/88392/smbj.pdf).
Each specified part also has its datasheet and full MPN in the schematic fields.

**Q1 orientation matters.** Source pins 1/2/3 connect to `VBAT_FUSED`; drain pins
5/6/7/8 connect to `VBAT`; pin 4 is the gate. Its body diode blocks battery-to-load
current when OFF. The stock `Transistor_FET:IRF7404` symbol is used only for its
identical SO-8 pin map; the fitted part is **AO4407A**, as specified by Value, MPN
and Datasheet. Do not order IRF7404 from the library identifier. At 3A and −6V gate
drive, the calculated Q1 loss is ~0.15W at the datasheet's 25°C resistance; provide
adequate copper and check temperature on the assembled board.

**Both dividers, the TVS and all four battery header pins are downstream of Q1.**
OFF removes their direct pack drain. R14 has essentially no voltage across it
while OFF; its ~84µA at 8.4V is drawn only while ON. Off-state drain is limited by
Q1 leakage rather than the former ~70µA divider load; do not promise literal zero.
This single MOSFET does not provide reverse-polarity protection or bidirectional
isolation: current can return to the battery through its body diode.

**USB operation is preserved with SW3 OFF.** F2 sits before *every* USB supply
branch, including the D3 enable path. D1/D2 still provide source OR-ing. The
existing high-value R7 can weakly bias the disconnected `VBAT` node from USB's EN
network; the switch does not guarantee a discharged/zero-volt motor rail.
Turning the whole board off requires removing USB as well as switching off SW3.
**With motors now on this board, that matters more than it did** — SW3 OFF plus USB
in must not leave a driver's inputs floating against a weakly-biased `VBAT`. Give the
drivers a defined disabled state (see issue 15).

**Current-budget check — now needed before *routing*, not just before fabrication
(issue 17):** verify steady load at the actual
fuse temperature, both motor stalls, pack short-circuit capability,
and the copper/header/wiring ratings. F1 is a thermal PPTC, not a hard 3A limiter:
its specified maximum trip time is 20s at 8A, and its hold current falls to about
2.31A at 60°C. Its 40A maximum fault-current rating must also suit the selected
pack. Do not increase F1 without checking the entire power path. F2 similarly does not enforce a USB host's negotiated current budget;
keep USB-only loads within that budget, including its voltage drop and derating.

**D6 protects the switched motor rail.** Cathode pin 1 is on `VBAT`, anode pin 2
on GND. Its 9V standoff exceeds the 8.4V full pack; specified breakdown is
10–11.1V and clamp is 15.4V at 39A for a 10/1000µs pulse. It is a transient clamp,
not a continuous braking-energy sink. On-board devices must tolerate that clamp plus
layout overshoot, and the local motor recirculation/bulk capacitance that used to be
the daughterboard's job is **now this schematic's job** — see issue 16.
Capacitor voltage ratings (issue 8) still need resolving.

**Verified:** netlist comparison confirms only the intended source splits and
new protection/control connections; all other existing nets and header mappings
are unchanged. ERC remains 0 errors and the same two GPIO45/GPIO46 warnings.
The rendered sheet was inspected for wiring and field overlaps.

### 8. Capacitor voltage ratings — RESOLVED (2026-09-20)

**Every capacitor now states its rating in the Value field**, following C13's
precedent so a reviewer sees it on the sheet rather than having to open a BOM.

| Ref | Value | Footprint | Net / role |
|---|---|---|---|
| C1 | `10uF 16V` | 0805 | `ESP_3V3` bulk |
| C2 | `0.1uF 16V` | 0603 | `ESP_3V3` decoupling |
| C3 | `1uF 16V` | 0603 | CHIP_PU debounce |
| C4 | `0.1uF 16V` | 0603 | CHIP_PU |
| C5 | `0.1uF 16V` | 0603 | GPIO0 |
| C6 | `0.1uF 25V` | 0603 | bootstrap, BST–SW |
| C7 | `22uF 16V` | 0805 | 3.3V output |
| C8 | `4.7nF 1kV` | **1206** | USB shield — see below |
| C11 | `22uF 16V` | 0805 | 3.3V output |
| C12 | `22uF 25V` | **1206** | `VSYS` input bulk — see below |
| C13 | `0.1uF 50V` | 0603 | UVLO (unchanged) |
| C14 | `0.1uF 50V` | 0603 | ADC filter (unchanged) |
| C15 | `10uF 16V` | 0805 | ToF rail (unchanged) |
| C16 | `0.1uF 16V` | 0603 | ToF rail (unchanged) |
| **C17** | `0.1uF 25V` | 0603 | **new** — `VSYS` HF bypass at U3.3 |

**C6 at 25V is margin, not necessity.** The datasheet's abs-max for VBST is
`VSW − 0.3` to `VSW + 6.0`, so the cap only ever sees ≤6V *across* it even though
both its terminals ride a node that swings to VIN. 16V would have done; 25V is free
in an 0603.

**C12: one 22µF 1206 rather than two 10µF 0805s.** Checked against the AP63203
datasheet (DS41326 Rev 3-2) rather than against this issue's own note, **which was
wrong**: it claimed "the AP63203 wants ~2×10µF *effective* input capacitance". It
does not. Table 2 specifies **C1 (input) = 10µF** for the 3.3V part, and the Input
Capacitor section says *"using a ceramic capacitor greater than 10µF is sufficient
for most applications."* The `2 × 22µF` figure in that table is the **output**, which
C7 ‖ C11 already match exactly.

Meeting a 10µF *effective* target at 8.4V bias is the real constraint. A 25V 10µF
0805 derates to roughly 3–4µF there, so two of them would have delivered ~7–9µF —
still short. A 25V 22µF 1206 retains roughly 11–13µF at that bias, so **one part
meets the recommendation where two smaller ones did not**, with one fewer placement
inside the loop the layout rules demand be kept tight. The package grew 0805 → 1206;
that is the cost, and it is worth it.

The datasheet also asks for an RMS rating above half the maximum load current. This
rail carries the module, four ToF sensors and the LEDs — ~0.7A, so ~0.35A — which any
1206 ceramic clears easily.

**C17 is the high-frequency bypass** the pin-3 description calls for (*"bypass VIN to
GND with a suitably large capacitor"*), and the layout section says **"place the VIN
capacitors as close to the device as possible"** — plural. C12 is the bulk; C17 is the
part that must sit hard against U3.3, closer than C12 if they compete.

**C8 is the one this issue's own guidance got wrong.** The original note said
"everything else: minimum 16V". C8 is the USB shield cap — R5 (1M) ‖ C8 from `J1.SH`
to GND — and it is an **ESD path**, not a bias node. During a strike R5 does nothing
and C8 takes the charge. An IEC 61000-4-2 8kV contact discharge dumps a 150pF source
into it, so the shield node divides as 8kV × 150pF / (150pF + 4.7nF) ≈ **250V across
C8**. A 16V or 50V part is destroyed. **1kV** gives 4× margin.

That rating is not available at 4.7nF in 0603 — high-voltage dielectric needs the
volume — so **the footprint moved to 1206 with it**. Value and Footprint moved
together deliberately: leaving `4.7nF 1kV` on an 0603 pad would have been exactly the
half-updated component this project's working notes warn about.

**Verified:** netlist diff against the previous commit shows exactly two changes —
`C17.1` joined `/VSYS` and `C17.2` joined `GND`. Net count steady at **62**, no new
auto-named `Net-(…)` strays, every other net byte-identical. ERC stays 0 errors,
0 warnings. The sheet was rendered and inspected three times: the first placement put
C17's GND label through R7's value text, the second left C12's label reading as if it
belonged to C17, and the third is clean. Both were invisible to the netlist diff.

### 9. OR-ing diodes D1/D2 — RESOLVED (2026-09-20)

Both were Value `D_Schottky` with an empty Datasheet field. **Both are now
onsemi `MBRA340T3G`**, same part in both positions — identical requirements,
identical footprint, one fewer BOM line and reel.

| Field | Value |
|---|---|
| Value | `MBRA340T3G` |
| Footprint | `Diode_SMD:D_SMA` (unchanged) |
| MPN | `MBRA340T3G` |
| Datasheet | `https://www.onsemi.com/pdf/datasheet/mbra340t3-d.pdf` |

Verified against that datasheet (MBRA340T3/D Rev. 12) rather than from memory:
SMA / CASE 403D (DO-214AC), **VRRM 40V**, **IO 3.0A at TL = 100°C**, IFSM 100A,
**VF 0.450V max at 3.0A / 25°C** (0.390V at 100°C), IR 0.3mA at 40V / 25°C,
TJ −55 to +150°C, RθJL 15°C/W, RθJA 81°C/W. LCSC C26178.

**Correction: this issue's original premise was wrong.** It said "D2 carries the
entire system current from the battery — at 1A that is ~400mW", and on that basis
floated replacing D2 with a P-FET ideal-diode controller. The netlist says otherwise.
`VSYS` has exactly four members — `C12.1, D1.1(K), D2.1(K), U3.3(IN)` — so **D2 feeds
the buck input and nothing else.** Motor current on `VBAT` reaches U4/U5 in
parallel with D2 and never passes through it.

Actual worst case: the 3.3V rail carries the module, four ToF sensors (76mA average,
160mA pulsed) and the LEDs, ~0.7A. Reflected to a 6V low pack at 90% efficiency that
is **~0.43A**, where the curve gives VF ≈ 0.30–0.33V — about **140mW**, some 11°C of
rise on RθJA. **The ideal-diode controller is unnecessary. Do not re-propose it**
unless something puts a real load on `VSYS`.

**Why 40V and not 30V.** D6 clamps `VBAT` at 15.4V during a motor transient, and that
propagates to `VSYS` through D2, so D1 can see ~15V reverse with USB absent. 40V
keeps a comfortable margin over that.

**Package trap, recorded so the next person does not repeat it.** "SS34" is the
obvious commodity answer and it is **wrong for this footprint**: Vishay's SS34 is
**SMC (DO-214AB)**, not SMA. In Vishay's numbering the first digit is the current
class and the package scales with it — SS1x is SMA, SS2x is SMB, SS3x is SMC. Other
manufacturers sell an "SS34" in SMA, so the part number alone does not pin the
package down. MBRA340T3G is unambiguously SMA.

**Reverse leakage is not zero**, and it lands on an existing caveat: 0.3mA at 40V and
25°C (much less at the ~5V this circuit actually applies, but not nothing). D2's
cathode is `VSYS` and its anode is `VBAT`, so with USB powering the board and SW3 OFF,
leakage flows toward `VBAT` — one more reason issue 7's "the switch does not guarantee
a discharged/zero-volt motor rail" is true.

**D3 was already specified** — `BAT54W` / `Diode_SMD:D_SOD-123`, with a datasheet
field. It carries ~70µA, so it has no thermal or Vf constraint worth revisiting.
D1/D2 now follow its pattern, with an MPN field as well.

### 10. Series resistors on USB D+/D− — RESOLVED (2026-09-20)

R3 and R4 (22Ω) sat between U2 and the module's USB pins. The ESP32-S3's internal
USB PHY is impedance-matched and Espressif's reference designs connect straight
through, so they did nothing. **Both are deleted** and U2 now drives U1 directly:
`/USB_D+` is `{U1.14, U2.4}`, `/USB_D-` is `{U1.13, U2.6}`.

**Deleted rather than set to 0Ω.** Both options were sanctioned by the original note.
Removal won because two 0805 jumper pads are a discontinuity in the 90Ω differential
pair the layout rules call for, sitting exactly where routing is tightest — next to
the USB-C connector. The pair carries Full Speed (12 Mbps), so the discontinuity
would have been harmless in practice; this is about keeping the pair clean and the
BOM short, not about fixing a signal-integrity fault. **If a future spin wants series
resistors back for rework or EMI, re-adding them is a schematic edit, not a
respin-level change** — but do not add them "just in case".

**Verified:** netlist diff shows exactly four changes and nothing else — `/USB_D+`
and `/USB_D-` absorbed U2.4 and U2.6, and the auto-named `Net-(R3-Pad2)` /
`Net-(R4-Pad1)` disappeared. **Net count 64 → 62**, which is the expected drop.
ERC stays 0 errors, 0 warnings. The sheet was rendered and inspected: both runs go
straight from U2 to their labels with no junction dot picked up on the way — the
wire-through-a-junction hazard this project has hit twice did not recur.

### 11. Module variant — RESOLVED

U1's Value is now **`ESP32-S3-WROOM-1-N16`**: 16MB flash, **no PSRAM**. That is the
outcome the design needed — **GPIO35, GPIO36 and GPIO37** (module pins 28/29/30,
now on test pads TP6/TP7/TP8) are consumed by octal PSRAM only on `-R8` parts, so on
an N16 they are genuinely free. **Do not substitute an `-N8R8` or `-N16R8` part
without accepting that those three pads become PSRAM signals** — probing them would
then be actively harmful, not merely useless. Silkscreen the caveat next to them.

### 12. Unused strapping pins — RESOLVED (2026-09-20)

GPIO45 (U1.26) and GPIO46 (U1.16) were unconnected on the module with a net label on
each, which is what the two `isolated_pin_label` ERC warnings were about. **Both now
carry explicit no-connect flags and the labels are gone.** ERC is 0 errors, 0
warnings.

This was always tidiness rather than a fault — the ESP32-S3's internal weak
pulldowns hold both pins at their safe state, so the board boots either way. What the
flags buy is *intent*: an unconnected pin and a pin someone forgot to wire look
identical in a netlist, and these two must stay unconnected. The flag is the only
thing in the file that says so.

**Explicit 10k pulldowns were considered and rejected.** They would also have cleared
the warnings, and the failure mode they defend against is severe (see the table) —
but the internal pulldown is ~45kΩ, so pulling either pin above V_IH would take a
leakage path under ~15kΩ, which is gross contamination rather than a plausible
board-level fault. Espressif's own reference designs leave both pins floating. Two
parts and two more things to place, to defend a failure the module already defends
against, is the same trade this project rejected in issue 5. **Do not re-add them
without a new reason.**

**GPIO3 is no longer one of these.** It drives the issue-13 status LED (U1.15 → R13 →
D5 → GND), which is exactly the use the table below sanctions.

Researched while choosing a gate pin for issue 5; recorded so the next person does
not have to repeat it. **If any of these are ever used, the risk is not equal:**

| Pin | Role at boot | Risk if driven high at reset |
|---|---|---|
| GPIO45 | VDD_SPI voltage select | **Sets flash rail to 1.8V — board will not boot.** Treat as unusable. |
| GPIO46 | ROM UART print control | GPIO46=1 **with GPIO0=0 is an invalid combination** with undefined behaviour — and GPIO0 is the BOOT button (SW2), so this bites exactly when someone is trying to flash. |
| GPIO3 | JTAG signal source | Harmless. No effect unless the `JTAG_SEL_ENABLE` eFuse is burned, and its safe state is low. The only one of the three safe to repurpose — **now used** by the status LED. |

GPIO0 is also a strapping pin and is used correctly (SW2 boot button). Worth a
silkscreen note wherever a strapping pin is exposed — on whatever debug header
survives issue 15, and on any test point that lands on one.

**Layout note:** GPIO45 and GPIO46 are now floating copper — module pad, no trace.
Do not route anything past them, do not let a pour create a large island on either,
and do not add a test point to either. They are already correct; the only way they
become a problem is if layout attaches something to them.

**Verified:** netlist diff shows exactly two changes and nothing else — `/GPIO45` and
`/GPIO46` became `unconnected-(U1-GPIO45-Pad26)` and `unconnected-(U1-GPIO46-Pad16)`.
Net count is unchanged at 64; no other net, pin or footprint moved. ERC went from 2
warnings to 0/0. The sheet was rendered and inspected: both NC markers sit on the
right pins, and every neighbouring label (GPIO14/17/18/21/38/47/48) is intact.

### 13. Missing conveniences — RESOLVED (2026-09-19)

All three are built. Nine parts added: D4/R12, D5/R13, TP1–TP4.

```
   ESP_3V3 --[R12 10k]--|>|-- GND        D4 = red    ~150uA
   GPIO3   --[R13 2.2k]-|>|-- GND        D5 = green  ~550uA when lit
```

| Ref | Value | Footprint | Net |
|---|---|---|---|
| R12 | 10kOhm | `Resistor_SMD:R_0805_2012Metric` | ESP_3V3 → D4 |
| D4 | Red | `LED_SMD:LED_0805_2012Metric` | power indicator |
| R13 | 2.2kOhm | `Resistor_SMD:R_0805_2012Metric` | GPIO3 → D5 |
| D5 | Green | `LED_SMD:LED_0805_2012Metric` | status indicator |
| TP1 | VBAT | `TestPoint:TestPoint_Pad_D1.5mm` | `VBAT` |
| TP2 | 3V3 | `TestPoint:TestPoint_Pad_D1.5mm` | `ESP_3V3` |
| TP3 | GND | `TestPoint:TestPoint_Pad_D1.5mm` | `GND` |
| TP4 | SW | `TestPoint:TestPoint_Pad_D1.5mm` | `Net-(U3-SW)` |

**The power LED must be a high-efficiency red part.** 10k was specified, and that
constrains the colour rather than the other way round: at 3.3V a 10k resistor only
delivers (3.3 − Vf)/10k, so a 3.0–3.2V pure-green InGaN part would get ~10µA and
effectively not light. Red (Vf ≈ 1.7–1.9V at these currents) gives **~150µA**, which
is dim but clearly visible indoors on a modern part. Do not substitute blue/white/
pure-green without raising the rail current budget or dropping the resistor.

**~150µA is not free.** It does not add to the issue-7 standing-drain problem — D4
hangs off `ESP_3V3`, so it dies with the rail when the regulator is off or UVLO
trips, unlike the two `VBAT` dividers. But it **will dominate deep sleep**: an
ESP32-S3 in deep sleep draws ~10µA, so the power LED is ~15× the MCU. If firmware
ever relies on deep sleep for pack life, D4 is the first thing to cut — fit it DNP,
or move it behind a GPIO.

**D5 is wired active-high (GPIO3 → R13 → anode, cathode to GND) deliberately.** At
reset GPIO3 is high-Z with an internal ~45kΩ pulldown and the LED cannot conduct
below its Vf, so the pin sits at 0V — which is GPIO3's safe strapping state (see
issue 12). An active-low arrangement (3V3 → LED → GPIO) would have held the pin near
the rail at reset. Firmware drives GPIO3 **high** to light it.

2.2k for the status LED rather than 10k: it is firmware-gated so it costs nothing
when off, and ~550µA through a modern green 0805 is unambiguously visible, where
10k would have been marginal. Well inside the ESP32-S3's 40mA per-pin limit.

**TP4 is on the SW node and that is in tension with the layout rules below** — see
the SW-island note in "Layout constraints". It is a 1.5mm pad, deliberately the
smallest in the `TestPoint` library, but it still has to be placed as a stub off the
existing island rather than allowed to grow it.

### 14. VL53L0X wall sensors — IMPLEMENTED (2026-09-19)

Four **VL53L0X** time-of-flight modules replace the IR emitter/receiver pairs the
original architecture note assumed. **The sensors are off-board**: this PCB carries
only the connectors, the shared bus pull-ups and the local rail decoupling, so the
modules can be aimed mechanically at the maze walls. Eight parts added.

**The fitted module is the GY-VL53L0XV2 (silkscreen `HW-842`)** and J4–J7 reproduce
its 6-pin header **in the module's own order**, so the cable is a straight-through
1:1 loom with no crossovers to get wrong:

| Conn. pin | Module silkscreen | Net |
|---:|---|---|
| 1 | VCC | `ESP_3V3` |
| 2 | GND | `GND` |
| 3 | SCL | `GPIO9` |
| 4 | SDA | `GPIO8` |
| 5 | GPIO1 | **no-connect** (sensor interrupt, not used) |
| 6 | XSHUT | `GPIO4` / `GPIO5` / `GPIO6` / `GPIO7` |

```
   ESP_3V3 --[R15 2.2k]-- GPIO8 (SDA) --> J4.4  J5.4  J6.4  J7.4
   ESP_3V3 --[R16 2.2k]-- GPIO9 (SCL) --> J4.3  J5.3  J6.3  J7.3

   GPIO4 --> J4.6    GPIO5 --> J5.6    GPIO6 --> J6.6    GPIO7 --> J7.6   (XSHUT)

   ESP_3V3 --+--[C15 10uF]-- GND       ESP_3V3 --> J4.1  J5.1  J6.1  J7.1
             +--[C16 100nF]-- GND      GND     --> J4.2  J5.2  J6.2  J7.2
                                               and the MP mounting pegs
```

| Ref | Value | Footprint | Role |
|---|---|---|---|
| J4–J7 | `SM06B-SRSS-TB` | `Connector_JST:JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal` | one per sensor |
| R15 | 2.2kOhm | `Resistor_SMD:R_0805_2012Metric` | SDA pull-up |
| R16 | 2.2kOhm | `Resistor_SMD:R_0805_2012Metric` | SCL pull-up |
| C15 | 10uF 16V | `Capacitor_SMD:C_0805_2012Metric` | ToF rail reservoir |
| C16 | 0.1uF 16V | `Capacitor_SMD:C_0603_1608Metric` | ToF rail HF decoupling |

The two `MP` mounting pegs are tied to GND. **Pin 5 carries a no-connect flag**, so
the pad and the cable conductor exist but go nowhere on this board — wiring the
interrupts later is a trace change, not a connector change.

**Every VL53L0X powers up at I2C address 0x29 and the address is volatile**, so four
on one bus is only possible with a per-sensor XSHUT. Firmware holds all four low,
then releases one at a time and writes a new address to register 0x8A before moving
on. This repeats on every power cycle — nothing is stored in the device.

**GPIO4–GPIO7 float at reset, and the module pulls XSHUT up.** Verified against the
ESP32-S3 datasheet v2.2 Table 2-1: GPIO4–8 have a *blank* "At Reset" and "After
Reset" column — no internal pull-up, no pull-down, input buffer disabled. The
GY-VL53L0XV2 pulls XSHUT (active low) up to its own regulated rail, so **all four
sensors come out of reset enabled and all four answer to 0x29 at once.** That is the
state firmware inherits; it is not a fault, but nothing works until firmware resolves
it. Two consequences:

- **Drive GPIO4–7 as open-drain outputs, not push-pull** (`GPIO_MODE_OUTPUT_OD`).
  Pull low to shut a sensor down; release to high-Z and let the module's own pull-up
  enable it. This matters: the module's XSHUT sits on a 2.8V rail, and the datasheet
  says high levels "have to be equal to AVDD in 2V8 mode" — a push-pull 3.3V drive
  is inside the 3.6V absolute maximum but outside that. Open-drain sidesteps it
  entirely and costs nothing.
- **Drive them low as firmware's first act**, before any I2C traffic, so the bus is
  not contended by four devices at the same address.
- Do **not** add a pull-down on this board to "fix" the float — it would divide
  against the module's pull-up and park XSHUT at an indeterminate level.

**3.3V is in spec; no 2.8V rail or level shifter is needed on this board.** The
datasheet gives AVDD 2.6/2.8/3.5V recommended with a 3.6V absolute maximum, and ST
support states plainly: *"Go ahead and use 3v3… just try to keep the voltage less
than 3.5."* The GY-VL53L0XV2 takes 3.0–5.0V on VCC, regulates it to 2.8V itself and
level-shifts SCL/SDA to the VCC rail — which is exactly why R15/R16 pull up to
`ESP_3V3` and not to some other reference.

**Leave the driver's 2V8 I/O mode on.** Table 7 note 4: *"The default API mode is
1V8."* The part's pads have to be told they are running from a 2.6–3.5V supply
rather than 1.8V; it is a single write to register 0x89
(`VHV_CONFIG_PAD_SCL_SDA__EXTSUP_HV`) bit 0, which `VL53L0X_DataInit()` performs and
Pololu's driver exposes as `io_2v8` — **on by default in both**. So this is "do not
turn it off" rather than "remember to add it". Nothing is damaged either way (abs
max on SCL/SDA/XSHUT/GPIO1 is 3.6V); 1V8 mode just leaves the pads mis-configured
for the rail they are actually on.

**R15/R16 = 2.2kΩ, and they belong here rather than on the modules.** The datasheet
says pull-ups are *"typically fitted only once per bus, near the host"* and
recommends 1.5–2kΩ for AVDD 2.8V at 400kHz; 2.2k is that value scaled to 3.3V. It
sinks 1.5mA against a 4mA VOL spec, and at ~100pF of bus plus cable it gives a
~190ns rise, inside fast mode's 300ns. **If the fitted modules carry their own 10k
pull-ups**, four in parallel with this pair lands near 1.2kΩ — 2.8mA, still legal,
but re-check it against the module's actual schematic. 4.7k here would have been
too slow for 400kHz on its own.

**GPIO1 (the modules' open-drain interrupt) is deliberately not wired** — the
datasheet sanctions it: *"GPIO1 to be left unconnected if not used."* Firmware polls
the status register, which is normal for continuous-mode ranging at ≤50Hz. The
connector still carries the pin because it mirrors the module header, so adding
interrupts later means running four traces to the TP5–TP8 spares (or wired-OR to one,
since the outputs are open-drain) — the connector and cable already fit.

**Current budget:** 19mA average per sensor while ranging and **40mA peak** during
the VCSEL pulse, so ~76mA average and up to 160mA of pulsed load on `ESP_3V3` if all
four fire together. That is nothing to the 2A AP63203, but it is why C15 exists: the
modules' own caps sit on the far side of the cable inductance.

**Not covered here:** there is no ESD protection on the sensor cables, and no way to
power-cycle a hung module — XSHUT is the sanctioned reset and it is wired, so this
is a considered omission rather than an oversight.

**Verified:** netlist diff shows exactly the intended additions — `ESP_3V3`, `GND`,
`GPIO4`–`GPIO9` gained the new members and **no other net changed**, with no
auto-named `Net-(…)` strays. ERC is unchanged at 0 errors and the same two
GPIO45/GPIO46 warnings. The sheet was rendered and inspected: no overlapping text,
and the block sits clear of the A3 border and title block.


### 15. On-board peripherals — MOTOR DRIVE BUILT, rest still open (2026-09-20)

**Built:** two motor channels (14 parts), the **BNO08x IMU connector block**
(J10, R23, C22), and the **debug header and spare-GPIO pads** (J11, TP5–TP9).
**Deleted:** J2 and J3, the two 22-pin daughterboard headers.
**Dropped:** the suction fan, removed from the design entirely.
**Still open:** the board outline — and that is now the only thing left in this issue.

#### Debug header J11 and test pads TP5–TP9

J2/J3 were the de-facto debug header: 44 pins carrying every spare GPIO. Once the
motor, IMU and console blocks claimed those signals the headers carried nothing
unique, while remaining the heaviest and tallest parts on the board after the module.
**They were deleted and replaced with J11 plus five pads.**

**J11 is `SM06B-SRSS-TB` — the same part as J4–J7**, so it adds no BOM line and no new
cable design:

| Pin | Net | Purpose |
|---:|---|---|
| 1 | `ESP_3V3` | level reference for a probe — **not** a way to power the board |
| 2 | `GND` | return, deliberately adjacent to the console pair |
| 3 | `GPIO43` | U0TXD — console out |
| 4 | `GPIO44` | U0RXD — console in |
| 5 | `GPIO0` | BOOT — adapter DTR |
| 6 | `CHIP_PU` | EN/reset — adapter RTS |
| MP | `GND` | mounting pegs |

**Pins 3–6 are an esptool auto-reset interface**, and that is the justification: it is
the recovery path if firmware ever disables the native USB-Serial-JTAG, or if you need
a console while debugging the USB stack itself. **`GPIO0` was previously on no
connector at all** — only SW2 — so before J11 there was no off-board way into the
bootloader.

**JTAG deliberately has no header.** U1.13/14 are GPIO19/20 (USB D−/D+) and already
reach the USB-C port, so the ESP32-S3's built-in USB-Serial-JTAG provides flashing,
console and JTAG debugging over the connector that is already there. Do not add a
JTAG header; it would duplicate working silicon.

**TP5–TP8 carry the four spare GPIOs** (`GPIO18`, `GPIO35`, `GPIO36`, `GPIO37`) on
`TestPoint_Pad_D1.5mm`, the same part as TP1–TP4. **TP9 is a dedicated probe ground**
beside them — a spare-GPIO pad with no nearby return is not much use to a logic
analyser. Pads rather than a connector because these are bring-up aids that only get
touched with a probe, and four 1.5mm pads weigh essentially nothing.

#### Driver selection — TI DRV8231A

The brief was "headroom above the clamp", and that is what eliminated the obvious
candidates. **D6 (SMBJ9.0A) clamps `VBAT` at up to 15.4V**, and a driver has to
survive what the TVS lets through:

| Part | VM abs max | Verdict |
|---|---|---|
| DRV8833 | **11.8V** | below the clamp — rejected |
| TB6612FNG | **15.0V** | below the clamp — rejected |
| DRV8874 / DRV8876 | 40V | good (200mΩ / 700mΩ), but **no KiCad stock symbol** |
| **DRV8231A** | **35V** | **fitted** — 2.3× the clamp |

Verified against the TI datasheet rather than from memory: **VM 4.5–33V operating,
35V absolute maximum**, 3.7A peak output, RDS(on) 300mΩ high-side + 300mΩ low-side,
integrated current sense and regulation, IN1/IN2 logic 0–5.5V with **internal 100kΩ
pulldowns**, device UVLO 4.15–4.45V rising, WSON-8 2.0 × 2.0 mm, RθJA 66.5°C/W.

**4.5V minimum matters more than it looks.** The board's own UVLO (issue 2) turns on
at 6.90V and off at 5.94V, so a driver with a 6.5V or 8V minimum — DRV8871, DRV8848,
A4950 — would be out of spec across part of the usable pack range. DRV8231A covers
the whole of it.

**The internal pulldowns are a safety property, not a detail.** ESP32-S3 GPIOs float
at reset; the pulldowns hold IN1/IN2 low, so **both motors are off until firmware
drives them.** Do not add external pulldowns and do not assume a different driver
behaves this way.

**600mΩ is the trade that was accepted.** At a ~0.5A running current that is 0.15W
and 0.3V of an 8.4V supply — fine. The DRV8874's 200mΩ would be better and its
package is the same family, but it has no stock KiCad symbol, so taking it means
authoring one. **If thermals prove tight, the cheaper move is the DDA (HSOP-8)
variant of the same die: RθJA 42.8°C/W against the DSG's 66.5°C/W**, at the cost of
a 4.9 × 6.0 mm package and a different symbol.

#### Current limit, and why it is set where it is

`VREF` is tied to `ESP_3V3` (3.3V, inside the 0–3.6V recommended range, 6V abs max).
With **AIPROPI = 1500 µA/A** and R17/R18 = 1.5kΩ:

```
   ITRIP = VREF / (AIPROPI x RIPROPI) = 3.3 / (1500u x 1500) = 1.47 A
   IPROPI sense scale = AIPROPI x RIPROPI = 2.25 V/A   (ADC full scale 3.1V ~ 1.38A)
```

**1.47A is chosen to protect the driver, not the motor.** Left unregulated, a stalled
N20 at 8.4V draws 8.4 / (3.75Ω motor + 0.6Ω driver) ≈ **1.93A**, which puts 2.24W
into a package with RθJA 66.5°C/W — a 149°C rise, i.e. thermal shutdown. Regulating
at 1.47A drops that to 1.29W. The cost is small: torque is proportional to current,
so the limit still delivers ~92% of the motor's rated stall torque.

It also keeps the connector legal — see below — and it is well under the part's own
3.7A overcurrent trip, so OCP stays a fault backstop rather than a control mechanism.

**This is the hardware half of the stall protection issue 17 asks firmware for.**
Current regulation caps the current; `IPROPI` on an ADC1 pin lets firmware *see* the
stall and react. Both channels use ADC1 (GPIO2 = CH1, GPIO10 = CH9) because ADC2 is
unusable while Wi-Fi is active — the same constraint as issue 5.

#### Connectors J8/J9

`S6B-PH-K`, 6-pin JST-PH at 2.00mm, side-entry. **The pin order mirrors the encoder
module** — 1 = M1, 2 = GND, 3 = OUT A, 4 = OUT B, 5 = VCC, 6 = M2 — so the cable is a
straight-through loom, the same principle as J4–J7 (issue 14).

**JST-PH is rated 2A per contact and the motor pins carry the full motor current.**
That is why the current limit matters here too: 1.47A regulated keeps M1/M2 inside
the contact rating, where the 1.93A natural stall would not. **Do not raise R17/R18
without re-checking the connector.**

The pinout does put M1 and M2 at opposite ends of the connector, which is a larger
current loop than adjacent pins would give. That is accepted for the same reason as
issue 14: mirroring the module makes the cable unmistakable, and a mis-wired motor
cable is a worse failure than the loop area.

**R19–R22 (10kΩ) pull up the encoder outputs.** Fitted because cheap N20 encoder
boards commonly use open-drain Hall sensors, which produce nothing at all without
them. If the fitted encoder has push-pull outputs the resistors are harmless.

#### A KiCad library bug was corrected locally — do not let it come back

**`Driver_Motor:DRV8231ADSG` types pin 8 (OUT2) as `power_in`, while pin 6 (OUT1) is
`output`.** It is a library error — `DRV8871DDA` in the same library types both
outputs correctly. Left alone it produces two `power_pin_not_driven` ERC errors on
the motor output nets.

The cached copy of the symbol **in this schematic** has OUT2 corrected to `output`.
**"Update Symbols from Library" will silently revert it** and the two errors will
reappear. If they do, this is the cause — re-apply the fix rather than papering over
it with PWR_FLAGs on the motor outputs.

A PWR_FLAG *was* legitimately needed elsewhere: **`#FLG04` on `VBAT`**, because the
rail reaches the drivers through BT1 → F1 → Q1 and ERC cannot see a power source
through them. That one is correct and should stay.

#### IMU — BNO08x module on SPI (J10)

**Off-board, like the ToF sensors.** This PCB carries J10 (`SM09B-SRSS-TB`, 9-pin
JST-SH, side-entry, mounting pegs to GND), R23 and C22. Nine conductors:
VIN, GND, SCK, MOSI, MISO, CS, INT, **RST** and **WAKE**.

**INT and RST are not optional in SPI mode** — the BNO08x signals data-ready on INT
and the host must wait for it; the datasheet calls both required for stable SPI.
That is why the connector is 9-way and not 6.

**WAKE is pin 9, and it is the same physical pin as PS0.** PS0/PS1 select the
protocol and are *sampled at reset*: both high selects SPI, both low selects I²C.
**After reset, PS0 is repurposed as WAKE**, which the host pulls low to ask a sleeping
device for attention. Hard-jumpering PS0 high on the module would select SPI but leave
the host unable to wake it, so WAKE is brought to a GPIO and **PS1 alone is the module
jumper**. SparkFun's driver expects a WAK pin; Adafruit's does not — bringing it out
costs one GPIO and suits both.

**The module must have PS1 jumpered high.** This is the single most likely bring-up
failure: a stock BNO08x breakout ships configured for I²C and will simply not answer
on SPI until that jumper is changed. Silkscreen it next to J10.

**GPIO11/12/13 are the ESP32-S3's native FSPI D/CLK/Q pins**, so SPI2 can drive them
through the IO MUX rather than the GPIO matrix. At the BNO08x's 3MHz ceiling that
buys nothing in bandwidth, but it costs nothing either, and it keeps the clock off a
matrix-routed pin. CS is on GPIO14 because GPIO10 — the native FSPICS0 — is taken by
motor B's IPROPI; CS has no timing requirement, so the matrix is fine for it.

**R23 (10k) holds RST high while GPIO16 floats.** ESP32-S3 GPIOs float at reset, and
a floating RST on a module without its own pull-up is indeterminate. With R23 the
module comes up running regardless, and firmware resets it deliberately.

**C22 is 0.1µF and there is no bulk cap here, unlike the ToF block.** C15 exists
because four VL53L0X modules pulse 40mA each into a cable; the BNO08x draws a low,
steady current, so HF decoupling is all this rail needs at J10.

**I²C was reconsidered and rejected, but it was closer than it first looked.** An
earlier note in this file claimed sharing the ToF bus would "cap gyro rate and couple
sensor timing" — that overstated it. Four VL53L0X at 50Hz is roughly 3% of a 400kHz
bus and a BNO08x rotation vector at 400Hz adds about 20%, so throughput was never the
problem. The real cost is **latency jitter**: an IMU interrupt arriving mid-ToF-read
waits up to ~150µs, which is 15% of a 1kHz control period. SPI was kept for that
reason, and because it leaves the I²C bus entirely to the wall sensors. The costs are
real and worth recording: three more conductors, a second cable design, four more
GPIOs, and a 3MHz clock on a ribbon cable rather than 400kHz.

#### What is still missing from this issue

| Decision | Status | What it gates |
|---|---|---|

**Direction settled 2026-09-20; exact parts still outstanding.** Three of the five
decisions below have answers now. They are recorded here rather than implemented —
the schematic is untouched — so the next session starts from them instead of
re-asking.

| Motor part number, gear ratio | **Class chosen: high-speed N20** (Pololu micro metal gearmotor HP 6V class), 1.6A stall at 6V. Exact gear ratio still needed | Nothing on this board — the electrical figures are the same across ratios |
| Motor driver part | **DONE — DRV8231A ×2** | — |
| Encoder type | **DONE — integrated with the motor**, 12 CPR quadrature on J8/J9 | — |
| IMU part and bus | **DONE — BNO08x module on SPI**, off-board via J10 | 7 GPIOs |
| Suction fan | **DROPPED** — no fan in the design | nothing; it was never built |
| Debug/expansion header | **DONE — J11 + TP5–TP9**; J2/J3 deleted | 2 GPIOs used, 4 on spare pads |
| Board outline | **Open — the only thing left** | Chassis, antenna keep-out, four ToF connectors, J8–J11, SW3, USB-C |

**Superseded 2026-09-20:** an earlier revision of this section recorded a
"high-power, ≥3A stall" class and concluded from it that F1 was undersized. The motor
choice changed to high-speed N20 before anything was built against it. The ≥3A
figures are gone from this file; **issue 17's F1 verdict is revised, not merely
softened** — see there.

**Reference figures** (Pololu 10:1 HP 6V, a representative high-speed variant, from
its product page): 3100 RPM free-run at 6V, **100mA free-run**, **1.6A stall**, 0.22
kg·cm stall torque. Gear ratio changes speed and torque but not the electrical
figures, so F1 and the driver can be sized before the ratio is fixed.

**Encoders are no longer this board's mechanical problem.** N20 gearmotors ship in
encoder variants with a 12 CPR quadrature encoder already mounted, brought out on a
back or side connector. That replaces the on-board AS5047P-plus-shaft-magnet scheme
the previous revision anticipated, and with it the constraint that the PCB sit at a
fixed small distance under each motor shaft. **This board needs two GPIOs and a
connector per motor, nothing more.** It is the single largest simplification the N20
choice buys, and it materially loosens the outline problem below.

**12 CPR is low, and that is a firmware consequence, not a hardware one.** 12 counts
per motor revolution before gearing; useful resolution comes from the gear ratio, so
a high-speed (low-ratio) variant gives *fewer* counts per wheel revolution than a
geared-down one. Check that the chosen ratio still yields enough edges for the
control loop rate before committing — this is the one place the "high speed" choice
costs something.

**The N20 is a 6V-nominal motor on an 8.4V pack.** That is a deliberate over-volt
for speed, and Pololu states plainly that higher voltages "could start negatively
affecting the life of the motor." It also scales stall current: 1.6A × 8.4/6 =
**2.24A per motor at a full pack**. Firmware should cap PWM duty — roughly 71% gives
a 6V equivalent from 8.4V — and that cap is also what keeps F1 comfortable (issue 17).

**Choosing SPI for the IMU also protects the ToF bus.** GPIO8/9 already carry four
VL53L0X sensors at 400kHz (issue 14); adding a gyro that wants high-rate reads would
have made sensor timing and gyro timing contend with each other, which matters
precisely during the fast turns where both are needed.

**Mechanical gate, not just electrical:** with the motors on this board, the outline
is now set by the chassis — wheel positions, motor body clearance, ground clearance —
*and* it must still satisfy the antenna keep-out, four outward-facing ToF connectors,
an accessible SW3 and a reachable USB-C port. Check the combined footprint before
committing to the outline; this is the constraint most likely to force a rethink.

**Done:** that header is J11, sized once the real GPIO surplus was known — 6 pins for
console and programming, with the four genuine spares on probe pads instead of
connector pins.

### 16. Motor noise shares the board with the ADC and the buck — RESOLVED (2026-09-20)

Created by the single-board decision, and closed when the motor block was built.
**C19 and C21 (22µF 25V, 1206) are the local bulk capacitance** on `VBAT` at each
driver, with C18/C20 (0.1µF 50V) as the high-frequency bypass the DRV8231A datasheet
asks for at the VM pin. Recirculation needs no external parts — the H-bridge's own
body diodes handle it — and D6 remains the transient clamp.

The placement discipline below still applies and is now a layout requirement, not a
plan. Motor switching is inches from U1, from the 150kΩ `VBAT_SENSE` node and from
the buck's feedback:

- **`VBAT_SENSE` (issue 5) will see real motor sag and real switching noise.** Its
  15ms RC helps a lot, but firmware should average across whole PWM periods rather
  than trusting a single conversion, and should not sample during a stall event and
  conclude the pack is flat.
- **Bulk capacitance is built** — C19/C21, one per driver. Issue 7 told the
  daughterboard to "retain local motor recirculation/bulk capacitance"; there is no
  daughterboard, so it lives here now. Both are 25V parts because D6 clamps `VBAT`
  at up to 15.4V.
- **That bulk capacitance interacts with F1 inrush**, though only 2 × 22µF of it
  (~22µF effective at 8.4V after DC-bias derating), which is small next to a PPTC's
  thermal time constant. It does **not** sit behind D2 — `VBAT` reaches the drivers
  directly, so D2's forward drop is not in this path (see issue 9).

The mitigation is placement, not plane splitting — see "Board stackup".

### 17. F1 and the `VBAT` path now carry motor current on *this* board (2026-09-20)

A promotion of issue 7's open item rather than a new fault. The current budget was
already outstanding, but with motors off-board it only had to be right before
*ordering parts*. Now the same number also sets **trace width, copper weight, via
count and thermal relief on this PCB**, so it has become a layout input.

Answer it before routing the power path, not before fabrication. F1's provisional 3A
hold was chosen without knowing the motors; if the real stall current moves it, the
copper sized around it moves too.

### F1 with N20 motors — revised 2026-09-20, verdict reversed

**An earlier revision of this section declared F1 undersized.** That was computed
against the "≥3A stall" motor class, which is no longer the plan. Recomputed against
high-speed N20s (issue 15), **F1's 3A hold is defensible** — but it is not
comfortable everywhere, and the margin depends on firmware.

F1 is a 3A-hold / 5A-trip PPTC whose hold falls to about **2.31A at 60°C**. Two
things have changed since that first estimate, and both help: **the fan is gone**, and
**the DRV8231A regulates each channel at 1.47A** (issue 15), so motor current is now
bounded by hardware instead of by motor impedance.

Everything on `VBAT` passes through F1, including the buck — BT1 → F1 → Q1 → `VBAT` →
D2 → `VSYS` → U3 — so the 3.3V rail's ~0.43A reflected input current counts too.

| Condition | `VBAT` current | vs F1 |
|---|---|---|
| Both motors free-running | ~0.7A | trivial |
| Normal driving, both motors loaded | ~1.4A | comfortable |
| Hard acceleration, ~1A per motor | ~2.4A | just above the **60°C** hold; fine for a 30s run, not indefinitely |
| **Both** motors at the 1.47A current limit | **~3.4A** | above the 3A hold, below the 5A trip — trips slowly |
| Unregulated double stall (**cannot happen now**) | 4.9A | this is what the limit removes |

**The verdict is that F1 is adequate, with one caveat.** The worst case the hardware
permits is ~3.4A, where before it was an unbounded ~4.9A. A polyfuse only trips
*quickly* well above its hold, so at 2.4A it will carry a speed run indefinitely in
practice, and at 3.4A it trips slowly — which is the right behaviour for a jammed
robot. **The caveat is thermal:** the 60°C hold of 2.31A is below hard-acceleration
current, so a hot board driven hard for minutes rather than seconds is the case that
trips. That is a competition-realistic scenario, so measure it on the assembled board.

**Firmware stall detection is now the primary protection, and it is finally
possible.** IPROPI on GPIO2/GPIO10 lets firmware see per-motor current directly
(2.25 V/A), so it can cut drive on a stall long before F1's thermal time constant
matters. The hardware current limit is the backstop; F1 is the backstop's backstop.

**What still has to be checked before fabrication:**

- **The actual N20 variant.** 1.6A is Pololu's HP figure; other N20s differ, and some
  cheaper ones are worse. A higher-stall motor does not change the *supply* current
  any more — the 1.47A limit caps it — but it does change how hard regulation works
  and therefore how hot U4/U5 run.
- **F1's 40A maximum fault current against the pack.** Unchanged from issue 7 — a
  low-impedance 2S LiPo can deliver far more than that into a hard short. This is
  independent of the motor choice and is still open.
- **Q1 (AO4407A, 17mΩ at VGS = −6V).** At 4.5A that is ~0.34W in a SOIC-8 — fine with
  reasonable copper on all three source and all four drain pads, where the previous
  ≥3A-class figure of ~0.61W was pushing it.

**D6's clamp voltage now constrains the driver, and this is new.** D6 (SMBJ9.0A)
clamps at up to **15.4V** at full surge current, sitting nearer 11–12V at the few-amp
kickback an N20 actually produces. Several obvious micromouse drivers are rated below
that: **DRV8833 has an 11.8V absolute maximum** and **TB6612FNG 15V**. A driver must
survive what D6 lets through, not just the 8.4V pack. Either pick a driver with
headroom above 15.4V, or accept the risk knowingly — **do not assume the TVS protects
the driver**, because at these ratings it does not.

**Do not simply fit a bigger polyfuse** if measurement shows F1 nuisance-tripping.
Raising F1 raises the fault current every downstream part must survive. The cheaper
fixes come first: lower the ITRIP resistors, or tighten the firmware duty cap.

## Board stackup — 4 layers (decided 2026-09-20)

Decided together with dropping the daughterboard. Two layers cannot carry on-board
motor drivers, a clean ADC reference, a 1.4MHz buck and a 90Ω USB pair at the same
time. The extra layers are bought primarily for **L2**.

| Layer | Use |
|---|---|
| **L1** (top) | components; short high-speed runs — USB D+/D− pair, the SW island, the motor-driver power loops |
| **L2** | **unbroken GND plane** — the whole reason for going to 4 layers |
| **L3** | power pours: `VBAT` (motor rail) and `ESP_3V3`, as separate regions |
| **L4** (bottom) | secondary signal routing plus a GND pour stitched to L2 |

**L2 is never split, cut, or routed through.** No signal traces on L2; no plane split
under the USB pair, the SW node, the ToF I2C pair or `VBAT_SENSE`. A split plane
forces return current around the gap and causes worse problems than the separation it
appears to buy.

**Partition by placement, not by plane splits.** Motor drivers, D6 and the battery
input go in one region; U1, the ADC nodes and the ToF I2C go in another. Keeping the
high-di/dt return currents physically out from under the quiet circuitry is what
makes a single plane work — it is the job the 8 header ground pins used to do badly
(old issue 6).

- Assume a standard 1.6mm 4-layer stackup with **thin L1↔L2 prepreg** (~0.2mm on
  JLCPCB's JLC04161H-7628 and its equivalents elsewhere). That tight spacing is what
  makes the 90Ω pair achievable with sane trace geometry and keeps every L1 return
  path directly beneath its trace.
- **Compute the USB pair geometry against the fab's actual stackup** with their
  impedance calculator. Do not carry a number over from another board. **Done
  2026-09-22 (review issue 7), by field solver: 0.25 mm trace / 0.15 mm gap, about
  88–94 Ω across 0.200/0.2104 mm prepreg and 10–25 µm mask.** The earlier guess in
  this bullet, 0.2 mm / 0.15 mm, solves to ~100 Ω, which is outside 90 Ω ± 10 %.
  The solver's figure is still not the fab's — confirm it with JLCPCB's
  calculator, or order impedance control, before fabrication.
- **The antenna keep-out must now be cut out of four layers, including both pours.**
  This is the main new risk the stackup introduces: it is far easier to let a ground
  or power pour flood under the antenna than it was to forget a trace. Define the
  keep-out as a board-level rule area so the pours respect it automatically, and
  verify it on all four layers before fab.
- Stitch L2 to the L4 ground pour generously — especially around the SW island, the
  motor-driver return paths and the module's thermal pad.
- 1oz outer copper is fine for signals, but **check the `VBAT` and motor-return
  copper against the final stall current** (issue 17). If the motor path is tight,
  widen on L1/L4 or specify 2oz outers; do not rely on L3's pour alone to carry it.
- **The AP63203 datasheet asks for 2oz on both outer layers** and for the ground
  layer to sit directly under the device for heat spreading (DS41326 §PCB Layout,
  items 1–3). L2 already provides the latter. The 2oz request is made at the part's
  full 2A; this rail draws ~0.7A, so 1oz is defensible — but if 2oz is taken for the
  motor path anyway, U3 gets it for free.
- Give the input and output capacitors' **GND pads their own via stitching to L2**,
  which the same datasheet section asks for by name. **Done 2026-09-22 for C7, C11,
  C17 and U3.4 itself; C12 keeps the via it already had.**

## Routing — done 2026-09-21

The board was routed with a purpose-written grid router (A* on a 0.05 mm grid over
F.Cu and B.Cu, planes and pours on the inner layers). **2241 mm of track, 242 vias,
1247 mm on F.Cu and 994 mm on B.Cu.** *(Those are this pass's figures. The motor
region was reworked later the same day — see "Motor-region rework" below — after which
the board carries 2253 mm and 249 vias.)* Every net in the netlist is connected:
`kicad-cli pcb drc --refill-zones` reports **0 unconnected items** and **0 clearance,
shorting, dangling, isolated-copper or hole-clearance errors from the routing**.

The copper zones implement the stackup decided on 2026-09-20. The first four came
from this routing pass; the F.Cu pour was added by the motor-region rework below:

| Zone | Layer | Net | Priority |
|---|---|---|---|
| GND plane | In1.Cu | `GND` | 0 — solid, unbroken, via antipads only |
| 3V3 pour | In2.Cu | `/ESP_3V3` | 0 |
| VBAT motor rail island | In2.Cu | `/VBAT` | 1 — x 100.5–127, y 88–122 |
| GND pour bottom | B.Cu | `GND` | 0 — fragmented by B.Cu routing, as expected |
| GND pour motor region | F.Cu | `GND` | 0 — x 104.2–123.2, y 104.6–120.2 (rework) |

All zones use **solid pad connections, not thermal reliefs** (island removal on).
Every SMD pad on `GND`, `/ESP_3V3` and `/VBAT` reaches its plane through a stitching
via: 77 GND vias, 28 on 3V3, 27 on VBAT.

Track widths, set by net and then widened wherever clearance allowed:

| Net(s) | Width |
|---|---|
| `VBAT_RAW`, `VBAT_FUSED`, `VBAT` trunk | 1.0 mm (tapering to 0.2 at small pads) |
| `MOT_A_*`, `MOT_B_*` | **superseded by the rework: 0.8 mm throughout, 0.2–0.4 mm only in the driver pin escapes** |
| `VSYS`, `VBUS`, `Net-(F2-Pad1)` | 0.6 mm — **was not true of `VBUS`/`Net-(F2-Pad1)` until issue 8**: they were 0.24 mm |
| `Net-(U3-SW)` | 0.5 mm |
| GND / 3V3 stubs | 0.4 mm |
| signals | 0.2 mm, 0.15 mm for escapes from the 0.25 mm-wide DRV8231A pads — **issue 8: the router had used 0.15 mm end to end on five nets; now only inside the pin fields** |

Escapes from fine-pitch parts (U4/U5 WSON-8, J1's 0.3 mm CC/D± pads) are 0.15–0.2 mm
and sit inside the pad they leave. Plane stitching for those parts is deliberately done
**after** their signal nets are routed — stitching them first walls in the neighbouring
pads and makes OUT1 unroutable on both drivers.

### What the router did NOT do — review these by hand

- ~~**`/USB_D+` and `/USB_D-` are ordinary 0.2 mm traces, not a 90 Ω differential pair.**~~
  **Fixed by review issue 7 (2026-09-22)** — see "Issue 7" below. As routed here they
  were 0.2 mm traces with lengths of 18.4 mm and 13.7 mm, and the issue-6 via pass
  later pushed the connector-side D− onto B.Cu through four vias.
- **None of the placement-sensitive rules below were modelled**: the C12→U3.3→U3.4
  input loop, the size of the SW island, keeping `REG_EN` and `VBAT_SENSE`
  (150 kΩ) away from SW and motor current, routing `MOT_x_1/2` as tight pairs, and
  keeping `GPIO2`/`GPIO10` IPROPI analog runs clear of the motor outputs. The router
  optimised length and via count only. Walk these five nets in the GUI.
  **The rework below moved `REG_EN` and the SW node clear (0.26 → 8.51 mm and
  0.28 → 6.62 mm) and paired `MOT_B_1/2`; the IPROPI runs are still open.**
- ~~**Thermal vias are 2 per driver EP**~~ — **this was never true.** U4's exposed pad
  had no via in it at all and U5 had one; both reached GND through a narrow neck to an
  offset via. Fixed by the rework below, which also corrects the "0.45/0.25 would fit
  ~6" estimate: at the board's 0.45 mm hole-to-hole rule only two fit.
  U1's 12 EP pads do have one via each.
- No teardrops, no length matching, no via stitching of the two GND layers beyond the
  signal/plane vias already placed.

### Pre-existing DRC errors, not caused by routing

Four `hole_clearance` errors between J1's GND pads (A1/A12/B1/B12) and J1's own NPTH
mounting holes — 0.25 mm against a 0.3 mm rule. They are inside the
`USB_C_Receptacle_Amazon` footprint and were present before any track was laid. Fix
the footprint or relax the rule; do not chase them in the routing.
The `lib_footprint_mismatch` warning on U1 is likewise pre-existing.

## Motor-region rework — 2026-09-21 (review issues 1–3)

A second pass over the motor region, driven by `REVIEW.md`.
`tools/autoroute/rework.py` reproduces it from `tools/autoroute/base-routed.kicad_pcb`
(the router's own output). It never edits the file it reads, but it does write the
board without zone fills, so **always follow it with**

```
kicad-cli pcb drc --schematic-parity --refill-zones --save-board --format json \
    -o /tmp/drc.json Pixy-M2.kicad_pcb
```

**DRC after the rework is identical to before it**: 0 unconnected items, 0 schematic
parity issues, and the only violations left are the four pre-existing J1
`hole_clearance` errors and the pre-existing U1 `lib_footprint_mismatch` warning.
Board totals went 2241 → **2253 mm of track** and 242 → **249 vias**.

### Issue 1 — motor output copper

`MOT_B_1` carried 38.8 mm of its 42 mm at 0.15 mm and `MOT_B_2` 41.3 mm of its 48 mm.
All four nets are now 0.8 mm trunks, and the only sub-0.5 mm copper left is the escape
inside each driver's own pin field.

| Net | length | sub-0.5 mm | DC resistance |
|---|---|---|---|
| `MOT_A_1` | 15.0 → 16.7 mm | 11.0 → **2.5 mm** | 39 → **14 mΩ** |
| `MOT_A_2` | 16.2 → 19.0 mm | 6.4 → **1.0 mm** | 27 → **13 mΩ** |
| `MOT_B_1` | 42.0 → 43.5 mm | 38.8 → **2.5 mm** | 129 → **31 mΩ** |
| `MOT_B_2` | 48.1 → 59.4 mm | 41.3 → **1.0 mm** | 138 → **37 mΩ** |

Resistance is DC at 20 °C into 35 µm copper. The motor-B pair goes from 0.267 Ω to
0.068 Ω, so at the DRV8231A's 1.47 A limit **0.393 V and 0.578 W become 0.100 V and
0.147 W**. The "before" column reproduces the review's own 0.268 Ω / 0.394 V / 0.579 W
exactly — that is the cross-check that this is the same measurement, not a new one.
(`MOT_B_2`'s length and resistance include the 11.3 mm the issue-4 pairing and the
issue-5 retune added; see those sections.)

0.8 mm of 1 oz external copper carries roughly 2.3 A for a 10 °C rise (IPC-2152), so
1.47 A is about a 4 °C rise — the trunks are sized on temperature, not just on drop.
**No 0.15 mm copper is left on any motor net**; the widths in use are 0.2, 0.3, 0.4
and 0.8 mm.

**The escapes are the only narrow copper and they are now fenced in.** OUT1 leaves
pin 6 between the bypass cap's two pads — a 0.65 mm slot — so it runs 0.2 mm for
2.1 mm, 0.4 mm for 0.4 mm, then 0.8 mm. OUT2 leaves pin 8 upward at 0.3 mm for 0.5 mm
and 0.4 mm for 0.5 mm. Worst case is ~11.5 squares, about 6 mΩ, on copper heat-sunk by
a wide trunk at one end and the pad at the other.

**A netclass and a custom DRC rule enforce it**, which is what the review asked for.
`Pixy-M2.kicad_pro` gains a `Motor` netclass (0.8 mm default width, matched by the
pattern `/MOT_*`), and the new `Pixy-M2.kicad_dru` carries:

```
(rule "Motor trunk minimum width"
	(constraint track_width (min 0.6mm))
	(condition "A.NetClass == 'Motor' && !A.enclosedByArea('Motor pin escape')"))
```

`Motor pin escape` is two named rule areas on F.Cu, one per driver, sized to contain
the escapes and nothing else. **`enclosedByArea`, not `intersectsArea`** — with
`intersects`, a trunk that merely *starts* inside the area is exempt along its whole
length, and that was observed: the first version of this rule silently passed a
deliberately narrowed `MOT_A_1` trunk. The rule was verified in both directions:
narrowing one 0.8 mm segment on each of the four nets produces four `track_width`
errors, and the real escapes produce none.

### Issue 2 — exposed-pad heat path

U4's exposed pad had **no via in it at all** and reached GND through a 0.4 mm neck to
a single via; U5 had one. Per driver the pad now has:

- **two in-pad thermal vias at 0.45 mm / 0.25 mm.** The board's own rules already
  allow this — `min_via_diameter` is 0.45 and `min_through_hole_diameter` 0.2 — and
  the 0.8 mm pitch leaves 0.55 mm hole-to-hole against the 0.45 mm rule. **Three do
  not fit:** the 0.45 mm hole-to-hole rule forces a 0.7 mm pitch, which puts the outer
  vias' copper outside a 1.6 mm pad. The earlier note in this file that
  "0.45/0.25 would fit ~6" was wrong — it counted copper and ignored hole-to-hole.
- **0.8 mm-wide copper out of the pad** to a further GND via above it.
- GND vias within 3 mm of the pad: U4 2 → 4, U5 1 → 4. With the in-pad pair that is
  six vias per driver into the In1 plane.
- a new F.Cu zone, **`GND pour motor region`** (x 104.2–123.2, y 104.6–120.2), which
  fills **165 mm² of top-side ground copper** around both drivers, D6 and the bulk
  caps. Solid pad connections, island removal on, same settings as the other pours.

**There is deliberately no copper neck out of the *lower* end of either pad.** The
`ESP_3V3` feed to pin 4 (VREF) passes within 0.43 mm of it on both drivers and nothing
0.6 mm wide fits past. `rework.py` prints `! no neck+via for GND from (…)` when it
gives up on this; that message is expected, not a failure. Widening it means rerouting
the VREF feed first.

**The via-in-pad still needs an assembly decision** — see issue 6 below, which
closed the rest of the board's vias-in-pads and put the requirement for these four
on a fabrication note. Confirming the fill-and-cap option with the fabricator is the
one part of it that is not a drawing change.

### Issue 3 — local bypass loops

C18 and C20 sat 4.95 mm and 3.61 mm from their driver's VM pin and reached it only
through the In2 plane, 1.065 mm of core away from the In1 return. Both now sit
**1.33 mm away, directly across VM (pin 5) and GND (pin 7)**, and the loop closes
entirely in top copper: pin 5 → cap pad 1 → cap → cap pad 2 → pin 7. No plane hop.

| | C18 / U4 | C20 / U5 |
|---|---|---|
| position | (106, 111) → **(111.25, 114.25)** rot 90 | (120, 111) → **(119.25, 114.25)** rot 90 |
| VBAT pad to VM pad | 4.95 → **1.33 mm** | 3.61 → **1.33 mm** |

**The 0.5 mm pin pitch caps those runs at 0.3–0.35 mm** for their 1.3 mm, because OUT1
sits between VM and GND and needs 0.2 mm of clearance either side. That is about
2 mΩ, 4 mV and 4 mW at 1.47 A, and it cannot be widened without moving OUT1 off the
package midline, which the pinout does not allow.

**C21 moved to (119.3, 109.4)** because its old position at (113, 114) sat squarely in
the new OUT1 escape corridor. Two constraints shaped where it went, both worth
remembering:

- it kept **rot 90**. Changing a footprint's rotation while leaving its text fields
  alone raises a `lib_footprint_mismatch` warning, which is how the first attempt at
  (120.5, 117) rot 0 was caught.
- the **`IMU module and bracket reservation` keepout (x 120.5–145.5, y 113.5–138.5,
  footprints not allowed)** rules out the obvious spot right of C20. Tracks and vias
  are allowed there; footprints are not.

Silkscreen references for C18, C20, C21 and U5 were moved off the pads they would
otherwise have covered.

### Issue 4 — the motor-B pair (2026-09-21, second rework pass)

`MOT_B_1` ran at y ≈ 113 while `MOT_B_2` detoured through the regulator at
y ≈ 97–105, so the two were **7.2 mm apart on average and 9.7 mm at worst** and the
loop they enclose was **423.6 mm²** as first routed (347.9 mm² after the issue-1–3
pass, which widened them but did not move them together).

`rework.py` now routes `MOT_B_1` first, samples its finished polyline, offsets each
sample 1.15 mm to the side `MOT_B_2` has to end up on, and routes `MOT_B_2` through
those points as waypoints. A waypoint that cannot be reached is skipped rather than
failing the net.

| | first routed | after issues 1–3 | now |
|---|---:|---:|---:|
| enclosed loop area | 423.6 mm² | 347.9 mm² | **83.4 mm²** ¹ |
| pair separation, mean / worst (x < 149) | — | 7.17 / 9.65 mm | **1.39 / 5.27 mm** |
| motor copper to `REG_EN` | 0.27 mm | 1.00 mm | **8.51 mm** |
| motor copper to the SW node | 0.28 mm | 1.33 mm | **6.62 mm** |
| motor copper to `VSYS` at U3 | 0.28 mm | 5.52 mm | **9.00 mm** |

¹ 111.5 mm² when this pass landed; the issue-5 rework moved C7/C11, which let the
fan-out be retuned. Loop area is measured by `tools/autoroute/loop.py`.

The regulator is now decisively out of the motor current's way, which was the other
half of the finding.

**U5 was deliberately not moved**, which is the review's first suggestion. Three
things argue against it, and they are worth recording because the idea will come back:

- **The In2 VBAT island stops at x = 127** and J9 is at x = 158. A driver next to J9
  would be off the motor supply plane entirely, so VM would need either a long trunk
  or the island extended east across the In2 3V3 pour that feeds J4–J7, J9.5, the
  encoder pull-ups and U1.
- **The space west of J9 is the buck output** — L1, C7, C11. Moving U5 there puts a
  switching driver hard against the regulator, which is the opposite of the placement
  partition the stackup section calls for, and it would undo the clearances above.
- **It splits the motor region.** D6, the bulk capacitance and the battery entry are
  all at the other end of the board; the partition only works while the motor drive
  stays in one corner.

**Two costs, both recorded rather than hidden:**

- `MOT_B_2` is longer — 48.6 → 55.0 mm here, 59.4 mm after the issue-5 retune — so
  the motor-B pair's resistance goes 61.5 → 68.1 mΩ: **+10 mV and +14 mW** at the
  1.47 A limit. Trivial against a 5× loop reduction.
- **Motor copper within 0.6 mm of the BNO08x SPI nets doubles, 5.0 → 11.0 mm**,
  because the corridor the pair now shares passes under J10's fan-out. That total is
  ~13 separate encounters of 0.2–2.0 mm — crossings and brushes, not a parallel run —
  and the longest is against `GPIO16`, which is the module's RST line with a 10 kΩ
  pull-up, not a clock or data line. The trade was taken deliberately: coupling into
  `REG_EN` trips a comparator and stops the robot, while a disturbed SPI word is
  something firmware can detect and retry.

**Motor A was measured with the same mechanism and gained nothing** (103.3 mm² either
way), so U4 is left unpaired. The reason is structural: both of its outputs have to
leave the WSON on the east side, while J8's two motor pins sit either side of the
driver in x, so `MOT_A_2` has to round U4 however it is routed. Do not re-attempt this
without moving U4 or J8.


### Issue 5 — the buck power stage (2026-09-22)

Four separate complaints, all about the regulator block being spread out rather
than wrong. Fixed by moving six parts and hand-routing the block; `rework.py`'s
`buck_block()` lays every track before it searches for a single via, because a
stitching via dropped into a corridor a later track needs is how the first
attempt shorted SW to GND under the package.

| | before | after |
|---|---:|---:|
| SW node copper area | 5.17 mm² | **3.57 mm²** |
| SW node on B.Cu | 2.55 mm | **0 mm** |
| SW node vias | 2 | **0** |
| C6 (BST) pad to U3.6 | 4.15 mm | **2.25 mm** |
| BST net track | 3.72 mm | **2.11 mm** |
| U3.4 return via ↔ C17 return via | 5.88 mm | **0.95 mm** |
| L1.2 → C11.1 through copper | *none* — plane only | **6.95 mm on F.Cu** |
| C7.1 → C11.1 | 4.00 mm | **2.30 mm** |
| FB / 3V3 copper to SW or BST | 0.27 mm | **2.10 mm** |
| VSYS copper to SW or BST | 0.83 mm | **2.07 mm** |

Six parts moved: **C6** (140, 91) → (139.5, 93.3), **C17** (136, 96) rot 90 →
(139, 98.6) rot 0, **C7** (147, 100) → (147, 99), **C11** (147, 104) →
(147, 101.3), **R8** (137, 100) → (136.6, 100.6), **TP4** (143, 100) →
(141.9, 99.6).

**The input capacitor now straddles the package.** U3 is a TSOT-23-6 with
FB/EN/IN down the left edge and GND/SW/BST down the right, so IN (pin 3) and
GND (pin 4) sit at the *same y on opposite sides*. C17 therefore goes underneath,
spanning the two, which is the tightest input loop this pinout allows. The metric
the review cited — the distance between C17's return via and U3's — goes from
5.88 mm to 0.95 mm, and U3.4 now has its own via 1.11 mm from the pin, hand-placed
because the search has no room left between the C17 pad, the TP4 stub and the two
B.Cu signal runs that pass under the package.

**TP4's back-layer branch is gone.** It was an F.Cu stub, two vias and 2.55 mm of
B.Cu hanging off the switch node; it is now a single 3.2 mm top-layer stub to a
pad that sits clear of the inductor body and can still be probed. The node has no
vias at all and 31 % less copper. TP3 (the probe ground) stayed at (142, 104),
4.4 mm away — within reach of a scope ground spring.

**The bootstrap capacitor could not go where it belongs.** BST (6) and SW (5) are
adjacent pins on the right edge, so the ideal spot is a vertical 0603 straddling
them — but **L1's courtyard starts 0.45 mm past U3's**, leaving nothing there.
C6 went above the package instead, with its SW pad pointing at L1 and its BST pad
at U3.6. That halves the BST run rather than perfecting it. Moving L1 east would
buy the ideal placement at the cost of a longer SW island, which is the wrong
trade — the island is the primary radiator and the bootstrap carries gate charge.

**The output filter is now one top-layer run.** Before, L1.2, C7.1 and C11.1 each
tapped the In2 3V3 pour independently and **no copper path joined them at all** —
`loop.py`'s path finder reports "no path" on the old board, which is the sharpest
statement of the review's complaint. Now L1 → C7 → C11 is a 0.8 mm F.Cu run, with
the plane tapped at the capacitors.

**Feedback has a dedicated sense line.** U3.1 used to reach the 3V3 plane through
a via 1.2 mm from BST. It now runs as its own 0.2 mm trace round the south of the
block to **C11.1, the far output capacitor** — about 21 mm, which is long, but it
never comes within 2.1 mm of SW or BST where the old tap was 0.27 mm away. For a
fixed-output part FB is the output sense into a ~1 MΩ internal divider, so it is
noise, not DC drop, that decides where it should run.

**`/VSYS` is pinned to the corridor north of the buck** by a waypoint. Left to
itself A* prefers a shorter path that threads the 8.4 V input rail straight
between L1 and C7/C11; it now enters the block only as the 4.4 mm IN→C17 leg and
the bulk feed from C12.

**One thing got worse and is not hidden:** `REG_EN` copper now passes **0.99 mm**
from switching copper where it was 2.12 mm. *(Corrected by issue 8: measured
exactly, the EN via under the package is **0.40 mm** from the SW pin. 0.99 mm was
not the closest pair. The issue-8 rule set guards 0.35 mm.)* Its via moved out of U3.2's pad —
which is review issue 6's defect, so that part is an improvement — into the
0.95 mm gap between the pin columns, the only spot left once vias are barred from
pads. With the In1 plane 0.2 mm below both, a via-to-trace gap of 1 mm is not a
coupling problem, but the real fix is the standing layout rule to put R8 and C13
next to U3.2, which needs the EN network re-placed and is not part of this issue.

**Motor B improved as a side effect.** Moving C7/C11 changed what `MOT_B_2` had
to route around, so the pair's fan-out was retuned (`skip_end` 3.0 → 1.5 mm): the
enclosed loop goes **111.5 → 83.4 mm²**, at the cost of 4.4 mm more `MOT_B_2`
(55.0 → 59.4 mm, 34.6 → 37.3 mΩ).

**A KiCad file-format trap, recorded because it cost a debugging cycle.** Every
text *and pad* inside a footprint stores its angle in the board frame. Rotating
only the footprint's own `(at …)` leaves the pads behind — C17's 0.9 × 0.95 mm
pads silently stayed 0.95 × 0.9 — and DRC reports it as
`lib_footprint_mismatch`, which reads like a library problem rather than a bad
edit. `pcbedit.move_footprint` now turns every `(at …)` in the block.


### Issue 6 — vias inside pad openings (completed 2026-09-22)

The first pass moved via **centres** out of pads, but that was not sufficient:
12 ordinary drill holes still overlapped solder-mask openings, and another 23
had less than 0.10 mm edge clearance. It also overlooked the independent,
unnumbered paste apertures over the four U4/U5 thermal vias. The earlier claim
that none of the remaining vias was under paste was incorrect.

The completion pass moves these **35 vias locally**, retaining every existing
track segment, all footprints, all via sizes and all 247 vias. Short connections
on the affected copper layers preserve the original routes. The P3 GPIO48
cleanup, USB routing and motor-output trunks are unchanged.

| Check | Before completion | After completion |
|---|---:|---:|
| Ordinary drill holes overlapping pad openings | 12 | **0** |
| Ordinary vias below the 0.10 mm opening clearance | 35 | **0** |
| Intentional thermal vias under paste | 4 | **4, explicitly filled/capped** |

`tools/autoroute/via_openings.py` checks complete drill circles against all front
and back mask and paste apertures, including paste-only pads, pad rotation and
rounded corners. It uses the pad's resolved mask/paste margins and fails on
unsupported geometry. The minimum measured ordinary drill-to-opening clearance
is **0.10 mm**; this is a board design allowance, not a quoted fabricator minimum.
`Pixy-M2.kicad_dru` also enforces 0.10 mm physical hole-to-SMD-pad clearance,
regardless of net. The only exceptions pair the four specified thermal vias with
their own U4/U5 exposed-pad apertures; the Python audit additionally requires
explicit fill and cap on each one.

**KiCad 10 supports filling and capping per via.** The earlier assertion that
these properties were board-wide only was wrong. Each 0.45/0.25 mm GND via at
(109, 113.6), (109, 114.4), (117, 113.6) and (117, 114.4) now has `(filling yes)`
and `(capping yes)`, verified after saving and reopening. Board-wide filling and
capping remain off. The `Dwgs.User` fabrication note requires resin fill and
copper cap, IPC-4761 type VII, for these four holes. The fabrication order must
include that process; tenting does not replace it.

`finish_issue6.py` replays the local repairs after the historical centre-based
pass and the P3 correction. Regeneration now audits apertures before replacing
the output board and stops if the expected geometry has changed. Always refill
zones and run DRC plus schematic parity afterward. The saved board has zero
unconnected items and zero parity issues; DRC still reports only the four known
J1 hole-clearance errors and the U1 library-footprint warning.

Measurements and validation: `layout/issue6-complete/README.md`.


### Issue 7 — the USB pair (2026-09-22)

D+/D− were ordinary 0.2 mm traces. They had varying separation, a D+ detour round
U2, and asymmetric layer changes. By the time issue 6 had finished, D− had 4 vias
and 8 mm on B.Cu, and the end-to-end skew was 8.08 mm. **Both polarities now run
as one pair, J1 to U1, entirely on F.Cu over the In1 plane, with no via anywhere
on the USB path.** `tools/autoroute/usb_pair.py` does it. `rework.py` runs it as
its last routing stage, after the issue-6 repairs, so no earlier stage changes.

| | before | after |
|---|---:|---:|
| USB vias / B.Cu copper | 4 / 8.01 mm | **0 / 0** |
| width, module-side gap | 0.20 mm, 0.25–0.35 mm | **0.25 mm, 0.15 mm** |
| J1 → U2 → U1 path, D+ / D− | 24.54 / 32.62 mm | **20.15 / 19.11 mm** |
| end-to-end skew | 8.08 mm | **1.04 mm** (≈ 6 ps) |
| U2 GND pin to plane via | 1.11 mm | **0.71 mm** |

**U2 turned 90°**, (154, 148) rot 0 → (153.5, 149.5) rot 90. That is the change
that makes a clean pair possible. The USBLC6-2SC6 is flow-through: D− enters on
pin 1 and leaves on pin 6, D+ enters on 3 and leaves on 4, and each pair of pins
sits on opposite sides of the package. At rot 0 that flow ran west→east across a
signal travelling south→north-west, so D+ had to wrap round the part. At rot 90
the connector row (1, 2, 3) faces J1 and the module row (6, 5, 4) faces U1, with
D− on the west in both. **Do not turn U2 back without re-routing the pair.**

**U2's middle pins leave under the body.** GND (2) and VBUS (5) sit between the
two lines of the pair, so both use the 1 mm gap between the pin rows:

- GND goes to a plane via *under the package* at (153.0, 149.5), which clears
  pins 1, 5 and 6 by 0.22 mm of copper and every pad opening by ≥ 0.37 mm of
  drill.
- VBUS runs east, between pins 3 and 4, to the existing feed from F2.

**J1's USB-C pads alternate D−, D+, D−, D+** (B7 A6 A7 B6), so one polarity has
to cross the other. Both crossings stay on F.Cu:

- D+ bridges A6 → B6 over the top of A7.
- D− loops A7 → B7 under the bottom of A6, where the old route used a via.

Each join is a ~1.4 mm stub, which is irrelevant at 12 Mbps. The pair is 0.25 mm
wide there too; that leaves 0.225 mm to the neighbouring pads.

**The 1.04 mm of remaining skew is geometric, not an oversight.** Two sources
make it:

- D− is the inner line at both 45° bends, so it is shorter there.
- D+ climbs into U1 pin 14.

The skew is below the 1.25 mm (50 mil) figure commonly used for *High* Speed
matching, and the ESP32-S3 PHY is Full Speed only. **Do not add a serpentine**;
it would cost more coupling than it buys.

**CC1/CC2 were ripped and re-searched**, because their vias sat where the pair now
runs. They cross under the pair on B.Cu with the In1 plane in between. While
they were routed, the pair was inflated by 0.15 mm, so their F.Cu copper and
vias keep that extra distance, except in J1's pad field. CC1 is 4.92 → 5.81 mm;
CC2 is 13.57 → 8.53 mm.

**Enforced by rules, and each rule was tested by breaking it.** The new rules
are:

- a **`USB` netclass** in `Pixy-M2.kicad_pro`, with 0.25 mm width, a 0.15 mm
  gap, and 0.15 mm clearance *inside* the class (0.2 mm to everything else).
  It matches `/USB_D*` and `Net-(J1-D*`.
- a **width rule** in `Pixy-M2.kicad_dru`: 0.24–0.26 mm.
- a **layer rule**: no track or via of a USB net on B.Cu.
- a **coupling rule** on `/USB_D±`: the gap must be 0.14–0.16 mm, with at most
  4 mm uncoupled. The routed pair has 3.4 mm uncoupled, forced by U2's 1.9 mm
  and U1's 1.27 mm pin pitch.

KiCad pairs nets by a trailing ±, so the connector-side nets get the width and
layer rules but not the coupling rule. Each rule fired on a copy of the board
with the matching defect: a 0.20 mm segment, a D− loop on B.Cu, and D− spread
0.10 mm. This covers the USB half of review issue 8. The netclass and rules
belong to this fix, because they are the geometry it chose.

**Impedance is a calculation, not a fab figure.** `tools/impedance/zdiff.py` is a
2D field solver of the coupled microstrip, and it gives:

| prepreg | mask 10 µm | mask 25 µm |
|---|---:|---:|
| 0.200 mm | 93.0 Ω | 89.5 Ω |
| 0.2104 mm | 94.2 Ω | 90.6 Ω |

At its default 5 µm mesh it reads about 1.5 Ω high. IPC-2141 gives 90.4 Ω. Call
it 88–94 Ω. Confirm with JLCPCB's calculator, or order impedance control.

DRC is unchanged: 0 unconnected, 0 parity issues, and only the four J1
`hole_clearance` errors and the U1 warning. The aperture audit passes, with 243
vias, down from 247. A track/via diff against the issue-6 board touches only the
USB nets, CC1, CC2, and U2's own GND and VBUS stubs. Motor loop areas are
unchanged at 103.3 / 83.4 mm².

**Not touched:** the shield return (J1 shell → C8/R5), which the review lists as a
separate observation, still takes its long B.Cu path behind U2.

Measurements and validation: `layout/issue7-usb/README.md`.


### Issue 8 — the rule set (2026-09-22)

Review issue 8 said the project rules did not encode its routing requirements.
There was only the Default netclass and a 0.15 mm global minimum, so narrow
copper anywhere passed DRC. Issue 1 added the `Motor` class and trunk rule;
issue 7 added the `USB` class and its width, layer and coupling rules. **This
pass does the rest, and fixes the copper the new rules caught.** The copper
stage is `tools/autoroute/issue8.py`, which runs after `usb_pair.py`.

**New netclasses** in `Pixy-M2.kicad_pro`:

- `Battery`: `/VBAT_RAW`, `/VBAT_FUSED`, 1.0 mm.
- `Power`: `/VBUS`, `/VSYS`, `Net-(F2-Pad1)`, 0.6 mm.

`/VBAT` is in neither. Its current runs in the In2 island, and its tracks are
pad-to-plane stubs sized by pin pitch, so a width rule on it would test nothing.

**New rules** in `Pixy-M2.kicad_dru`:

| rule | floor | exception |
|---|---|---|
| Signal minimum width | every track 0.2 mm | `Motor pin escape` areas (DRV8231A pin fields) |
| Power path width | 0.5 mm | `Power pin escape` area: U2's VBUS pin, out under the package |
| Battery path width | 0.8 mm | none |
| REG_EN clear of the switch node | 0.35 mm | — |
| Sense nodes clear of motor and switch copper | 5 mm for `REG_EN` to motor, and for `VBAT_SENSE` to motor, SW and BST | — |
| IPROPI clear of motor outputs | 0.25 mm | — |

**Three KiCad behaviours fix how these rules must be written.** Each was
verified, and each will bite whoever edits them next:

- **The board-setup minimum track width is absolute.** A custom rule cannot
  relax it, so it stays at 0.15 mm, what the pin fields need, and the 0.2 mm
  floor is a custom rule. Raising the board setting to 0.2 mm breaks the pin
  fields.
- **The later of two rules setting the same constraint wins.** "Signal minimum
  width" is therefore the **first rule in the file**. Move it below the motor,
  USB, power or battery rule and it silently relaxes that rule to 0.2 mm.
- **`enclosedByArea` tests the whole track outline, round caps included.** A
  segment ending exactly on an area edge is *not* enclosed.

**The clearance rules are floors just under what the board achieves, not the
constraints in "Layout constraints".** Two sit well below them:

- **`REG_EN`**: 0.40 mm from the SW pin, via the EN via under U3; see issue 5.
- **IPROPI**: 0.29 mm from a `MOT_A_2` trunk near U4.

They stop further erosion; they do not certify either constraint.

**Copper the rules required:**

| | before | after |
|---|---:|---:|
| track below 0.2 mm | 219.4 mm | **8.7 mm**, all inside the pin fields |
| `/VBUS` F2 → D1 | 0.24 mm, 105.4 mΩ | **0.6 mm, 44.4 mΩ** |
| `Net-(F2-Pad1)`, J1.A9 / J1.A4 → F2 | 9.7 / 32.7 mΩ | **4.0 / 8.2 mΩ** |
| `/VBAT_FUSED` R14 tap | 0.2 mm | 0.8 mm |

- **The five 0.15 mm nets** were `GPIO39/40/41` (motor IN) and `GPIO2/10`
  (IPROPI). The router had used 0.15 mm end to end because it takes one width
  per net. Each segment is split at the pin-field areas, shrunk by 0.1 mm for
  the caps, and widened outside them. One GPIO41 corner doglegs round the GPIO47
  via that issue 6 moved.
- **The USB supply carries the whole board on USB**, yet it was 0.24 mm despite
  the width table above. It is re-routed at 0.6 mm. **The D3 tap is pinned to
  its old corridor along the top edge.** Left free, A* ran it 0.5 mm from C6's
  switch-node pad, and that tap feeds `REG_EN` through R9.
- **`Router.route_waypoints` can leave a leg unconnected.** Each waypoint is
  offered on both layers, so consecutive legs can meet on different layers with
  no via. The MOT_B_2 pairing happens not to hit this; `issue8.py` pins its
  waypoints to F.Cu.
- **The router's via-to-pad bar is too small for issue 6's floor.** It keeps via
  centres 0.15 mm from pads, which lets a drill touch the mask opening; this
  landed 0.04 mm from both J1 VBUS pads. `issue8.py` rebuilds the bar at drill
  radius + 0.10 mm + one grid step, for its own stage only.

DRC is unchanged: 0 unconnected, 0 parity issues, and the same five
pre-existing items. The aperture audit passes with 243 vias. Every new rule
fired on a copy of the board broken to violate it, including the motor rule
under the new generic rule. A track/via diff against the issue-7 board touches
only the eight nets above. Exact clearances, from `layout/issue8-rules/clearmin.py`,
are identical before and after.

**Measuring clearance with DRC needs care.** With a large threshold, DRC
reports the first violating shape pair it meets, not the closest. A single
20 mm threshold gave 0.95 mm for `REG_EN` and 0.75 mm for IPROPI, both wrong.
`clearmin.py` descends from several thresholds.

Measurements and validation: `layout/issue8-rules/README.md`.


### What this pass did not touch

- **Review issue 4** was still open after this pass and is closed by the next one.
- **Review issue 5** was open after this pass and is closed by the next one.
- **Review issue 6** was open after this pass and is closed below.
- **Review issue 7** (the USB pair) was open after this pass and is closed above,
  together with the USB half of issue 8.
- **Review issue 8** (the rule set) was open after this pass and is closed above.
- `GPIO2` / `GPIO10` (IPROPI) still pass within **0.29 mm** of motor copper near U4,
  essentially unchanged from 0.26 mm (confirmed exactly by issue 8, which guards
  0.25 mm). The review's own note applies: their 1.5 kΩ
  source impedance is not `VBAT_SENSE`'s 150 kΩ, so validate this on hardware rather
  than assuming it is a fault.

## Layout constraints (written before layout; the routing above does not satisfy all of them)

Read "Board stackup" first — several rules below assume the L2 plane exists.

- Put **F1 immediately after BT1** and F2 immediately after J1's joined VBUS pins.
  Keep unfused copper short; every downstream branch must go through its fuse.
- Put **SW3 at an accessible edge**, marked BAT ON/OFF (USB can still power the
  controller). Route only Q1 gate control to it, not motor current. Keep R14 close
  to Q1 and connect all three source and all four drain pads with adequate copper.
- Place **D6 next to the motor drivers** — it used to be "near J2.19–22", but the
  load it protects is now on this board. Put it across switched `VBAT` with a short,
  wide GND return, in the motor region of the partition. Keep its surge-current loop
  away from the ADC and MCU ground paths. Size the battery/return copper for the
  final load and F1's fault-clearing interval (issue 17).
- **Put the motor drivers, their bulk capacitance and D6 in one corner**, as far
  from U1, `VBAT_SENSE` and the ToF I2C as the outline allows, with their power loops
  closed locally on L1 over the L2 plane. This placement *is* the noise strategy
  (issue 16) — there is no plane split to fall back on.
- **Antenna keep-out is non-negotiable.** The module's antenna must overhang a board
  edge with zero copper on every layer in the keep-out region — no traces, no pours,
  no components.
- Place U3 as far from the antenna as the outline allows.
- The **C12 → U3.3 → U3.4 loop must be as tight as physically possible.** This is
  the highest-di/dt loop on the board. **Closed 2026-09-22 by C17, not C12: the HF
  bypass now straddles IN (pin 3) and GND (pin 4) under the package and its return
  via sits 0.95 mm from U3.4's, where the two were 5.88 mm apart. C12 stays outside
  as bulk.**
- Keep the **SW copper island small** — it is the primary radiator. Note the SRP5030T
  is a 5×5mm part, so its SW-side pad is already a substantial copper area. Place the
  inductor tight against U3 and do not let that pad grow into a pour. **2026-09-22:
  3.57 mm² of copper, entirely on F.Cu, no vias. L1's courtyard starts 0.45 mm past
  U3's — that gap is why the bootstrap cap sits above the package rather than across
  BST/SW, and it is why L1 must not be moved east to make room.**
- **TP4 sits on that same SW island, so it fights the rule above.** Hang it off the
  U3.5–L1.1 run as a short stub on the *quiet* side, away from the L1 pad; do not
  centre the island on it and do not widen the trace to reach it. If the island ends
  up marginal, TP4 is the part to drop — the scope probe can go on the L1 pad
  instead. Keep its ground return short: TP3 (GND) should be within probe-tip reach
  of TP4, otherwise the measurement it exists for will be worthless. **Done
  2026-09-22: a single 3.2 mm top-layer stub, no vias, no back-layer branch; TP4 sits
  clear of the inductor body and TP3 is 4.4 mm away.**
- Route the **FB trace** back to the output caps away from SW and L1. **Done
  2026-09-22: a dedicated 0.2 mm trace from U3.1 round the south of the block to
  C11.1, never closer than 2.1 mm to SW or BST. It was a plane via 1.2 mm from BST.**
- Keep the **`REG_EN` node away from SW and L1**. It is a ~20kΩ-impedance node sitting
  1.2V above a comparator threshold, so it is easy to couple into. Put R8 and C13
  physically next to U3.2 and run the long leg from R7/R9 into them, not the reverse.
  **Not met: the EN via under U3 is 0.40 mm from the SW pin (issue 8). DRC guards
  0.35 mm so it cannot get worse; the fix above is still outstanding.**
- **`VBAT_SENSE` is worse — 150kΩ.** Same rule, more strictly: C14 goes hard against
  U1.39 and R10/R11 sit behind it, so the high-impedance run is as short as possible.
  Keep the whole node away from SW, L1 and any motor current on `VBAT`, and do not
  route it as a long thin trace beside a switching node.
- USB D+/D− as a **90Ω differential pair** over unbroken ground reference. **Done
  2026-09-22 (issue 7): 0.25 / 0.15 mm on F.Cu over In1, no vias, J1 to U1.**
- Ground the module's thermal pad with a via array.
- **D4 (power LED) goes where a user can see it**, near the USB-C port or a board
  edge. With the daughterboard gone nothing shadows the board any more, so the old
  "not under the mezzanine" caveat is void — but the chassis, wheels and motors will
  now obstruct parts of the board instead, so check visibility against the mechanics.
  Same for D5. Neither is timing- or noise-critical, so placement is otherwise free;
  just keep both out of the antenna keep-out.
- **J4–J7 go at the board edges, facing the walls they sense**, with their cable
  exits pointing outward — they are side-entry parts, so the connector body sets the
  cable direction. Keep all four out of the antenna keep-out. The daughterboard no
  longer competes for edge space, but the motors, wheels and the drivers' thermal
  copper now do — edge budget is the scarce resource in this layout, not area.
- Put **C15 in the middle of the four connectors**, not next to the regulator: it is
  there to serve the pulsed VCSEL load at the cable ends. C16 goes hard against
  whichever connector is furthest from C15.
- Route **SDA/SCL as a pair with a ground reference**, and keep R15/R16 near U1
  rather than out at the connectors — "once per bus, near the host". The XSHUT lines
  are DC and need no care beyond not running them alongside the SW node.
- **Silkscreen J4–J7 with pin 1 and the sensor position** (FL/FR/L/R, or whatever the
  mechanical design calls them), and silkscreen which XSHUT GPIO each one carries —
  the address assignment order is a firmware constant that has to match the wiring.
  Pin 1 is **VCC**, not GND: the connector follows the module's header order, so a
  cable built "the usual way round" with GND first will put 3.3V into the sensor's
  ground pin. Mark pin 1 unambiguously on the silkscreen.
- **U4/U5 thermal pads carry the heat, and the WSON-8 has almost no other path.**
  RθJA is 66.5°C/W and the datasheet asks for "large ground planes on multiple layers
  and multiple nearby vias". Put a dense via array under each pad into L2, and do not
  neck the pad's connection with thermal relief spokes — this is a heat path, not a
  solderability concern. **Built by the 2026-09-21 rework, as far as the geometry
  allows: 2 in-pad vias (the hole-to-hole rule caps it there), 4 more within 3 mm, a
  0.8 mm neck out of the pad and an F.Cu ground pour. "Dense" is not achievable in a
  0.9 × 1.6 mm pad — do not re-specify it without changing the package.**
- **Keep C18/C20 (0.1µF) hard against each driver's VM pin**, closer than the 22µF
  bulk. The bulk caps C19/C21 go next, and both must sit in the motor region of the
  placement partition, not near U1 or the ADC nodes. **Done 2026-09-21: both caps are
  1.33 mm from their VM pin, across pins 5 and 7, with the loop closed in top copper.
  C21 moved to (119.3, 109.4) to clear the OUT1 escape; C19 is unchanged.**
- **`MOT_A_1/2` and `MOT_B_1/2` are the only high-di/dt nets outside the buck.**
  Route each pair together and keep the loop from the driver through the connector
  tight. Size them for the 1.47A regulated limit, not the free-run current.
  **Sized and paired 2026-09-21. 0.8 mm trunks enforced by the `Motor` netclass and
  `Pixy-M2.kicad_dru`; `MOT_B_1`/`MOT_B_2` now run as a pair (loop 423.6 → 111.5 mm²)
  without moving U5. `MOT_A_1`/`MOT_A_2` cannot be paired usefully — see issue 4
  below for why, and do not re-try it.**
- **`GPIO2` and `GPIO10` carry IPROPI analog current**, not logic. Keep them short,
  away from the motor outputs and the SW node. They no longer run anywhere else —
  J2/J3 are gone, so there is no header stub on them to keep short.
- **Place J8/J9 facing their motors** with the cable exit pointing at the motor, and
  keep them out of the antenna keep-out. Silkscreen pin 1 and which motor each one
  is — the pinout mirrors the encoder module, so a cable built "the usual way round"
  will put motor voltage into the encoder.
- **J11 and TP5–TP9 go where a hand and a probe can reach them** — a board edge, not
  under the chassis or behind a motor. J11 is the only way back in if USB-Serial-JTAG
  is ever disabled, so burying it defeats the point. Keep TP9 within probe-tip reach
  of TP5–TP8, the same rule TP3/TP4 already follow.
- **J10 (IMU) placement is mechanical, not electrical.** A fusion IMU should sit as
  near the robot's centre of rotation as the outline allows, and its cable should not
  run alongside the motor outputs — `MOT_x_1/2` are the only high-di/dt nets outside
  the buck, and a 3MHz SPI cable beside them is asking for trouble. Give SCK a ground
  return: J10 pin 2 (GND) is deliberately adjacent to pin 3 (SCK), so the cable should
  keep that pair together.
- **Silkscreen J10 with "PS1 HIGH = SPI"** next to pin 1. A stock BNO08x breakout
  ships in I²C mode and will not answer until that jumper is changed; the board gives
  no other hint.
- **Silkscreen the test points** with their net names (VBAT, 3V3, GND, SW). An
  unlabelled 1.5mm pad is not a test point. Per issue 12, also silkscreen any exposed
  strapping pin on whatever debug header survives issue 15.

## Working notes for this session

- Treat the extracted netlist above as ground truth over anything inferred from a
  rendered schematic view.
- **ERC passing means nothing here.** Do not use "ERC is clean" as evidence that a
  change is correct.
- When changing a component, update **Value, Footprint, and any datasheet/MPN field
  together.** Half-updated components are how the wrong part gets ordered.
- Re-run the netlist extraction after structural edits and diff against the table
  above rather than trusting that an edit did what was intended.
- **Also render and look at it.** A netlist diff cannot see overlapping text or a
  wire routed through another net's junction. Both bugs happened while adding the
  issue-2 network and both were caught visually:

  ```
  kicad-cli sch export svg --exclude-drawing-sheet --black-and-white -o /tmp/svg Pixy-M2.kicad_sch
  rsvg-convert -z 8 -b white /tmp/svg/Pixy-M2.svg -o /tmp/sheet.png   # ~30 px/mm
  ```

  Watch for wires crossing a point where two other wires meet end-to-end: KiCad
  treats that endpoint as a connection, so a crossing there silently shorts two nets.
  Symbol *fields* inherit the symbol's rotation — a field on a 90°-rotated part needs
  its own angle set to 90 to render horizontally. **Field `justify` rotates with it
  too, and flips:** on a 90°-rotated symbol `justify left` renders *right*-justified,
  so the stored `(at x y)` becomes the text's right-hand edge and the text grows
  leftward into the symbol. Write `justify right` to get text starting at the anchor.
  This was caught on D4/D5, whose Value text landed on top of the LED body the first
  time round; it is invisible in a netlist diff, so render and look.
- **Check the board, not just the schematic.** Zones are only filled by KiCad, so a
  CLI DRC without a refill reports every plane-connected pad as unconnected:

  ```
  kicad-cli pcb drc --refill-zones --save-board --format json -o /tmp/drc.json Pixy-M2.kicad_pcb
  ```

  `--save-board` writes the filled zones back, so the file you commit shows the pours
  as KiCad will. Read `unconnected_items` as well as `violations` — a net that is not
  routed at all shows up only there.
- **`Driver_Motor:DRV8231ADSG` is patched in this file.** Its cached copy has OUT2
  retyped from `power_in` to `output` to fix a stock-library bug. Never run "Update
  Symbols from Library" on U4/U5 without re-applying it — see issue 15.
- **Ask before deleting connector pins or renaming nets.** J2/J3 were deleted on
  2026-09-20, and the reason it was safe is worth remembering as the rule: every GPIO
  they carried already terminated on a real part first. Deleting a connector before
  its nets have somewhere else to go strands them and buries real ERC warnings under
  noise.
