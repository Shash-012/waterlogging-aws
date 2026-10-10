# Delhi waterlogging hotspots (A1)

`delhi_hotspots.json` holds 69 spots: 29 road stretches, 15 underpasses, 15 colonies and 10 junctions. Rebuild it with:

    python scripts/hotspots/build_hotspots.py data/hotspots/research/spots_central_south_east.json data/hotspots/research/spots_north_west.json --report

- **Evidence** (`research/`): news reports of waterlogging from the 2019–2025 monsoons, plus the 2025 PWD prone-points list as covered by Tribune and PTI. Every URL was fetched, except two entries marked `verified_by: snippet`, which are Delhi Traffic Police posts we saw only in search results. Many big outlets (HT, TOI, Indian Express, NDTV, The Hindu) blocked automated fetching, so the evidence leans on Outlook, Tribune, India.com, The Week, National Herald and similar.
- **flood_seasons** = the number of distinct monsoon years from 2019 to 2025 with a documented report, plus one if the spot is on an official prone-points list (the contract's H definition). Reports from 2026 are kept as sources but don't count. We found no reports from 2019, so H is probably understated for long-standing spots.
- **Pins**: each spot is geocoded with OSM Nominatim (one request a second, identifying User-Agent, responses cached in `geocode_cache.json`) and then reverse-geocoded to check the road. When the first Nominatim hit was the wrong place or an area centroid, the pin was moved to the OSM feature for the named place (an underpass, flyover, bus stop or station on the right road). Those overrides are in `curation.json`.
- **Dropped**: 6 spots we couldn't place reliably (Ashok Vihar, Okhla Road 13, Libaspur, Rani Khera and Narela-Lampur underpasses, and the Dwarka NH-48 underpass).
- **Merged**: duplicates within 150 m, plus three same-site pairs: the two Moti Bagh entries, Laxmi Nagar with Vikas Marg, and Phirni Road with Najafgarh town.
- **Hindi**: names are hand-written. Road names in the avoid and diversion text are transliterated word by word from the glossary in `curation.json`.
- **Diversion roads** are the researchers' suggestions, either named in the articles or the obvious parallel arterial. They aren't traffic-police advice.
