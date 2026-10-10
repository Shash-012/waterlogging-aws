# Susceptibility factors (A2)

`delhi_factors.csv` holds L (low-lying), C (catchment), H (history) and susceptibility for every hotspot. `low_lying.png` and `catchment.png` map the two DEM factors with the hotspots overlaid. `data/hotspots/hotspots_contract.json` is the full contract Hotspot list. It validates against `contract/schemas/hotspot_list.schema.json`, and the contract's formula checks pass.

To rebuild (the rasters are git-ignored under `data/dem/`):

    python scripts/dem/download_dem.py   # Copernicus GLO-30 tiles N28E076 + N28E077 → UTM 43N, 30 m
    python scripts/dem/factors.py

## Checks ("done when")

- **Catchment span:** 0.0018 to 15.0 km², 3.9 orders of magnitude. The requirement is at least 2.
- **Underpasses:** all 15 have L of 0.9 or more, by the contract rule.
- **Top third:** 7 well-known spots are in the top 23 of 69 for susceptibility:
  - Minto Bridge underpass #1 (0.878)
  - Pragati Maidan tunnel #2
  - Dhaula Kuan #4
  - Pul Prahladpur underpass #6
  - Moolchand underpass #12
  - Zakhira underpass #13
  - ITO crossing #15

## What to know about these numbers

- **GLO-30 is a surface model.** It includes buildings, flyovers and the metro viaduct. A pin under an elevated road reads that road's deck, not the street, which gives a strongly negative d:
  - Rohtak Road at Mundka: −8.0 m, under the Green Line viaduct
  - Munirka: −10.3 m
  - Shastri Park: −4.8 m

  These spots get L = 0. Their susceptibility is understated, and history is the only factor carrying them. This is why the contract forces L ≥ 0.9 for underpasses.
- **Catchment depends on the 60 m snap.** On a 30 m surface model, roads and buildings break up small drainage lines, so several spots that flood often have tiny upstream areas and C = 0:
  - Moolchand: 0.006 km²
  - Zakhira: 0.008 km²
  - ITO: 0.008 km²

  The spots with large C are those next to the Yamuna-side drains and the Barapullah nallah: Pragati Maidan (11 km²), Ring Road opposite WHO (15 km²) and Connaught Place (4.5 km²).
- **The bottom of the table is mostly mis-measured, not safe.** Karol Bagh market and Rohtak Road from Punjabi Bagh to Shadipur score 0. They have no 2019–2025 report (only 2026 ones), and both sit in dense built-up blocks where the surface model reads rooftops. Treat that end of the table as weak.

None of these was "fixed". The contract fixes the definitions, and the numbers are reported as they came out.
