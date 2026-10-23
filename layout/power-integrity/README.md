# Independent motor cutoff, current margin and USB isolation

Added 2026-10-14 (`devkit-daughterboard`); revised 2026-10-15 after a review of
that change. The socket selection/mechanical issue is unchanged.

## What the circuit does

**Motor cutoff independent of USB.** R7/R8 disable only the buck, so USB could
keep the ESP32 alive and driving motors from a flat pack. U6 (TLV3012B)
monitors VBAT on its own; U7 (SN74LV4066A) disconnects GPIO39–42 from both
bridges when MOTOR_OK is low, and the drivers' internal 100 kΩ pulldowns
command coast. U6's power-on reset holds its push-pull output low for up to
1.9 ms, and R27 keeps the switch enables low while U6 is unpowered. No GPIO or
firmware cooperation is needed.

R24/R25/R26 are 100 kΩ / 23.2 kΩ / 825 kΩ, **0.1 %, 25 ppm/°C thin film**
(Yageo RT0805BRD07100KL / 0723K2L / 07825KL). With the 1.242 V reference:

```
Venable = 1.242 × (1 + 100/23.2 + 100/825) = 6.746 V   (3.37 V/cell)
Vcoast  = Venable − 3.3 × 100/825          = 6.346 V   (3.17 V/cell)
```

C27 filters the node (18.4 kΩ × 100 nF ≈ 1.8 ms). Over −40…125 °C, counting
reference initial error and drift, 9 mV offset, the full 8 mV hysteresis,
5 mV of common-mode/supply effects, reference loading and resistor tolerance
and drift, the DC envelopes are **6.01–6.74 V (coast)** and **6.39–7.08 V
(enable)**. A pack resting at 3.6 V/cell always enables the motors. These are
DC envelopes, not response bounds for a fast dip.

The cutoff is a backstop **under** firmware's own cutoff (about 6.8 V under
load, latched so a rebounding pack cannot restart a stalled motor). Below VM
6.5 V the DRV8231A still regulates current; TI only specifies its ±6 % mirror
accuracy at VM ≥ 6.5 V. The 2026-10-14 version cut off at 6.92 V and enabled at
7.39 V to stay inside that condition at every corner, which cost the bottom
third of the pack and made a half-charged pack refuse to enable; firmware would
then have had to stop even higher, near 3.7 V/cell.

**Current limit with margin.** U6's REF supplies MOTOR_VREF to both bridges,
and R17/R18 are 1 kΩ 1 %, ≤100 ppm/°C (Yageo RC0805FR-071KL):

```
ITRIP  = 1.242 / (0.0015 × 1000) = 0.828 A nominal
IPROPI = 1.5 V/A, about 1.242 V at trip
```

At 1 A the minimum specified mirror gain, the minimum resistor and the maximum
reference leave 108 mV of trip-comparator margin. TI specifies the gain only at
1 A, VM ≥ 6.5 V and VIPROPI ≤ 3 V, so the 0.92 A upper estimate is not a
guaranteed PWM peak: scope blanking, ripple and cable heating.

MOTOR_VREF runs about 74 mm from U6, at the rear of the socket rows, to the
drivers, and inside the motor corner it passes 0.26 mm from MOT_A_2 (the old
3V3 VREF copper, unchanged). It used to be the stiff 3V3 plane; it is now a
single reference output. **C25 (2.2 nF) at U6 and C28 (4.7 nF) where the feed
splits to U4.4 and U5.4** decouple it. Their sum, 7.6 nF with tolerance, stays
under the TLV3012B REF's 10 nF stability limit.

**Separate USB and buck sources.** U3/L1/C7/C11 and the feedback are on
BUCK_3V3, upstream of U8. U8 (LM66100) and Q2 (AO3401A) feed ESP_3V3: Q2's
source is BUCK_PASS and its drain ESP_3V3, opposing U8's body diode. Q3 pulls
Q2's gate low only while U8's ST is high-impedance (U8 on); R31 turns Q2 off
when ST is low (U8 off). R30 is 100 kΩ: Q3 only sinks R31's 33 µA, so 26 µA
of base drive saturates it, and the battery no longer feeds 0.26 mA into its
base continuously, deep sleep included.

U1.21 is **voltage sensing only**, through R28/R29 (10 kΩ / 82 kΩ) into U8's
CE comparator, which is referenced to U8's VIN (on below VIN − 80…250 mV, off
above VIN + 0…80 mV). With valid USB, CE is above VIN and the buck path opens;
the devkit LDO supplies all logic. Without USB, a devkit 5 V rail back-fed even
to the full buck voltage keeps CE below the enable threshold.

USB-priority selection is **not seamless**: on unplug, the devkit LDO drops out
before U8 turns on (~40 µs typical; the datasheet gives no maximum). **C30
(100 µF X5R 1206, Murata GRM31CR60J107ME39L)** holds ESP_3V3 meanwhile. Taking
45 % of its capacitance at 3.3 V bias, −20 %, plus C1/C15, and ignoring the
devkit's own capacitance, the sag is about 0.42 V at 0.5 A and 0.2 V at 0.25 A.
Scope it under the intended load.

The LDO's 800 mA electrical rating does not establish a safe continuous board
load: at 0.7 A from 4.6 V it would dissipate about 0.91 W. Begin USB bring-up
with RF off.

## Pin maps

| Part | Verified pin mapping |
|---|---|
| U6, TLV3012B DBV | 1 OUT, 2 GND, 3 IN+, 4 IN−, 5 REF, 6 VCC |
| U7, SN74LV4066A PW | Channels 1↔2, 4↔3, 8↔9, 11↔10; enables 13/5/6/12; 14 VCC, 7 GND |
| U8, LM66100 DCK | 1 VIN, 2 GND, 3 CE, 4 NC, 5 ST, 6 VOUT |
| Q2, AO3401A | 1 G, 2 S, 3 D |
| Q3, MMBT3904 | 1 B, 2 E, 3 C |

## 2026-10-15 review and fixes

The 2026-10-14 layout placed U8's cluster and U7 across existing corridors and
ripped only the copper pieces touching the new pads; A* then patched the loose
ends around the new parts. DRC was clean, but:

| Finding (2026-10-14) | Fix (2026-10-15) | Result |
|---|---|---|
| IMU SPI (GPIO12/13/14) re-routed along motor B's trunk: 0.75–1.35 mm from MOT_B_2 (was 10–14 mm) | clusters moved out of the SPI diagonal; displaced nets ripped whole and re-routed; 5 mm router floor; DRC rule `SPI clear of motor and switch copper` | GPIO14 10.0 mm, GPIO13 11.9, GPIO12 14.0 (HEAD values) |
| Encoder GPIO21 re-routed past the buck: via 1.60 mm from the SW node (was 9.75), 27.9 → 79.5 mm long | same, plus DRC rule `Encoders clear of the switch node` | 9.73 mm, 27.9 mm long |
| Collateral detours: SDA 115 → 151 mm, GPIO3 64 → 100, GPIO6 86 → 123 | whole-net re-routing | SDA 119 mm, GPIO3 64, GPIO6 86 |
| BUCK_3V3 C11 → U8: 23.5 mm with 4 vias; R30 fed by a 23 mm 0.6 mm loop; BUCK_GATE 29.6 mm, 4 vias | U8 cluster in front of the devkit, fed straight from L1.2 | BUCK_3V3 supply ~2 mm, no via; BUCK_PASS 2.8 mm; BUCK_GATE 3.1 mm |
| MOTOR_UVLO node spread over 24.9 mm | rear cluster around U6.3 | 5.4 mm, ≥43 mm from motor copper |
| MOTOR_VREF a bare 65 mm trace, 10.6 mm of it within 2 mm of motor copper | C28 at the driver split, C25 2.2 nF | see above |
| No designators on the 18 new parts; C11/R19/R20/R21's hidden | `silk_refs.py` | all but R28/R29 placed (F.Fab only for those) |
| MOTOR_OK, MOTOR_VREF, BUCK_3V3 only probe-able under the devkit | TP10/TP11; the U8 cluster sits in front of the devkit | BUCK_3V3 at L1.2/C26 |
| Schematic text collisions (GND/BUCK_3V3, BUCK_ENABLE/Q3 pin, MOTOR_VREF/GPIO42); MOTOR_VREF, DRV_x_INn and USB_PRIORITY labels crossing block frames | U4/U5 groups shifted 7.62 mm right; U8/Q2/R30/C25/C27 nudged | rendered and checked |
| Cutoff at 6.92 / 7.39 V | lowered (user decision) | 6.35 / 6.75 V |
| USB unplug may reset the MCU | C30 hold-up (user decision) | ~0.2 V sag at 0.25 A |

Same-layer clearances and lengths come from
`/usr/bin/python3 layout/power-integrity/measure.py Pixy-M2.kicad_pcb`
(`measurements.json`). Copper totals: **233 vias, 864 segments, 2.20 m of
track** (the 2026-10-14 board: 288, 1,103, 2.62 m; before the revision: 192
vias, ~2.0 m).

## 2026-10-16: SCL clear of the buck

SCL (GPIO9) passed **0.45 mm from C6's BST pad**, on HEAD as well as on both
power-integrity boards. Between J6 and J5 it has to pass south of C15, and
C12's GND via, just north of C12's GND pad, closed that lane. A* therefore
dropped SCL under C12's body and back up past C6. The via now sits east of the
pad, at (135.55, 91.53), which is also nearer U3.4. Stage 21 always rips and
re-routes SCL and SDA, with a 3 mm floor from SW/BST in the router, in
octilinear and in DRC (`I2C clear of the switch node`).

| | Before | After |
|---|---|---|
| SCL to SW/BST copper | 0.45 mm (C6.1) | 4.37 mm |
| SCL length | 119.6 mm | 117.4 mm |
| SDA to SW/BST copper | 5.18 mm | 5.18 mm |

Only SCL's run between J6 and J5 and C12's GND tap changed; every other track
and via is identical. One 0.1 mm step remains where SCL's run meets C15's
lane, a router-grid offset like ten others on the board.

Not changed: both I²C lines cross the end of motor B's trunk beside J9. SDA
passes 0.25 mm from MOT_B_1's B.Cu trunk (HEAD 0.28) and SCL 0.75 mm (HEAD
1.43, on F.Cu).

## Placement

- **Front, in front of the devkit's USB end** (accessible): U8, Q2, Q3,
  R28–R31, C26. Motor B's trunk (MOT_B_1 on B.Cu, MOT_B_2 on F.Cu, stacked)
  walls this area off from the socket rows, so every connection arrives from
  the front side; DEVKIT_5V runs under J9. U8's GND pin is tapped between its
  pad columns to a via below the package: a via under an SC70 body does not fit
  (0.65 mm between the pad columns).
- **Rear, between the socket rows:** U7 with each signal pin escaping to its
  own staggered via (the 2026-10-14 pattern, moved), C24; U6, R24–R27,
  C23/C25/C27 below it; C30. VBAT is taken from R10.1.
- **Corner:** C28 at (115.0, 120.2) on the MOTOR_VREF diagonal; TP11 at
  (124.9, 117.0).
- **TP10** (MOTOR_OK) at (132.0, 156.6), rear-left, outside the devkit.
- **TP2/TP3** moved to (148.4, 86.6) / (151.8, 86.6), between J5 and J7,
  labelled `3V3` and `GND`.

Every re-routable net (`devkit.FULL`, and GPIO2/GPIO10 outside the motor
corner) with copper in a cluster box is ripped whole and routed again in the
devkit stage's order: GPIO4, 6–9, 15, 21, 47, 48. The stage asserts the old U1
placement and R17 value, changes all relevant part fields together, and
asserts that motor-output copper and the feedback segments are unchanged.

## DRC rules added

| Rule | Constraint | Negative test |
|---|---|---|
| Motor UVLO clear of switching copper | MOTOR_UVLO ≥ 5 mm from motor, SW, BST | (2026-10-14) a 1 mm MOTOR_UVLO track at (136, 99.5) fires at 4.006 mm |
| SPI clear of motor and switch copper | GPIO11–17 ≥ 5 mm from motor, SW, BST | 15 violations on the 2026-10-14 board; a GPIO14 track at y 109.6 fires at 0.75 mm |
| Encoders clear of the switch node | GPIO18/21/47/48 ≥ 5 mm from SW, BST | 3 violations on the 2026-10-14 board; a GPIO21 track at (140, 101.5) fires at 1.51 mm |
| I2C clear of the switch node | GPIO8/9 ≥ 3 mm from SW, BST | 2 violations on the 2026-10-15 board (SCL against C6.1, 0.45 mm) |

## Reproduce and validate

Close KiCad before editing. The schematic conversion is one-shot from the
2026-10-13 devkit schematic.

```sh
git show 7a35cc5:Pixy-M2.kicad_sch > /tmp/BEFORE.kicad_sch
kicad-cli sch export netlist --format kicadsexpr -o /tmp/before.net /tmp/BEFORE.kicad_sch
python3 tools/schematic/power_integrity.py /tmp/BEFORE.kicad_sch Pixy-M2.kicad_sch
kicad-cli sch export netlist --format kicadsexpr -o /tmp/after.net Pixy-M2.kicad_sch
python3 tools/power_integrity_check.py /tmp/before.net /tmp/after.net
/usr/bin/python3 tools/autoroute/rework.py
kicad-cli sch erc --format json -o /tmp/erc.json Pixy-M2.kicad_sch
kicad-cli pcb drc --schematic-parity --refill-zones --save-board --format json -o /tmp/drc.json Pixy-M2.kicad_pcb
/usr/bin/python3 tools/autoroute/via_openings.py Pixy-M2.kicad_pcb --output /tmp/apertures.json
/usr/bin/python3 layout/power-integrity/measure.py Pixy-M2.kicad_pcb
```

The netlist audit checks all **278 pins**, every old part's fields and every
new part's fields, and that only the intended nets changed. The schematic has
**72 nets and 79 references** (73 fitted PCB parts, counting U1 as two sockets
and excluding the bare test pads TP1–TP4 and TP9–TP11). ERC 0, DRC 0/0/0 with
schematic parity, aperture audit 0. A full replay from
`base-routed.kicad_pcb` and a replay of stages 21–22 from an earlier run's
pre-power checkpoint produce identical copper. Results are in
`validation.json`; the DC corners and pin audit in `design-audit.json`.

## Bench tests still required

1. USB on, command both motors continuously, sweep VBAT down and up. Measure
   each driver input and output, the actual trip/release voltage (TP10), filter
   delay and coast behaviour. Repeat with battery-only power and at temperature.
2. Measure both motor currents at full pack, acceleration, blocked rotor and
   every intended PWM frequency/duty; check TP11 stays at 1.242 V while the
   motors switch. Verify sustained/RMS cable current and connector temperature;
   stop prolonged stalls in firmware.
3. With RF off initially, sweep the USB logic load. Measure the ESP_3V3
   minimum, LDO and U8/Q2 temperatures, then repeat with the intended
   RF/sensor workload.
4. Scope ESP_3V3 at USB plug/unplug and battery switching under load (C30's
   ride-through), and check reverse current.
5. Confirm the firmware cutoff (~6.8 V under load, latched) leaves the hardware
   backstop untriggered in normal runs and does not chatter as a loaded pack
   rebounds.

## Primary references

- [TI DRV8231A](https://www.ti.com/lit/ds/symlink/drv8231a.pdf): current mirror,
  current regulation (VREF 0–3.6 V) and input pulldowns.
- [TI TLV3012B](https://www.ti.com/lit/ds/symlink/tlv3012b.pdf): reference
  1.223–1.260 V, 100 ppm/°C, 0.5 mA, ≤10 nF load; POR; fail-safe inputs.
- [TI SN74LV4066A](https://www.ti.com/lit/ds/symlink/sn74lv4066a.pdf): switches,
  pin map and off leakage.
- [TI LM66100](https://www.ti.com/lit/ds/symlink/lm66100.pdf): CE comparator
  thresholds relative to VIN, ST low when disabled, body diode, tON.
- [AOS AO3401A](https://www.aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf).
- [Yageo RT series](https://www.mouser.com/datasheet/2/447/PYu_RT_1_to_0_01_RoHS_L_12-1995645.pdf).
- [Espressif DevKitC-1 schematic](https://dl.espressif.com/dl/schematics/SCH_ESP32-S3-DevKitC-1_V1.1_20220413.pdf).

Artifacts: [schematic detail](power-schematic.png),
[combined copper](pcb-copper.png), [measurements](measurements.json),
[DC corners and pin audit](design-audit.json), [validation](validation.json),
[DRC](drc.json), [ERC](erc.json), [apertures](apertures.json),
[netlist diff](netdiff.txt).
