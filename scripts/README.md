# Scripts

This folder contains standalone Python scripts for data acquisition and preprocessing.
Notebooks for modelling and analysis live under `analysis/` and `model/`.

---

## Case Study 2 – Wildfire Data Pipeline

The wildfire data is **not committed to GitHub** (files are 300–400 MB).
Run these two scripts in order to reproduce it locally:

```bash
python scripts/download_cwfis_hotspots.py
python scripts/clean_cwfis_hotspots.py
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

## Case Study 1 Scripts

### Q1_script.py

Standalone version of the Q1 modelling notebook, used by the CI pipeline.
Trains and evaluates OLS, ElasticNet, and XGBoost models for next-day AQI forecasting.

### run.sh

Entry point for the CI pipeline. Executes the Q2 notebook and renders the Quarto report.
