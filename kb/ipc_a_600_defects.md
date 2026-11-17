# IPC-A-600 Bare-Board Defect Handling SOP

## 1. Open Circuit (Trace Break)
- **Defect Class**: `Open`
- **IPC Reference**: IPC-A-600 Section 2.2 (Conductor Width and Continuity)
- **Disposition Policy**: Mandatory `SCRAP` under both Class 2 and Class 3. Zero tolerance (`max_allowed_px = 0`).
- **Root Cause**: Photoresist flaking, dust contamination on negative film during UV exposure, or over-etching in cupric chloride bath.
- **Operator Action**: Quarantine board immediately. Do not attempt jumper-wire rework on bare-board inner/outer signal layers. If 3 or more `Open` defects occur in the same batch, halt the exposure/etching line and inspect artwork film cleanliness.

## 2. Short Circuit (Copper Bridge)
- **Defect Class**: `Short`
- **IPC Reference**: IPC-A-600 Section 2.3 (Minimum Electrical Clearance)
- **Disposition Policy**: Mandatory `SCRAP` under Automated Optical Inspection safety guardrails (`max_allowed_px = 0`).
- **Root Cause**: Incomplete photoresist development (scum in trace spacing), under-etching due to depleted etchant, or scratch on dark-field phototool.
- **Operator Action**: Reject board to scrap bin. When batch drift counter reaches 3 occurrences (`halt_production_line = True`), verify developer spray nozzle pressure (target 1.5–2.0 bar) and check etchant specific gravity.

## 3. Mousebite (Conductor Edge Nick)
- **Defect Class**: `Mousebite`
- **IPC Reference**: IPC-A-600 Section 2.2.1 (Edge Imperfections)
- **Disposition Policy**: `PASS` if localized nick area is ≤ 250 px² (Class 2) or ≤ 120 px² (Class 3) and does not reduce conductor width by more than 20%. Otherwise `REWORK`.
- **Root Cause**: Air bubbles trapped along resist sidewalls during developing or localized etchant turbulence.
- **Operator Action**: Measure remaining conductor width on AOI overlay. If over area threshold, route to micro-inspection bench for copper touch-up evaluation or downgrade disposition.

## 4. Spur (Copper Protrusion)
- **Defect Class**: `Spur`
- **IPC Reference**: IPC-A-600 Section 2.3.2 (Conductor Spacing Reduction)
- **Disposition Policy**: `PASS` if protrusion area is ≤ 200 px² (Class 2) or ≤ 100 px² (Class 3). Exceeding the area limit requires `REWORK` to prevent high-voltage breakdown.
- **Root Cause**: Pinholes in dry-film photoresist or resist edge lifting during acid etching.
- **Operator Action**: Route `REWORK` boards to precision scalpel/laser trim station to excise excess copper protrusion without damaging adjacent laminate.

## 5. Spurious Copper (Isolated Copper Speck)
- **Defect Class**: `Spurious_Copper`
- **IPC Reference**: IPC-A-600 Section 2.1.4 (Metallic Foil Residue on Base Laminate)
- **Disposition Policy**: `PASS` if isolated speck area is ≤ 180 px² (Class 2) or ≤ 80 px² (Class 3). Over-limit specks require `REWORK`.
- **Root Cause**: Undissolved dry-film residue shielding underlying copper from etchant, or redeposition of copper particulates.
- **Operator Action**: Remove isolated residual copper at mechanical deburring/rework station and re-run AOI verification.

## 6. Pin-hole (Void in Copper Area)
- **Defect Class**: `Pin-hole`
- **IPC Reference**: IPC-A-600 Section 2.2.2 (Pinholes and Pits in Conductors/Ground Planes)
- **Disposition Policy**: `PASS` if pinhole area is ≤ 160 px² (Class 2) or ≤ 75 px² (Class 3). Larger voids require `REWORK`.
- **Root Cause**: Particulate contamination on laminator rollers or micro-bubbles during dry-film lamination.
- **Operator Action**: Distinguish true铜皮针孔 (copper pinhole) from normal drill vias using the Golden Template layer. If over limit, send to solder-mask/conductor repair assessment.
