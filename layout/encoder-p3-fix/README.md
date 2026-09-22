**Encoder detour cleanup — audit P3, 2026-09-22**

GPIO48 now takes a local route between J8.4, R20.2 and U1.25. Its total track
length falls from **72.36 mm to 26.03 mm (64% shorter)**, removing the excursion
around TP5 and J11. The route uses 0.2 mm tracks and four 0.6/0.3 mm vias. All
four drill edges are at least **0.45 mm clear of SMD solder-mask openings**.

The J8-to-R20 branch and U1 pad escape were retained; a short bridge above R20
reaches the bottom-layer corridor alongside GPIO47. Component positions, pad
geometry and every other net's tracks and vias are unchanged. Copper zones were
refilled after the edit.

`encoder48_cleanup()` in `tools/autoroute/rework.py` reproduces the verified route
after the generic via relocation pass, so regeneration does not restore the
detour. Its generated geometry was checked against the validated board.

Fresh KiCad 10.0.5 DRC with zone refill and schematic parity reports **zero
unconnected items, zero schematic mismatches and zero new violations**. The
existing four J1 hole-clearance reports and U1 library-footprint warning remain.
This closes the layout concern in P3; it is not a hardware encoder-noise test.

[Route illustration](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/encoder-p3-fix/encoder-after.png)
· [DRC report](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/encoder-p3-fix/drc.json)
· [Measurements and scope checks](/home/galm/Workspace/KiCad/Pixy-M2/Pixy-M2/layout/encoder-p3-fix/validation.json)
