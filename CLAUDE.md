# Pixy-M2 — Micromouse Controller PCB

Context for a Claude Code session working on this KiCad project via the KiCad MCP server.

## What this board is

Controller PCB for a micromouse robot. An **ESP32-S3-WROOM-1** module is soldered
directly to this board. The board carries the MCU, USB-C programming/power port,
and a buck converter; motors, motor drivers, IR emitters/receivers, and the IMU live
on a daughterboard that mates through two 22-pin headers (J2, J3).

Power comes from a **2S LiPo (7.4V nominal, 8.4V full charge)** via an XT30 connector,
F1 battery polyfuse and Q1/SW3 load switch, then is diode-OR'd with fused USB 5V
and down-converted to 3.3V by an AP63203WU buck. `VBAT` is the switched, fused
daughterboard supply; `VBUS` is downstream of the USB polyfuse F2.
The 2S pack is charged separately; no onboard battery charger is required.

- Schematic: `Pixy-M2.kicad_sch` — single flat sheet, no hierarchy
- KiCad 10.0
- **PCB layout has not been started.**

## Current status

The schematic is complete. **ERC reports 0 errors and 2 warnings.** Both are
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

**Netlist last re-extracted: 2026-09-19, after the issue-1 L1 field fix.** That edit
touched component fields only — the connectivity is unchanged since the issue-7
battery switch, fuses and TVS. The tables below are current as of that extraction.

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
- **All 41 module pins land on a net.** Three of them land on a *single-pin* net
  though — `GPIO3`, `GPIO45`, `GPIO46` — see issue 12.
- **U3's EN is independently driven** (issue 2). `VSYS` carries U3.3 (IN) only; EN is
  on `REG_EN`. If a review reports EN tied to IN, it is reading a stale netlist.
- **Boot/reset.** SW1 pulls CHIP_PU low (R2 10k pull-up, C3 1µF, C4 0.1µF debounce);
  SW2 pulls GPIO0 low (C5 0.1µF).

## Net map (extracted, authoritative)

| Net | Members |
|---|---|
| `ESP_3V3` | C1.1, C2.1, C7.1, C11.1, J3.1, J3.2, L1.2, R2.1, R12.1, TP2.1, U1.2, U3.1(FB) |
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

`GND` additionally carries D4.1(K), D5.1(K), TP3.1, D6.2(A) and SW3.3(ON).
SW3.1 (OFF) is intentionally marked no-connect.

`VCC_USB_5V` has been **renamed `VSYS`**. It is the diode-OR output and sits at up to
**~8.1V** on a full pack, so the old "5V" name was actively misleading. `VBAT` and
`VBUS` are now explicit labels too, not auto-generated net names — do not let them
revert to `Net-(D1-A)` style names.

Header assignments have moved on from the original extraction. J2 carries GPIO2, 21,
35–44, 47, 48, GND on 1/6/12/18, and **VBAT on 19–22**; the dead `GPIO19`/`GPIO20`
pins are gone (issue 4 resolved). J3 carries GPIO4–18, 3V3, CHIP_PU, and GND on
7/12/17/22. There are now **8 ground pins across the two headers**, not 4 (issue 6
partly addressed). GPIO0, GPIO3, GPIO45 and GPIO46 are on no header at all — though
`GPIO3` now drives the issue-13 status LED, so only GPIO45/46 are truly unused.

## Open issues

Ordered by severity. **Resolved since this list was written: 1 (L1 part), 2 (UVLO),
3 (U1 footprint), 4 (dead header pins), 5 (battery sense), 7 (switch/fuses/TVS added;
battery fuse sizing remains provisional), 11 (module variant), 13 (conveniences).**
**Nothing blocks layout any more.** Items 6, 8–10 and 12 are still open but none of
them gate starting the PCB. Confirm the issue-7 load/fault-current budget before
fabrication.

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

### 6. Ground pins — improved, still thin

Now **8** across 44 positions: J2.1/6/12/18 and J3.7/12/17/22, interleaved among the
signals rather than bunched at the ends. That is a real improvement over the original
4. Motor and IR-emitter switching returns are still sharing them, so if any header
positions free up, convert more to GND — but this is no longer blocking.

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
network; the switch does not guarantee a discharged/zero-volt daughterboard rail.
Turning the whole board off requires removing USB as well as switching off SW3.

**Current-budget check before fabrication:** verify steady load at the actual
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
not a continuous braking-energy sink. Daughterboard devices must tolerate that
clamp plus layout overshoot; retain local motor recirculation/bulk capacitance.
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
broken out on J2.14/13/11) are consumed by octal PSRAM only on `-R8` parts, so on an
N16 they are genuinely free. Do not substitute an `-N8R8` or `-N16R8` part without
deleting those three header pins.

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
silkscreen note on the headers at minimum.

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

## Layout constraints (for when layout starts)

- Put **F1 immediately after BT1** and F2 immediately after J1's joined VBUS pins.
  Keep unfused copper short; every downstream branch must go through its fuse.
- Put **SW3 at an accessible edge**, marked BAT ON/OFF (USB can still power the
  controller). Route only Q1 gate control to it, not motor current. Keep R14 close
  to Q1 and connect all three source and all four drain pads with adequate copper.
- Place **D6 near J2.19–22**, across switched `VBAT` and a short, wide GND return.
  Keep its surge-current loop away from the ADC and MCU ground paths. Size the
  battery/return copper for the final load and F1's fault-clearing interval.
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
  edge — not under the daughterboard, which mates over J2/J3 and will hide anything
  between them. Same for D5. Neither is timing- or noise-critical, so they are free
  placement; just keep both out of the antenna keep-out.
- **Silkscreen the test points** with their net names (VBAT, 3V3, GND, SW). An
  unlabelled 1.5mm pad is not a test point. Per issue 12, also silkscreen the header
  pins that carry strapping pins.

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
- Ask before deleting header pins or renaming nets — pin assignments may be
  constrained by a daughterboard design not visible in this project.
