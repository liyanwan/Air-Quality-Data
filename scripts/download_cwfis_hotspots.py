"""
Download CWFIS Fire M3 Daily Hotspot archives for 2022-2024.

Downloads the annual hotspot ZIP files from the Canadian Wildland Fire Information
System (CWFIS) Datamart, extracts them, combines all three years, filters to
Canadian hotspots only (country == "C"), and saves a single gzipped CSV.

Source:  https://cwfis.cfs.nrcan.gc.ca/downloads/hotspots/archive/
Files:   2022_hotspots.zip (~55 MB), 2023_hotspots.zip (~216 MB), 2024_hotspots.zip (~135 MB)

Output:
    data/wildfire/raw/{year}_hotspots.zip        raw ZIP archives (gitignored)
    data/wildfire/raw/{year}_hotspots/           extracted CSVs  (gitignored)
    data/wildfire/hotspots_2022_2024_canada.csv.gz  combined, Canada-only (~320 MB, gitignored)

Re-running this script is safe: already-downloaded ZIPs and extracted folders are skipped.
Run clean_cwfis_hotspots.py afterwards to produce the analysis-ready file.

Usage:
    python scripts/download_cwfis_hotspots.py
"""

import urllib.request
import zipfile
import io
import os
import glob
import pandas as pd
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "wildfire" / "raw"
OUT_CSV = REPO_ROOT / "data" / "wildfire" / "hotspots_2022_2024_canada.csv.gz"

RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── Archive URLs ───────────────────────────────────────────────────────────────
BASE_URL = "https://cwfis.cfs.nrcan.gc.ca/downloads/hotspots/archive"
YEARS = [2022, 2023, 2024]


def download_with_progress(url: str, dest: Path) -> None:
    """Download url to dest, showing MB progress."""
    if dest.exists():
        print(f"  [skip] {dest.name} already downloaded")
        return
    print(f"  Downloading {url} ...")
    tmp = dest.with_suffix(".tmp")
    try:
        with urllib.request.urlopen(url) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk = 1 << 20  # 1 MB
            with open(tmp, "wb") as f:
                while True:
                    block = resp.read(chunk)
                    if not block:
                        break
                    f.write(block)
                    downloaded += len(block)
                    if total:
                        pct = 100 * downloaded / total
                        print(f"    {downloaded/1e6:.1f} / {total/1e6:.1f} MB  ({pct:.0f}%)",
                              end="\r", flush=True)
        tmp.rename(dest)
        print(f"\n  Saved → {dest}")
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def extract_zip(zip_path: Path, extract_dir: Path) -> None:
    """Extract zip archive, skip if already done."""
    sentinel = extract_dir / ".extracted"
    if sentinel.exists():
        print(f"  [skip] {extract_dir.name} already extracted")
        return
    extract_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Extracting {zip_path.name} → {extract_dir} ...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    sentinel.touch()
    print(f"  Done.")


def find_csv(extract_dir: Path) -> list[Path]:
    """Recursively find all CSV files under extract_dir."""
    return sorted(Path(p) for p in glob.glob(str(extract_dir / "**" / "*.csv"), recursive=True))


def load_year(year: int, extract_dir: Path) -> pd.DataFrame:
    """
    Load all CSVs for a given year into one DataFrame.
    The archive may contain one CSV per day or one CSV per year — handle both.
    """
    csvs = find_csv(extract_dir)
    if not csvs:
        raise FileNotFoundError(f"No CSV files found under {extract_dir}. "
                                "Archive may contain shapefiles only — see note below.")

    print(f"  Found {len(csvs)} CSV(s) for {year}")
    frames = []
    for p in csvs:
        try:
            df = pd.read_csv(p, low_memory=False)
            frames.append(df)
        except Exception as e:
            print(f"  Warning: could not read {p.name}: {e}")

    combined = pd.concat(frames, ignore_index=True)
    combined["source_year"] = year
    return combined


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise column names to lowercase and map known aliases.
    CWFIS CSVs use lowercase names but aliases vary across years.
    """
    df.columns = df.columns.str.strip().str.lower()

    # Common aliases observed in CWFIS exports
    renames = {
        "latitude": "lat",
        "longitude": "lon",
        "rep_date": "rep_date",        # already correct
        "datetime": "rep_date",
        "date": "rep_date",
        "headfireintensity": "hfi",
        "estimatedarea": "estarea",
        "totalfuelconsumption": "tfc",
        "fireradiativepower": "frp",
    }
    df = df.rename(columns={k: v for k, v in renames.items() if k in df.columns})
    return df


def main() -> None:
    all_frames = []

    for year in YEARS:
        print(f"\n{'='*60}")
        print(f"Year {year}")
        zip_path = RAW_DIR / f"{year}_hotspots.zip"
        extract_dir = RAW_DIR / f"{year}_hotspots"

        # 1. Download
        url = f"{BASE_URL}/{year}_hotspots.zip"
        download_with_progress(url, zip_path)

        # 2. Extract
        extract_zip(zip_path, extract_dir)

        # 3. Load
        df = load_year(year, extract_dir)
        df = normalise_columns(df)

        print(f"  Shape: {df.shape}")
        print(f"  Columns: {list(df.columns)}")

        # 4. Sanity-check key columns
        for col in ["lat", "lon", "rep_date"]:
            if col not in df.columns:
                print(f"  WARNING: expected column '{col}' not found — check column list above")

        all_frames.append(df)

    # ── Combine all years ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("Combining all years ...")
    combined = pd.concat(all_frames, ignore_index=True)

    # Parse date
    date_col = "rep_date" if "rep_date" in combined.columns else None
    if date_col:
        combined[date_col] = pd.to_datetime(combined[date_col], utc=True, errors="coerce")
        combined["date"] = combined[date_col].dt.normalize().dt.tz_localize(None)
    else:
        print("WARNING: no date column found; 'date' column not created")

    print(f"Combined shape: {combined.shape}")
    print(f"Date range: {combined['date'].min()} – {combined['date'].max()}" if "date" in combined.columns else "")
    print(f"Columns:\n  {list(combined.columns)}")

    # ── Filter to Canada only ──────────────────────────────────────────────────
    if "country" in combined.columns:
        n_before = len(combined)
        combined = combined[combined["country"].str.upper().eq("C")].copy()
        print(f"Filtered to Canada: {n_before:,} → {len(combined):,} rows")
    else:
        print("WARNING: no 'country' column found; keeping all rows")

    # ── Save ───────────────────────────────────────────────────────────────────
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUT_CSV, index=False, compression="gzip")
    print(f"\nSaved combined CSV → {OUT_CSV}")
    print(f"File size: {OUT_CSV.stat().st_size / 1e6:.1f} MB")

    # ── Quick preview ──────────────────────────────────────────────────────────
    print("\nSample rows:")
    print(combined.head(3).to_string())

    print("\nValue counts by year:")
    if "source_year" in combined.columns:
        print(combined["source_year"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
