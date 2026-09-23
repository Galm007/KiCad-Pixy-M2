# Pixy-M2 bill of materials — one robot

Extracted from `Pixy-M2.kicad_sch` on 2026-09-23 with `kicad-cli sch export bom`,
after J8/J9 moved to JST SH in the Pololu encoder pin order, then compared with
the board. The PCB has the same 78
footprints and no footprint that is only on the board. This file replaces the
2026-09-19 list. That list predated the motor, IMU and debug blocks, and it still
showed J2/J3 and R3/R4.

Quantities are for **one robot**, with no spares. Imperial package codes are used
(0603, 0805, 1206). **69 parts are fitted to the PCB.** TP1–TP9 are bare 1.5 mm
copper pads, so nothing is bought for them.

Status key: **Fixed** means the part is named in the schematic or design notes.
**Spec** means any part meeting the spec will do. **Open** means the design has
not chosen one yet.

## A. PCB assembly — 69 parts

### Semiconductors

| Qty | Ref | Part | Package | Status |
|---:|---|---|---|---|
| 1 | U1 | Espressif **ESP32-S3-WROOM-1-N16** | module | Fixed. Must be N16, not -R8/-N8R8/-N16R8 (issue 11). |
| 1 | U2 | ST **USBLC6-2SC6** | SOT-23-6 | Fixed |
| 1 | U3 | Diodes Inc **AP63203WU-7** | TSOT-23-6 | Fixed. The fixed 3.3 V variant; do not substitute the adjustable AP63200. |
| 2 | U4, U5 | TI **DRV8231ADSGR** | WSON-8 2×2 | Fixed |
| 1 | Q1 | AOS **AO4407A** | SOIC-8 | Fixed. The symbol is `IRF7404`; do not order that. |
| 2 | D1, D2 | onsemi **MBRA340T3G** | SMA | Fixed |
| 1 | D3 | Vishay **BAT54W-E3-08** | SOD-123 | Fixed as a part. The schematic datasheet link is still Nexperia's, whose BAT54W is SOT-323 and does **not** fit. |
| 1 | D6 | Vishay **SMBJ9.0A-E3/52** | SMB | Fixed |
| 1 | D4 | Red LED, high-efficiency (AlInGaP) | 0805 | Spec. Runs at ~150 µA, so it must be visibly lit at that current. No blue, white or pure-green part (issue 13). |
| 1 | D5 | Green LED | 0805 | Spec. Runs at ~550 µA. |

### Passive power parts, protection and switches

| Qty | Ref | Part | Package | Status |
|---:|---|---|---|---|
| 1 | L1 | Bourns **SRP5030T-4R7M**, 4.7 µH | 5.0×5.0 mm | Fixed (LCSC C2045677) |
| 1 | F1 | Littelfuse **2920L300/15DR**, 3 A hold PPTC | 2920 | Fixed. The rating is provisional pending the issue-17 measurement. |
| 1 | F2 | Bourns **MF-MSMF050-2**, 500 mA hold PPTC | 1812 | Fixed |
| 1 | SW3 | C&K **JS102011SAQN** SPDT slide | SMD | Fixed |
| 2 | SW1, SW2 | E-Switch **TL3301NF160QG** tactile, 160 gf | 6×6 SMD | The footprint is fixed as TL3301N-family. The 160 gf force is a suggestion; 100 gf and 260 gf fit the same footprint. |

### Connectors on the PCB

| Qty | Ref | Part | Status |
|---:|---|---|---|
| 1 | J1 | Amphenol **12401948E412A** USB-C receptacle | Fixed by the footprint. Other USB-C sockets do not fit. |
| 1 | BT1 | AMASS **XT30U-M** (male), vertical in PCB | Fixed by the footprint |
| 7 | J4–J9, J11 | JST **SM06B-SRSS-TB(LF)(SN)**, SH 6-pin side entry | Fixed. J8/J9 are the motor/encoder ports, in Pololu's pin order. |
| 1 | J10 | JST **SM09B-SRSS-TB(LF)(SN)**, SH 9-pin side entry | Fixed |

### Capacitors (MLCC)

Use X7R where it is available; X5R is acceptable for the 10 µF and 22 µF parts.
The voltage ratings are the minimums from issue 8. Do not go lower.

| Qty | Ref | Value | Package |
|---:|---|---|---|
| 5 | C2, C4, C5, C16, C22 | 0.1 µF 16 V | 0603 |
| 2 | C6, C17 | 0.1 µF 25 V | 0603 |
| 4 | C13, C14, C18, C20 | 0.1 µF 50 V | 0603 |
| 1 | C3 | 1 µF 16 V | 0603 |
| 2 | C1, C15 | 10 µF 16 V | 0805 |
| 2 | C7, C11 | 22 µF 16 V | 0805 |
| 3 | C12, C19, C21 | 22 µF 25 V | **1206** |
| 1 | C8 | 4.7 nF **1 kV** | **1206** |

One 0.1 µF 50 V 0603 part can fill all 11 of the 0.1 µF positions. Buying one
reel instead of three is a valid choice.

### Resistors (0805 thick film)

The design requires **1 %** on the eight parts marked 1 %. Buying 1 % for every
position costs nothing extra.

| Qty | Ref | Value |
|---:|---|---|
| 7 | R2, R12, R19–R23 | 10 kΩ |
| 3 | R13, R15, R16 | 2.2 kΩ |
| 2 | R1, R6 | 5.1 kΩ |
| 2 | R17, R18 | 2.2 kΩ **1 %** (motor current limit, 1.0 A) |
| 1 | R5 | 1 MΩ |
| 1 | R7 | 120 kΩ **1 %** |
| 1 | R8 | 24 kΩ **1 %** |
| 1 | R9 | 39 kΩ **1 %** |
| 1 | R10 | 470 kΩ **1 %** |
| 1 | R11 | 220 kΩ **1 %** |
| 1 | R14 | 100 kΩ |

## B. The bare PCB

| Qty | Item | Notes |
|---:|---|---|
| 1 | 4-layer PCB, 1.6 mm, 66 × 100 mm | Use JLC04161H-7628 or an equivalent with ~0.2 mm L1–L2 prepreg. **Order the options below with the PCB:** |
| | • Impedance control on USB D+/D− | 90 Ω differential, 0.25 / 0.15 mm on L1. Otherwise confirm the geometry with the fab's calculator (see "Board stackup"). |
| | • Via fill and cap, IPC-4761 type VII | Only for the four thermal vias under U4/U5. It is recorded on `Dwgs.User`. Tenting is not a substitute. |
| 1 | SMT stencil | Optional, but hard to do without for two 2×2 mm WSON parts with exposed pads. |

## C. Off-board modules

| Qty | Item | Status |
|---:|---|---|
| 4 | **GY-VL53L0XV2** ToF module (silkscreen `HW-842`) | Fixed. J4–J7 copy its header order. A different module needs different cables. |
| 1 | **Adafruit BNO085 9-DoF breakout, #4754** | Fixed. For SPI: wire **P0 to J10.9** (PS0/WAKE) and **tie P1 to VIN** at the module end. SCL is SCK, SDA is MISO and DI is MOSI (Adafruit's pin names). |
| 2 | **Pololu Micro Metal Gearmotor HP 6V with 12 CPR encoder** (#5153–#5165 series, extended shaft, encoder fitted) | **Ratio open.** Pick one ratio for both motors, e.g. #5155 (10:1) or #5157 (15:1). The side- and back-connector versions have the same pinout. |
| 1 pack (listing is 4) | **OVONIC 2S 450 mAh 100C, XT30** ([Amazon B0D2KT723L](https://www.amazon.com/gp/product/B0D2KT723L)) | Chosen. The maker lists it at 7.4 V / 4.2 V per cell (standard LiPo, not LiHV, despite "High Voltage" in the title), **62 × 17 × 14 mm, 31 g**, XT30 female, JST-XH balance lead. XT30 female is the battery-side part, so it mates with BT1 (male). **See "Battery" below: it does not fit the drawn reservation, and it is stronger than F1 is rated to interrupt.** |

## D. Cables and crimp parts

Hand-crimped JST is fiddly. Pre-crimped single-ended "SH 6-pin" leads
with bare wire, avoid most of the crimping.

| Qty | Cable | Board end | Far end |
|---:|---|---|---|
| 4 | ToF, 6-way, straight 1:1 | SHR-06V-S-B + 6 × SSH-003T-P0.2-H | 6-way 2.54 mm Dupont socket, or solder to the module |
| 1 | IMU, 9-way | SHR-09V-S-B + 9 × SSH-003T-P0.2-H | Dupont sockets or solder, wired per the J10 table in CLAUDE.md |
| 2 | Motor/encoder | **Pololu JST SH-style encoder cable, female-female**, straight 1:1: #4765 (10 cm), #4766 (16 cm), #4767 (25 cm), #4768 (40 cm) or #4769 (63 cm) | Ready-made, so no crimping. Both ends are SH, so it plugs straight into J8/J9. |
| 1 | Debug (optional) | SHR-06V-S-B + 6 × SSH-003T-P0.2-H | a 3.3 V USB-UART adapter with DTR/RTS |

Crimp totals, including the debug lead: **5 × SHR-06V-S-B**, **1 × SHR-09V-S-B** and
**39 × SSH-003T-P0.2-H**. Buy about 2× the contacts, because hand crimping loses
some. Also needed: 28–32 AWG wire.

### J8/J9 and the Pololu motors

J8/J9 now use the Pololu encoder board's own connector and pin order (checked on
[#5161](https://www.pololu.com/product/5161) and the cable page
[#4766](https://www.pololu.com/product/4766)):

| pin | 1 | 2 | 3 | 4 | 5 | 6 | MP |
|---|---|---|---|---|---|---|---|
| encoder / J8 / J9 | GND | OUT B | OUT A | VCC (3.3 V) | M2 | M1 | GND |
| Pololu cable wire | green | white | yellow | blue | black | red | — |

Pololu's cable is straight 1:1, so it plugs in either way round with no
re-pinning. Pololu rates these contacts and cables at **1 A**, so **R17/R18 are
now 2.2 kΩ**. That puts the DRV8231A's current limit at 1.00 A, down from 1.47 A,
and still gives about 63 % of the motor's 6 V stall torque. IPROPI now reads
3.3 V/A, so the ADC clips at about 0.94 A, just below the limit.

### Battery

- **Size.** The pack is 62 × 17 × 14 mm; the underside reservation drawn in
  `layout/README.md` is 40 × 30 × 15 mm. Turned 90°, it fits across the 66 mm
  board in the front strip (Y ≈ 5–22), clear of the motors and BT1's pads. The
  reservation drawing and the battery attachment bands have not been updated.
- **Fault current.** F1 (2920L300/15DR) is rated to interrupt at most **40 A**.
  This pack is sold as 100C continuous and 200C burst, which is 45 A and 90 A. A
  hard short downstream of F1 can therefore exceed what F1 is rated to break.
  This is the issue-17 check, and this pack fails it. It needs a design decision,
  such as a higher-rated fuse or a pack with lower C; nothing in this change
  addresses it.
- **Charging.** You need a 2S balance charger with an XT30 lead (or an adapter)
  and a JST-XH balance port.

## E. Mechanical — not designed yet

This section is **not definitive**. `layout/README.md` gives only space
reservations: "idlers, axle supports and gear ratios remain unspecified". Nothing
here can be ordered from the repo until the drivetrain is designed.

| Qty | Item | Constraint from the layout |
|---:|---|---|
| 2 | Wheels, Ø30 mm, ≤ 8 mm tire | They must fit the motor's 3 mm D-shaft or a drivetrain axle |
| 2 | Micro metal gearmotor brackets | 38 × 16 × 16 mm underside envelopes |
| ? | Gears, idlers, axles, bearings | Undefined. The motors are staggered at Y = 50 / 82 and are not coaxial with the wheels. |
| 4 | Sensor brackets | 14 × 19 mm mounts. J6/J7 are aimed 45° ± 15°. |
| 1 | IMU standoff or bracket | 25 × 25 mm at the rotation centre |
| — | Fasteners, battery strap | **The PCB has no mounting holes**; the attachment method is open |

## F. Tools and consumables (if you don't already have them)

2S LiPo balance charger (XT30, JST-XH balance) · JST SH crimp tool · solder paste and a hot-air or
reflow setup (the WSON exposed pads and the module's ground pads need it) · 3.3 V USB-UART adapter (only
for J11).
