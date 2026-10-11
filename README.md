# PBS Network Route Plan Generator — v1.0.11

Portable Windows x64 engineering drawing generator for KML/KMZ FTTH networks.

## Adaptive NRP Sheet Planning & Detailed Worker Progress

- Dynamic number of pages: one overview plus density-dependent details (up to 24). Detail extents overlap for continuity. No fixed four quadrants.
- Preview Sheet dropdown reflects every planned detail sheet.
- OSM+Google pipeline progress: OSM per-tile checks, Google catalog/size validation, merge/deduplication and auto-pagination.
- Generate PDF/DXF/DWG disabled throughout acquisition and sheet planning, then restored at 100% workflow completion, including partial/unavailable Google results.
- Large Google tiles: official tiles may exceed 5 GB. Desktop download safety cap is 80 MB. Skipped-large remains an explicit status with zero Google polygons; 100% workflow progress does NOT assert 100% geographic coverage.
- Cumulative features retained: responsive GUI, KML/KMZ import, intersection-aware road offset, audited building classification, PDF/DXF, optional ODA DWG.

## Testing
Download latest successful GitHub Actions artifact. Extract the Windows 64-bit PBS_NRP_Generator.exe. No Python or AutoCAD needed for PDF/DXF.

1. Import KML or KMZ.
2. Review dynamic sheet count under Layout & Sheet and select any sheet in preview.
3. Press Ambil / gunakan cache OSM + Google. Watch the progressbar, detailed event ledger and tile-size decision.
4. PDF/DXF export is unlocked after the acquisition + geometry-fusion + sheet-planning pipeline finishes. An unavailable Google dataset is never counted as successful download.
5. Generate PDF/DXF: number of pages equals 1 overview plus detail sheet count.

## Limitations
- Road widths are schematic if not surveyed.
- The desktop cannot automatically materialize official multi-GB Google tile data with a small network budget. Authorized Earth Engine regional export is needed for those cases.
- Professional annotation/approval still requires drafter QA.
- Native DWG requires ODA File Converter installed separately.
- Windows CI validates regression tests and UI widgets; a live regional Google download has not been verified.
