"""
Streamlit dashboard for the India DCF model.

Run with:
    streamlit run app.py

Data is sourced via Yahoo Finance (yfinance) — free, no API key required.
"""

import io
import traceback

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from modeling.data import (
    get_balance_statement,
    get_cashflow_statement,
    get_EV_statement,
    get_historical_share_prices,
    get_income_statement,
)
from modeling.dcf import equity_value, ulFCF

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="India DCF Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .company-header {
        background: linear-gradient(135deg, #0f2942 0%, #1a4a7a 100%);
        border-radius: 16px;
        padding: 24px 32px;
        color: white;
        margin-bottom: 28px;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .company-header .name { font-size: 1.7rem; font-weight: 700; }
    .company-header .sub  { opacity: 0.65; font-size: 0.88rem; margin-top: 4px; }
    .company-header .prices { display: flex; gap: 48px; margin-top: 16px; }
    .company-header .price-block .label { opacity: 0.55; font-size: 0.78rem; }
    .company-header .price-block .value { font-size: 1.35rem; font-weight: 700; }

    .stButton > button {
        background: linear-gradient(135deg, #1565C0, #0D47A1);
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.65rem 1rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        width: 100% !important;
        transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.88; }

    div[data-testid="stExpander"] { border-radius: 10px !important; }
    .footer { text-align: center; opacity: 0.4; font-size: 0.78rem; margin-top: 32px; }
</style>
""", unsafe_allow_html=True)

# ── Popular stocks ────────────────────────────────────────────────────────────
POPULAR_STOCKS = {
    "Custom ticker...": "",
    "DMART.NS — Avenue Supermarts": "DMART.NS",
    "RELIANCE.NS — Reliance Industries": "RELIANCE.NS",
    "TCS.NS — Tata Consultancy Services": "TCS.NS",
    "HDFCBANK.NS — HDFC Bank": "HDFCBANK.NS",
    "INFY.NS — Infosys": "INFY.NS",
    "HINDUNILVR.NS — Hindustan Unilever": "HINDUNILVR.NS",
    "BAJFINANCE.NS — Bajaj Finance": "BAJFINANCE.NS",
    "ASIANPAINT.NS — Asian Paints": "ASIANPAINT.NS",
    "NESTLEIND.NS — Nestle India": "NESTLEIND.NS",
    "TITAN.NS — Titan Company": "TITAN.NS",
    "WIPRO.NS — Wipro": "WIPRO.NS",
    "BHARTIARTL.NS — Bharti Airtel": "BHARTIARTL.NS",
    "ICICIBANK.NS — ICICI Bank": "ICICIBANK.NS",
    "KOTAKBANK.NS — Kotak Mahindra Bank": "KOTAKBANK.NS",
    "PIDILITIND.NS — Pidilite Industries": "PIDILITIND.NS",
    "MARUTI.NS — Maruti Suzuki": "MARUTI.NS",
    "ADANIENT.NS — Adani Enterprises": "ADANIENT.NS",
}

SWEEP_LABEL = {
    "eg":       "Earnings Growth",
    "cg":       "CapEx Growth",
    "pg":       "Perpetual Growth",
    "discount": "Discount Rate",
}

COLORS = ["#2196F3", "#FF9800", "#4CAF50", "#E91E63", "#9C27B0", "#00BCD4"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_inr(val):
    """Format a large INR number as ₹X Cr / ₹X L.Cr."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return "N/A"
    if abs(v) >= 1e12:
        return f"₹{v / 1e12:.2f} L.Cr"
    if abs(v) >= 1e7:
        return f"₹{v / 1e7:.2f} Cr"
    return f"₹{v:,.0f}"


# ── Cached data fetchers ──────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_statements(ticker):
    return (
        get_income_statement(ticker),
        get_cashflow_statement(ticker),
        get_balance_statement(ticker),
        get_EV_statement(ticker),
    )


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_company_info(ticker):
    return yf.Ticker(ticker).info


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_hist_prices(ticker, dates_tuple):
    return get_historical_share_prices(ticker, list(dates_tuple))


# ── Core DCF calculation (no print statements — returns structured data) ──────
def compute_dcf(i, income, cashflow, balance, ev_stmt,
                forecast, discount, eg, cg, pg):
    """
    Compute a single DCF for historical interval i.

    Returns a dict with:
        date, enterprise_value, equity_value, share_price, forecast_rows
    Raises ValueError / IndexError on missing data.
    """
    inc = income[i: i + 2]
    bal = balance[i: i + 2]
    cf  = cashflow[i: i + 2]
    ev  = ev_stmt[i]

    if len(inc) < 2 or len(bal) < 2 or len(cf) < 1:
        raise IndexError("Not enough historical rows for this interval.")

    ebit     = float(inc[0].get("ebit") or 0)
    if ebit == 0:
        raise ValueError(f"EBIT is zero / missing for {inc[0]['date']}.")

    tax_rate = float(inc[0]["incomeTaxExpense"]) / float(inc[0]["incomeBeforeTax"])
    da       = float(cf[0]["depreciationAndAmortization"] or 0)
    cwc      = (
        (float(bal[0]["totalAssets"]) - float(bal[0]["totalNonCurrentAssets"])) -
        (float(bal[1]["totalAssets"]) - float(bal[1]["totalNonCurrentAssets"]))
    )
    capex    = float(cf[0]["capitalExpenditure"] or 0)
    base_yr  = int(inc[0]["date"][:4])

    flows = []
    forecast_rows = []

    for yr in range(1, forecast + 1):
        ebit  *= 1 + yr * eg
        da    *= 1 + yr * eg
        cwc   *= 0.7
        capex *= 1 + yr * cg

        flow    = ulFCF(ebit, tax_rate, da, cwc, capex)
        pv_flow = flow / ((1 + discount) ** yr)
        flows.append(pv_flow)

        forecast_rows.append({
            "Year":       base_yr + yr,
            "DFCF (₹)":  fmt_inr(pv_flow),
            "EBIT (₹)":  fmt_inr(ebit),
            "D&A (₹)":   fmt_inr(da),
            "CWC (₹)":   fmt_inr(cwc),
            "CapEx (₹)": fmt_inr(capex),
        })

    npv_fcf = sum(flows)
    tv      = (flows[-1] * (1 + pg)) / (discount - pg)
    npv_tv  = tv / (1 + discount) ** (1 + forecast)
    ent_val = npv_fcf + npv_tv

    eq_val, sp = equity_value(ent_val, ev)

    return {
        "date":             inc[0]["date"],
        "enterprise_value": ent_val,
        "equity_value":     eq_val,
        "share_price":      sp,
        "forecast_rows":    forecast_rows,
    }


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 India DCF Model")
    st.markdown("---")

    # Company selection
    st.markdown("### 🏢 Company")
    stock_choice = st.selectbox("Select a company", list(POPULAR_STOCKS.keys()), index=1)

    if stock_choice == "Custom ticker...":
        ticker = st.text_input(
            "Enter NSE/BSE ticker",
            placeholder="e.g. TITAN.NS, BHARTIARTL.NS"
        ).strip().upper()
    else:
        ticker = POPULAR_STOCKS[stock_choice]
        st.caption(f"Ticker: `{ticker}`")

    st.markdown("---")

    # DCF Parameters
    st.markdown("### ⚙️ DCF Parameters")
    years    = st.slider("Historical years to analyse", 1, 5, 3)
    forecast = st.slider("Years to forecast FCF",       1, 10, 5)
    discount = st.slider("Discount rate / WACC (%)",    5, 20, 10, 1) / 100
    eg       = st.slider("Earnings growth rate (%)",    5, 40, 12, 1) / 100
    cg       = st.slider("CapEx growth rate (%)",       2, 20,  5, 1) / 100
    pg       = st.slider("Perpetual growth rate (%)",   3, 10,  6, 1) / 100

    st.markdown("---")

    # Sensitivity sweep
    st.markdown("### 📈 Sensitivity Sweep")
    sweep_on = st.toggle("Enable sensitivity sweep", value=True)
    if sweep_on:
        sweep_var   = st.selectbox("Variable to sweep", list(SWEEP_LABEL.keys()),
                                   format_func=lambda k: SWEEP_LABEL[k])
        sweep_steps = st.slider("Number of steps", 1, 5, 2)
        sweep_pct   = st.slider("Step size (%)", 5, 30, 10, 5) / 100

    st.markdown("---")
    run = st.button("🚀  Run DCF Analysis")


# ── Main panel ────────────────────────────────────────────────────────────────
st.markdown("# 📊 India DCF Dashboard")
st.caption("Discounted Cash Flow valuation for NSE/BSE-listed companies · Data sourced via Yahoo Finance · Values in INR (₹)")

if not run:
    st.info("👈  Configure your parameters in the sidebar, then click **Run DCF Analysis**.")
    st.stop()

if not ticker:
    st.error("Please enter or select a valid ticker symbol.")
    st.stop()

# ── Fetch data ────────────────────────────────────────────────────────────────
with st.spinner(f"Fetching financial statements for **{ticker}**…"):
    try:
        income, cashflow, balance, ev_stmt = fetch_all_statements(ticker)
        info = fetch_company_info(ticker)
    except Exception as e:
        st.error(f"❌ Could not fetch data for `{ticker}`: {e}")
        st.stop()

if not income:
    st.error(f"❌ No income statement data found for `{ticker}`. Please check the ticker.")
    st.stop()

# ── Company header ────────────────────────────────────────────────────────────
name       = info.get("longName") or info.get("shortName") or ticker
exchange   = info.get("exchange", "")
sector     = info.get("sector", "—")
industry   = info.get("industry", "—")
curr_price = info.get("currentPrice") or info.get("regularMarketPrice")
mkt_cap    = info.get("marketCap")
price_str  = f"₹{curr_price:,.2f}" if curr_price else "N/A"
mcap_str   = fmt_inr(mkt_cap) if mkt_cap else "N/A"

st.markdown(f"""
<div class="company-header">
  <div class="name">{name}</div>
  <div class="sub">{ticker} &nbsp;·&nbsp; {exchange} &nbsp;·&nbsp; {sector} / {industry}</div>
  <div class="prices">
    <div class="price-block">
      <div class="label">Current Market Price</div>
      <div class="value">{price_str}</div>
    </div>
    <div class="price-block">
      <div class="label">Market Capitalisation</div>
      <div class="value">{mcap_str}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Build scenarios ───────────────────────────────────────────────────────────
base = {"eg": eg, "cg": cg, "pg": pg, "discount": discount}

if sweep_on:
    scenarios = {}
    for step in range(1, sweep_steps + 1):
        p = base.copy()
        p[sweep_var] = base[sweep_var] * (1 + sweep_pct * step)
        label = f"{SWEEP_LABEL[sweep_var]}: {p[sweep_var]*100:.1f}%"
        scenarios[label] = p
else:
    scenarios = {"DCF Valuation": base}

# ── Run DCF ───────────────────────────────────────────────────────────────────
max_intervals = min(years,
                    len(income) - 1,
                    len(balance) - 1,
                    len(cashflow) - 1,
                    len(ev_stmt))

all_results: dict[str, dict] = {}  # label → {date → result}

for label, params in scenarios.items():
    all_results[label] = {}
    for i in range(max_intervals):
        try:
            res = compute_dcf(
                i, income, cashflow, balance, ev_stmt,
                forecast,
                params["discount"], params["eg"], params["cg"], params["pg"],
            )
            all_results[label][res["date"]] = res
        except Exception as e:
            st.warning(f"Skipped interval {i} for '{label}': {e}")

if not any(all_results[s] for s in all_results):
    st.error("No DCF results could be computed. Financial data may be insufficient for this ticker.")
    st.stop()

# ── Headline metrics ──────────────────────────────────────────────────────────
st.markdown("### 📋 Most Recent DCF Snapshot")

first_label   = list(all_results.keys())[0]
first_results = all_results[first_label]
if first_results:
    latest_date = sorted(first_results.keys())[-1]
    latest      = first_results[latest_date]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Enterprise Value",  fmt_inr(latest["enterprise_value"]),
              help="NPV of explicit FCFs + NPV of Terminal Value")
    c2.metric("Equity Value",      fmt_inr(latest["equity_value"]),
              help="Enterprise Value − Total Debt + Cash")
    c3.metric("DCF Per Share",     f"₹{latest['share_price']:,.0f}",
              help="Equity Value ÷ Shares Outstanding")
    with c4:
        if curr_price:
            pct = ((curr_price - latest["share_price"]) / latest["share_price"]) * 100
            lbl = "Market Premium" if pct > 0 else "Market Discount"
            st.metric(lbl, f"{abs(pct):.1f}%",
                      delta=f"Market @ ₹{curr_price:,.0f}",
                      delta_color="inverse")
        else:
            st.metric("Market Price", "N/A")

st.markdown("---")

# ── Year-by-year expandable detail ───────────────────────────────────────────
st.markdown("### 📅 Year-by-Year FCF Forecast Detail")

for label, results in all_results.items():
    for date, res in sorted(results.items()):
        with st.expander(
            f"📆 **{date}**  ·  {label}  ·  Per Share: ₹{res['share_price']:,.0f}"
        ):
            ca, cb, cc = st.columns(3)
            ca.metric("Enterprise Value", fmt_inr(res["enterprise_value"]))
            cb.metric("Equity Value",     fmt_inr(res["equity_value"]))
            cc.metric("Per Share Value",  f"₹{res['share_price']:,.2f}")

            if res["forecast_rows"]:
                df = pd.DataFrame(res["forecast_rows"]).set_index("Year")
                st.dataframe(df, use_container_width=True)

st.markdown("---")

# ── Interactive Plotly chart ──────────────────────────────────────────────────
st.markdown("### 📈 DCF Intrinsic Value vs. Actual Market Price")

all_dates = sorted({
    date
    for results in all_results.values()
    for date in results.keys()
})

with st.spinner("Fetching historical prices…"):
    try:
        hist_prices = fetch_hist_prices(ticker, tuple(all_dates))
    except Exception as e:
        hist_prices = {}
        st.warning(f"Could not fetch historical prices: {e}")

fig = go.Figure()

for idx, (label, results) in enumerate(all_results.items()):
    if not results:
        continue
    dates_sorted = sorted(results.keys())
    prices_sorted = [results[d]["share_price"] for d in dates_sorted]
    color = COLORS[idx % len(COLORS)]

    fig.add_trace(go.Scatter(
        x=dates_sorted,
        y=prices_sorted,
        mode="lines+markers",
        name=label,
        line=dict(color=color, width=2.5),
        marker=dict(size=9),
        hovertemplate=(
            "<b>%{fullData.name}</b><br>"
            "Date: %{x}<br>"
            "DCF per share: ₹%{y:,.0f}"
            "<extra></extra>"
        ),
    ))

valid_hist = {d: p for d, p in hist_prices.items() if p is not None}
if valid_hist:
    fig.add_trace(go.Scatter(
        x=list(valid_hist.keys()),
        y=list(valid_hist.values()),
        mode="lines+markers",
        name=f"{ticker} — Actual Price",
        line=dict(color="#FFD700", width=3, dash="dash"),
        marker=dict(size=10, symbol="diamond"),
        hovertemplate=(
            "<b>Actual Market Price</b><br>"
            "Date: %{x}<br>"
            "Price: ₹%{y:,.2f}"
            "<extra></extra>"
        ),
    ))

fig.update_layout(
    title=dict(
        text=f"{name} — DCF Intrinsic Value vs. Market Price",
        font=dict(size=17, color="white"),
    ),
    xaxis=dict(
        title="Fiscal Year End Date",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        color="rgba(255,255,255,0.7)",
    ),
    yaxis=dict(
        title="Share Price (₹)",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        color="rgba(255,255,255,0.7)",
        tickprefix="₹",
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(color="white"),
    ),
    hovermode="x unified",
    plot_bgcolor="rgba(12, 26, 42, 0.95)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="white", family="Inter"),
    height=500,
    margin=dict(l=60, r=20, t=90, b=60),
)

st.plotly_chart(fig, use_container_width=True)

# ── Download buttons ──────────────────────────────────────────────────────────
dl1, dl2, _ = st.columns([1, 1, 2])

with dl1:
    try:
        img_bytes = fig.to_image(format="png", width=1400, height=700, scale=2)
        st.download_button(
            label="⬇️ Download PNG",
            data=img_bytes,
            file_name=f"{ticker}_dcf_chart.png",
            mime="image/png",
        )
    except Exception:
        # kaleido not installed — offer HTML fallback
        buf = io.StringIO()
        fig.write_html(buf)
        st.download_button(
            label="⬇️ Download HTML",
            data=buf.getvalue().encode(),
            file_name=f"{ticker}_dcf_chart.html",
            mime="text/html",
        )

with dl2:
    # CSV download of all results
    rows = []
    for label, results in all_results.items():
        for date, res in results.items():
            rows.append({
                "Scenario":          label,
                "Date":              date,
                "Enterprise Value":  res["enterprise_value"],
                "Equity Value":      res["equity_value"],
                "Per Share (₹)":     res["share_price"],
            })
    if rows:
        csv = pd.DataFrame(rows).to_csv(index=False).encode()
        st.download_button(
            label="⬇️ Download Results CSV",
            data=csv,
            file_name=f"{ticker}_dcf_results.csv",
            mime="text/csv",
        )

st.markdown("---")
st.markdown(
    '<div class="footer">Data via Yahoo Finance · Values in INR (₹) · '
    'This tool is for learning purposes only and does not constitute investment advice.</div>',
    unsafe_allow_html=True,
)
