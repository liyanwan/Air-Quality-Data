# scripts/q1_make_report_artifacts.py
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from sklearn.metrics import mean_absolute_error, root_mean_squared_error


def main() -> None:
    # ----------------------------
    # Resolve repo paths
    # scripts/ is under repo root
    # ----------------------------
    SCRIPT_DIR = Path(__file__).resolve().parent
    ROOT_DIR = SCRIPT_DIR.parent

    # Inputs (repo-relative)
    FEATURE_COLS_PATH = ROOT_DIR / "data" / "Q1_data" / "feature_cols.json"
    TEST_ALL_PATH = ROOT_DIR / "data" / "Q1_data" / "test_all.csv"
    ST12008_DAILY_PATH = ROOT_DIR / "data" / "Q1_data" / "station12008_test_daily.csv"

    MODEL_PATHS = {
        "OLS": ROOT_DIR / "model" / "Q1_models" / "ols_pipe.joblib",
        "ElasticNet": ROOT_DIR / "model" / "Q1_models" / "elasticnet_best.joblib",
        "XGBoost": ROOT_DIR / "model" / "Q1_models" / "xgb_best.joblib",
        "MLP": ROOT_DIR / "model" / "Q1_models" / "mlp_best.joblib",
    }

    # Outputs (scripts/output/)
    OUT_DIR = SCRIPT_DIR / "output"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_METRICS_CSV = OUT_DIR / "q1_table1_test_metrics.csv"
    OUT_FIG_PNG = OUT_DIR / "q1_fig1_station12008_small_multiples_error.png"

    # ----------------------------
    # Load feature list + data
    # ----------------------------
    feature_cols = json.load(open(FEATURE_COLS_PATH, "r", encoding="utf-8"))

    test_all = pd.read_csv(TEST_ALL_PATH, parse_dates=["Date"])
    test_all["Station ID"] = test_all["Station ID"].astype(str)

    st = pd.read_csv(ST12008_DAILY_PATH, parse_dates=["Date"])
    st = st.sort_values("Date")

    # ----------------------------
    # Load pretrained models
    # ----------------------------
    models = {name: joblib.load(path) for name, path in MODEL_PATHS.items()}

    # ----------------------------
    # (1) Test-set metrics (ALL stations) + Naive baseline
    # ----------------------------
    X_test = test_all[feature_cols + ["Station ID"]].copy()
    y_test = test_all["AQI"].to_numpy()

    rows: list[dict] = []

    # Naive: y_hat(t) = y(t-1) within each Station ID
    if "AQI_lag1" in test_all.columns:
        y_naive = test_all["AQI_lag1"]
    else:
        y_naive = (
            test_all.sort_values(["Station ID", "Date"])
            .groupby("Station ID")["AQI"]
            .shift(1)
        )

    mask = y_naive.notna()
    rows.append(
        {
            "model": "Naive (y_hat = y_lag1)",
            "RMSE_test": float(
                root_mean_squared_error(test_all.loc[mask, "AQI"], y_naive.loc[mask])
            ),
            "MAE_test": float(
                mean_absolute_error(test_all.loc[mask, "AQI"], y_naive.loc[mask])
            ),
            "n_eval": int(mask.sum()),
        }
    )

    for name, m in models.items():
        y_pred = m.predict(X_test)
        rows.append(
            {
                "model": name,
                "RMSE_test": float(root_mean_squared_error(y_test, y_pred)),
                "MAE_test": float(mean_absolute_error(y_test, y_pred)),
                "n_eval": int(len(y_test)),
            }
        )

    metrics_df = (
        pd.DataFrame(rows)
        .sort_values("RMSE_test")
        .reset_index(drop=True)
    )

    metrics_df.to_csv(OUT_METRICS_CSV, index=False)
    print(f"[OK] Saved metrics: {OUT_METRICS_CSV}")

    # ----------------------------
    # (2) Figure: Station 12008 small multiples + error
    # ----------------------------
    station_id = "12008"

    X_station = st[feature_cols].copy()
    X_station["Station ID"] = station_id

    dates = st["Date"].to_numpy()
    y_true = st["AQI"].to_numpy()

    preds = {name: m.predict(X_station) for name, m in models.items()}

    model_names = list(preds.keys())
    n = len(model_names)
    ncols = 2
    nrows_top = int(np.ceil(n / ncols))

    fig = plt.figure(figsize=(16, 4 * nrows_top + 4))
    gs = fig.add_gridspec(
        nrows=nrows_top + 1,
        ncols=ncols,
        height_ratios=[1] * nrows_top + [1.2],
    )

    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    formatter = mdates.ConciseDateFormatter(locator)

    # Make prediction more prominent than actual
    actual_kwargs = dict(label="Actual", linewidth=1.6, alpha=0.35, zorder=2)
    pred_kwargs = dict(linewidth=3.0, alpha=0.95, zorder=3)

    # Top: small multiples
    for i, name in enumerate(model_names):
        r, c = divmod(i, ncols)
        ax = fig.add_subplot(gs[r, c])

        ax.plot(dates, y_true, **actual_kwargs)
        ax.plot(dates, preds[name], label="Predicted", **pred_kwargs)

        ax.set_title(name)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        ax.tick_params(axis="x", rotation=30)
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper right")

    # Hide unused cells
    for j in range(n, nrows_top * ncols):
        r, c = divmod(j, ncols)
        ax = fig.add_subplot(gs[r, c])
        ax.axis("off")

    # Bottom: error plot
    ax_err = fig.add_subplot(gs[nrows_top, :])
    for name in model_names:
        err = np.asarray(preds[name]) - y_true
        ax_err.plot(dates, err, label=name, alpha=0.9)

    ax_err.axhline(0, linewidth=1)
    ax_err.set_title("Prediction Error (Pred - Actual)")
    ax_err.set_ylabel("Error")
    ax_err.xaxis.set_major_locator(locator)
    ax_err.xaxis.set_major_formatter(formatter)
    ax_err.tick_params(axis="x", rotation=30)
    ax_err.grid(True, alpha=0.25)
    ax_err.legend(ncol=3, loc="upper right")

    fig.suptitle(
        f"Station {station_id} (Test Period): Small Multiples + Error",
        y=1.02,
        fontsize=14,
    )
    fig.tight_layout()

    fig.savefig(OUT_FIG_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Saved figure: {OUT_FIG_PNG}")

    print("[DONE] Artifacts generated successfully.")


if __name__ == "__main__":
    main()
