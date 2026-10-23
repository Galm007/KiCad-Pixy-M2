# Pixy-M2 bill of materials — one robot

**Branch `devkit-daughterboard` (2026-10-15).** U1 is an
**ESP32-S3-DevKitC-1-N8R8** that plugs into two 1×22 SMD female headers. The
parts the devkit carries itself are gone from the PCB: the USB-C input (J1, U2,
F2, R1, R5, R6, C8), the USB supply path (D1, D3, R9), reset/boot (R2, C3–C5,
SW1, SW2), the J11 programming header and TP5–TP8. The schematic and board
have the same 79 references.

Quantities are for **one robot**, with no spares. Imperial package codes are used
(0603, 0805, 1206). **73 parts are fitted to the PCB**: 71 references plus
the two sockets that make up U1's footprint. TP1–TP4 and TP9–TP11 are bare 1.5 mm
copper pads, so nothing is bought for them. The devkit itself is listed under
C, off-board modules.

Status key: **Fixed** means the part is named in the schematic or design notes.
**Spec** means any part meeting the spec will do. **Open** means the design has
not chosen one yet.

## A. PCB assembly — 73 parts

### Semiconductors

| Qty | Ref | Part | Package | Status |
|---:|---|---|---|---|
| 1 | U3 | Diodes Inc **AP63203WU-7** | TSOT-23-6 | Fixed. The fixed 3.3 V variant; do not substitute the adjustable AP63200. |
| 2 | U4, U5 | TI **DRV8231ADSGR** | WSON-8 2×2 | Fixed |
| 1 | U6 | TI **TLV3012BIDBVR** | SOT-23-6 | Fixed. The B version supplies POR and the 1.242 V current reference. |
| 1 | U7 | TI **SN74LV4066APWR** | TSSOP-14 | Fixed. All four motor inputs are disconnected on undervoltage. |
| 1 | U8 | TI **LM66100DCKR** | SC70-6 | Fixed. USB-priority isolation, used with Q2. |
| 1 | Q2 | AOS **AO3401A** | SOT-23 | Fixed. Opposes U8’s body diode; source at BUCK_PASS. |
| 1 | Q3 | onsemi **MMBT3904LT1G** | SOT-23 | Fixed. Q2 gate driver from U8 ST. |
| 1 | Q1 | AOS **AO4407A** | SOIC-8 | Fixed. The symbol is `IRF7404`; do not order that. |
| 1 | D2 | onsemi **MBRA340T3G** | SMA | Fixed |
| 1 | D6 | Vishay **SMBJ9.0A-E3/52** | SMB | Fixed |
| 1 | D4 | Red LED, high-efficiency (AlInGaP) | 0805 | Spec. Runs at ~150 µA, so it must be visibly lit at that current. No blue, white or pure-green part (issue 13). |
| 1 | D5 | Green LED | 0805 | Spec. Runs at ~550 µA. |

### Passive power parts, protection and switches

| Qty | Ref | Part | Package | Status |
|---:|---|---|---|---|
| 1 | L1 | Bourns **SRP5030T-4R7M**, 4.7 µH | 5.0×5.0 mm | Fixed (LCSC C2045677) |
| 1 | F1 | Littelfuse **0885005.DR**, 5 A fast-acting fuse, **breaks 1500 A @ 125 VDC** | 885 series, 10.9 × 4.8 × 4.8 mm | Fixed. One-time, not resettable. It replaced the 2920L300/15DR PPTC, which could only break 40 A; this pack can put an estimated 200–400 A into a dead short. |
| 1 | SW3 | C&K **JS102011SAQN** SPDT slide | SMD | Fixed |

### Connectors on the PCB

| Qty | Ref | Part | Status |
|---:|---|---|---|
| 2 | U1 (sockets) | 1×22 2.54 mm **vertical SMD female header**, Harwin M20-786 land pattern (pin 1 left), body ≤ 8.5 mm | **Open.** The footprint is KiCad's `PinSocket_1x22_P2.54mm_Vertical_SMD_Pin1Left` twice. Harwin's M20-786 SMT range is confirmed at 15 and 20 ways (M20-7861546, M20-7862042); no 22-way part number was confirmed. Two 11-way strips butted end to end on each row also fit the land pattern. Must be SMD: through-hole tails would stand into the underside battery bay and motor B. |
| 1 | BT1 | AMASS **XT30U-M** (male), vertical in PCB | Fixed by the footprint |
| 6 | J4–J9 | JST **SM06B-SRSS-TB(LF)(SN)**, SH 6-pin side entry | Fixed. J8/J9 are the motor/encoder ports, in Pololu's pin order. |
| 1 | J10 | JST **SM09B-SRSS-TB(LF)(SN)**, SH 9-pin side entry | Fixed |

### Capacitors (MLCC)

Use X7R where it is available; X5R is acceptable for the 10 µF and 22 µF parts.
The voltage ratings are the minimums from issue 8. Do not go lower.

| Qty | Ref | Value | Package |
|---:|---|---|---|
| 6 | C2, C16, C22–C24, C27 | 0.1 µF 16 V | 0603 |
| 2 | C6, C17 | 0.1 µF 25 V | 0603 |
| 4 | C13, C14, C18, C20 | 0.1 µF 50 V | 0603 |
| 1 | C25 | 2.2 nF 16 V | 0603 |
| 1 | C28 | 4.7 nF 16 V | 0603 |
| 1 | C26 | 1 µF 16 V | 0603 |
| 2 | C1, C15 | 10 µF 16 V | 0805 |
| 2 | C7, C11 | 22 µF 16 V | 0805 |
| 3 | C12, C19, C21 | 22 µF 25 V | **1206** |
| 1 | C30 | 100 µF 6.3 V X5R, Murata **GRM31CR60J107ME39L** | **1206** |

One 0.1 µF 50 V 0603 part can fill all 12 of the 0.1 µF positions. Buying one
type instead of three is a valid choice. C25 + C28 load the TLV3012B
reference: keep their sum ≤ 10 nF. C30 is the USB-unplug hold-up; its
capacitance at 3.3 V bias matters, so keep the named part or one with the
same DC-bias curve.

### Resistors (0805)

R24–R26 are **thin film, 0.1 % and ≤25 ppm/°C**, named by part number: a
thick-film substitute moves the motor cutoff. The others are thick film and
may all be 1 %; R17/R18 and R28/R29 must also be ≤100 ppm/°C (R17/R18: Yageo
RC0805FR-071KL).

| Qty | Ref | Value |
|---:|---|---|
| 7 | R12, R19–R23, R28 | 10 kΩ |
| 3 | R13, R15, R16 | 2.2 kΩ |
| 2 | R17, R18 | **1 kΩ 1 %**, RC0805FR-071KL (0.828 A nominal) |
| 1 | R7 | 120 kΩ **1 %** |
| 1 | R8 | 24 kΩ **1 %** |
| 1 | R10 | 470 kΩ **1 %** |
| 1 | R11 | 220 kΩ **1 %** |
| 4 | R14, R27, R30, R31 | 100 kΩ 1 % |
| 1 | R29 | 82 kΩ 1 % |
| 1 | R24 | 100 kΩ **0.1 %, 25 ppm/°C**, Yageo RT0805BRD07100KL |
| 1 | R25 | 23.2 kΩ **0.1 %, 25 ppm/°C**, Yageo RT0805BRD0723K2L |
| 1 | R26 | 825 kΩ **0.1 %, 25 ppm/°C**, Yageo RT0805BRD07825KL |

## B. The bare PCB

| Qty | Item | Notes |
|---:|---|---|
| 1 | 4-layer PCB, 1.6 mm, 66 × 100 mm | Use JLC04161H-7628 or an equivalent with ~0.2 mm L1–L2 prepreg. **Order the options below with the PCB:** |
| | • Via fill and cap, IPC-4761 type VII | Only for the four thermal vias under U4/U5. It is recorded on `Dwgs.User`. Tenting is not a substitute. |
| 1 | SMT stencil | Optional, but hard to do without for two 2×2 mm WSON parts with exposed pads. |

## C. Off-board modules

| Qty | Item | Status |
|---:|---|---|
| 1 | **Espressif ESP32-S3-DevKitC-1-N8R8** (v1.1) | Fixed as U1. Plugs into the two sockets above, USB ports toward the front (the silkscreen between the rows says which end). N8R8's octal PSRAM takes GPIO35–37, and v1.1's RGB LED is on GPIO38; the design uses none of them. Fit male headers to it if it ships without. A v1.0 board puts the RGB LED on GPIO48 (encoder A OUT B) instead: remove that LED's series resistor or use v1.1. |
| 4 | **GY-VL53L0XV2** ToF module (silkscreen `HW-842`) | Fixed. J4–J7 copy its header order. A different module needs different cables. |
| 1 | **Adafruit BNO085 9-DoF breakout, #4754** | Fixed. For SPI: wire **P0 to J10.9** (PS0/WAKE) and **tie P1 to VIN** at the module end. SCL is SCK, SDA is MISO and DI is MOSI (Adafruit's pin names). |
| 2 | **Pololu Micro Metal Gearmotor HP 6V with 12 CPR encoder** (#5153–#5165 series, extended shaft, encoder fitted) | **Ratio open.** Pick one ratio for both motors, e.g. #5155 (10:1) or #5157 (15:1). The side- and back-connector versions have the same pinout. Either encoder version stands 3–4 mm proud of one face of the motor. **Mount each motor with that face outboard (A forward, B rearward) or toward the floor:** the battery sits 1.5 mm from their inboard faces. |
| 1 pack (listing is 4) | **OVONIC 2S 450 mAh 100C, XT30** ([Amazon B0D2KT723L](https://www.amazon.com/gp/product/B0D2KT723L)) | Chosen. The maker lists it at 7.4 V / 4.2 V per cell (standard LiPo, not LiHV, despite "High Voltage" in the title), **62 × 17 × 14 mm, 31 g**, XT30 female, JST-XH balance lead. XT30 female is the battery-side part, so it mates with BT1 (male). **See "Battery" below: it goes across the underside between the motors, and F1 was changed to interrupt its fault current.** |

## D. Cables and crimp parts

Hand-crimped JST is fiddly. Pre-crimped single-ended "SH 6-pin" leads
with bare wire, avoid most of the crimping.

| Qty | Cable | Board end | Far end |
|---:|---|---|---|
| 4 | ToF, 6-way, straight 1:1 | SHR-06V-S-B + 6 × SSH-003T-P0.2-H | 6-way 2.54 mm Dupont socket, or solder to the module |
| 1 | IMU, 9-way | SHR-09V-S-B + 9 × SSH-003T-P0.2-H | Dupont sockets or solder, wired per the J10 table in CLAUDE.md |
| 2 | Motor/encoder | **Pololu JST SH-style encoder cable, female-female**, straight 1:1: #4765 (10 cm), #4766 (16 cm), #4767 (25 cm), #4768 (40 cm) or #4769 (63 cm) | Ready-made, so no crimping. Both ends are SH, so it plugs straight into J8/J9. |
| 1 | USB | USB cable for the devkit's ports: micro-USB or USB-C, depending on the board batch; check the one bought | Flashing, console and JTAG all go through the devkit |

Crimp totals: **4 × SHR-06V-S-B**, **1 × SHR-09V-S-B** and
**33 × SSH-003T-P0.2-H**. Buy about 2× the contacts, because hand crimping loses
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
re-pinning. Pololu rates these contacts and cables at **1 A**. U6 now supplies the driver
reference at 1.242 V, and **R17/R18 are 1 kΩ**, giving **0.828 A nominal**.
This leaves tolerance margin below the connector rating. IPROPI reads **1.5 V/A**.
The independent U6/U7 cutoff coasts both motors at 6.35 V (enable 6.75 V)
even while USB powers the MCU. See [the tolerance and validation notes](layout/power-integrity/README.md).
Current ripple, PWM blanking, sustained stall heating and cable temperature still
require measurement; the nominal limit is not a guarantee on every current peak.

### Battery

- **Where it goes (2026-09-24).** Across the underside, between the two
  motors: board X 0.5–62.5, Y 57.5–74.5, wide face on the board, with its
  leads at the +X (right-hand) end. Its centre is on the rotation centre's Y.
  The listing gives 61.5 × 15.77 × 13.48 mm and the maker 62 × 17 × 14 mm, so
  the bay is drawn at the larger size, 1.5 mm from each motor body. The front
  strip also fits, but it puts the robot's CG about 6 mm ahead of the front
  axle. The underside silkscreen shows the outline, the lead end and the
  lead's route. See `layout/README.md`, "Battery bay".
- **Fixing.** Hook-and-loop tape on the pack's top face. The drive lanes beside
  it leave no path for a strap.
- **Lead.** The XT30 and balance leads leave the +X end and run forward on the
  underside along X = 64.5. They cross the front strip at Y = 29.5 and wrap the
  left edge between J6 and BT1. From the pack to the back of the XT30 plug that
  is **about 13 cm**. If the pack's own lead is shorter, add an XT30
  extension (below) or re-lead the pack.
- **Fault current — handled by F1.** The pack is sold as 100C continuous and
  200C burst (45 A and 90 A), and its dead-short current is estimated at
  200–400 A. The original F1 PPTC could break only 40 A. Rather than give up the
  burst current with a lower-C pack, F1 is now a Littelfuse 0885005.DR rated to
  break 1500 A.
- **Charging.** You need a 2S balance charger with an XT30 lead (or an adapter)
  and a JST-XH balance port.

## E. Mechanical — not designed yet

This section is **not definitive**. `layout/README.md` gives only space
reservations: "idlers, axle supports and gear ratios remain unspecified". Nothing
here can be ordered from the repo until the drivetrain is designed.

| Qty | Item | Constraint from the layout |
|---:|---|---|
| 2 | Wheels, Ø30 mm, ≤ 8 mm tire | They must fit the motor's 3 mm D-shaft or a drivetrain axle |
| 2 | Micro metal gearmotor brackets | 38 × 16 × 16 mm underside envelopes. **Outboard side only:** the battery fills the space between the motors, so nothing may clamp or fasten on their inboard faces. |
| ? | Gears, idlers, axles, bearings | Undefined. The motors are staggered at Y = 50 / 82 and are not coaxial with the wheels. |
| 4 | Sensor brackets | 14 × 19 mm mounts. J6/J7 are aimed 45° ± 15°. |
| 1 | IMU standoff or bracket | 25 × 25 mm, chip 8.6 mm left of and 7.5 mm behind the rotation centre (devkit-daughterboard). It ends at board x 36.7, 1.9 mm short of the devkit's edge. |
| — | Fasteners | **The PCB has no mounting holes**; the attachment method is open |
| 1 | Hook-and-loop tape, ~60 × 15 mm | Holds the battery to the underside between the motors |
| 1 | XT30 male-to-female extension, 10–15 cm | Only if the pack's lead is shorter than the ~13 cm route to BT1 |

## F. Tools and consumables (if you don't already have them)

2S LiPo balance charger (XT30, JST-XH balance) · JST SH crimp tool · solder paste and a hot-air or
reflow setup (the WSON exposed pads need it).
