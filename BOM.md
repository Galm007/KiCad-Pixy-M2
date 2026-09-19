# Pixy-M2 component list — one board

Extracted from `Pixy-M2.kicad_sch` on 2026-09-19, following commit `be64018`
plus the working-tree VL53L0X sensor-connector block (J4-J7, R15/R16, C15/C16).

**54 fitted parts**, plus **four PCB test pads**. Quantities are for one board and
exclude assembly spares. Package codes 0603, 0805, 1812 and 2920 are imperial.

The 2S LiPo pack is charged separately. No charger IC or charging components are
required on this board. Motors, motor drivers, IMU and any suction fan belong to
the daughterboard/system and are outside this controller BOM.

Wall sensing is four **GY-VL53L0XV2 time-of-flight modules**, which are off-board:
this board carries only their connectors (J4-J7), the shared I2C pull-ups and the
local rail decoupling. J4-J7 reproduce the module's 6-pin header in its own order,
so each cable is a straight 1:1 loom. The modules themselves, their cables and the
mating JST housings are listed under "Off-board sensor parts" below and are not in
the 54-part count.

This records the current schematic. Entries marked TBD or conflict require
resolution before purchasing; additional capacitors considered in issue 8 are
not yet present and are not counted here.

| Qty | References | Component / value | Package / footprint | Selection notes |
|---:|---|---|---|---|
| 1 | U1 | ESP32-S3-WROOM-1-N16 MCU module | ESP32-S3-WROOM-1 | 16MB flash, no PSRAM; retain the N16 variant. |
| 1 | U2 | USBLC6-2SC6 USB ESD protection | SOT-23-6 |  |
| 1 | U3 | AP63203WU fixed 3.3V buck regulator | TSOT-23-6 |  |
| 1 | Q1 | AO4407A P-channel MOSFET | SOIC-8, 3.9 × 4.9mm, 1.27mm pitch | Order AO4407A; IRF7404 is only the compatible symbol used in the schematic. |
| 2 | D1, D2 | Schottky power diodes — MPN TBD | SMA / DO-214AC | The schematic currently specifies only D_Schottky. Final electrical ratings and exact parts remain open. |
| 1 | D3 | BAT54W small-signal Schottky diode | SOD-123 | Use the Vishay SOD-123 version, e.g. BAT54W-E3-08; correct the schematic datasheet/manufacturer fields before releasing the BOM. See the package note below. |
| 1 | D4 | High-efficiency red LED | 0805 | Choose an LED with useful brightness at about 150µA; exact MPN remains open. |
| 1 | D5 | Green LED | 0805 | Status LED; exact MPN remains open. |
| 1 | D6 | SMBJ9.0A-E3/52 unidirectional TVS | SMB / DO-214AA |  |
| 1 | L1 | Bourns SRP5030T-4R7M 4.7µH power inductor | SRP5030T, 5.0 × 5.0 × 3.0mm | 53mΩ DCR max, 4.6A Irms, 6A Isat, shielded; LCSC C2045677. Value, footprint, MPN and datasheet now agree (issue 1 resolved). |
| 1 | F1 | 2920L300/15DR resettable fuse, 3A hold, 15V | 2920 | Provisional current rating; validate motor/fan load, temperature and pack fault current. |
| 1 | F2 | MF-MSMF050-2 resettable fuse, 500mA hold, 15V | 1812 |  |
| 1 | BT1 | AMASS XT30U-M battery connector | Vertical THT, 5mm pitch | Connector model inferred from assigned footprint. BT1 is the PCB connector; the pack is external. |
| 1 | J1 | Amphenol 12401948E412A USB-C receptacle | Manufacturer-specific USB-C footprint | Part inferred from assigned footprint; use this mechanical pattern, not an arbitrary USB-C socket. |
| 2 | J2, J3 | 1 × 22-position female socket headers | 2.54mm pitch, vertical THT | Exact manufacturer, socket height and mating header selection remain open. |
| 4 | J4-J7 | JST SM06B-SRSS-TB 6-position receptacle | JST SH, 1.0mm pitch, side-entry SMD, 2 mounting pegs | VL53L0X module connectors, wired in the GY-VL53L0XV2 header order: 1 VCC, 2 GND, 3 SCL, 4 SDA, 5 GPIO1 (no-connect), 6 XSHUT. Mounting pegs are tied to GND. Order the full suffix, e.g. SM06B-SRSS-TB(LF)(SN). |
| 2 | SW1, SW2 | Normally-open momentary tactile switches | E-Switch TL3301N-family SMD footprint | RESET and BOOT; select full suffix for actuator height and operating force. |
| 1 | SW3 | C&K JS102011SAQN SPDT slide switch | Manufacturer-specific SMD footprint | Battery ON/OFF gate control. |
| 2 | R1, R6 | 5.1kΩ resistors | 0805 | Tolerance and manufacturer part numbers not specified. |
| 2 | R2, R12 | 10kΩ resistors | 0805 | Tolerance and manufacturer part numbers not specified. |
| 2 | R3, R4 | 22Ω resistors | 0805 | Current schematic values; USB series-resistor decision is recorded as issue 10. |
| 1 | R5 | 1MΩ resistor | 0805 | Tolerance and manufacturer part number not specified. |
| 1 | R7 | 120kΩ resistor, 1% | 0805 | UVLO threshold resistor. |
| 1 | R8 | 24kΩ resistor, 1% | 0805 | UVLO threshold resistor. |
| 1 | R9 | 39kΩ resistor, 1% | 0805 | USB enable resistor. |
| 1 | R10 | 470kΩ resistor, 1% | 0805 | Battery ADC divider. |
| 1 | R11 | 220kΩ resistor, 1% | 0805 | Battery ADC divider. |
| 1 | R13 | 2.2kΩ resistor | 0805 | Tolerance and manufacturer part number not specified. |
| 1 | R14 | 100kΩ resistor | 0805 | MOSFET gate pull-up; tolerance and manufacturer part number not specified. |
| 2 | R15, R16 | 2.2kΩ resistors | 0805 | I2C SDA/SCL bus pull-ups to 3.3V — one pair for the whole bus, at the host. Tolerance and manufacturer part numbers not specified. |
| 2 | C1, C12 | 10µF capacitors | 0805 | Voltage ratings, dielectric and exact MPNs are not set. C12 is on VSYS; its effective input capacitance needs review under issue 8. |
| 4 | C2, C4, C5, C6 | 100nF capacitors | 0603 | Voltage ratings, dielectric and exact MPNs are not set. |
| 1 | C3 | 1µF capacitor | 0603 | Voltage rating, dielectric and exact MPN are not set. |
| 2 | C7, C11 | 22µF capacitors | 0805 | Voltage ratings, dielectric and effective capacitance under 3.3V bias need final selection. |
| 1 | C8 | 4.7nF capacitor | 0603 | Voltage rating, dielectric and exact MPN are not set. |
| 2 | C13, C14 | 100nF, 50V capacitors | 0603 | Voltage rating is specified; exact manufacturer parts remain open. |
| 1 | C15 | 10µF, 16V capacitor | 0805 | Reservoir for the four ToF modules at J4-J7. Voltage rating is specified; dielectric and exact manufacturer part remain open. |
| 1 | C16 | 100nF, 16V capacitor | 0603 | HF decoupling for the ToF module rail. Voltage rating is specified; exact manufacturer part remains open. |

## PCB-only features

TP1 (VBAT), TP2 (3V3), TP3 (GND) and TP4 (SW) are each a 1.5mm copper test pad.
They do not require purchased test-point posts or loops. The fabricated PCB,
external 2S pack and its mating XT30 lead are separate from the 54 fitted parts.

## Off-board sensor parts

Needed to make the ToF sensors work, but not fitted to this PCB:

| Qty | Item | Notes |
|---:|---|---|
| 4 | GY-VL53L0XV2 breakout module (silkscreen `HW-842`) | The fitted module. 6-pin 2.54mm header: VCC, GND, SCL, SDA, GPIO1, XSHUT. VCC 3.0-5.0V, on-board 2.8V regulator, SCL/SDA level-shifted to the VCC rail, and **XSHUT pulled up on-board** so the sensors are enabled by default. Do not substitute a module with a different header order without re-cutting the cables — the connector reproduces this one 1:1. |
| 4 | 6-way cable, JST SH to 2.54mm | JST SHR-06V-S-B housing plus SSH-003T-P0.2 crimp contacts (28-32 AWG) at the board end; a 6-way 2.54mm socket or direct-soldered wires at the module end. Straight-through, conductor for conductor. Keep them short, both for bus capacitance and to limit the 40mA VCSEL current loop. |

## Ordering details to settle

- **D1/D2:** choose actual SMA Schottky part numbers and their ratings.
- **Capacitors:** most voltage ratings and all exact part numbers remain unset.
  Select dielectric and effective capacitance at operating bias, especially C12
  and the 22µF output capacitors; finish issue 8 before freezing quantities.
- **F1:** the 3A hold-current choice is provisional while motor and fan currents
  remain unknown. Verify the complete battery path before fabrication.
- **R15/R16:** 2.2kΩ follows the VL53L0X datasheet recommendation (1.5-2kΩ at
  2.8V, 400kHz) scaled to 3.3V. If the chosen modules carry their own pull-ups,
  four 10kΩ in parallel with this pair lands near 1.2kΩ — still only 2.8mA of
  sink, inside the part's 4mA VOL spec, but worth re-checking against the actual
  module schematic.
- **D3:** the generic BAT54W name alone is ambiguous between manufacturers.
  [Vishay BAT54W-E3-08](https://www.vishay.com/docs/86408/bat54w.pdf) is SOD-123
  and matches the assigned package. [Nexperia BAT54W](https://assets.nexperia.com/documents/data-sheet/BAT54W_SER.pdf)
  uses SOT323. The schematic currently links a Nexperia BAT54-family datasheet;
  its manufacturer/MPN/datasheet fields need to identify the chosen SOD-123 part.
- **Switches, sockets, LEDs and passives:** finalize remaining ordering suffixes,
  mechanical heights, ratings and manufacturer parts. SW1/SW2 specify the
  [E-Switch TL3301N footprint family](https://www.e-switch.com/product/tl3301-series-smt-tactile-switch/),
  not a complete orderable switch number.

The USB connector model is taken from the assigned footprint and checked against
[Amphenol's 12401948E412A product page](https://www.amphenol-cs.com/product/12401948e412a.html).
No schematic component values or wiring were changed to prepare this list.
