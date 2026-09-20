# Pixy-M2 — Micromouse Controller PCB

Context for a Claude Code session working on this KiCad project via the KiCad MCP server.

## What this board is

Controller PCB for a micromouse robot — a **single-board design**. An
**ESP32-S3-WROOM-1** module is soldered directly to it. The board carries the MCU,
USB-C programming/power port, a buck converter, four JST-SH connectors (J4–J7) for
**off-board VL53L0X time-of-flight wall sensors**, and — once the parts are chosen —
the **motor drivers, encoders and IMU on the board itself**.

**There is no daughterboard.** Decided 2026-09-20, before layout started. It replaces
the earlier two-board architecture in which motors, motor drivers and the IMU mated
through two 22-pin headers (J2, J3). Those headers are still in the schematic and
have not been removed yet — see issue 15.

Power comes from a **2S LiPo (7.4V nominal, 8.4V full charge)** via an XT30 connector,
F1 battery polyfuse and Q1/SW3 load switch, then is diode-OR'd with fused USB 5V
and down-converted to 3.3V by an AP63203WU buck. `VBAT` is the switched, fused
motor/high-current supply; `VBUS` is downstream of the USB polyfuse F2.
The 2S pack is charged separately; no onboard battery charger is required.

- Schematic: `Pixy-M2.kicad_sch` — single flat sheet, no hierarchy
- KiCad 10.0
- **PCB layout has not been started.** It will be **4 layers** — see "Board stackup".

## Current status

The **controller section** of the schematic is complete — MCU, USB, power path,
protection and ToF connectors. **ERC reports 0 errors and 2 warnings.** Both are
`isolated_pin_label` (label on a single-pin net): `GPIO45` and `GPIO46` — the two
remaining unused strapping pins, see issue 12. (`GPIO3` cleared when the issue-13
status LED took it.) Even so, ERC proves very little here: most issues below survive it, because
ERC does not check footprint assignment, component ratings, saturation current, or
whether a labelled header pin actually goes anywhere.

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
- **All 41 module pins land on a net.** Two of them land on a *single-pin* net
  though — `GPIO45` and `GPIO46` — see issue 12. (`GPIO3` was the third until the
  issue-13 status LED took it.)
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
| `ESP_3V3` | C1.1, C2.1, C7.1, C11.1, C15.1, C16.1, J3.1, J3.2, J4.1, J5.1, J6.1, J7.1, L1.2, R2.1, R12.1, R15.1, R16.1, TP2.1, U1.2, U3.1(FB) |
| `VSYS` | C12.1, D1.1(K), D2.1(K), U3.3(IN) |
| `REG_EN` | C13.1, R7.2, R8.1, R9.2, U3.2(EN) |
| `VBAT_RAW` | BT1.1(+), F1.1 |
| `VBAT_FUSED` | F1.2, Q1.1/2/3(S), R14.1 |
| `VBAT` | Q1.5/6/7/8(D), D2.2(A), D6.1(K), J2.19, J2.20, J2.21, J2.22, R7.1, R10.1, TP1.1 |
| `Net-(Q1-G)` | Q1.4(G), R14.2, SW3.2(common) |
| USB connector (`Net-(F2-Pad1)`) | J1.A4/A9/B4/B9, F2.1 |
| `VBUS` | F2.2, D1.2(A), D3.2(A), U2.5 |
| `CHIP_PU` | C3.1, C4.2, J3.3, R2.2, SW1.1, U1.3(EN) |
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
interrupt pin — issue 14).

The four ToF connector nets (issue 14):

| Net | Members |
|---|---|
| `GPIO9` (SCL, conn. pin 3) | U1.17, J3.15, J4.3, J5.3, J6.3, J7.3, R16.2 |
| `GPIO8` (SDA, conn. pin 4) | U1.12, J3.14, J4.4, J5.4, J6.4, J7.4, R15.2 |
| `GPIO4` (XSHUT 1, conn. pin 6) | U1.4, J3.4, J4.6 |
| `GPIO5` (XSHUT 2, conn. pin 6) | U1.5, J3.5, J5.6 |
| `GPIO6` (XSHUT 3, conn. pin 6) | U1.6, J3.6, J6.6 |
| `GPIO7` (XSHUT 4, conn. pin 6) | U1.7, J3.8, J7.6 |

`VCC_USB_5V` has been **renamed `VSYS`**. It is the diode-OR output and sits at up to
**~8.1V** on a full pack, so the old "5V" name was actively misleading. `VBAT` and
`VBUS` are now explicit labels too, not auto-generated net names — do not let them
revert to `Net-(D1-A)` style names.

Header assignments have moved on from the original extraction. J2 carries GPIO2, 21,
35–44, 47, 48, GND on 1/6/12/18, and **VBAT on 19–22**; the dead `GPIO19`/`GPIO20`
pins are gone (issue 4 resolved). J3 carries GPIO4–18, 3V3, CHIP_PU, and GND on
7/12/17/22. GPIO0, GPIO3, GPIO45 and GPIO46 are on no header at all — though
`GPIO3` now drives the issue-13 status LED, so only GPIO45/46 are truly unused.

**These two headers are now placeholders.** With the daughterboard gone they no
longer terminate anything real; they are the parking spot for 29 GPIOs until the
on-board motor drivers, encoders and IMU exist to claim them. Do not treat the
J2/J3 pin assignments below as an interface contract any more — issue 15.

**`GPIO4`–`GPIO9` are claimed by the ToF sensors (issue 14) and are also still on
J3.4/5/6/8/14/15.** Nothing attached to J3 may *drive* any of those six.
`GPIO8`/`GPIO9` remain a shared I2C bus — an on-board IMU can sit on it as a second
device rather than consuming its own pins.

**Free GPIO budget for the on-board peripherals: 23.** J2's 14 (GPIO2, 21, 35–44,
47, 48) plus J3's 9 that the ToF sensors did not take (GPIO10–18). A typical
two-motor micromouse spends roughly 13–15 of those — two driver channels, two
quadrature encoders, an IMU interrupt, a fan, and a driver fault/sleep line or two —
so the budget is comfortable but not unlimited. Count it properly before promising
pins to anything (issue 15).

## Open issues

Ordered by severity. **Resolved since this list was written: 1 (L1 part), 2 (UVLO),
3 (U1 footprint), 4 (dead header pins), 5 (battery sense), 6 (dissolved by the
single-board decision), 7 (switch/fuses/TVS added; battery fuse sizing remains
provisional), 11 (module variant), 13 (conveniences), 14 (ToF wall sensors).**

**Layout is blocked again, deliberately.** The 2026-09-20 single-board decision means
the part count and the board outline are not yet known, so there is nothing stable to
place. **Issue 15 now gates layout** — the motor drivers, encoders and IMU have to
exist in the schematic first. Issues 8–10, 12 and 16 do not gate starting layout;
issue 17's current budget gates *routing* the power path, which is earlier than the
pre-fabrication deadline it used to have.

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

The `5V0`, `GPIO19` and `GPIO20` header pins are gone. J2.19–22 now carry `VBAT` and
J3.21 carries `GPIO14`. No header pin is on a single-pin net.

Still dangling, but on the module rather than a header: `GPIO3` (U1.15), `GPIO45`
(U1.26), `GPIO46` (U1.16). These are the three remaining ERC warnings and are
covered by issue 12.

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
still thin".

**The single-board decision removes the question.** Motor return current now flows in
the L2 ground plane instead of through header pins, which is a change of kind rather
than degree. Nothing to do here.

If a reduced debug header survives issue 15, give it a ground pin next to each signal
group as ordinary good practice — but it carries no power return, so the old concern
does not transfer to it.

### 7. Power switch, fuses and TVS — IMPLEMENTED (2026-09-19)

Six components added. **F1's current rating is provisional:** the intended loads
are two coreless motors, four IR sensors and possibly a suction fan; their exact
part numbers, operating current and startup/stall current are not yet known.

```
 BT1+ -- F1 -- VBAT_FUSED -- Q1(S -> D) -- VBAT -- D2 -- VSYS
                    |           |          |-- J2.19-22, TP1
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
fuse temperature, both motor stalls, fan startup, pack short-circuit capability,
and the copper/header/wiring ratings. F1 is a thermal PPTC, not a hard 3A limiter:
its specified maximum trip time is 20s at 8A, and its hold current falls to about
2.31A at 60°C. Its 40A maximum fault-current rating must also suit the selected
pack. Do not increase F1 just to accommodate a fan without checking the entire
power path. F2 similarly does not enforce a USB host's negotiated current budget;
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

### 8. Capacitor voltage ratings are unspecified everywhere

Only **C13** (`0.1uF 50V`, added with the issue-2 UVLO network) carries a rating. On
a system that reaches 8.4V every cap needs one explicitly. Follow C13's precedent:
put it in the Value field, where a reviewer sees it on the schematic sheet.

- **C12** is the urgent one — it sits on the ~8.1V OR node (`VSYS`). Spec **≥25V**, and note that a 25V 10µF 0805 derates to roughly 3–4µF at
  that bias. The AP63203 wants ~2×10µF *effective* input capacitance: add a second
  bulk cap plus a 100nF right at U3.3.
- **C7, C11** (22µF 0805, 3.3V rail): spec 10V or 16V to survive DC-bias derating.
- Everything else: state the rating explicitly, minimum 16V on anything touching
  VBAT or the OR node.

### 9. Diodes are generic symbols with no part numbers

D1 and D2 still have Value `D_Schottky` in `Diode_SMD:D_SMA`. D2 carries the entire
system current from the battery — at 1A that is ~400mW dissipated and ~0.4V of
headroom thrown away.

**Fix:** spec a real part (≥3A, ≥30V, low Vf), or replace D2 with a P-FET
ideal-diode controller. D1 can stay a diode but still needs a real part number.

**D3 is already specified** — `BAT54W` / `Diode_SMD:D_SOD-123`, with a datasheet
field. It carries ~70µA, so it has no thermal or Vf constraint worth revisiting.
Follow its pattern when fixing D1 and D2.

### 10. Unnecessary series resistors on USB D+/D−

R3 and R4 (22Ω) sit between U2 and the module's USB pins. The ESP32-S3's internal
USB PHY is impedance-matched; Espressif's reference designs connect straight
through. Replace with 0Ω or remove.

### 11. Module variant — RESOLVED

U1's Value is now **`ESP32-S3-WROOM-1-N16`**: 16MB flash, **no PSRAM**. That is the
outcome the design needed — **GPIO35, GPIO36 and GPIO37** (module pins 28/29/30,
currently parked on J2.14/13/11) are consumed by octal PSRAM only on `-R8` parts, so
on an N16 they are genuinely free, and they count toward the 23-GPIO budget available
to the on-board peripherals. Do not substitute an `-N8R8` or `-N16R8` part without
first freeing those three pins from whatever issue 15 assigns them to — the budget
drops to 20.

### 12. Two unused strapping pins are left floating

Stale as written: GPIO45 and GPIO46 are **not** on the headers any more. They are
simply unconnected on the module (U1.26, U1.16), which is what the two remaining ERC
warnings are about. Internal weak pulldowns cover the floating case, so the board
boots — this is tidiness, not a fault.

**GPIO3 is no longer one of them.** It now drives the issue-13 status LED (U1.15 →
R13 → D5 → GND), which is exactly the use the table below sanctions.

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
interrupts later means running four traces to four of J2's free GPIOs (or wired-OR
to one, since the outputs are open-drain) — the connector and cable already fit.

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


### 15. On-board peripherals do not exist yet — BLOCKS LAYOUT (2026-09-20)

The single-board decision deleted the daughterboard from the plan but not from the
schematic. J2 and J3 are still there, 29 GPIOs still terminate on them, and there is
no motor driver, encoder or IMU anywhere in the design. **Deleting the headers is not
a standalone edit** — do it and the board has no motor interface at all and ~29 new
ERC warnings. The sequence is: choose the parts, add them, move the nets onto them,
*then* delete whatever header pins are left over.

None of these decisions exist in this project yet, and each one blocks the next:

| Decision needed | What it gates |
|---|---|
| Motor part number, gear ratio, stall current, rated voltage | Driver selection, F1 sizing (issue 17), `VBAT` copper width, bulk cap sizing |
| Motor driver part | GPIO count (PWM+DIR vs. dual-PWM), thermal copper area, whether current sense is wanted |
| Encoder type — magnetic on-shaft vs. optical | GPIO count, and whether the encoders can sit on this PCB at all or need a stub/flex at the motor |
| IMU part and bus | Whether it joins the ToF I2C on GPIO8/9 or takes its own SPI (4 more pins) |
| Suction fan — fitted or not | F1 sizing, a third driver channel, and the fan's own inrush |

**Mechanical gate, not just electrical:** with the motors on this board, the outline
is now set by the chassis — wheel positions, motor body clearance, ground clearance —
*and* it must still satisfy the antenna keep-out, four outward-facing ToF connectors,
an accessible SW3 and a reachable USB-C port. Check the combined footprint before
committing to the outline; this is the constraint most likely to force a rethink.

**Keep a small debug/expansion header.** Not 44 pins, but do not go to zero. Six to
ten spare GPIOs plus 3V3/GND costs almost nothing and is the difference between
bodging a fix and respinning the whole board — which is exactly the modularity the
single-board decision gave up. Size it once the peripherals above are placed and the
real GPIO surplus is known.

### 16. Motor noise now shares the board with the ADC and the buck (2026-09-20)

New, and created by the single-board decision. Motor switching used to be physically
on another PCB; it is now inches from U1, from the 150kΩ `VBAT_SENSE` node and from
the buck's feedback. Three consequences:

- **`VBAT_SENSE` (issue 5) will see real motor sag and real switching noise.** Its
  15ms RC helps a lot, but firmware should average across whole PWM periods rather
  than trusting a single conversion, and should not sample during a stall event and
  conclude the pack is flat.
- **Motor recirculation and bulk capacitance are now this schematic's parts.** Issue
  7 told the daughterboard to "retain local motor recirculation/bulk capacitance";
  there is no daughterboard, so that bulk cap has to be added here, next to the
  drivers, on `VBAT`, rated per issue 8 (≥16V, and derate for DC bias).
- **That bulk capacitance interacts with F1 inrush and D2's forward drop.** Size it
  together with issues 8 and 9 rather than in isolation — a large bulk cap on a
  polyfuse is an inrush problem, and D2 is already the biggest loss in the path.

The mitigation is placement, not plane splitting — see "Board stackup".

### 17. F1 and the `VBAT` path now carry motor current on *this* board (2026-09-20)

A promotion of issue 7's open item rather than a new fault. The current budget was
already outstanding, but with motors off-board it only had to be right before
*ordering parts*. Now the same number also sets **trace width, copper weight, via
count and thermal relief on this PCB**, so it has become a layout input.

Answer it before routing the power path, not before fabrication. F1's provisional 3A
hold was chosen without knowing the motors; if the real stall current moves it, the
copper sized around it moves too.

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
  impedance calculator. Do not carry a number over from another board. On ~0.2mm
  prepreg it lands somewhere near 0.2mm trace / 0.15mm gap — treat that as a starting
  point to verify, not as a specification.
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

## Layout constraints (for when layout starts)

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
  the highest-di/dt loop on the board.
- Keep the **SW copper island small** — it is the primary radiator. Note the SRP5030T
  is a 5×5mm part, so its SW-side pad is already a substantial copper area. Place the
  inductor tight against U3 and do not let that pad grow into a pour.
- **TP4 sits on that same SW island, so it fights the rule above.** Hang it off the
  U3.5–L1.1 run as a short stub on the *quiet* side, away from the L1 pad; do not
  centre the island on it and do not widen the trace to reach it. If the island ends
  up marginal, TP4 is the part to drop — the scope probe can go on the L1 pad
  instead. Keep its ground return short: TP3 (GND) should be within probe-tip reach
  of TP4, otherwise the measurement it exists for will be worthless.
- Route the **FB trace** back to the output caps away from SW and L1.
- Keep the **`REG_EN` node away from SW and L1**. It is a ~20kΩ-impedance node sitting
  1.2V above a comparator threshold, so it is easy to couple into. Put R8 and C13
  physically next to U3.2 and run the long leg from R7/R9 into them, not the reverse.
- **`VBAT_SENSE` is worse — 150kΩ.** Same rule, more strictly: C14 goes hard against
  U1.39 and R10/R11 sit behind it, so the high-impedance run is as short as possible.
  Keep the whole node away from SW, L1 and any motor current on `VBAT`, and do not
  route it as a long thin trace beside a switching node.
- USB D+/D− as a **90Ω differential pair** over unbroken ground reference.
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
- **Ask before deleting header pins or renaming nets.** The old reason — a
  daughterboard design not visible in this project — is gone, but the rule stands for
  a new one: J2/J3 are now the parking spot for 29 GPIOs, and removing pins before
  the issue-15 peripherals exist strands nets and buries real ERC warnings under
  noise. Delete them as part of moving nets onto real parts, not ahead of it.
