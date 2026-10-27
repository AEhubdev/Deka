# Deka-Deutschland Nebenwerte CF — 2026 performance analysis

Python project for the assignment on Deka-Deutschland Nebenwerte CF (ISIN LU0923076540). It reads the supplied daily NAV series, calculates return and risk measures, creates an interactive HTML dashboard and a PDF report with charts.

## Data and interpretation

`data/nav_prices.csv` is extracted from the supplied workbook `Trainee-Aufgabe_2026.xlsx`; the series runs from 30 Dec 2025 through 30 Sep 2026. The project preserves those observations and does not fetch or overwrite market data. Returns use 30 Dec 2025 as the YTD base because the first 2026 observation is 2 Jan 2026. These are price/NAV returns and exclude investor-specific taxes, transaction costs and any front-end load. No distribution adjustment is made; confirm treatment of distributions before interpreting as total return.

The workbook contains no benchmark history. The analysis therefore reports absolute performance and risk; it does not invent relative performance, beta, alpha or tracking error. Optionally add `data/benchmark.csv` with columns `date,close` and rerun; the dashboard will show relative performance and beta/alpha with at least 60 matched daily returns. Deka's official fund page should be consulted to verify current benchmark and fund details before a relative comparison.

Risk measures use daily simple returns, annualization factor 252, sample standard deviation and a 0% risk-free rate. Historical VaR/ES use the empirical 5th percentile and tail mean; these are backward-looking estimates, not loss limits. With less than one calendar year of observations, annualized measures are indicative.

## Run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python src/analyze.py
```

Outputs go to `outputs/`: `summary.pdf`, `dashboard.html`, and `metrics.json`. Open `dashboard.html` in a browser for interactive charts; Plotly.js loads from its CDN. The PDF is a portable summary with the same core facts and vector charts.

## Source

The source workbook was provided by the user. Official fund page: https://www.deka.de/privatkunden-legacy/fondsprofil?fl=1&id=LU0923076540
