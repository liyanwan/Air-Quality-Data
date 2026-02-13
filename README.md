# Air-Quality-Data

This repository contains the full analytical pipeline, modeling framework, and reporting outputs for our Ontario air quality study. The project addresses two primary research questions:

- **Q1** – How daily pollutant levels (focus: NO / AQI) are associated with traffic volume after controlling for meteorology, and whether the relationship varies by season.
- **Q2** – How pollutant concentrations vary by hour of day and weekday vs weekend, and whether these temporal patterns differ by season or station.

The repository is structured to support **reproducibility, modular development, and automated reporting** via GitHub Actions (uv + Quarto).

## Repository Structure

```text
Air-Quality-Data/
│
├── .github/workflows/
│   ├── README.md
│   └── pipeline.yml
│
├── analysis/
│   ├── 00_smoke_test.py
│   ├── AQProcess.ipynb
│   ├── Merge.ipynb
│   ├── Q1.ipynb
│   ├── WX_TRProcess.ipynb
│   └── README.md
│
├── data/
│   ├── Q1_data/
│   │   ├── cutoff.csv
│   │   ├── feature_cols.json
│   │   ├── station12008_test_daily.csv
│   │   └── test_all.csv
│   │
│   ├── AirQuality_ON_2022_2024.csv
│   ├── Hourly_AQI_EPA.xlsb
│   ├── merged_10km_daily_updated.csv
│   ├── traffic_ON_2022_2024.csv
│   └── weather_ON_2022_2024.csv
│
├── model/
│   ├── Q1_models/
│   │   ├── elasticnet_best.joblib
│   │   ├── mlp_best.joblib
│   │   ├── ols_pipe.joblib
│   │   └── xgb_best.joblib
│   │
│   ├── Model Fitting to question 2.ipynb
│   ├── Q1.ipynb
│   └── README.md
│
├── outputs/
│   └── figures/
│       └── .gitkeep
│
└── report/
    ├── Q1_report.qmd
    ├── Research Question 2 Report.qmd
    ├── Synthesized Report.qmd
    ├── final_report_with_code_included.pdf
    ├── final_report_with_code_included.qmd
    ├── final_report_without_code.pdf
    ├── final_report_without_code.qmd
    └── test_report.qmd
```

# Data Sources

The analysis integrates the following datasets:

### 1. Ontario Air Quality Data (2022–2024)
- Source: Ontario Ministry of the Environment
- File: `AirQuality_ON_2022_2024.csv`
- Hourly station-level pollutant measurements

### 2. EPA AQI Reference
- File: `Hourly_AQI_EPA.xlsb`
- Used for AQI standardization and validation

### 3. Traffic Data (Ontario, 2022–2024)
- File: `traffic_ON_2022_2024.csv`
- Aggregated traffic camera volume data

### 4. Weather Data (Ontario, 2022–2024)
- File: `weather_ON_2022_2024.csv`
- Includes temperature, wind speed, humidity

### 5. Spatially Merged Dataset
- File: `merged_10km_daily_updated.csv`
- Left-joined dataset linking AQI stations to traffic and weather within a 10 km radius

### Q1 Modeling Subset
Located in `data/Q1_data/`:
- Pre-split train/test data
- Feature definitions (`feature_cols.json`)
- Station-level evaluation data

# Processing Pipeline

All major processing steps are modularized under `analysis/`.

### Step 1 – AQI Processing
**AQProcess.ipynb**
- Cleans and standardizes AQI
- Handles missing values
- Produces structured station-level dataset

### Step 2 – Weather & Traffic Processing
**WX_TRProcess.ipynb**
- Aggregates weather + traffic
- Constructs lag features
- Groups by station within 10 km radius

### Step 3 – Data Merge
**Merge.ipynb**
- Left joins AQI with weather and traffic
- Ensures temporal alignment
- Produces modeling-ready dataset

### Step 4 – Q1 Modeling
**analysis/Q1.ipynb**
- Time-based split
- Model training (OLS, ElasticNet, RF, XGBoost, MLP)
- Out-of-sample evaluation

### Step 5 – Q2 Modeling
**model/Model Fitting to question 2.ipynb**
- Mixed-effects modeling
- GAM for nonlinear time effects
- XGBoost forecasting benchmark


# Pretrained Models

Located under: `model/Q1_models/`

These include:
- `ols_pipe.joblib`
- `elasticnet_best.joblib`
- `xgb_best.joblib`
- `mlp_best.joblib`

These models are stored to avoid recomputing resource-intensive training during CI runs.

Heavy computations such as:
- Hyperparameter tuning
- Cross-validation
- Out-of-sample model selection  

are not rerun in CI. Instead, pretrained artifacts are loaded for evaluation and reporting.


# Reports

All Quarto reports are under:`report`

These include:
- `ols_pipe.joblib`
- `elasticnet_best.joblib`
- `xgb_best.joblib`
- `mlp_best.joblib`

These models are stored to avoid recomputing resource-intensive training during CI runs.

Heavy computations such as:
- Hyperparameter tuning
- Cross-validation
- Out-of-sample model selection  

are not rerun in CI. Instead, pretrained artifacts are loaded for evaluation and reporting.


# Reports

All Quarto reports are under: `.github/workflows/pipeline.yml`

This pipeline:
- Installs dependencies via uv
- Runs smoke tests
- Executes Quarto rendering
- Regenerates reports

Estimated runtime: **~3 minutes**


# How to Run the Repository (Professor Instructions)

1. Go to the **Actions** tab at the top of the repository.
2. In the left-hand sidebar, click **“Analysis Pipeline (uv + Quarto)”**.
3. Click **“Run workflow”**.
4. Click the green **“Run workflow”** button again.
5. The full pipeline will execute (~3 minutes).

All reports will be regenerated automatically and downloaded as a.zip file to your local drive.

# Notes on Reproducibility

- Resource-intensive model calibration is not re-executed during CI.
- Pretrained model artifacts are stored in `model/Q1_models/`.
- Data processing notebooks are modular and clearly separated.
- Outputs and figures are stored under `outputs/`.

The repository is structured so that:
- Data lives in `/data`
- Processing logic lives in `/analysis`
- Modelling artifacts live in `/model`
- Final communication lives in `/report`

This ensures logical grouping of related information and ease of navigation.


# Intended Audience

This repository is designed for:
- Academic evaluation
- Reproducible analytics demonstration
- Public-sector analytics stakeholders
- Environmental policy modelling teams

It supports decision-ready insights for Ontario municipal environmental offices and the Ministry of the Environment.
