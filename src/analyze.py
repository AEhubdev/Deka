from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing, String, Line, PolyLine, Rect

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
TRADING_DAYS = 252
RISK_FREE = 0.0
FUND = "Deka-Deutschland Nebenwerte CF"
ISIN = "LU0923076540"


def load_series(path: Path, value_col: str) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["date"])
    if not {"date", value_col}.issubset(frame.columns):
        raise ValueError(f"{path} must contain date,{value_col}")
    series = pd.Series(pd.to_numeric(frame[value_col], errors="raise").values,
                       index=pd.DatetimeIndex(frame["date"]), name=value_col)
    series = series[~series.index.duplicated(keep="last")].sort_index().dropna()
    if len(series) < 2 or (series <= 0).any():
        raise ValueError(f"{path} must have at least two positive observations")
    return series


def pct(x: float) -> str:
    return f"{x:.2%}" if pd.notna(x) else "n/a"


def calculate(nav: pd.Series) -> tuple[dict, pd.Series, pd.Series, pd.Series]:
    daily = nav.pct_change().dropna()
    wealth = nav / nav.iloc[0]
    drawdown = wealth / wealth.cummax() - 1
    ytd = nav.iloc[-1] / nav.iloc[0] - 1
    vol = daily.std(ddof=1) * np.sqrt(TRADING_DAYS)
    downside = daily[daily < 0].std(ddof=1) * np.sqrt(TRADING_DAYS)
    q05 = daily.quantile(.05)
    expected_shortfall = daily[daily <= q05].mean()
    dd_end = drawdown.idxmin()
    dd_peak = wealth.loc[:dd_end].idxmax()
    post_peak = nav.loc[dd_peak:]
    max_recovery = nav.index[-1] if nav.iloc[-1] < nav.loc[dd_peak] else nav.loc[dd_peak:].loc[lambda z: z >= nav.loc[dd_peak]].index.min()
    m = {
        "fund": FUND, "isin": ISIN, "start_date": nav.index[0].date().isoformat(),
        "end_date": nav.index[-1].date().isoformat(), "observations": int(len(nav)),
        "base_nav_eur": float(nav.iloc[0]), "latest_nav_eur": float(nav.iloc[-1]),
        "ytd_price_return": float(ytd), "annualized_volatility": float(vol),
        "annualized_downside_deviation": float(downside),
        "sharpe_ratio_rf_0": float((daily.mean() * TRADING_DAYS - RISK_FREE) / vol) if vol else None,
        "sortino_ratio_rf_0": float((daily.mean() * TRADING_DAYS - RISK_FREE) / downside) if downside and pd.notna(downside) else None,
        "max_drawdown": float(drawdown.min()), "max_drawdown_peak_date": dd_peak.date().isoformat(),
        "max_drawdown_trough_date": dd_end.date().isoformat(),
        "recovered_previous_peak": bool(nav.iloc[-1] >= nav.loc[dd_peak]),
        "historical_var_95_daily_loss": float(-q05),
        "historical_expected_shortfall_95_daily_loss": float(-expected_shortfall),
        "best_day": float(daily.max()), "best_day_date": daily.idxmax().date().isoformat(),
        "worst_day": float(daily.min()), "worst_day_date": daily.idxmin().date().isoformat(),
        "positive_days_share": float((daily > 0).mean()),
        "risk_free_rate_annual": RISK_FREE, "annualization_days": TRADING_DAYS,
        "distribution_adjusted": False, "benchmark_available": False,
    }
    return m, daily, wealth, drawdown


def monthly_returns(nav: pd.Series) -> pd.Series:
    return nav.resample("ME").last().pct_change().dropna()


def make_dashboard(nav: pd.Series, m: dict, daily: pd.Series, wealth: pd.Series, dd: pd.Series, benchmark: pd.Series | None) -> None:
    monthly = monthly_returns(nav)
    fig = make_subplots(rows=2, cols=2, subplot_titles=("Wertentwicklung (Start = 100)", "Drawdown", "Monatsrenditen", "Tägliche Renditeverteilung"),
                        vertical_spacing=.14, horizontal_spacing=.1)
    fig.add_trace(go.Scatter(x=wealth.index, y=wealth * 100, mode="lines", name="Fonds", line=dict(color="#174A7E", width=2.5), hovertemplate="%{x|%d.%m.%Y}<br>%{y:.2f}<extra>Index</extra>"), row=1, col=1)
    if benchmark is not None:
        b = benchmark.reindex(nav.index).ffill().dropna()
        aligned = b / b.iloc[0] * 100
        fig.add_trace(go.Scatter(x=aligned.index, y=aligned, mode="lines", name="Benchmark", line=dict(color="#E28E2C")), row=1, col=1)
    fig.add_trace(go.Scatter(x=dd.index, y=dd * 100, mode="lines", fill="tozeroy", name="Drawdown", line=dict(color="#B24745"), hovertemplate="%{x|%d.%m.%Y}<br>%{y:.2f}%<extra></extra>"), row=1, col=2)
    fig.add_trace(go.Bar(x=monthly.index, y=monthly * 100, name="Monat", marker_color=["#27866B" if x >= 0 else "#C45454" for x in monthly], hovertemplate="%{x|%b %Y}<br>%{y:.2f}%<extra></extra>"), row=2, col=1)
    fig.add_trace(go.Histogram(x=daily * 100, nbinsx=24, name="Tägliche Renditen", marker_color="#7199B9", hovertemplate="Rendite: %{x:.2f}%<br>Anzahl: %{y}<extra></extra>"), row=2, col=2)
    fig.update_xaxes(title_text="Datum", row=1, col=1); fig.update_xaxes(title_text="Datum", row=1, col=2)
    fig.update_yaxes(title_text="Indexstand", row=1, col=1); fig.update_yaxes(title_text="Rendite (%)", row=1, col=2)
    fig.update_yaxes(title_text="Rendite (%)", row=2, col=1); fig.update_xaxes(title_text="Tagesrendite (%)", row=2, col=2)
    fig.update_layout(template="plotly_white", height=850, title=f"{FUND} · YTD bis {m['end_date']}", hovermode="x unified",
                      legend=dict(orientation="h", y=1.04), margin=dict(t=100, l=55, r=30, b=50))
    metrics = f"<b>YTD NAV-Rendite:</b> {pct(m['ytd_price_return'])} &nbsp; <b>Annualisierte Volatilität:</b> {pct(m['annualized_volatility'])} &nbsp; <b>Max. Drawdown:</b> {pct(m['max_drawdown'])} &nbsp; <b>95%-VaR/Tag:</b> {pct(m['historical_var_95_daily_loss'])}"
    notes = ("<p><b>Interpretation:</b> NAV-Preisrendite vom ersten bereitgestellten Stichtag 30.12.2025 bis 30.09.2026. "
             "Die Excel-Datei enthält keine Benchmark-Zeitreihe; ein Vergleich wird nur bei separater data/benchmark.csv (date,close) angezeigt. "
             "Keine Ausschüttungsbereinigung, Steuern oder Anlegerkosten. Annualisierte Risiken bei unterjähriger Stichprobe sind indikativ; VaR/ES sind historische Schätzungen und keine Verlustgrenzen.</p>")
    html = f"<html><head><meta charset='utf-8'><title>{FUND} 2026</title></head><body style='font-family:Arial,sans-serif;margin:24px;color:#263746'><h1>{FUND}</h1><p>ISIN {ISIN} · {m['start_date']} bis {m['end_date']} · {m['observations']} NAV-Beobachtungen</p><p>{metrics}</p>{fig.to_html(full_html=False, include_plotlyjs='cdn')}{notes}</body></html>"
    (OUT / "dashboard.html").write_text(html, encoding="utf-8")


def chart(values: pd.Series, title: str, color: colors.Color, percent: bool = False) -> Drawing:
    w, h = 510, 160
    d = Drawing(w, h)
    d.add(String(0, h-14, title, fontName="Helvetica-Bold", fontSize=9, fillColor=colors.HexColor("#263746")))
    left, right, bottom, top = 36, w-8, 22, h-28
    d.add(Line(left, bottom, right, bottom, strokeColor=colors.HexColor("#AAB4BC")))
    vals = values.astype(float).to_numpy()
    if len(vals) < 2: return d
    lo, hi = float(np.nanmin(vals)), float(np.nanmax(vals))
    if hi == lo: hi = lo + 1
    pts = []
    for i, val in enumerate(vals):
        x = left + (right-left)*i/(len(vals)-1)
        y = bottom + (top-bottom)*(val-lo)/(hi-lo)
        pts.extend([x, y])
    d.add(PolyLine(pts, strokeColor=color, strokeWidth=1.7, fillColor=None))
    d.add(String(left, 5, f"{lo:.1%}" if percent else f"{lo:.1f}", fontSize=7, fillColor=colors.grey))
    d.add(String(right-35, 5, f"{hi:.1%}" if percent else f"{hi:.1f}", fontSize=7, fillColor=colors.grey))
    return d


def make_pdf(nav: pd.Series, m: dict, daily: pd.Series, wealth: pd.Series, dd: pd.Series, benchmark: pd.Series | None) -> None:
    dest = OUT / "summary.pdf"
    doc = SimpleDocTemplate(str(dest), pagesize=A4, rightMargin=17*mm, leftMargin=17*mm, topMargin=14*mm, bottomMargin=14*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Sub", parent=styles["Normal"], textColor=colors.HexColor("#536779"), fontSize=9, leading=13))
    styles.add(ParagraphStyle(name="Finding", parent=styles["Normal"], fontSize=10, leading=15, backColor=colors.HexColor("#EEF3F7"), borderPadding=8, spaceAfter=9))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, leading=11, textColor=colors.HexColor("#506070")))
    story = [Paragraph(FUND, styles["Title"]), Paragraph(f"Wertentwicklung 2026 · ISIN {ISIN} · Datenstand {m['end_date']}", styles["Sub"]), Spacer(1, 5*mm)]
    desc = (f"Der Fonds erzielte seit dem letzten verfügbaren NAV des Vorjahres ({m['base_nav_eur']:.2f} EUR am {m['start_date']}) "
            f"bis {m['latest_nav_eur']:.2f} EUR am {m['end_date']} eine NAV-Preisrendite von <b>{pct(m['ytd_price_return'])}</b>. "
            f"Das Bild war zwischenzeitlich deutlich schwankungsreich: der maximale beobachtete Rückgang vom vorherigen Hoch betrug "
            f"<b>{pct(m['max_drawdown'])}</b> ({m['max_drawdown_peak_date']} bis {m['max_drawdown_trough_date']}); "
            f"der NAV liegt {'wieder über' if m['recovered_previous_peak'] else 'noch unter'} diesem Höchststand.")
    story.append(Paragraph(desc, styles["Finding"]))
    rows = [
        ["Kennzahl", "Ergebnis", "Lesart"],
        ["NAV-Preisrendite (seit 30.12.2025)", pct(m["ytd_price_return"]), "Ohne Ausschüttungsbereinigung"],
        ["Annualisierte Volatilität", pct(m["annualized_volatility"]), "Tägliche NAV-Renditen × √252"],
        ["Annualisierte Downside-Abweichung", pct(m["annualized_downside_deviation"]), "Nur negative Tagesrenditen"],
        ["Sharpe Ratio (Rf = 0%)", f"{m['sharpe_ratio_rf_0']:.2f}" if m["sharpe_ratio_rf_0"] is not None else "n/a", "Indicative, annualisiert"],
        ["Sortino Ratio (Rf = 0%)", f"{m['sortino_ratio_rf_0']:.2f}" if m["sortino_ratio_rf_0"] is not None else "n/a", "Downside-Risiko im Nenner"],
        ["Maximaler Drawdown", pct(m["max_drawdown"]), f"Hoch {m['max_drawdown_peak_date']} → Tief {m['max_drawdown_trough_date']}"],
        ["Historischer 95%-VaR (1 Tag)", pct(m["historical_var_95_daily_loss"]), "Empirisches 5%-Quantil"],
        ["Historischer 95%-Expected Shortfall", pct(m["historical_expected_shortfall_95_daily_loss"]), "Mittlerer Verlust in schlechtesten 5%"],
        ["Bester / schlechtester Tag", f"{pct(m['best_day'])} / {pct(m['worst_day'])}", f"{m['best_day_date']} / {m['worst_day_date']}"],
        ["Positive Handelstage", pct(m["positive_days_share"]), f"{len(daily)} Tagesrenditen"],
    ]
    t = Table(rows, colWidths=[52*mm, 42*mm, 76*mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#174A7E")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                           ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
                           ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F2F5F7")]),
                           ("GRID",(0,0),(-1,-1),.25,colors.HexColor("#D2DAE0")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                           ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
                           ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [t, Spacer(1, 5*mm), chart(wealth*100, "NAV-Entwicklung (Start = 100)", colors.HexColor("#174A7E")), Spacer(1, 3*mm), chart(dd, "Drawdown vom bisherigen Hoch", colors.HexColor("#B24745"), True)]
    if benchmark is not None:
        story.append(Paragraph("Benchmark: verfügbare Benchmark-Reihe separat eingelesen; interaktive relative Rendite im Dashboard.", styles["Small"]))
    story.append(Spacer(1, 4*mm))
    caveat = ("<b>Einordnung und Grenzen.</b> Die Einschätzung beschreibt den Verlauf innerhalb des beobachteten Zeitraums; ein einzelnes Jahr erlaubt keine Aussage über die dauerhafte Qualität des Fonds. "
              "Die Excel-Aufgabe enthält keine Benchmarkreihe, daher sind relative Rendite, Alpha, Beta und Tracking Error nicht beurteilbar. "
              "Die Daten sind Fondspreise/NAVs; Ausschüttungen, Ausgabeaufschlag, laufende Anlegerkosten und Steuern sind nicht berücksichtigt. "
              "VaR und Expected Shortfall basieren auf der historischen Verteilung und garantieren keine Verlustobergrenze. Annualisierung aus weniger als einem Jahr ist mit Vorsicht zu lesen. "
              "Datenquelle: bereitgestellte Trainee-Aufgabe_2026.xlsx; 30.12.2025 bis 30.09.2026; {} NAVs. Reproduzierbare Kennzahlen stehen in metrics.json; interaktive Grafiken in dashboard.html.").format(m["observations"])
    story.append(Paragraph(caveat, styles["Small"]))
    doc.build(story)


def main() -> None:
    nav = load_series(DATA / "nav_prices.csv", "nav_eur")
    m, daily, wealth, dd = calculate(nav)
    benchmark = None
    bpath = DATA / "benchmark.csv"
    if bpath.exists():
        benchmark = load_series(bpath, "close")
        aligned = pd.concat([daily, benchmark.pct_change().rename("benchmark")], axis=1).dropna()
        if len(aligned) >= 60:
            m["benchmark_available"] = True
            m["benchmark_return_aligned"] = float((1 + aligned["benchmark"]).prod() - 1)
            m["fund_return_aligned"] = float((1 + aligned.iloc[:,0]).prod() - 1)
            m["beta"] = float(aligned.iloc[:,0].cov(aligned["benchmark"]) / aligned["benchmark"].var())
            m["alpha_annualized_rf_0"] = float((aligned.iloc[:,0].mean() - m["beta"] * aligned["benchmark"].mean()) * TRADING_DAYS)
        else:
            benchmark = None
    (OUT / "metrics.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    make_dashboard(nav, m, daily, wealth, dd, benchmark)
    make_pdf(nav, m, daily, wealth, dd, benchmark)
    print(f"YTD NAV return: {pct(m['ytd_price_return'])}")
    print(f"Annualized volatility: {pct(m['annualized_volatility'])}; max drawdown: {pct(m['max_drawdown'])}")
    print(f"Created {OUT / 'summary.pdf'} and {OUT / 'dashboard.html'}")


if __name__ == "__main__":
    main()
