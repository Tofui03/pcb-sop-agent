# Line Halt & Process Drift Troubleshooting SOP

## 1. Batch Drift Line Halt Protocol
- **Trigger Condition**: 3 occurrences of the same defect class within a single `batch_id` (`BATCH_HALT_THRESHOLD = 3`, `halt_production_line = True`).
- **Immediate Action**: Stop conveyor feed into etching/stripping chambers. Lock batch status in operator station until Process Engineering signs off on root-cause remediation.

## 2. Etching Bath Chemical Drift Remediation
- **Applicable Defects**: Recurring `Short`, `Spur`, `Spurious_Copper` (Under-etching) or `Open`, `Mousebite`, `Pin-hole` (Over-etching).
- **Corrective Procedure**:
  1. Check Oxidation-Reduction Potential (ORP): maintain between 510 mV and 540 mV.
  2. Check Free HCl concentration and cupric ion specific gravity (1.26–1.30 g/cm³).
  3. Inspect upper and lower spray manifold nozzles for clogging; clean blocked nozzles to eliminate localized under-etching streaks.

## 3. Photolithography & Dry-Film Exposure Audit
- **Applicable Defects**: Recurring `Open`, `Short`, `Pin-hole` at identical `(x, y)` coordinates across multiple panels.
- **Corrective Procedure**:
  1. Compare defect coordinates across the 3x3 board grid. Identical coordinates indicate a contaminated or scratched phototool/glass master.
  2. Clean exposure frame glass with lint-free IPA wipes in Class 10,000 yellow room.
  3. Verify UV exposure energy using Stouffer 21-step sensitivity guide (target step 7–9).
