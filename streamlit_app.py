from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.analyze import (  # noqa: E402
    DATA,
    OUT,
    FUND,
    ISIN,
    calculate,
    load_series,
    make_pdf,
    monthly_returns,
    pct,
)

st.set_page_config(page_title=f"{FUND} | Analyse 2026", page_icon="📈", layout="wide")
st.title(FUND)
st.caption(f"Wertentwicklung und Risikoanalyse 2026 · ISIN {ISIN}")

with st.sidebar:
    st.header("Daten")
    st.write("Standardmäßig wird die NAV-Reihe aus der Aufgabenmappe verwendet.")
    uploaded = st.file_uploader("Eigene NAV-Reihe laden (CSV)", type=["csv"], help="Erwartete Spalten: date,nav_eur")
    benchmark_file = st.file_uploader("Optional: Benchmark-Reihe laden (CSV)", type=["csv"], help="Erwartete Spalten: date,close")
    st.caption("Datenstichtag der enthaltenen Reihe: 30.09.2026")


def series_from_upload(file, column: str) -> pd.Series:
    frame = pd.read_csv(file, parse_dates=["date"])
    if not {"date", column}.issubset(frame.columns):
        raise ValueError(f"CSV benötigt die Spalten date und {column}.")
    s = pd.Series(pd.to_numeric(frame[column], errors="raise").values, index=pd.DatetimeIndex(frame["date"]), name=column)
    s = s[~s.index.duplicated(keep="last")].sort_index().dropna()
    if len(s) < 2 or (s <= 0).any():
        raise ValueError("Die Reihe muss mindestens zwei positive Werte enthalten.")
    return s


try:
    nav = series_from_upload(uploaded, "nav_eur") if uploaded else load_series(DATA / "nav_prices.csv", "nav_eur")
    benchmark = series_from_upload(benchmark_file, "close") if benchmark_file else None
except Exception as exc:
    st.error(str(exc))
    st.stop()

metrics, daily, wealth, drawdown = calculate(nav)
metrics["benchmark_available"] = benchmark is not None

st.info(
    f"**Kurzbeurteilung:** Die NAV-Preisrendite betrug **{pct(metrics['ytd_price_return'])}** "
    f"vom Startwert {metrics['base_nav_eur']:.2f} EUR am {metrics['start_date']} bis "
    f"{metrics['latest_nav_eur']:.2f} EUR am {metrics['end_date']}. "
    f"Der maximale Drawdown lag bei **{pct(metrics['max_drawdown'])}**; bis zum Datenende "
    f"war der vorherige Höchststand {'wieder erreicht' if metrics['recovered_previous_peak'] else 'noch nicht wieder erreicht'}."
)

cols = st.columns(5)
cols[0].metric("NAV-Rendite", pct(metrics["ytd_price_return"]))
cols[1].metric("Annualisierte Rendite", pct(metrics["annualized_compound_return"]))
cols[2].metric("Annualisierte Volatilität", pct(metrics["annualized_volatility"]))
cols[3].metric("Max. Drawdown", pct(metrics["max_drawdown"]))
cols[4].metric("Sharpe (Rf 0%)", f"{metrics['sharpe_ratio_rf_0']:.2f}")

st.subheader("Interaktive Kurs- und Risikoanalyse")
left, right = st.columns(2)
with left:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=wealth.index, y=wealth * 100, mode="lines", name="Fonds", line=dict(color="#174A7E", width=2.5)))
    if benchmark is not None:
        b = benchmark.reindex(nav.index).ffill().dropna()
        fig.add_trace(go.Scatter(x=b.index, y=b / b.iloc[0] * 100, mode="lines", name="Benchmark", line=dict(color="#E28E2C", width=2)))
    fig.update_layout(title="Wertentwicklung (Start = 100)", yaxis_title="Indexstand", xaxis_title="Datum", hovermode="x unified", template="plotly_white", legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)
with right:
    fig = go.Figure(go.Scatter(x=drawdown.index, y=drawdown * 100, mode="lines", fill="tozeroy", name="Drawdown", line=dict(color="#B24745")))
    fig.update_layout(title="Drawdown vom bisherigen Höchststand", yaxis_title="Drawdown (%)", xaxis_title="Datum", hovermode="x unified", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
with left:
    monthly = monthly_returns(nav)
    fig = px.bar(x=monthly.index, y=monthly.values * 100, color=monthly.values >= 0,
                 color_discrete_map={True: "#27866B", False: "#C45454"}, labels={"x": "Monat", "y": "Rendite (%)"}, title="Monatsrenditen")
    fig.update_layout(showlegend=False, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)
with right:
    fig = px.histogram(x=daily.values * 100, nbins=24, labels={"x": "Tagesrendite (%)", "y": "Häufigkeit"}, title="Verteilung der Tagesrenditen")
    fig.update_layout(template="plotly_white", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

rolling_vol = daily.rolling(21).std() * (252 ** 0.5) * 100
fig = go.Figure(go.Scatter(x=rolling_vol.index, y=rolling_vol, mode="lines", name="21-Tage-Volatilität", line=dict(color="#6C5AA7")))
fig.update_layout(title="Rollierende annualisierte Volatilität (21 Handelstage)", yaxis_title="Volatilität (%)", xaxis_title="Datum", template="plotly_white")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Alle Kennzahlen und Definitionen"):
    detail = [
        ("Beobachtungen", str(metrics["observations"])),
        ("Zeitraum", f"{metrics['start_date']} bis {metrics['end_date']}"),
        ("Start-NAV / letzter NAV", f"{metrics['base_nav_eur']:.2f} / {metrics['latest_nav_eur']:.2f} EUR"),
        ("Annualisierte Downside-Abweichung", pct(metrics["annualized_downside_deviation"])),
        ("Sortino Ratio (Rf = 0%)", f"{metrics['sortino_ratio_rf_0']:.2f}" if metrics["sortino_ratio_rf_0"] is not None else "n/a"),
        ("Historischer 95%-VaR (1 Tag)", pct(metrics["historical_var_95_daily_loss"])),
        ("Historischer 95%-Expected Shortfall", pct(metrics["historical_expected_shortfall_95_daily_loss"])),
        ("Bester / schlechtester Tag", f"{pct(metrics['best_day'])} ({metrics['best_day_date']}) / {pct(metrics['worst_day'])} ({metrics['worst_day_date']})"),
        ("Positive Tagesrenditen", pct(metrics["positive_days_share"])),
        ("Max-Drawdown-Hoch → Tief", f"{metrics['max_drawdown_peak_date']} → {metrics['max_drawdown_trough_date']}"),
    ]
    st.dataframe(pd.DataFrame(detail, columns=["Kennzahl", "Wert"]), hide_index=True, use_container_width=True)

st.subheader("PDF-Bericht")
OUT.mkdir(exist_ok=True)
pdf_path = OUT / "summary.pdf"
make_pdf(nav, metrics, daily, wealth, drawdown, benchmark)
st.download_button("PDF-Zusammenfassung herunterladen", data=pdf_path.read_bytes(), file_name="deka_deutschland_nebenwerte_2026.pdf", mime="application/pdf", type="primary")

st.caption(
    "Hinweise: Die NAV-Reihe reicht bis 30.09.2026. Renditen sind Preisrenditen ohne Ausschüttungsbereinigung, "
    "Steuern oder Anlegerkosten. Ohne Benchmark-Datei ist kein relativer Vergleich möglich. "
    "Annualisierte Kennzahlen beruhen auf weniger als einem Jahr und sind indikativ; VaR/ES sind historische Schätzwerte."
)
