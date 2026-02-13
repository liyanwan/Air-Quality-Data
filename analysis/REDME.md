# Analysis Folder

This folder contains the core data processing, modelling, and validation workflows supporting the Ontario air quality analysis (Q1 forecasting and Q2 temporal modelling).


## File Overview

### 00_smoke_test.py
Lightweight validation script used for CI.  
Ensures the environment, dependencies, and key pipelines execute successfully.  
Supports reproducibility via automated checks (uv + Quarto pipeline).


### AQProcess.ipynb
Air quality data preprocessing:
- Data cleaning and filtering  
- Missingness assessment  
- Feature engineering  
- Station-level consistency checks  

Forms the foundation for both Q1 and Q2 modelling.

### WX_TRProcess.ipynb
Weather and traffic preprocessing:
- Temporal alignment of meteorology and traffic volume  
- Lag feature construction (e.g., previous-day predictors)  
- Quality checks and imputation  

Outputs structured inputs for forecasting models.

### Merge.ipynb
Data integration workflow:
- Merges air quality, weather, and traffic datasets  
- Ensures time-index alignment  
- Produces modelling-ready datasets  

Acts as the bridge between preprocessing and modelling.


### Q1.ipynb
AQI data specific to research question 1 forecasting analysis:
- Time-based train/test split  
- Model training (OLS, ElasticNet, XGBoost, MLP)  
- Hyperparameter tuning with TimeSeries CV  
- Out-of-sample performance evaluation (RMSE, MAE)  

Supports model comparison and production candidate selection.

## Purpose

This folder contains the full analytical pipeline from raw data processing to model-ready datasets and forecasting evaluation. It is designed to be reproducible, modular, and CI-compatible to support production-grade analytics for public-sector decision-making.

