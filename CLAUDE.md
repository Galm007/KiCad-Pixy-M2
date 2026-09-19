# Pixy-M2 — Micromouse Controller PCB

Context for a Claude Code session working on this KiCad project via the KiCad MCP server.

## What this board is

Controller PCB for a micromouse robot. An **ESP32-S3-WROOM-1** module is soldered
directly to this board. The board carries the MCU, USB-C programming/charging port,
and a buck converter; motors, motor drivers, IR emitters/receivers, and the IMU live
on a daughterboard that mates through two 22-pin headers (J2, J3).

Power comes from a **2S LiPo (7.4V nominal, 8.4V full charge)** via an XT30 connector,
diode-OR'd with USB 5V, down-converted to 3.3V by an AP63203WU buck.

- Schematic: `Pixy-M2.kicad_sch` — single flat sheet, no hierarchy
- KiCad 10.0
- **PCB layout has not been started.**

## Current status

The schematic is complete. **ERC reports 0 errors and 4 warnings.** All four are
`isolated_pin_label` (label on a single-pin net): `VBAT_SENSE`, `GPIO3`, `GPIO45`,
`GPIO46`. Even so, ERC proves very little here: most issues below survive it, because
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

**Netlist last re-extracted: 2026-09-19, after the UVLO fix (issue 2).** The tables
below are current as of that extraction.

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
- **All 41 module pins land on a net.** Four of them land on a *single-pin* net
  though — `VBAT_SENSE`, `GPIO3`, `GPIO45`, `GPIO46` — see issues 5 and 12.
- **U3's EN is independently driven** (issue 2). `VSYS` carries U3.3 (IN) only; EN is
  on `REG_EN`. If a review reports EN tied to IN, it is reading a stale netlist.
- **Boot/reset.** SW1 pulls CHIP_PU low (R2 10k pull-up, C3 1µF, C4 0.1µF debounce);
  SW2 pulls GPIO0 low (C5 0.1µF).

## Net map (extracted, authoritative)

| Net | Members |
|---|---|
| `ESP_3V3` | C1.1, C2.1, C7.1, C11.1, J3.1, J3.2, L1.2, R2.1, U1.2, U3.1(FB) |
| `VSYS` | C12.1, D1.1(K), D2.1(K), U3.3(IN) |
| `REG_EN` | C13.1, R7.2, R8.1, R9.2, U3.2(EN) |
| `VBAT` | BT1.1(+), D2.2(A), J2.19, J2.20, J2.21, J2.22, R7.1 |
| `VBUS` | D1.2(A), D3.2(A), J1.A4/A9/B4/B9, U2.5 |
| `CHIP_PU` | C3.1, C4.2, J3.3, R2.2, SW1.1, U1.3(EN) |
| `GPIO0` | C5.2, SW2.1, U1.27 |
| `VBAT_SENSE` | U1.39 **only — dangling, see issue 5** |
| `Net-(D3-K)` | D3.1(K), R9.1 |
| SW node (unnamed) | C6.2, L1.1, U3.5 |
| BST (unnamed) | C6.1, U3.6 |

`VCC_USB_5V` has been **renamed `VSYS`**. It is the diode-OR output and sits at up to
**~8.1V** on a full pack, so the old "5V" name was actively misleading. `VBAT` and
`VBUS` are now explicit labels too, not auto-generated net names — do not let them
revert to `Net-(D1-A)` style names.

Header assignments have moved on from the original extraction. J2 carries GPIO2, 21,
35–44, 47, 48, GND on 1/6/12/18, and **VBAT on 19–22**; the dead `GPIO19`/`GPIO20`
pins are gone (issue 4 resolved). J3 carries GPIO4–18, 3V3, CHIP_PU, and GND on
7/12/17/22. There are now **8 ground pins across the two headers**, not 4 (issue 6
partly addressed). GPIO0, GPIO3, GPIO45 and GPIO46 are on no header at all.

## Open issues

Ordered by severity. **Resolved since this list was written: 2 (UVLO), 3 (U1
footprint), 4 (dead header pins), 11 (module variant).** Item 1 has regressed into a
new inconsistency. Items 5–10, 12 and 13 are still open; 1 and 5 must be settled
before layout.

### 1. L1 — Value and Footprint name two different parts — BLOCKS LAYOUT

**Resolved:** L1 was `Inductor_SMD:L_0805_2012Metric`, which was the worst problem in
the design. A 4.7µH 0805 part saturates somewhere around 300–700mA with DCR often
>300mΩ; the AP63203 is a 2A converter at ~1.4MHz, so the core would have saturated
under load, current would have run into the IC's cycle-by-cycle limit, and the part
would have overheated.

The footprint is now **`Inductor_SMD:L_Bourns_SRP5030T`**. The intended part is
**Bourns SRP5030T-4R7M** — 4.7µH ±20%, DCR 53mΩ max, rated current 4.6A, shielded,
5.0×5.0×3.0mm body. LCSC C2045677, also stocked at DigiKey/Mouser.

**REGRESSED — L1 is now half-updated, which is worse than either end state.** As of
the 2026-09-19 extraction:

| Field | Current value | Part it describes |
|---|---|---|
| Value | `4.7uH SWPA4030S4R7MT` | Sunlord SWPA4030S, **4.0×4.0**×3.0mm |
| Footprint | `Inductor_SMD:L_Bourns_SRP5030T` | Bourns SRP5030T, **5.0×5.0**×3.0mm |

The MPN and the land pattern are different parts of different sizes. A SWPA4030S
soldered to an SRP5030T land pattern will not sit on its pads properly. **Pick one
and make both fields agree before layout.** Either part works electrically —
SWPA4030S4R7MT is ~1.6A Isat / ~92mΩ DCR, comfortably above the ~700mA peak — so
this is purely a "which package" decision, but it has to be made explicitly.

Operating margin for reference: ripple is roughly 300mA p-p at 8.4V in, steady load
300–500mA, so peak inductor current stays under ~700mA against a 4.6A rating. DCR
loss is ~15mW — negligible next to the ~400mW burned in D2 (issue 9).

*Correction to an earlier spec in this file's history: a "DCR ≤ 60mΩ" target at
4.7µH in a 4×4mm package is not physically achievable. The 5030T meets it because
it is a larger part.*

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
  acceptable — but when the issue-7 power switch is added, **put this divider
  downstream of it** and the drain goes away entirely.
- **With USB connected, hardware UVLO is intentionally defeated** — D3/R9 hold EN up
  regardless of pack voltage. That is correct (you want to bench-run a flat board),
  but it means a low pack left connected alongside USB can still be pulled down to
  ~4.65V. Firmware must cover that case.
- Primary low-voltage protection is still **firmware**, using the battery sense in
  issue 5 — which is *not built yet*: `VBAT_SENSE` is a dangling single-pin net.
  Until that divider exists, this hardware UVLO is the only protection there is.

### 3. U1 footprint — RESOLVED

U1 is now `ESP32-S3-WROOM-1-N16` with footprint `PCM_Espressif:ESP32-S3-WROOM-1`.
No component in the design is missing a footprint.

### 4. Dead header pins — RESOLVED

The `5V0`, `GPIO19` and `GPIO20` header pins are gone. J2.19–22 now carry `VBAT` and
J3.21 carries `GPIO14`. No header pin is on a single-pin net.

Still dangling, but on the module rather than a header: `VBAT_SENSE` (U1.39),
`GPIO3` (U1.15), `GPIO45` (U1.26), `GPIO46` (U1.16). These are the four ERC warnings.
`VBAT_SENSE` is issue 5; the other three are issue 12.

### 5. Battery sense divider is still not built — HIGHEST REMAINING PRIORITY

Half done. **VBAT now reaches the daughterboard** on J2.19–22, so the motor drivers
have their supply rail. But `VBAT_SENSE` is a **label on U1.39 and nothing else** —
a single-pin net. The MCU currently has no way to read pack voltage.

This matters more than it did before: issue 2's hardware UVLO is deliberately
defeated whenever USB is connected, and its battery-only cutoff carries a
±0.15 V/cell tolerance spread. Firmware is the accurate mechanism and it is blind.

**Fix:** divider from `VBAT` into U1.39 (`GPIO1`/ADC1_CH0 — already the net's
endpoint, and correctly on **ADC1**; do not move it to ADC2, which is unusable while
Wi-Fi is active). 100k/47k puts 8.4V at 2.69V, inside the 12dB attenuation range.
Add 100nF to GND at the ADC node. Gate the divider with a small MOSFET so it does not
drain the pack at rest — and note the issue-2 divider already draws 58µA, so put both
downstream of the issue-7 switch.

### 6. Ground pins — improved, still thin

Now **8** across 44 positions: J2.1/6/12/18 and J3.7/12/17/22, interleaved among the
signals rather than bunched at the ends. That is a real improvement over the original
4. Motor and IR-emitter switching returns are still sharing them, so if any header
positions free up, convert more to GND — but this is no longer blocking.

### 7. No power switch, no fuse

BT1 runs straight through D2 into the regulator. Add a slide switch or P-FET load
switch plus a polyfuse in the battery line, and a ~500mA polyfuse on VBUS. Once
motors share VBAT, add a TVS there — inductive kickback will travel back down it.

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

### 12. Strapping pins exposed without pulldowns

GPIO45 (J2.15) and GPIO46 (J3.14) both must be low at boot. Internal weak pulldowns
cover the floating case, but anything on the daughterboard that pulls them high will
prevent boot. Add 10k pulldowns on this board. GPIO0 and GPIO3 are also strapping
pins and are on the headers — worth a silkscreen note at minimum.

### 13. Missing conveniences

- Power LED on 3V3 with a **10k** series resistor (not 1k — battery life matters)
- At least one status LED on a spare GPIO
- Test points on VBAT, 3V3, GND, and the SW node

## Layout constraints (for when layout starts)

- **Antenna keep-out is non-negotiable.** The module's antenna must overhang a board
  edge with zero copper on every layer in the keep-out region — no traces, no pours,
  no components.
- Place U3 as far from the antenna as the outline allows.
- The **C12 → U3.3 → U3.4 loop must be as tight as physically possible.** This is
  the highest-di/dt loop on the board.
- Keep the **SW copper island small** — it is the primary radiator. Note the SRP5030T
  is a 5×5mm part, so its SW-side pad is already a substantial copper area. Place the
  inductor tight against U3 and do not let that pad grow into a pour.
- Route the **FB trace** back to the output caps away from SW and L1.
- Keep the **`REG_EN` node away from SW and L1**. It is a ~20kΩ-impedance node sitting
  1.2V above a comparator threshold, so it is easy to couple into. Put R8 and C13
  physically next to U3.2 and run the long leg from R7/R9 into them, not the reverse.
- USB D+/D− as a **90Ω differential pair** over unbroken ground reference.
- Ground the module's thermal pad with a via array.

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
  its own angle set to 90 to render horizontally.
- Ask before deleting header pins or renaming nets — pin assignments may be
  constrained by a daughterboard design not visible in this project.
