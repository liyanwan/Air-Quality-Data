# Ontario Air Quality Analytics

This repository contains modelling and analytical work addressing two core research questions on air pollution dynamics across Ontario monitoring stations. The objective is to generate decision-ready insights for public-sector stakeholders using statistical and machine learning approaches.

### Folder Details

**CS2RQ2_models/**
Contains pretrained and tuned forecasting models:
- 'lstm_baseline.pt' – LSTM baseline model without wildfire features
- 'lstm_wildfire.pt' – LSTM model with wildfire features
- 'lstm_metadata.json' – Metadata on LSTM model architectures and training details
- 'model_registry.json' - Registry of all models with performance metrics and hyperparameters
- "nn_baseline.joblib" - Neural network baseline model without wildfire features
- "nn_wildfire.joblib" - Neural network model with wildfire features
- "ols_baseline.joblib" - OLS baseline model without wildfire features
- "ols_wildfire.joblib" - OLS model with wildfire features

**Q1 Models/**  
Contains pretrained and tuned forecasting models:
- `ols_pipe.joblib` – Linear baseline model (production candidate)
- `elasticnet_best.joblib` – Regularized linear model
- `xgb_best.joblib` – Gradient boosting model
- `mlp_best.joblib` – Neural network model

**Q1.ipynb**  
Model training, evaluation, and comparison for one-step AQI forecasting.

**Model Fitting to question 2.ipynb**  
Statistical modelling and visualization of hourly, weekday/weekend, and seasonal effects.


## Methods Overview

- Time-based train/test split to prevent leakage  
- TimeSeries cross-validation for hyperparameter tuning  
- Mixed-effects modelling for station-level heterogeneity  
- Nonlinear modelling for seasonal hourly patterns  
- Out-of-sample RMSE/MAE evaluation  


## Purpose

This repository provides reproducible modelling workflows and pretrained models designed to support evidence-based environmental policy, advisory issuance, and traffic/emission intervention assessment.



