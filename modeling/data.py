"""
Data layer for the India DCF model.

Uses Yahoo Finance (yfinance) to fetch financial statements and historical
prices for NSE/BSE-listed companies — completely free, no API key required.

Ticker format:
    NSE stocks  →  e.g. DMART.NS, RELIANCE.NS, TCS.NS
    BSE stocks  →  e.g. RELIANCE.BO
"""

import yfinance as yf
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _df_to_records(df):
    """
    Transpose a yfinance financial DataFrame (columns = dates, rows = items)
    into a list of dicts ordered most-recent first.

    args:
        df: pandas DataFrame from yfinance (income_stmt / cashflow / balance_sheet)

    returns:
        list of dicts, each with a 'date' key and one key per financial line item
    """
    records = []
    for col in df.columns:          # columns are already sorted newest → oldest
        row = {'date': str(col)[:10]}
        for idx in df.index:
            val = df.loc[idx, col]
            try:
                row[idx] = float(val) if val is not None else None
            except (TypeError, ValueError):
                row[idx] = None
        records.append(row)
    return records


# ---------------------------------------------------------------------------
# Financial statement fetchers
# ---------------------------------------------------------------------------

def get_income_statement(ticker, period='annual'):
    """
    Fetch income statement via yfinance for an NSE/BSE-listed company.

    args:
        ticker: NSE/BSE ticker symbol, e.g. 'DMART.NS'
        period: 'annual' (default) or 'quarter'

    returns:
        list of dicts with keys: date, ebit, incomeTaxExpense, incomeBeforeTax
    """
    t = yf.Ticker(ticker)
    df = t.income_stmt if period == 'annual' else t.quarterly_income_stmt
    if df is None or df.empty:
        raise ValueError(f"No income statement data found for {ticker}.")

    records = _df_to_records(df)
    normalised = []
    for r in records:
        normalised.append({
            'date':             r['date'],
            'ebit':             r.get('EBIT') or r.get('Operating Income'),
            'incomeTaxExpense': r.get('Tax Provision'),
            'incomeBeforeTax':  r.get('Pretax Income'),
        })
    return normalised


def get_cashflow_statement(ticker, period='annual'):
    """
    Fetch cash-flow statement via yfinance for an NSE/BSE-listed company.

    args:
        ticker: NSE/BSE ticker symbol, e.g. 'DMART.NS'
        period: 'annual' (default) or 'quarter'

    returns:
        list of dicts with keys: date, depreciationAndAmortization,
        capitalExpenditure, changeInWorkingCapital
    """
    t = yf.Ticker(ticker)
    df = t.cashflow if period == 'annual' else t.quarterly_cashflow
    if df is None or df.empty:
        raise ValueError(f"No cash flow data found for {ticker}.")

    records = _df_to_records(df)
    normalised = []
    for r in records:
        normalised.append({
            'date':                        r['date'],
            'depreciationAndAmortization': r.get('Depreciation And Amortization')
                                           or r.get('Reconciled Depreciation'),
            'capitalExpenditure':          r.get('Capital Expenditure'),
            'changeInWorkingCapital':      r.get('Change In Working Capital'),
        })
    return normalised


def get_balance_statement(ticker, period='annual'):
    """
    Fetch balance sheet via yfinance for an NSE/BSE-listed company.

    args:
        ticker: NSE/BSE ticker symbol, e.g. 'DMART.NS'
        period: 'annual' (default) or 'quarter'

    returns:
        list of dicts with keys: date, totalAssets, totalNonCurrentAssets,
        addTotalDebt, minusCashAndCashEquivalents
    """
    t = yf.Ticker(ticker)
    df = t.balance_sheet if period == 'annual' else t.quarterly_balance_sheet
    if df is None or df.empty:
        raise ValueError(f"No balance sheet data found for {ticker}.")

    records = _df_to_records(df)
    normalised = []
    for r in records:
        total_assets = r.get('Total Assets')
        non_current  = r.get('Total Non Current Assets')
        total_debt   = r.get('Total Debt') or r.get('Long Term Debt', 0) or 0
        cash         = (r.get('Cash And Cash Equivalents')
                        or r.get('Cash Cash Equivalents And Short Term Investments')
                        or 0)
        normalised.append({
            'date':                          r['date'],
            'totalAssets':                   total_assets,
            'totalNonCurrentAssets':         non_current,
            'addTotalDebt':                  total_debt,
            'minusCashAndCashEquivalents':   cash,
        })
    return normalised


def get_EV_statement(ticker, period='annual'):
    """
    Build an enterprise-value record list from yfinance for an NSE/BSE company.

    Each record mirrors the fields read by equity_value() in dcf.py:
        addTotalDebt, minusCashAndCashEquivalents, numberOfShares

    args:
        ticker: NSE/BSE ticker symbol, e.g. 'DMART.NS'
        period: 'annual' (default) or 'quarter'

    returns:
        list of dicts, one per historical year, indexed by dcf.py as [interval]
    """
    t = yf.Ticker(ticker)
    info = t.info

    shares     = info.get('sharesOutstanding') or info.get('impliedSharesOutstanding')
    total_debt = info.get('totalDebt', 0) or 0
    cash       = info.get('totalCash', 0) or 0

    df = t.balance_sheet if period == 'annual' else t.quarterly_balance_sheet
    if df is None or df.empty:
        raise ValueError(f"No balance sheet data found for {ticker} (needed for EV).")

    records = []
    for col in df.columns:
        bs        = df[col]
        debt_hist = float(bs.get('Total Debt', total_debt) or total_debt)
        cash_hist = float(
            bs.get('Cash And Cash Equivalents',
            bs.get('Cash Cash Equivalents And Short Term Investments', cash)) or cash
        )
        sh = float(shares) if shares else 1.0
        records.append({
            'date':                          str(col)[:10],
            'addTotalDebt':                  debt_hist,
            'minusCashAndCashEquivalents':   cash_hist,
            'numberOfShares':                sh,
        })
    return records


# ---------------------------------------------------------------------------
# Historical price fetcher
# ---------------------------------------------------------------------------

def get_historical_share_prices(ticker, dates):
    """
    Fetch historical closing prices for a list of fiscal year-end dates
    via yfinance.

    Looks back up to 7 days to ensure a market trading day is captured
    even if the date falls on a weekend or NSE holiday.

    args:
        ticker: NSE/BSE ticker symbol, e.g. 'DMART.NS'
        dates:  list of date strings in 'YYYY-MM-DD' format

    returns:
        dict of {'YYYY-MM-DD': close_price (float or None), ...}
    """
    prices = {}
    t = yf.Ticker(ticker)

    for date_end in dates:
        try:
            date_end_dt  = datetime.strptime(date_end[:10], '%Y-%m-%d')
            date_start   = (date_end_dt - timedelta(days=7)).strftime('%Y-%m-%d')
            date_end_str = (date_end_dt + timedelta(days=1)).strftime('%Y-%m-%d')  # yf end is exclusive
        except Exception as e:
            print(f"Error parsing '{date_end}' to date: {e}")
            prices[date_end] = None
            continue

        try:
            hist = t.history(start=date_start, end=date_end_str)
            prices[date_end] = float(hist['Close'].iloc[-1]) if not hist.empty else None
        except Exception as e:
            print(f"Error fetching price for {ticker} on {date_end}: {e}")
            prices[date_end] = None

    return prices


if __name__ == '__main__':
    """ Quick smoke-test — run this file directly to verify data fetching. """
    ticker = 'DMART.NS'
    print(f"Fetching income statement for {ticker}...")
    data = get_income_statement(ticker)
    for row in data:
        print(row)
