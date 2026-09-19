# Pixy-M2 component list — one board

Extracted from `Pixy-M2.kicad_sch` on 2026-09-19, following commit `301e854`.

**46 fitted parts**, plus **four PCB test pads**. Quantities are for one board and
exclude assembly spares. Package codes 0603, 0805, 1812 and 2920 are imperial.

The 2S LiPo pack is charged separately. No charger IC or charging components are
required on this board. Motors, motor drivers, IR sensors/emitters, IMU and any
suction fan belong to the daughterboard/system and are outside this controller BOM.

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
| 1 | L1 | 4.7µH power inductor — part/footprint conflict | Assigned: Bourns SRP5030T | Value says SWPA4030S4R7MT; footprint says SRP5030T. Resolve issue 1 before ordering or layout. |
| 1 | F1 | 2920L300/15DR resettable fuse, 3A hold, 15V | 2920 | Provisional current rating; validate motor/fan load, temperature and pack fault current. |
| 1 | F2 | MF-MSMF050-2 resettable fuse, 500mA hold, 15V | 1812 |  |
| 1 | BT1 | AMASS XT30U-M battery connector | Vertical THT, 5mm pitch | Connector model inferred from assigned footprint. BT1 is the PCB connector; the pack is external. |
| 1 | J1 | Amphenol 12401948E412A USB-C receptacle | Manufacturer-specific USB-C footprint | Part inferred from assigned footprint; use this mechanical pattern, not an arbitrary USB-C socket. |
| 2 | J2, J3 | 1 × 22-position female socket headers | 2.54mm pitch, vertical THT | Exact manufacturer, socket height and mating header selection remain open. |
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
| 2 | C1, C12 | 10µF capacitors | 0805 | Voltage ratings, dielectric and exact MPNs are not set. C12 is on VSYS; its effective input capacitance needs review under issue 8. |
| 4 | C2, C4, C5, C6 | 100nF capacitors | 0603 | Voltage ratings, dielectric and exact MPNs are not set. |
| 1 | C3 | 1µF capacitor | 0603 | Voltage rating, dielectric and exact MPN are not set. |
| 2 | C7, C11 | 22µF capacitors | 0805 | Voltage ratings, dielectric and effective capacitance under 3.3V bias need final selection. |
| 1 | C8 | 4.7nF capacitor | 0603 | Voltage rating, dielectric and exact MPN are not set. |
| 2 | C13, C14 | 100nF, 50V capacitors | 0603 | Voltage rating is specified; exact manufacturer parts remain open. |

## PCB-only features

TP1 (VBAT), TP2 (3V3), TP3 (GND) and TP4 (SW) are each a 1.5mm copper test pad.
They do not require purchased test-point posts or loops. The fabricated PCB,
external 2S pack and its mating XT30 lead are separate from the 46 fitted parts.

## Ordering details to settle

- **L1:** the Sunlord value and Bourns footprint describe different packages.
  Choose the intended part and make the schematic fields and land pattern agree.
- **D1/D2:** choose actual SMA Schottky part numbers and their ratings.
- **Capacitors:** most voltage ratings and all exact part numbers remain unset.
  Select dielectric and effective capacitance at operating bias, especially C12
  and the 22µF output capacitors; finish issue 8 before freezing quantities.
- **F1:** the 3A hold-current choice is provisional while motor and fan currents
  remain unknown. Verify the complete battery path before fabrication.
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
