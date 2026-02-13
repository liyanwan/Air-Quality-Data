#!/usr/bin/env bash
set -euo pipefail

echo "==> Running notebooks to generate figures"
jupyter nbconvert --to notebook --execute --inplace model/"Model Fitting to question 2.ipynb" \
  --ExecutePreprocessor.timeout=600

echo "==> Rendering Quarto report"
quarto render report/"Research Question 2 Report.qmd"

echo "==> Verify outputs"
test -d outputs/figures && echo "OK: figures generated"
ls outputs/figures/*.png
echo "Done"
