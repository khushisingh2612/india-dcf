"""
DCF (Discounted Cash Flow) modeling for Indian (NSE/BSE) companies.

Data is sourced from Yahoo Finance via yfinance — free, no API key needed.
All monetary values are in INR (Indian Rupees).

Ticker format:
    NSE stocks  →  e.g. DMART.NS, RELIANCE.NS, TCS.NS
    BSE stocks  →  e.g. RELIANCE.BO
"""

import traceback
from decimal import Decimal

from modeling.data import (
    get_income_statement,
    get_cashflow_statement,
    get_balance_statement,
    get_EV_statement,
)


def DCF(ticker, ev_statement, income_statement, balance_statement, cashflow_statement,
        discount_rate, forecast, earnings_growth_rate, cap_ex_growth_rate, perpetual_growth_rate):
    """
    Single-point DCF valuation for a given set of financial statements.

    args:
        ticker:               company ticker symbol (e.g. 'DMART.NS')
        ev_statement:         dict with addTotalDebt, minusCashAndCashEquivalents, numberOfShares
        income_statement:     list of dicts (most-recent first), at least 2 entries
        balance_statement:    list of dicts (most-recent first), at least 2 entries
        cashflow_statement:   list of dicts (most-recent first), at least 2 entries
        discount_rate:        WACC / discount rate (e.g. 0.10 for 10%)
        forecast:             number of years to forecast FCF
        earnings_growth_rate: assumed YoY growth in EBIT
        cap_ex_growth_rate:   assumed YoY growth in CapEx
        perpetual_growth_rate: terminal growth rate for perpetuity value

    returns:
        dict with keys: date, enterprise_value, equity_value, share_price
    """
    enterprise_val = enterprise_value(
        income_statement,
        cashflow_statement,
        balance_statement,
        forecast,
        discount_rate,
        earnings_growth_rate,
        cap_ex_growth_rate,
        perpetual_growth_rate,
    )

    equity_val, share_price = equity_value(enterprise_val, ev_statement)

    print(
        '\nEnterprise Value for {}: ₹{}.'.format(ticker, '%.2E' % Decimal(str(enterprise_val))),
        '\nEquity Value for {}:     ₹{}.'.format(ticker, '%.2E' % Decimal(str(equity_val))),
        '\nPer share value for {}:  ₹{}.\n'.format(ticker, '%.2E' % Decimal(str(share_price))),
    )

    return {
        'date':             income_statement[0]['date'],
        'enterprise_value': enterprise_val,
        'equity_value':     equity_val,
        'share_price':      share_price,
    }


def historical_DCF(ticker, years, forecast, discount_rate, earnings_growth_rate,
                   cap_ex_growth_rate, perpetual_growth_rate, interval='annual'):
    """
    Compute DCF valuations across multiple historical fiscal years.

    args:
        ticker:               NSE/BSE ticker symbol (e.g. 'DMART.NS')
        years:                number of historical years to compute DCF for
        forecast:             number of years to forecast FCF per valuation
        discount_rate:        WACC / discount rate
        earnings_growth_rate: YoY EBIT growth assumption
        cap_ex_growth_rate:   YoY CapEx growth assumption
        perpetual_growth_rate: terminal growth rate
        interval:             'annual' (default) or 'quarter'

    returns:
        dict of {'YYYY-MM-DD': dcf_result_dict, ...}
    """
    dcfs = {}

    income_statement           = get_income_statement(ticker, period=interval)
    balance_statement          = get_balance_statement(ticker, period=interval)
    cashflow_statement         = get_cashflow_statement(ticker, period=interval)
    enterprise_value_statement = get_EV_statement(ticker, period=interval)

    intervals = years * 4 if interval == 'quarter' else years

    for i in range(0, intervals):
        try:
            dcf = DCF(
                ticker,
                enterprise_value_statement[i],
                income_statement[i:i+2],         # pass year + 1 for change-in-WC calculation
                balance_statement[i:i+2],
                cashflow_statement[i:i+2],
                discount_rate,
                forecast,
                earnings_growth_rate,
                cap_ex_growth_rate,
                perpetual_growth_rate,
            )
        except (Exception, IndexError):
            print(traceback.format_exc())
            print(f'Interval {i} unavailable — no historical statement.')
        else:
            dcfs[dcf['date']] = dcf
        print('-' * 60)

    return dcfs


# ---------------------------------------------------------------------------
# Core financial calculations
# ---------------------------------------------------------------------------

def ulFCF(ebit, tax_rate, non_cash_charges, cwc, cap_ex):
    """
    Unlevered Free Cash Flow to Firm formula.

    args:
        ebit:             Earnings Before Interest and Taxes
        tax_rate:         effective tax rate (e.g. 0.25)
        non_cash_charges: Depreciation & Amortization
        cwc:              Change in Working Capital
        cap_ex:           Capital Expenditure (negative in yfinance data)

    returns:
        unlevered FCF (float)
    """
    return ebit * (1 - tax_rate) + non_cash_charges + cwc + cap_ex


def get_discount_rate():
    """
    Weighted Average Cost of Capital (WACC) placeholder.
    TODO: implement dynamic WACC calculation.

    returns:
        float — default 10%
    """
    return 0.1


def equity_value(enterprise_val, enterprise_value_statement):
    """
    Derive equity value from enterprise value by adjusting for debt and cash.

    Equity Value = Enterprise Value − Total Debt + Cash & Equivalents

    args:
        enterprise_val:           computed enterprise value (float)
        enterprise_value_statement: dict with addTotalDebt,
                                   minusCashAndCashEquivalents, numberOfShares

    returns:
        tuple: (equity_value: float, share_price: float)
    """
    equity_val  = enterprise_val - enterprise_value_statement['addTotalDebt']
    equity_val += enterprise_value_statement['minusCashAndCashEquivalents']
    share_price = equity_val / float(enterprise_value_statement['numberOfShares'])
    return equity_val, share_price


def enterprise_value(income_statement, cashflow_statement, balance_statement,
                     period, discount_rate, earnings_growth_rate,
                     cap_ex_growth_rate, perpetual_growth_rate):
    """
    Calculate enterprise value as:
        NPV of explicit-period FCFs  +  NPV of terminal value
    both discounted at WACC.

    args:
        income_statement:     list of dicts (most-recent first)
        cashflow_statement:   list of dicts (most-recent first)
        balance_statement:    list of dicts (most-recent first)
        period:               number of years to forecast
        discount_rate:        WACC
        earnings_growth_rate: YoY EBIT growth
        cap_ex_growth_rate:   YoY CapEx growth
        perpetual_growth_rate: terminal growth rate

    returns:
        enterprise value (float, in INR)
    """
    # -- Extract base-year values --
    if income_statement[0].get('ebit'):
        ebit = float(income_statement[0]['ebit'])
    else:
        ebit = float(input(
            f"EBIT missing for {income_statement[0]['date']}. Enter manually or 0 to skip: "
        ))

    tax_rate = (float(income_statement[0]['incomeTaxExpense']) /
                float(income_statement[0]['incomeBeforeTax']))

    non_cash_charges = float(cashflow_statement[0]['depreciationAndAmortization'])

    # Change in Working Capital = ΔCurrentAssets (Total − NonCurrent)
    cwc = (
        (float(balance_statement[0]['totalAssets']) - float(balance_statement[0]['totalNonCurrentAssets'])) -
        (float(balance_statement[1]['totalAssets']) - float(balance_statement[1]['totalNonCurrentAssets']))
    )

    cap_ex   = float(cashflow_statement[0]['capitalExpenditure'])
    discount = discount_rate

    flows = []

    print(
        'Forecasting flows for {} years out, starting at {}.'.format(
            period, income_statement[0]['date']
        ),
        '\n         DFCF   |    EBIT   |    D&A    |    CWC     |   CAP_EX   | '
    )

    for yr in range(1, period + 1):
        # Grow each driver by its respective growth rate
        ebit             = ebit             * (1 + (yr * earnings_growth_rate))
        non_cash_charges = non_cash_charges * (1 + (yr * earnings_growth_rate))
        cwc              = cwc              * 0.7       # gradual WC normalisation
        cap_ex           = cap_ex           * (1 + (yr * cap_ex_growth_rate))

        flow    = ulFCF(ebit, tax_rate, non_cash_charges, cwc, cap_ex)
        PV_flow = flow / ((1 + discount) ** yr)
        flows.append(PV_flow)

        print(
            str(int(income_statement[0]['date'][0:4]) + yr) + '  ',
            '%.2E' % Decimal(PV_flow)        + ' | ',
            '%.2E' % Decimal(ebit)           + ' | ',
            '%.2E' % Decimal(non_cash_charges) + ' | ',
            '%.2E' % Decimal(cwc)            + ' | ',
            '%.2E' % Decimal(cap_ex)         + ' | ',
        )

    NPV_FCF = sum(flows)

    # Terminal value (Gordon Growth Model)
    final_cashflow = flows[-1] * (1 + perpetual_growth_rate)
    TV     = final_cashflow / (discount - perpetual_growth_rate)
    NPV_TV = TV / (1 + discount) ** (1 + period)

    return NPV_TV + NPV_FCF
