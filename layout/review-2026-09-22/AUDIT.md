**Audit of Claude's fixes — 2026-09-22**

Follow-up: **P3's encoder detour has been resolved**, reducing GPIO48 to 26.03 mm.
See the [fix and validation](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/encoder-p3-fix/README.md).
The findings and measurements below describe the audited `86f2628` snapshot.

Issues 1–5 are substantively addressed in the copper. Issue 6 is **not fully fixed**: 12 unintended via holes still overlap solder-pad openings, in addition to the four intentional driver thermal vias. The issue-6 reroute also worsened USB D−, and introduced a large, unnecessary encoder detour. I would not accept the blanket “findings 1–6 are fixed” statement in `REVIEW.md`.

Reviewed HEAD `86f2628` against routed baseline `3a8bd96`, with `e802e25` used to isolate the final via-relocation pass. PCB SHA-256: `dff608a097b87df66954081140b5fe07cb19f2f9c4d8a6019298e1b60e6f39a9`. KiCad 10.0.5. The board, schematic, project settings, and original review were left unchanged; only this audit and its evidence were added. Coordinates are absolute KiCad millimetres.

**Verification of the six fixes**

| Original issue | Verdict | Evidence and qualification |
|---|---|---|
| 1. Undersized motor outputs | Fixed in the layout | All four trunks are 0.8 mm. Widths below 0.5 mm are restricted to the driver escapes: 2.50 mm on each OUT1, 0.995 mm on each OUT2. The new minimum-width rule actually works: deliberately narrowing one trunk on each net, on a disposable copy, produced four corresponding violations. |
| 2. Driver thermal paths | Copper fix verified; assembly process remains a dependency | Each exposed pad has two 0.45/0.25 mm vias, a broad connection northward, and six GND vias total within 3 mm of its centre. The filled top ground pour is present and connects to the thermal copper. The four in-pad holes still require the specified fill-and-cap process. This is not a thermal qualification at sustained stall current. |
| 3. Motor bypass loops | Fixed | C18/C20 now sit 1.329 mm pad-centre to VM-pad-centre away. Each has direct top-layer VM and GND connections to its driver. The high-frequency bypass loop no longer depends on separate power-plane taps. Local bulk capacitance is retained. |
| 4. Motor-B routing through the buck | Substantively fixed | The outputs now share the corridor below the buck instead of taking widely separated routes through it. U5 did not have to move to solve the original placement problem. MOT_B_2 uses seven vias, so the result is not a uniformly paired, single-layer route; nevertheless, the original excursion through the regulator is gone. |
| 5. Buck placement/routing | Substantively fixed, with compromises | SW has no vias or bottom copper; C6 is closer; C17 directly spans the IN/GND sides; the two nearby return vias are 0.951 mm apart; L1/C7/C11 have a direct top output connection; FB has a separate sense trace to C11. C6 placement and the long FB trace are compromises, not newly demonstrated faults. C12 remains the bulk input capacitor; C17 is the local 100 nF bypass. |
| 6. Vias in solder pads | **Incomplete** | The via-centre test misses holes that overlap a pad edge. Independent geometry and a temporary physical-hole DRC rule both expose the remaining problem. Details below. |

Motor trace resistance, calculated from actual segment widths and lengths using 35 µm copper and resistivity at 20°C:

| Net | Track length | Track resistance |
|---|---:|---:|
| MOT_A_1 | 16.65 mm | 14.38 mΩ |
| MOT_A_2 | 18.96 mm | 12.49 mΩ |
| MOT_B_1 | 43.51 mm | 30.91 mΩ |
| MOT_B_2 | 59.41 mm | 37.40 mΩ |

Motor B's combined track resistance is approximately 68.3 mΩ, versus 268 mΩ originally: approximately 0.100 V drop and 0.148 W at 1.47 A. These estimates exclude via barrels, connectors, pad spreading resistance and temperature rise. The improvement is real; neither those numbers nor a trace-current calculator establish the assembled board's temperature.

The thermal and bypass changes follow the intent of [TI's DRV8231A layout guidance](https://www.ti.com/lit/ds/symlink/drv8231a.pdf), and the buck changes address the original concerns against the [AP63203 reference layout](https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf).

[Actual filled motor-region top copper](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/motor-top.png) · [Buck routing](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/buck.png)

**P2 — Issue 6 still leaves unintended holes exposed to solder**

The remaining unintended overlaps are:

| Part/pad | Unique holes | Example via centre | Hole penetration into nominal pad opening |
|---|---:|---|---:|
| U1, ground pad 41 | 7 | (133.60, 149.15) | Six holes overlap by 0.100 mm; the seventh by 0.010 mm |
| Q1, drain pads 6/7/8 | 3 | (126.50, 95.35) | 0.059–0.074 mm, accounting for rounded pad corners |
| U5, IPROPI pad 1 | 1 | (115.80, 113.05) | 0.074 mm |
| R22, pad 2 | 1 | (157.40, 111.70) | 0.046 mm |

For example, U1's 0.9 mm square pad at (133.10, 149.14) ends at x=133.55. The neighbouring 0.3 mm drill centred at x=133.60 begins at x=133.45. Its centre is outside the pad, but its hole overlaps the opening by 0.10 mm. The board has zero nominal mask expansion here, so this is already an overlap in the requested artwork, before fabrication tolerances.

`stuck_vias()` in `tools/autoroute/rework.py` tests whether a via **centre** is inside the pad rectangle. It does not test the whole drill against the opening. Consequently these holes escape the final “no via left in a solder pad” check. There are also zero-margin tangencies, including vias beside C7 and C11; these are not included in the 12 positive overlaps.

The four intentional thermal vias sit directly under the separate paste apertures in the U4/U5 footprints. Counting only whether the electrical pad itself has `F.Paste` misses those apertures. The documentation's “0 under solder paste” total is therefore also wrong: the physical aperture audit finds 16 overlapping holes, including the four intentional thermal ones.

Repair the check to compare the complete drill circle with every relevant mask opening, including corner geometry and a positive manufacturing margin. Move the unintended holes or explicitly include them in an approved filled/capped process. Recheck paste-only apertures separately. Update the fabrication note, which currently claims only four holes lie in pad openings. [JLCPCB distinguishes ordinary tenting from the filled/capped process used for via-in-pad assembly](https://jlcpcb.com/help/article/pcb-via-covering).

[U1 overlap illustration](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/u1via.png) · [All 16 overlapping holes, including the intentional four](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/overlapping-holes.csv)

**P2 — The final pass worsens the existing USB issue**

This is a regression of original issue 7, not an unrelated new defect. The via-relocation pass ripped and rerouted the connector-side D− net alone:

| Connector-to-U2 net | Before final pass | Current |
|---|---:|---:|
| D− total branch track length | 9.83 mm | 17.91 mm |
| D− vias | 2 | 4 |
| D+ total branch track length | 5.52 mm | 5.52 mm |
| D+ vias | 0 | 0 |

D− now detours around the R1/C1 area while D+ still goes directly to U2. The additional layer changes and greater separation worsen the pair geometry. These are total branched-net lengths, **not end-to-end differential skew**. They do not prove that a short Full Speed USB connection will fail.

Route both polarities together when fixing issue 7, including the connector branches and the ESD footprint. Avoid treating a differential signal as an arbitrary net during via repair. [Espressif calls for parallel, matched 90 Ω ±10% routing and minimized via transitions](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/pcb-layout-design.html#usb).

[Current USB routing](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/usb.png)

**P3 — Newly introduced encoder detour, worth cleaning up**

GPIO48, the J8 encoder channel with R20's pull-up, grew from 21.61 to 72.36 mm of total copper in the final pass, and from three to four vias (the original baseline had two). It now travels west around TP5, down past J11, then east and back up to U1. GPIO47 remains about 21 mm. This detour adds avoidable trace capacitance and routed area to an external sensor input; with an open-collector encoder, added capacitance also loads the 10 kΩ pull-up.

This is a routing-quality regression, **not evidence of missed encoder counts**. Actual edge integrity depends on the selected encoder output, cable, edge rate and receiver configuration. Restore a short local route while keeping vias outside openings, and check the waveform during motor switching. No need to length-match the two quadrature channels merely because they differ in length.

[Encoder detour](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/encoder-full.png)

**Documentation corrections that should not be mistaken for additional PCB failures**

- The stated SW-node copper area of 3.57 mm² cannot describe the entire node: L1's SW pad alone is 3.60 mm². A polygon union including pads and tracks gives approximately 8.97 mm² on F.Cu now, versus 9.39 mm² on F.Cu plus 1.58 mm² on B.Cu originally. Eliminating the bottom branch is still an improvement; the published area metric overstates what was removed.
- The current refilled motor top zone measures approximately 205.94 mm² total, shared by the motor region. It is not 165 mm² separately available to each driver. Copper area alone is not a thermal model.
- The 0.45/0.25 mm thermal vias are not automatically a JLCPCB annular-ring violation. Their dimensions meet the separate published **via** diameter/hole guidance. Do not incorrectly apply JLCPCB's component-PTH annular-ring minimum to them. [JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)

**Checks and limits**

Fresh zone refill and schematic-parity DRC on a temporary copy returned **0 unconnected items, 0 schematic-parity issues**, and exactly the existing four J1 hole-clearance reports plus the U1 library-footprint warning. The schematic has no diff from the baseline. L2 remains one continuous filled ground region. No new copper short, courtyard collision, outline violation or antenna-keepout violation was reported.

The ordinary DRC result does not cover same-net solder-wicking geometry. A separate temporary rule, `(constraint physical_hole_clearance (min 0.1mm))` for via/SMD-pad pairs, produced 44 additional diagnostic reports, including intentional thermal holes, duplicate pad reports and near misses. That 0.1 mm diagnostic threshold is an audit margin, not a claim that all 44 are distinct JLCPCB violations. The independent signed-distance calculation isolates the 12 unintended positive overlaps above.

Beyond those findings, I did not confirm another distinct new functional defect. Original open concerns about USB, the remaining rule set, current-sense noise, shield return and mechanics still need their own work; they were not relabelled as new discoveries. No thermal, EMC, signal-integrity or hardware qualification was performed.

Evidence: [ordinary DRC](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/drc.json), [physical-hole diagnostic DRC](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/pad-hole-diagnostic-drc.json), [motor-width negative test](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/motor-width-negative-test.json), [per-net measurements](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/measurements.json), [pad-hole distances](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/review-2026-09-22/pad-hole-measurements.json). Current board: 2,309 track segments, 247 vias, 2,431.77 mm total track centreline.
