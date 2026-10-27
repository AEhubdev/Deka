# Deka-Deutschland Nebenwerte CF — 2026 performance analysis

A Streamlit app for the assignment on Deka-Deutschland Nebenwerte CF (ISIN LU0923076540). It calculates return and risk measures, displays interactive Plotly charts, and provides a downloadable one-page PDF summary.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, create an app from the repository.
3. Set the branch to `main` and the app file path to `streamlit_app.py`.
4. Deploy. Streamlit installs the dependencies from `requirements.txt`.

## Data and interpretation

`data/nav_prices.csv` comes from the supplied workbook `Trainee-Aufgabe_2026.xlsx`; it runs from 30 Dec 2025 through 30 Sep 2026. The app uses the file in the repository by default. You can upload another NAV CSV with columns `date,nav_eur`, and optionally a benchmark CSV with columns `date,close`.

The workbook contains no benchmark history, so the default analysis reports absolute performance and risk; it does not invent relative performance, beta, alpha or tracking error. Deka's official fund page should be consulted to verify current benchmark and fund details before any relative comparison.

Returns use 30 Dec 2025 as the YTD base because the first 2026 observation is 2 Jan 2026. These are price/NAV returns; distributions, investor-specific taxes, transaction costs and front-end loads are excluded. No distribution adjustment is made; confirm distributions before interpreting as total return.

Risk measures use daily simple returns, annualization factor 252, sample standard deviation and a 0% risk-free rate. Historical VaR/ES use the empirical 5th percentile and tail mean; these are backward-looking estimates, not loss limits. Since the available period is shorter than a full year, annualized measures are indicative.

## Outputs and source

The Streamlit app includes an in-browser PDF download and interactive charts for normalized NAV, drawdown, monthly returns, daily-return distribution and rolling volatility. The CLI report generator remains available via `python src/analyze.py` and writes `outputs/summary.pdf`, `outputs/dashboard.html`, and `outputs/metrics.json`.

Source workbook: provided by the user. Official fund page: https://www.deka.de/privatkunden-legacy/fondsprofil?fl=1&id=LU0923076540
