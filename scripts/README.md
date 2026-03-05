# Scripts

This folder contains standalone Python scripts for data acquisition and preprocessing.
Notebooks for modelling and analysis live under `analysis/` and `model/`.

---

## Case Study 2 – Wildfire Data Pipeline

The wildfire data is **not committed to GitHub** (files are 300–400 MB).
Run these three scripts in order to reproduce it locally:

```bash
python scripts/download_cwfis_hotspots.py
python scripts/clean_cwfis_hotspots.py
python scripts/build_wsei_features.py
```

### download_cwfis_hotspots.py

Downloads the Canadian Wildland Fire Information System (CWFIS) Fire M3 Daily
Hotspot archives for 2022, 2023, and 2024 from the public CWFIS Datamart:

```
https://cwfis.cfs.nrcan.gc.ca/downloads/hotspots/archive/
```

Each year is a ZIP file containing one CSV of satellite-detected fire hotspots
across North America. The script:

1. Downloads each ZIP (skips if already present)
2. Extracts it to `data/wildfire/raw/{year}_hotspots/`
3. Combines all three years into one DataFrame
4. Filters to **Canadian hotspots only** (`country == "C"`)
5. Saves `data/wildfire/hotspots_2022_2024_canada.csv.gz` (~320 MB)

**Output columns (36):** `rep_date`, `satellite`, `sensor`, `source`, `lat`, `lon`,
`frp`, `country`, `agency`, `ecozone`, `elev`, `slope`, `aspect`, `fuel`, `greenup`,
`pcuring`, `pconif`, `sfl`, `cfl`, `cbh`, `temp`, `rh`, `ws`, `wd`, `pcp`,
`ffmc`, `dmc`, `dc`, `bui`, `isi`, `fwi`, `sfc`, `tfc`, `ros`, `hfi`, `date`

**Row counts before cleaning:**

| Year | Canadian hotspots |
|------|-------------------|
| 2022 | 265,358           |
| 2023 | 3,200,152         |
| 2024 | 1,476,608         |

---

### clean_cwfis_hotspots.py

Cleans `hotspots_2022_2024_canada.csv.gz` and saves the analysis-ready file
`data/wildfire/hotspots_clean.csv.gz` (~313 MB).

Cleaning steps applied:

| Step | Action | Rows affected |
|------|--------|---------------|
| Null `hfi` | Dropped — no intensity information | 1,423 |
| `temp > 100°C` | Dropped — physically impossible, all were exactly 261.0°C (data error) | 211 |
| `cbh` column | Dropped — 74% null, not needed | — |
| `country` column | Dropped — redundant after Canada filter | — |
| `source_year` column | Dropped — derivable from `date` | — |
| `hfi == 0` rows | **Kept** — valid low-intensity observations (3.4% of data) | — |

**Output:** 4,940,484 rows × 34 columns

Key columns for downstream analysis:

| Column | Description |
|--------|-------------|
| `date` | Calendar day (UTC, no timezone) |
| `rep_date` | Exact detection timestamp (UTC) |
| `lat`, `lon` | Hotspot location (WGS84) |
| `agency` | Provincial fire agency (e.g. `ON`, `BC`, `AB`) |
| `hfi` | Head Fire Intensity — primary intensity proxy |
| `frp` | Fire Radiative Power — alternative intensity proxy |
| `tfc` | Total Fuel Consumption — alternative intensity proxy |
| `ws`, `wd` | Wind speed (km/h) and direction (degrees) at hotspot |
| `ffmc`–`fwi` | Canadian Forest Fire Weather Index system components |

---

### build_wsei_features.py

Builds the **Wildfire Smoke Exposure Index (WSEI)** features for Case Study 2 and
produces the final modeling dataset. Requires `hotspots_clean.csv.gz` (from
`clean_cwfis_hotspots.py`) and the original `merged_10km_daily_updated.csv`.

The script does three things in sequence:

**1. Wind direction join**

Extracts `Dir of Max Gust (10s deg)` from `weather_ON_2022_2024.csv` and matches
it to each AQI station using the same 10 km spatial radius used when building the
merged dataset. Wind direction is aggregated with a **circular mean** (sin/cos
averaging) to correctly handle the 0°/360° wraparound (e.g. 350° + 10° = 0°, not 180°).

ECCC encoding note: values are in tens of degrees (1 = 10°, 36 = 360° = North,
0 = calm/missing). Multiplied by 10 to produce standard degrees.

**2. WSEI computation**

For every (AQI station, date) pair at lags k = 0, 1, 2, 3 days:

```
WSEI(s, t, k) = Σ_f  log(1+I_f) × K(d(s,f)) × W(Δθ_{s,f}, v_{s,t-k})
```

- **Intensity proxy** `I`: primary = `hfi`; alternatives = `frp`, `tfc` (sensitivity checks)
- **Distance kernel** `K(d) = 1 / (1 + (d / 500 km)²)` — Cauchy/inverse-square; half-weight at 500 km; hard cutoff at 2,000 km
- **Wind alignment** `W = v × max(0, cos(Δθ))` — upweights hotspots that are upwind of the station, scaled by wind speed

Hotspots are pre-filtered to a bounding box (lat 35–62, lon −107 to −62) covering
Ontario plus a ~1,000–1,500 km buffer in all directions.

**Output columns (per station × date):**

| Column | Description |
|--------|-------------|
| `wind_dir_deg` | Circular-mean wind direction (°, met. FROM convention) |
| `wind_spd_kmh` | Mean wind gust speed (km/h) |
| `wsei_hfi_k0` – `k3` | WSEI (hfi) at lag 0–3 days |
| `wsei_frp_k0` – `k3` | WSEI (frp) at lag 0–3 days — sensitivity check |
| `wsei_tfc_k0` – `k3` | WSEI (tfc) at lag 0–3 days — sensitivity check |
| `wsei_hfi_max3d` | max(k0..k3) — peak exposure in 3-day window |
| `wsei_hfi_sum3d` | sum(k0..k3) — cumulative 3-day exposure |

**3. Outputs**

| File | Description |
|------|-------------|
| `data/wildfire/wsei_features.csv` | Intermediate WSEI-only cache (fast reload) |
| `data/wildfire/merged_with_wsei.csv` | Full modeling dataset: merged + wind + WSEI |

Runtime: ~5–15 minutes (dominated by 2023 hotspot density, ~8,700 hotspots/day).

See `data/data_dictionary.md` for the full data dictionary and design-decision rationale
(kernel choice, wind alignment, distance cutoff).

---

## Case Study 1 Scripts

### Q1_script.py

Standalone version of the Q1 modelling notebook, used by the CI pipeline.
Trains and evaluates OLS, ElasticNet, and XGBoost models for next-day AQI forecasting.

### run.sh

Entry point for the CI pipeline. Executes the Q2 notebook and renders the Quarto report.
