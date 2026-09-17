# DCF: Discounted Cash Flow — India Edition

A Python library for computing Discounted Cash Flow (DCF) valuations for **NSE/BSE-listed Indian companies** using freely available financial data via [Yahoo Finance (yfinance)](https://github.com/ranaroussi/yfinance).

No API key required. No paid subscription required.

Tweaking each configurable variable (CapEx growth, earnings growth, discount rate, etc.) develops an insight into how the assumptions made in a DCF drive the end valuation — which is the real value of this tool.

The library also overlays actual historical stock prices on top of the DCF-implied values, immediately showing whether the market has historically priced a stock at a premium or discount to its intrinsic value.

> **Note:** DCF is a model, not a fact. The quality of the output is entirely determined by the quality of the assumptions fed in. Use this as a learning and exploration tool, not an investment recommendation.

---

### Next Steps

- [ ] Implement dynamic WACC (Weighted Average Cost of Capital) calculation
- [ ] Multivariable earnings growth rate inputs (instead of a single flat rate)
- [ ] EBITDA multiples for terminal value (as an alternative to Gordon Growth)
- [ ] Support for quarterly interval DCF sweeps

---

### Supported Tickers

Any company listed on **NSE** or **BSE** that Yahoo Finance covers:

| Exchange | Ticker Format | Examples |
|---|---|---|
| NSE | `SYMBOL.NS` | `DMART.NS`, `RELIANCE.NS`, `TCS.NS`, `HDFCBANK.NS` |
| BSE | `SYMBOL.BO` | `RELIANCE.BO`, `500325.BO` |

---

### Dependencies

```
pip install yfinance matplotlib seaborn
```

No API key or account is needed. yfinance pulls data directly from Yahoo Finance.

---

### Setup

```powershell
# Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install yfinance matplotlib seaborn
```

---

### Basic Usage

All parameters are passed as command-line arguments. Run `python main.py --help` to see all options.

```
python main.py \
    --t     TICKER              # NSE/BSE ticker symbol
    --y     YEARS               # historical years to compute DCF for
    --p     PERIOD              # years to forecast FCF into the future
    --i     INTERVAL            # 'annual' (default) or 'quarter'
    --d     DISCOUNT_RATE       # WACC / discount rate
    --eg    EARNINGS_GROWTH     # YoY EBIT growth assumption
    --cg    CAPEX_GROWTH        # YoY CapEx growth assumption
    --pg    PERPETUAL_GROWTH    # terminal / perpetual growth rate
    --s     STEP_INCREASE       # sensitivity sweep step size (0 = off)
    --steps STEPS               # number of steps in the sweep
    --v     VARIABLE            # variable to sweep: eg | cg | pg | discount_rate
```

| Argument | Description |
|---|---|
| `--t` | NSE/BSE ticker of the company (e.g. `DMART.NS`) |
| `--y` | Number of historical years to run DCF for |
| `--p` | Number of years to explicitly forecast FCF (default: 5) |
| `--i` | Statement interval: `annual` or `quarter` |
| `--d` | Discount rate / WACC (e.g. `0.10` for 10%) |
| `--eg` | Earnings (EBIT) growth rate YoY (e.g. `0.12` for 12%) |
| `--cg` | CapEx growth rate YoY |
| `--pg` | Perpetual / terminal growth rate (e.g. `0.06` for 6%) |
| `--s` | Step size for sensitivity sweep |
| `--steps` | Number of steps in the sensitivity sweep |
| `--v` | Variable to sweep: `eg`, `cg`, `pg`, or `discount_rate` |

---

### Example — DMart (Avenue Supermarts)

Run a 3-year historical DCF for DMart, sweeping earnings growth in 2 steps of +10%:

```powershell
python main.py --t DMART.NS --y 3 --eg .12 --steps 2 --s 0.1 --v eg
```

Terminal output (values in INR ₹):

```
Forecasting flows for 5 years out, starting at 2026-03-31.
         DFCF   |    EBIT   |    D&A    |    CWC     |   CAP_EX   |
2027   1.01E+10 |  4.78E+10 |  1.17E+10 |  7.60E+09 |  -4.30E+10 |
2028   1.43E+10 |  6.04E+10 |  1.48E+10 |  5.32E+09 |  -4.69E+10 |
2029   2.45E+10 |  8.44E+10 |  2.07E+10 |  3.72E+09 |  -5.32E+10 |
2030   4.46E+10 |  1.29E+11 |  3.17E+10 |  2.61E+09 |  -6.28E+10 |
2031   8.27E+10 |  2.14E+11 |  5.25E+10 |  1.82E+09 |  -7.69E+10 |

Enterprise Value for DMART.NS: ₹1.41E+12.
Equity Value for DMART.NS:     ₹1.40E+12.
Per share value for DMART.NS:  ₹2.14E+03.
```

The chart saved to `imgs/DMART.NS_eg.png` compares DCF-implied per-share value across earnings growth scenarios against DMart's actual traded price over the same period.

![DMART DCF chart](imgs/DMART.NS_eg.png)

---

### Output Files

Charts are automatically saved to the `imgs/` folder:

```
imgs/{ticker}_{variable}.png
```

For example: `imgs/DMART.NS_eg.png`, `imgs/RELIANCE.NS_cg.png`

---

### Interpreting Results

| Observation | Meaning |
|---|---|
| DCF-implied price **below** market price | Stock trading at a **premium** to intrinsic value — market prices in higher growth or a quality moat |
| DCF-implied price **above** market price | Stock trading at a **discount** to intrinsic value — potential undervaluation |
| DCF-implied price rises with `--eg` | Valuation is sensitive to earnings growth assumption — validate carefully |

DMart, for example, typically trades at 2–3× its DCF-implied value at conservative growth rates (~12%), because the market prices in significantly higher long-run growth (~25–30%).

---

### References

[1] http://people.stern.nyu.edu/adamodar/pdfiles/eqnotes/dcfcf.pdf
[2] http://people.stern.nyu.edu/adamodar/pdfiles/basics.pdf
[3] https://www.oreilly.com/library/view/valuation-techniques-discounted/9781118417607/xhtml/sec30.html
[4] https://www.cchwebsites.com/content/calculators/BusinessValuation.html
