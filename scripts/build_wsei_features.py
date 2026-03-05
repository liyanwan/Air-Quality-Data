"""
Build Wildfire Smoke Exposure Index (WSEI) features for Case Study 2.

This script does three things in sequence:

  1. Wind direction join
     Extract "Dir of Max Gust" from weather_ON_2022_2024.csv and match it to
     each AQI station using the same 10 km radius used when building
     merged_10km_daily_updated.csv.  Wind direction is aggregated with a
     circular mean (sin/cos averaging) to avoid the 350°+10° = 180° error.

  2. WSEI computation
     For every (station, date) pair, aggregate nearby wildfire hotspots from
     hotspots_clean.csv.gz using:
         WSEI(s,t,k) = Σ_f  log(1+I_f) × K(d(s,f)) × W(Δθ_{s,f}, v_{s,t-k})
     at lags k = 0, 1, 2, 3 days.
     Three intensity proxies are computed (hfi, frp, tfc) for sensitivity checks.

  3. Merge and save
     Merge wind direction + WSEI into merged_10km_daily_updated.csv and save
     two output files:
         data/wildfire/wsei_features.csv.gz        — intermediate WSEI-only cache
         data/wildfire/merged_with_wsei.csv.gz     — full modeling-ready dataset

Design decisions and their trade-offs are documented in data/README.md.

Usage:
    python scripts/build_wsei_features.py

Runtime: ~5–15 minutes depending on CPU (dominated by 2023 hotspot density).
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).resolve().parent.parent
MERGED_PATH  = REPO_ROOT / "data" / "merged_10km_daily_updated.csv"
WEATHER_PATH = REPO_ROOT / "data" / "weather_ON_2022_2024.csv"
HOTSPOT_PATH = REPO_ROOT / "data" / "wildfire" / "hotspots_clean.csv.gz"
OUT_WSEI     = REPO_ROOT / "data" / "wildfire" / "wsei_features.csv"
OUT_MERGED   = REPO_ROOT / "data" / "wildfire" / "merged_with_wsei.csv"

# ── Tunable parameters ─────────────────────────────────────────────────────────
MATCH_RADIUS_KM  = 10      # weather station match radius (same as merged dataset)
D0_KM            = 500     # distance kernel scale: half-weight at 500 km
MAX_DIST_KM      = 2000    # hard cutoff: K < 0.05 beyond this, negligible
LAGS             = [0, 1, 2, 3]

# Bounding box for hotspot pre-filter (Ontario + ~1000–1500 km buffer)
BBOX_LAT = (35.0, 62.0)
BBOX_LON = (-107.0, -62.0)


# ── Geometry helpers ───────────────────────────────────────────────────────────

def haversine_km(lat1: np.ndarray, lon1: np.ndarray,
                 lat2: float, lon2: float) -> np.ndarray:
    """Vectorised haversine distance from arrays of (lat1, lon1) to scalar (lat2, lon2)."""
    R = 6371.0
    phi1 = np.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * math.cos(phi2) * np.sin(dlam / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def bearing_from_to(lat1: np.ndarray, lon1: np.ndarray,
                    lat2: float, lon2: float) -> np.ndarray:
    """
    Forward bearing (degrees, 0–360) from each (lat1, lon1) point to (lat2, lon2).
    This is the direction you would travel FROM the hotspot TO the station.
    """
    phi1 = np.radians(lat1)
    phi2 = math.radians(lat2)
    dlam = np.radians(lon2 - lon1)
    x = np.sin(dlam) * math.cos(phi2)
    y = math.cos(phi2) * np.sin(phi1) - np.sin(phi2) * np.cos(phi1) * np.cos(dlam)
    # Note: standard bearing formula uses cos(phi1) for y — corrected below
    y = np.cos(phi1) * math.sin(phi2) - np.sin(phi1) * math.cos(phi2) * np.cos(dlam)
    bearing = np.degrees(np.arctan2(x, y)) % 360
    return bearing


def distance_kernel(d_km: np.ndarray) -> np.ndarray:
    """
    Cauchy/inverse-square distance decay kernel.
    K(d) = 1 / (1 + (d / D0_KM)^2)
    Half-weight at d = D0_KM (500 km by default).
    """
    return 1.0 / (1.0 + (d_km / D0_KM) ** 2)


def wind_alignment_weight(bearing_hotspot_to_station: np.ndarray,
                          wind_dir_deg: float,
                          wind_spd_kmh: float) -> np.ndarray:
    """
    Wind alignment weight W(Δθ, v) = v × max(0, −cos(Δθ)).

    Δθ = bearing_hotspot_to_station − wind_dir_deg

    Rationale:
      - wind_dir_deg is the meteorological direction the wind blows FROM.
      - bearing_hotspot_to_station is the direction FROM hotspot → TO station.
      - The bearing FROM station → TO hotspot = bearing_hotspot_to_station + 180°.
      - For a hotspot to be upwind, (bearing_hotspot_to_station + 180°) ≈ wind_dir_deg,
        i.e., Δθ ≈ −180°, so cos(Δθ) ≈ −1 → we negate to get +1 (full weight).
      - −cos(Δθ) is 1 when perfectly aligned (upwind), 0 at ±90°, negative beyond
        (clamped to 0 so downwind/crosswind hotspots contribute zero).
      - Scales linearly with wind speed: stronger wind → more transport potential.

    Special cases:
      - wind_dir_deg is NaN or 0 (calm): directional correction is neutralised;
        alignment is set to 0.5 (half-weight, representing alignment uncertainty).
      - wind_spd_kmh is NaN: use 1.0 as a neutral speed weight.
    """
    if np.isnan(wind_dir_deg) or wind_dir_deg == 0.0:
        cos_align = np.full(len(bearing_hotspot_to_station), 0.5)
    else:
        delta_theta = np.radians(bearing_hotspot_to_station - wind_dir_deg)
        cos_align = np.maximum(0.0, -np.cos(delta_theta))

    v = wind_spd_kmh if not np.isnan(wind_spd_kmh) else 1.0
    return v * cos_align


# ── Step 1: Wind direction join ────────────────────────────────────────────────

def load_station_locations(merged: pd.DataFrame) -> pd.DataFrame:
    """Return unique (Station ID, Latitude, Longitude) from merged dataset."""
    return (merged[["Station ID", "Latitude", "Longitude"]]
            .drop_duplicates("Station ID")
            .reset_index(drop=True))


def circular_mean_deg(angles_deg: pd.Series) -> float:
    """Circular mean of angles in degrees (handles 350°+10° = 0° correctly)."""
    rad = np.radians(angles_deg.dropna())
    if len(rad) == 0:
        return np.nan
    return float(np.degrees(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360)


def build_wind_features(merged: pd.DataFrame) -> pd.DataFrame:
    """
    For each (AQI station, date) pair, find matching ECCC weather stations
    within MATCH_RADIUS_KM and compute:
        wind_dir_deg  — circular mean of Dir of Max Gust (converted from 10s-deg)
        wind_spd_kmh  — mean Spd of Max Gust (km/h)

    Returns a DataFrame indexed by (Station ID, Date) with those two columns.
    """
    print("\n── Step 1: Wind direction join ──────────────────────────────────────")
    print(f"  Loading {WEATHER_PATH} ...")
    wx = pd.read_csv(
        WEATHER_PATH,
        usecols=["Station ID", "Latitude (y)", '"Longitude (x)"', "Date/Time",
                 "Dir of Max Gust (10s deg)", "Spd of Max Gust (km/h)"],
        low_memory=False,
    )
    wx = wx.rename(columns={
        "Latitude (y)":              "wx_lat",
        '"Longitude (x)"':           "wx_lon",
        "Date/Time":                 "Date",
        "Dir of Max Gust (10s deg)": "gust_dir_10s",
        "Spd of Max Gust (km/h)":   "gust_spd",
        "Station ID":                "wx_station_id",
    })
    wx["Date"] = pd.to_datetime(wx["Date"]).dt.normalize()

    # Convert ECCC 10s-degree encoding to degrees (0 = calm/missing → NaN)
    wx["gust_dir_10s"] = pd.to_numeric(wx["gust_dir_10s"], errors="coerce")
    wx["gust_dir_deg"] = wx["gust_dir_10s"].where(wx["gust_dir_10s"] > 0) * 10
    wx["gust_spd"]     = pd.to_numeric(wx["gust_spd"], errors="coerce")

    stations = load_station_locations(merged)
    print(f"  Matching {len(stations)} AQI stations to weather stations within {MATCH_RADIUS_KM} km ...")

    wx_lat = wx["wx_lat"].values
    wx_lon = wx["wx_lon"].values

    # For each AQI station, collect the IDs of all ECCC stations within radius
    station_to_wx_ids: dict[int, list] = {}
    unique_wx = wx[["wx_station_id", "wx_lat", "wx_lon"]].drop_duplicates("wx_station_id")
    for _, row in stations.iterrows():
        d = haversine_km(unique_wx["wx_lat"].values, unique_wx["wx_lon"].values,
                         row["Latitude"], row["Longitude"])
        nearby = unique_wx.loc[d <= MATCH_RADIUS_KM, "wx_station_id"].tolist()
        station_to_wx_ids[int(row["Station ID"])] = nearby

    n_matched = sum(1 for v in station_to_wx_ids.values() if v)
    print(f"  Matched {n_matched}/{len(stations)} AQI stations to at least one weather station")

    # Build a reverse mapping: wx_station_id → list of AQI station IDs
    wx_to_aqi: dict[int | str, list[int]] = {}
    for aqi_id, wx_ids in station_to_wx_ids.items():
        for wx_id in wx_ids:
            wx_to_aqi.setdefault(wx_id, []).append(aqi_id)

    # Filter weather data to only the matched ECCC stations
    all_wx_ids = {wx_id for ids in station_to_wx_ids.values() for wx_id in ids}
    wx_sub = wx[wx["wx_station_id"].isin(all_wx_ids)].copy()

    # Explode: one row per (aqi_station_id, date, wx_obs)
    wx_sub = wx_sub.copy()
    wx_sub["aqi_station_ids"] = wx_sub["wx_station_id"].map(wx_to_aqi)
    wx_sub = wx_sub.dropna(subset=["aqi_station_ids"])
    wx_sub = wx_sub.explode("aqi_station_ids").rename(columns={"aqi_station_ids": "Station ID"})
    wx_sub["Station ID"] = wx_sub["Station ID"].astype(int)

    # Aggregate per (AQI station, date)
    print("  Aggregating wind direction and speed per (station, date) ...")
    agg_dir = (wx_sub.groupby(["Station ID", "Date"])["gust_dir_deg"]
               .apply(circular_mean_deg)
               .rename("wind_dir_deg"))
    agg_spd = (wx_sub.groupby(["Station ID", "Date"])["gust_spd"]
               .mean()
               .rename("wind_spd_kmh"))

    wind_df = pd.concat([agg_dir, agg_spd], axis=1).reset_index()
    wind_df["Date"] = pd.to_datetime(wind_df["Date"])
    print(f"  Wind features: {len(wind_df):,} (station, date) pairs")
    nan_dir = wind_df["wind_dir_deg"].isna().mean()
    print(f"  NaN wind_dir_deg: {nan_dir:.1%}")
    return wind_df


# ── Step 2: Hotspot pre-filtering ─────────────────────────────────────────────

def load_hotspots() -> dict[pd.Timestamp, pd.DataFrame]:
    """
    Load clean hotspots, apply bounding-box pre-filter, and group by date.
    Returns a dict mapping date → DataFrame (with lat, lon, hfi, frp, tfc).
    """
    print("\n── Step 2: Loading and filtering hotspots ───────────────────────────")
    print(f"  Loading {HOTSPOT_PATH} ...")
    hp = pd.read_csv(
        HOTSPOT_PATH,
        usecols=["date", "lat", "lon", "hfi", "frp", "tfc"],
        low_memory=False,
    )
    hp["date"] = pd.to_datetime(hp["date"])
    n_raw = len(hp)

    hp = hp[
        hp["lat"].between(*BBOX_LAT) &
        hp["lon"].between(*BBOX_LON)
    ].copy()
    print(f"  Bounding-box filter: {n_raw:,} → {len(hp):,} hotspots "
          f"(lat {BBOX_LAT}, lon {BBOX_LON})")

    # Drop rows where all intensity cols are NaN (can't contribute to WSEI)
    hp = hp.dropna(subset=["hfi", "frp", "tfc"], how="all")

    # Fill individual NaNs with 0 (no contribution from that proxy)
    hp["hfi"] = hp["hfi"].fillna(0.0)
    hp["frp"] = hp["frp"].fillna(0.0)
    hp["tfc"] = hp["tfc"].fillna(0.0)

    print(f"  Final hotspot pool: {len(hp):,} rows")
    print(f"  Date range: {hp['date'].min().date()} to {hp['date'].max().date()}")

    # Group by date for fast O(1) lookup
    groups: dict[pd.Timestamp, pd.DataFrame] = {}
    for date, grp in hp.groupby("date"):
        groups[date] = grp[["lat", "lon", "hfi", "frp", "tfc"]].reset_index(drop=True)

    print(f"  Unique dates in hotspot pool: {len(groups):,}")
    return groups


# ── Step 3: WSEI computation ──────────────────────────────────────────────────

def compute_wsei_for_station_date(
    s_lat: float,
    s_lon: float,
    wind_dir: float,
    wind_spd: float,
    hotspot_groups: dict[pd.Timestamp, pd.DataFrame],
    target_date: pd.Timestamp,
) -> dict[str, float]:
    """
    Compute all WSEI variants for one (station, target_date) pair.
    Returns a dict of column_name → value.
    """
    result: dict[str, float] = {}

    for k in LAGS:
        lag_date = target_date - pd.Timedelta(days=k)
        hp = hotspot_groups.get(lag_date)

        if hp is None or len(hp) == 0:
            for proxy in ("hfi", "frp", "tfc"):
                result[f"wsei_{proxy}_k{k}"] = 0.0
            continue

        hp_lat = hp["lat"].values.astype(float)
        hp_lon = hp["lon"].values.astype(float)

        # Distance and kernel
        d_km = haversine_km(hp_lat, hp_lon, s_lat, s_lon)
        mask = d_km <= MAX_DIST_KM
        if not mask.any():
            for proxy in ("hfi", "frp", "tfc"):
                result[f"wsei_{proxy}_k{k}"] = 0.0
            continue

        d_sub   = d_km[mask]
        K       = distance_kernel(d_sub)

        # Wind alignment (uses station wind at lag date, same date as hotspots)
        bearing = bearing_from_to(hp_lat[mask], hp_lon[mask], s_lat, s_lon)
        W       = wind_alignment_weight(bearing, wind_dir, wind_spd)

        KW = K * W  # shape: (n_hotspots_in_range,)

        for proxy in ("hfi", "frp", "tfc"):
            I = np.log1p(hp[proxy].values[mask].astype(float))
            result[f"wsei_{proxy}_k{k}"] = float((I * KW).sum())

    # Derived aggregates (hfi only, as primary proxy)
    hfi_lags = [result[f"wsei_hfi_k{k}"] for k in LAGS]
    result["wsei_hfi_max3d"] = float(max(hfi_lags))
    result["wsei_hfi_sum3d"] = float(sum(hfi_lags))

    return result


def compute_all_wsei(
    merged: pd.DataFrame,
    wind_df: pd.DataFrame,
    hotspot_groups: dict[pd.Timestamp, pd.DataFrame],
) -> pd.DataFrame:
    """
    Iterate over all (station, date) pairs and compute WSEI features.
    Returns a DataFrame with Station ID, Date, wind cols, and all WSEI cols.
    """
    print("\n── Step 3: Computing WSEI features ──────────────────────────────────")

    # Merge wind into merged dataset for easy lookup
    merged_dated = merged[["Station ID", "Date", "Latitude", "Longitude"]].copy()
    merged_dated["Date"] = pd.to_datetime(merged_dated["Date"])
    merged_dated = merged_dated.merge(
        wind_df[["Station ID", "Date", "wind_dir_deg", "wind_spd_kmh"]],
        on=["Station ID", "Date"],
        how="left",
    )
    # Rename to valid Python identifier so itertuples access works
    merged_dated = merged_dated.rename(columns={"Station ID": "station_id"})

    # Station lookup: id → (lat, lon)
    station_locs: dict[int, tuple[float, float]] = {
        int(row["Station ID"]): (float(row["Latitude"]), float(row["Longitude"]))
        for _, row in load_station_locations(merged).iterrows()
    }

    total = len(merged_dated)
    print(f"  Processing {total:,} (station, date) pairs ...")
    print(f"  Lags: {LAGS}, intensity proxies: hfi, frp, tfc")
    print(f"  Distance kernel: Cauchy, d0={D0_KM} km, cutoff={MAX_DIST_KM} km")

    records = []
    for i, row in enumerate(merged_dated.itertuples(index=False)):
        if i % 5000 == 0:
            pct = 100 * i / total
            print(f"  {i:>6,} / {total:,}  ({pct:.1f}%)", end="\r", flush=True)

        s_id  = int(row.station_id)
        date  = row.Date
        s_lat, s_lon = station_locs[s_id]
        wind_dir = float(row.wind_dir_deg) if not _isnan(row.wind_dir_deg) else np.nan
        wind_spd = float(row.wind_spd_kmh) if not _isnan(row.wind_spd_kmh) else np.nan

        wsei = compute_wsei_for_station_date(
            s_lat, s_lon, wind_dir, wind_spd, hotspot_groups, date
        )
        wsei["Station ID"] = s_id
        wsei["Date"]       = date
        wsei["wind_dir_deg"]  = wind_dir
        wsei["wind_spd_kmh"]  = wind_spd
        records.append(wsei)

    print(f"\n  Done. {total:,} records computed.")

    out = pd.DataFrame(records)
    # Reorder columns
    front = ["Station ID", "Date", "wind_dir_deg", "wind_spd_kmh"]
    wsei_cols = [c for c in out.columns if c not in front]
    out = out[front + sorted(wsei_cols)]
    return out


def _isnan(x) -> bool:
    """Safe NaN check for values that could be float or numpy scalar."""
    try:
        return math.isnan(x)
    except (TypeError, ValueError):
        return x is None or pd.isna(x)


# ── Step 4: Sanity checks ─────────────────────────────────────────────────────

def sanity_checks(wsei_df: pd.DataFrame, merged_df: pd.DataFrame) -> None:
    print("\n── Sanity checks ────────────────────────────────────────────────────")
    print(f"  Output shape: {wsei_df.shape}")
    pct_nonzero = (wsei_df["wsei_hfi_k0"] > 0).mean()
    print(f"  Station-days with wsei_hfi_k0 > 0: {pct_nonzero:.1%}")

    # Top dates by mean WSEI (should be summer 2023)
    wsei_df2 = wsei_df.copy()
    wsei_df2["Date"] = pd.to_datetime(wsei_df2["Date"])
    top_dates = (wsei_df2.groupby("Date")["wsei_hfi_k0"].mean()
                 .nlargest(10).reset_index())
    print("\n  Top 10 dates by mean wsei_hfi_k0:")
    print(top_dates.to_string(index=False))

    # Correlation with AQI
    merged_df2 = merged_df[["Station ID", "Date", "AQI"]].copy()
    merged_df2["Date"] = pd.to_datetime(merged_df2["Date"])
    combined = wsei_df2.merge(merged_df2, on=["Station ID", "Date"], how="inner")
    corr = combined["wsei_hfi_k0"].corr(combined["AQI"])
    print(f"\n  Pearson correlation(wsei_hfi_k0, AQI): {corr:.4f}")
    if corr > 0.05:
        print("  [OK] Positive correlation -- wildfire signal is present")
    else:
        print("  [WARN] Correlation low -- check bounding box, kernel, or data coverage")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 65)
    print("  build_wsei_features.py — Case Study 2 Feature Engineering")
    print("=" * 65)

    # Load merged station-day dataset
    print(f"\nLoading {MERGED_PATH} ...")
    merged = pd.read_csv(MERGED_PATH, low_memory=False)
    print(f"  Merged dataset: {merged.shape}")

    # Step 1: Wind direction
    wind_df = build_wind_features(merged)

    # Step 2: Hotspots
    hotspot_groups = load_hotspots()

    # Step 3: WSEI
    wsei_df = compute_all_wsei(merged, wind_df, hotspot_groups)

    # Step 4: Sanity
    sanity_checks(wsei_df, merged)

    # Save intermediate WSEI cache
    print(f"\n── Saving outputs ───────────────────────────────────────────────────")
    OUT_WSEI.parent.mkdir(parents=True, exist_ok=True)
    wsei_df.to_csv(OUT_WSEI, index=False)
    print(f"  Saved wsei_features:     {OUT_WSEI}  ({OUT_WSEI.stat().st_size / 1e6:.1f} MB)")

    # Merge with original dataset and save full modeling dataset
    merged["Date"] = pd.to_datetime(merged["Date"])
    wsei_df["Date"] = pd.to_datetime(wsei_df["Date"])
    full = merged.merge(
        wsei_df.drop(columns=["wind_spd_kmh"]),  # wind_spd_kmh ≈ MaxGustSpd already in merged
        on=["Station ID", "Date"],
        how="left",
    )
    full.to_csv(OUT_MERGED, index=False)
    print(f"  Saved merged_with_wsei:  {OUT_MERGED}  ({OUT_MERGED.stat().st_size / 1e6:.1f} MB)")
    print(f"\nDone. Final dataset shape: {full.shape}")
    print(f"New columns added: {[c for c in full.columns if c not in merged.columns]}")


if __name__ == "__main__":
    main()
