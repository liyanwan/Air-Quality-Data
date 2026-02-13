# Air Quality Data

This repository contains air quality and climate datasets collected for a case study for STAT 946.

## Data Source
- Environment and Climate Change Canada
- Publicly available air quality and climate monitoring data

## Repository Structure
Air-Quality-Data/\
|-- data/\
|  |-- Calgary_Edmonton_PM25.csv\
|  |-- Kitchener_PM25.csv\
|  |-- climate_summaries.csv\
|  |-- README.md\
|-- README.md

## Datasets
- **Calgary_Edmonton_PM25.csv**: PM2.5 concentration levels for Calgary and Edmonton
- **Kitchener_PM25.csv**: PM2.5 measurements for Kitchener
- **climate_summaries.csv**: Daily temperature and precipitation summaries

## Data Dictionary
Variable definitions, units, and missing value explanations are provided in `data/README.md`.

## Usage
The datasets are intended for exploratory data analysis and statistical case studies.

## File Format
- CSV

## Pipeline: Adding Figures to a Quarto Report

This project uses a two-step pipeline: a Jupyter notebook generates and saves figures, then the `.qmd` report references those saved images. Follow these steps to add new figures.

### Step 1: Save figures from your notebook

In your Jupyter notebook (e.g. `model/Model Fitting to question 2.ipynb`), save each figure as a `.png` to `outputs/figures/`:

```python
import matplotlib.pyplot as plt
import os

os.makedirs("outputs/figures", exist_ok=True)

fig, ax = plt.subplots()
ax.plot(x, y)
fig.savefig("outputs/figures/q2_fig8_my_new_plot.png", dpi=150, bbox_inches="tight")
plt.close(fig)
```

Use a consistent naming convention: `q<question>_fig<number>_<description>.png`.

### Step 2: Reference the figure in the `.qmd` file

In your Quarto report (e.g. `report/Research Question 2 Report.qmd`), insert the image using a relative path from the `report/` folder:

```markdown
![Your caption here.](../outputs/figures/q2_fig8_my_new_plot.png){width=80%}
```

- `width=80%` controls the display size (adjust as needed).
- The path must start with `../outputs/figures/` since the `.qmd` lives in `report/`.

### Step 3: Run the pipeline

**Locally:**

```bash
# 1. Execute the notebook (generates/updates figures)
jupyter nbconvert --to notebook --execute --inplace "model/Model Fitting to question 2.ipynb"

# 2. Render the Quarto report
quarto render "report/Research Question 2 Report.qmd"
```

Or use the convenience script:

```bash
bash scripts/run.sh
```

**On CI:** The GitHub Actions workflow (`.github/workflows/pipeline.yml`) runs both steps automatically on push to `main`.

### Summary

| Step | What to do | Where |
|------|-----------|-------|
| 1 | `fig.savefig("outputs/figures/q2_fig8_name.png")` | Jupyter notebook |
| 2 | `![Caption](../outputs/figures/q2_fig8_name.png){width=80%}` | `.qmd` file |
| 3 | Run `scripts/run.sh` or push to `main` | Terminal / GitHub |

## License
This data is publicly available and intended for academic use.
