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

The schematic is complete and **ERC reports zero errors and zero warnings**. That
clean ERC is misleading: every issue in the "Open issues" section below survives ERC
because ERC does not check footprint assignment, component ratings, saturation
current, or whether a labelled header pin actually goes anywhere.

The netlist was independently extracted from the `.kicad_sch` S-expressions and
verified pin-by-pin. Findings below are from that extraction, not from reading the
schematic image.

**Changes made since that extraction:** L1's footprint was changed from 0805 to
`Inductor_SMD:L_Bourns_SRP5030T` (issue 1). Re-extract before trusting the netlist
tables below for anything structural.

## Verified correct — do not re-flag these

These were checked against the actual netlist and are right. If a review pass
"finds" one of these, the review is wrong:

- **Buck topology.** C6 (0.1µF) is across U3.6 (BST) and U3.5 (SW). SW also drives
  L1.1. FB (U3.1) senses the 3.3V output directly — AP63203WU is the fixed-3.3V
  variant, so no feedback divider is needed or wanted.
- **Input capacitance exists.** C12 (10µF) is on VCC_USB_5V at U3.3 (IN).
- **USB-C CC termination.** R1 and R6 are 5.1kΩ resistors (`Device:R_US`), one on
  CC1 (J1.A5), one on CC2 (J1.B5), each independently to GND. Correct Rd.
- **ESD protection.** U2 (USBLC6-2SC6) is correctly in-line: pins 1/6 on D−,
  pins 3/4 on D+, pin 5 on VBUS, pin 2 on GND.
- **Shield.** J1.SH via R5 (1M) ‖ C8 (4.7nF) to GND.
- **All four VBUS and all four GND pins of J1 are tied together.**
- **All 41 module pins land on a net.** No stranded pins anywhere in the design.
- **Boot/reset.** SW1 pulls CHIP_PU low (R2 10k pull-up, C3 1µF, C4 0.1µF debounce);
  SW2 pulls GPIO0 low (C5 0.1µF).

## Net map (extracted, authoritative)

| Net | Members |
|---|---|
| `ESP_3V3` | C1.1, C2.1, C7.1, C11.1, J3.1, J3.2, L1.2, R2.1, U1.2, U3.1(FB) |
| `VCC_USB_5V` | C12.1, D1.1(K), D2.1(K), U3.2(EN), U3.3(IN) |
| `CHIP_PU` | C3.1, C4.2, J3.3, R2.2, SW1.1, U1.3(EN) |
| `GPIO0` | C5.2, J2.14, SW2.1, U1.27 |
| VBUS (unnamed) | D1.2(A), J1.A4/A9/B4/B9, U2.5 |
| VBAT (unnamed) | BT1.1(+), D2.2(A) |
| SW node (unnamed) | C6.2, L1.1, U3.5 |
| BST (unnamed) | C6.1, U3.6 |

Note `VCC_USB_5V` is a misleading name: it is the diode-OR output, so it sits at up
to **~8.1V** on a full pack, not 5V. Consider renaming to `VSYS` or `VIN_SW`.

Module pin → net mapping is 1:1 with GPIO labels throughout; J3 carries GPIO3–18
plus 3V3/CHIP_PU, J2 carries GPIO0–2 and GPIO21, 35–48.

## Open issues

Ordered by severity. Items 2, 3 and 4 must be resolved before layout. Item 1 is
resolved apart from a Value-field update.

### 1. L1 — footprint FIXED, Value field still needs the MPN

**Resolved:** L1 was `Inductor_SMD:L_0805_2012Metric`, which was the worst problem in
the design. A 4.7µH 0805 part saturates somewhere around 300–700mA with DCR often
>300mΩ; the AP63203 is a 2A converter at ~1.4MHz, so the core would have saturated
under load, current would have run into the IC's cycle-by-cycle limit, and the part
would have overheated.

The footprint is now **`Inductor_SMD:L_Bourns_SRP5030T`**. The intended part is
**Bourns SRP5030T-4R7M** — 4.7µH ±20%, DCR 53mΩ max, rated current 4.6A, shielded,
5.0×5.0×3.0mm body. LCSC C2045677, also stocked at DigiKey/Mouser.

**Still to do:** set L1's Value to the full MPN `SRP5030T-4R7M`, not bare `4.7uH`.
The bare value is exactly how the wrong part gets ordered a second time. Also verify
the library land pattern against the Bourns SRP5030T datasheet before routing.

Operating margin for reference: ripple is roughly 300mA p-p at 8.4V in, steady load
300–500mA, so peak inductor current stays under ~700mA against a 4.6A rating. DCR
loss is ~15mW — negligible next to the ~400mW burned in D2 (issue 9).

*Correction to an earlier spec in this file's history: a "DCR ≤ 60mΩ" target at
4.7µH in a 4×4mm package is not physically achievable. The 5030T meets it because
it is a larger part.*

### 2. No undervoltage lockout on the 2S pack — CRITICAL (safety)

U3.2 (EN) and U3.3 (IN) are the same net. The regulator can never turn itself off,
so the ESP will run the LiPo down past the safe floor and damage or ignite it.

**Fix:** resistor divider from `VCC_USB_5V` to EN. **220k top / 47k bottom** gives
~6.25V turn-on against the ~1.1V EN threshold. Two caveats to carry forward:

- EN hysteresis means the *turn-off* point sits below turn-on, so this is coarse
  backup protection, not the primary mechanism.
- **Check the AP63203WU datasheet EN absolute-maximum rating.** Some Diodes Inc.
  buck parts clamp EN below VIN, and VIN here reaches 8.1V. If EN is not rated to
  full VIN the divider must be resized or a clamp added.

Primary low-voltage protection should be firmware, using the battery sense in item 5.

### 3. U1 has no footprint assigned — CRITICAL (blocks layout)

The `Footprint` property on U1 is an empty string. "Update PCB from Schematic" will
fail. Assign `RF_Module:ESP32-S3-WROOM-1` (or the variant-matched footprint).

### 4. Three header pins are labelled but electrically dead

| Pin | Label | Reality |
|---|---|---|
| J3.21 | `5V0` | Single-pin net, no-connect flag |
| J2.19 | `GPIO20` | Single-pin net, no-connect flag |
| J2.20 | `GPIO19` | Single-pin net, no-connect flag |

ERC passes *because* the no-connect flags are there. On the physical board these
pins float while the silkscreen promises a signal.

GPIO19 and GPIO20 are consumed by the native USB PHY (module pins 13/14 are on
`USB_D-`/`USB_D+`) and are genuinely unavailable. **Delete them from J2.** Either
wire `5V0` to the VBUS net or delete it too.

### 5. No battery sense, and no VBAT on either header

Neither J2 nor J3 carries battery voltage — only `ESP_3V3` (J3.1, J3.2) and GND.
The motor drivers on the daughterboard have no supply rail.

**Fix:** add several VBAT pins to the headers, and add a sense divider into an
**ADC1** pin — 100k/47k puts 8.4V at 2.69V, inside the 12dB attenuation range. Add
100nF to GND at the ADC node. Gate the divider with a small MOSFET so it does not
drain the pack at rest. **Do not use ADC2** — it is unusable while Wi-Fi is active.

### 6. Only 4 ground pins across 44 header positions

J2 has GND on pins 1, 21, 22. J3 has GND on pin 22 only. Motor and IR-emitter
switching returns through that will inject noise across the whole board. Convert
several unused positions to GND and interleave them among the signals.

### 7. No power switch, no fuse

BT1 runs straight through D2 into the regulator. Add a slide switch or P-FET load
switch plus a polyfuse in the battery line, and a ~500mA polyfuse on VBUS. Once
motors share VBAT, add a TVS there — inductive kickback will travel back down it.

### 8. Capacitor voltage ratings are unspecified everywhere

No cap in the design has a rated voltage in its Value or a field. On a system that
reaches 8.4V this has to be explicit.

- **C12** is the urgent one — it sits on the ~8.1V OR node despite the "5V" net
  name. Spec **≥25V**, and note that a 25V 10µF 0805 derates to roughly 3–4µF at
  that bias. The AP63203 wants ~2×10µF *effective* input capacitance: add a second
  bulk cap plus a 100nF right at U3.3.
- **C7, C11** (22µF 0805, 3.3V rail): spec 10V or 16V to survive DC-bias derating.
- Everything else: state the rating explicitly, minimum 16V on anything touching
  VBAT or the OR node.

### 9. Diodes are generic symbols with no part numbers

D1 and D2 are both `Device:D_Schottky` in `Diode_SMD:D_SMA`. D2 carries the entire
system current from the battery — at 1A that is ~400mW dissipated and ~0.4V of
headroom thrown away.

**Fix:** spec a real part (≥3A, ≥30V, low Vf), or replace D2 with a P-FET
ideal-diode controller. D1 can stay a diode but still needs a real part number.

### 10. Unnecessary series resistors on USB D+/D−

R3 and R4 (22Ω) sit between U2 and the module's USB pins. The ESP32-S3's internal
USB PHY is impedance-matched; Espressif's reference designs connect straight
through. Replace with 0Ω or remove.

### 11. Module variant is unspecified

U1's Value is just `ESP32-S3-WROOM-1` with no `-N8`/`-N8R2`/`-N8R8` suffix. The
design breaks out **GPIO35, GPIO36, GPIO37** (module pins 28/29/30), which are
consumed by octal PSRAM on `-N8R8` and `-N16R8` parts. Pin the exact variant into
the Value field before ordering; if it is an R8 part, those three header pins are
unusable and should be removed.

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
- Ask before deleting header pins or renaming nets — pin assignments may be
  constrained by a daughterboard design not visible in this project.
