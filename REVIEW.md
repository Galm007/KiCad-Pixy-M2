# Pixy-M2 layout review — 2026-09-21

> **Status, 2026-09-22: findings 1–5 are fixed on the board; 6–8 are open.**
> The fix is a single reproducible pass, `tools/autoroute/rework.py`, run against a
> snapshot of the routed board; DRC after it is byte-for-byte the same verdict as
> before (0 unconnected, 0 schematic-parity issues, only the four pre-existing J1
> `hole_clearance` errors and the U1 `lib_footprint_mismatch` warning). What changed,
> with measurements, is written up under "Motor-region rework" in `CLAUDE.md` /
> `AGENTS.md`. Headline numbers: the motor-B pair goes from 0.267 Ω to 0.066 Ω
> (0.393 V / 0.578 W → 0.096 V / 0.141 W at 1.47 A), each driver's exposed pad gains
> two in-pad thermal vias plus 165 mm² of F.Cu ground pour, and C18/C20 move from
> 4.95 mm / 3.61 mm to 1.33 mm from their VM pin with the loop closed in top copper.
> Finding 4 was then fixed by pairing the motor-B outputs rather than by moving U5:
> the enclosed loop goes 423.6 → 111.5 mm², mean separation 7.17 → 1.39 mm, and motor
> copper to `REG_EN` 0.27 → 8.51 mm, to the SW node 0.28 → 6.62 mm. U5 stayed put
> because J9 sits off the In2 VBAT island and next to the buck output — see
> "Issue 4" in `CLAUDE.md` for the full argument and the two costs it carries.
> Finding 5 followed on 2026-09-22: six parts moved and the regulator block hand
> routed. TP4's two vias and 2.55 mm of back-layer switch-node copper are gone (the
> node is now 3.57 mm² on one layer with no vias), C17 straddles U3's IN and GND pins
> so the two return vias are 0.95 mm apart instead of 5.88 mm, L1 → C7 → C11 is a
> single top-layer run where no copper joined them at all before, and FB has its own
> sense trace to C11 that stays 2.1 mm clear of the switch node. One regression is
> recorded there too: REG_EN now passes 0.99 mm from switching copper, having moved
> out of a via-in-pad.

The saved layout needs another routing pass before fabrication. The most consequential findings are undersized motor-output copper and inadequate thermal copper around the motor drivers. The segmented bends themselves are not a manufacturing defect.

Reviewed the current, uncommitted PCB on disk using KiCad 10.0.5. Refilled zones and ran DRC plus schematic parity on a temporary copy; exported a fresh schematic netlist; extracted pad, track and via geometry; inspected all four copper layers. No electrical or mechanical design files were changed. Source SHA-256: `7c847069c641a7e9ac56d550b5bf75c23de3d4db644b60ffecd3322e98b71fdd`.

Coordinates below are absolute KiCad millimetres. Board front-left is (100, 60). Measurements describe geometry; noise and temperature consequences are engineering assessments, not simulation or hardware test results. The figures highlight track centerlines and pad envelopes; copper planes are omitted in these illustrations.

1. **High priority: motor outputs have long 0.15 mm sections.**

   | Net | Total track length | Length at 0.15 mm |
   |---|---:|---:|
   | MOT_A_1 | 15.02 mm | 10.99 mm |
   | MOT_A_2 | 16.24 mm | 6.35 mm |
   | MOT_B_1 | 41.95 mm | 38.80 mm |
   | MOT_B_2 | 48.06 mm | 40.73 mm |

   These are extended narrow runs, not merely short escapes from WSON pads. For example, MOT_B_1 is 0.15 mm wide for the entire 19.5 mm segment from (119.55, 113.10) to (139.05, 113.10). MOT_B_2 has another 15.65 mm straight segment of the same width near y=97.50.

   Using the board's specified 35 µm outer copper and copper resistivity at 20°C, the two motor-B traces together have approximately **0.268 Ω** resistance. At a sustained 1.47 A, that is approximately **0.394 V drop and 0.579 W copper loss**. This excludes connectors, vias and rising copper resistance with temperature. PWM operation changes average heating according to RMS current; this calculation does not establish an actual trace temperature.

   Reroute motor trunks with broad copper throughout, retaining fine necks only where necessary immediately at pads. The intended 0.8 mm trunk width is a useful starting point, with final sizing against current, copper and allowed temperature rise. Define a motor-specific minimum-width rule so DRC catches extended necks.

   [Motor routing illustration](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-21/motors.png)

2. **High priority: U4's exposed pad has a poor heat path; U5 also needs better heat spreading.**

   U4 pin 9 is at (109, 114), with a 0.9 × 1.6 mm copper pad. There is **no via inside it**. Its external copper connection is a 0.4 mm trace to a single ground via at (109, 112.75). U4's pin-7 ground via is separate; it is not a via underneath the exposed pad. U5 has one via inside its exposed pad at (117.20, 113.75), plus the offset connection above the package. There is no top ground pour around either driver.

   This is materially different from the routing note claiming two vias per exposed pad. Ground connectivity is correct; the concern is heat flow. At high motor current, relying on a small pad and narrow neck creates avoidable thermal-shutdown risk. Add broad exposed-pad ground copper and appropriate thermal vias to the ground plane, coordinating via treatment with assembly. TI recommends maximizing thermal copper and connecting the exposed pad to top/internal ground through vias. [DRV8231A datasheet, layout section](https://www.ti.com/lit/ds/symlink/drv8231a.pdf)

   [Driver copper illustration](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-21/driver.png)

3. **High priority: motor bypass capacitors do not form compact local supply loops.**

   C18's VBAT pad is 4.95 mm from U4 VM; C20's is 3.61 mm from U5 VM, measured pad-center to pad-center. More significantly, each capacitor connects to its own plane vias, while each VM pin reaches the VBAT plane through a 0.15 mm × 0.762 mm track and one via. There is no direct top-layer capacitor-to-VM connection. Their grounds also return independently through the plane.

   The stackup separates the L2 ground and L3 power planes by a 1.065 mm core. Those plane connections therefore do not substitute for a tight local bypass loop. Move/orient C18 and C20 beside the VM/GND side of each driver and close the switching-current loop locally with short, broad copper. Keep C19/C21 nearby. This reduces supply ringing and noise injected into the shared rails. TI's layout guidance calls for close VM capacitors and thick high-current connections. [DRV8231A datasheet](https://www.ti.com/lit/ds/symlink/drv8231a.pdf)

4. **Medium priority: motor B takes two widely separated routes, including through the buck area.**

   U5 is at (117, 114), while J9 is at (158, 107). MOT_B_1 traverses approximately y=113.1, whereas MOT_B_2 detours through approximately y=97.5–97.6, immediately below U3's VIN/GND pads and beside its enable network. The two outputs are about 15 mm apart across part of the board.

   This spreads switching current across the regulator region and increases motor-loop area. Widening the same route alone will not fix its placement. Move U5 and its supporting parts toward J9, or find a paired route through the motor region away from the buck. Preserve the accepted connector pinout; the avoidable separation is on the PCB.

   [Buck-area illustration](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-21/buck.png)

5. **Medium priority: the buck power stage needs more deliberate local routing.**

   TP4 extends the SW node onto B.Cu through two vias at (142.85, 96.85) and (142.85, 99.40), joined by a 2.55 mm bottom trace. This is a test-point branch, not the main U3-to-L1 path; nonetheless, it unnecessarily spreads switching copper across both faces.

   C6 is about 5 mm above U3, creating extended bootstrap connections. C17 is reasonably close to VIN (1.87 mm pad-center distance), but its ground via and U3's ground via are approximately 5.88 mm apart. L1 output, C7/C11 and FB each independently connect to the 3V3 plane; there is no compact top output-filter connection or dedicated feedback pickup at the output capacitor.

   Rework this as a compact regulator block: place C6 beside BST/SW, close the input/output loops locally, take a quiet feedback sense from the output-capacitor node, and shorten or remove TP4's branch. There is no claim that the fixed-voltage regulator needs a feedback divider. The component manufacturer's reference layout is the appropriate starting point. [AP63203 datasheet, page 15](https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf)

6. **Medium priority: several unfilled vias lie inside solder pads.**

   Examples include U2 pin 1 at (152.40, 147.15), U3 EN at (137.60, 96.05), U5's exposed pad, several U1 pads and L1's output pad. These are 0.3 mm drills. The board specifies front/back tenting but no filling or capping. Where a via lies inside a pad's mask opening, the pad opening exposes the hole despite the general tenting setting.

   Solder can wick into these holes, especially troublesome for small IC pads. Move ordinary signal vias outside solderable pad areas. For intentional thermal via-in-pad, specify an assembly-compatible hole, stencil and filling/capping process. Confirm the actual order option; tenting and filled/capped via-in-pad are different processes. [JLCPCB via covering guidance](https://jlcpcb.com/help/article/pcb-via-covering)

7. **Medium priority: USB is not routed as a controlled differential pair.**

   U2-to-U1 D+ and D− are 18.43 and 13.74 mm of 0.2 mm copper with varying separation and a pronounced D+ detour around U2. Before U2, D− changes to B.Cu and back through two vias while D+ remains on F.Cu. These asymmetric layer transitions matter more than the visual bend style.

   The two connector-side net lengths are 5.52 mm and 9.83 mm. Do not interpret the 4.69 mm difference after U2 as the entire end-to-end skew: the difference before U2 partially offsets it, and the connector nets contain branches.

   Reorient U2 if useful and route both sides as a consistent pair against the chosen JLCPCB stackup. Espressif specifies parallel, matched routing at 90 Ω ±10%, a continuous reference, and minimized transitions. This is a robustness/compliance concern; these short Full Speed routes are not proof that USB will fail. [Espressif USB layout guidance](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/pcb-layout-design.html#usb)

   [USB routing illustration](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-21/usb.png)

8. **Medium priority: project rules do not encode the electrical routing requirements.**

   The project has only the Default netclass, no netclass assignments and a global 0.15 mm minimum track width. It has no motor-specific width constraint and no enforceable USB pairing/impedance geometry. This explains why the narrow motor traces pass DRC. Configure those requirements before rerouting, with narrowly scoped pad-escape exceptions where needed.

Additional review observations:

- GPIO2 and GPIO10 current-sense nets have 52.02 and 40.67 mm of track. Some sections run alongside drive-control signals. Improve isolation where convenient during motor rerouting; validate current readings during switching on hardware. Their 1.5 kΩ conversion resistors mean these are not the same 150 kΩ source impedance as VBAT_SENSE. Length alone is insufficient evidence of a fault. [Current-sense routing illustration](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-21/sense.png)
- The shield net has 32.26 mm total branch copper and a bottom-layer detour behind U2. Shorten the shell-to-C8 return during USB rework; the long narrow path adds inductance to the intended ESD return. This does not challenge the existing shield RC topology.
- Mechanical attachment is still provisional. There are reservation drawings but no dedicated chassis mounting holes. Confirm the actual clamp/bracket/adhesive scheme and motor, battery, cable and antenna clearances before ordering; holes are not mandatory if the chosen attachment method does not need them.
- D6 has two VBAT vias but one ground via. A broader local return and more ground stitching are useful while rebuilding the motor power region. Its actual surge performance requires measurement.

Checks that did not reveal a new flaw:

- **Zero unconnected items and zero schematic-parity issues.** No track short, copper-clearance or courtyard error was reported by the fresh check.
- L2 is a continuous ground plane with no signal routing. The antenna overhang has all-layer copper exclusions; no copper violation was reported there. This does not validate RF clearance to external mechanics.
- The remaining DRC errors are four duplicate-pad reports of two physical 0.25 mm pad-to-NPTH gaps inside J1, against the project's 0.30 mm rule. JLCPCB lists 0.20 mm NPTH-to-track clearance, so these are not automatically a fabrication rejection. Reconcile the connector land pattern and applicable fabricator clearance before changing or excluding the rule. [JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- The single U1 library-footprint mismatch warning corresponds to a previously documented footprint customization; it is not evidence of a net or pin-map error.

Evidence: [fresh DRC report](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-21/drc.json) and [per-net measurements](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-21/measurements.json). Total extracted routing is 1694 track segments, 242 vias and 2241.44 mm of copper centerline. No thermal, signal-integrity or EMC simulation was performed, and this was not a complete component-rating or BOM audit.
