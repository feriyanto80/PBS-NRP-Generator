# PBS Network Route Plan Generator

**Version v1.0.4 — KML + KMZ dual input release.**

Build a standalone Windows 64-bit application to generate a five-sheet A3 engineering PDF and layered DXF from Google Earth **.kml or .kmz**. The source retains OSM roads/buildings overlay acquisition, data caching and optional DWG conversion using the separately installed ODA converter.

### Repository layout
- \`PBS_NRP_Source_v1.0.3.tar.xz\`: cumulative desktop engine baseline.
- \`kml_support.py\`: namespace-tolerant KML/KMZ reader for points and lines.
- \`launcher.py\`: v1.0.4 desktop UI with KML/KMZ file selector.
- \`test_wrapper.py\`: dual-format regression tests.
- \`.github/workflows/windows-build.yml\`: automatic Windows PyInstaller build.

**GitHub Actions** → **PBS NRP Generator - Windows EXE** → latest successful workflow → download \`PBS_NRP_Generator_Windows_x64_v1.0.4_KML_KMZ\`.

**Limits:** Prototype; no Windows interactive UI smoke test, optimized professional sheet tiling or built-in native DWG writer. EXE file must be tested by the user on Windows 10/11.
