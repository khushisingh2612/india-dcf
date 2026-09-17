"""
India DCF — Discounted Cash Flow Analysis for NSE/BSE-listed companies.

Data is fetched from Yahoo Finance (yfinance) — free, no API key required.

Ticker format:
    NSE stocks  →  e.g. DMART.NS, RELIANCE.NS, TCS.NS, HDFCBANK.NS
    BSE stocks  →  e.g. RELIANCE.BO

Example usage:
    python main.py --t DMART.NS --y 3 --eg .12 --steps 2 --s 0.1 --v eg

future goals:
    -- Formalize sensitivity analysis.
    -- More robust revenue forecasts in FCF.
    -- EBITDA multiples terminal value calculation.
    -- Dynamic WACC calculation.
"""

import argparse

from modeling.dcf import historical_DCF
from visualization.plot import visualize_bulk_historicals
from visualization.printouts import prettyprint


def main(args):
    """
    Entry point. Runs historical DCF across one or more growth-rate scenarios
    for a given NSE/BSE ticker, then visualizes the results.
    """
    if args.s > 0:
        if args.v is not None:
            if args.v == 'eg' or args.v == 'earnings_growth_rate':
                cond, dcfs = run_setup(args, variable='eg')
            elif args.v == 'cg' or args.v == 'cap_ex_growth_rate':
                cond, dcfs = run_setup(args, variable='cg')
            elif args.v == 'pg' or args.v == 'perpetual_growth_rate':
                cond, dcfs = run_setup(args, variable='pg')
            elif args.v == 'discount_rate' or args.v == 'discount':
                cond, dcfs = run_setup(args, variable='d')
            else:
                raise ValueError(
                    'Invalid --v value. Choose from: eg, cg, pg, discount_rate'
                )
        else:
            raise ValueError(
                'If --s > 0, you must specify the variable via --v.'
            )
    else:
        cond = {'Ticker': [args.t]}
        dcfs = {
            args.t: historical_DCF(
                args.t, args.y, args.p, args.d,
                args.eg, args.cg, args.pg, args.i,
            )
        }

    if args.y > 1:
        visualize_bulk_historicals(dcfs, args.t, cond)
    else:
        prettyprint(dcfs, args.y)


def run_setup(args, variable):
    """
    Run historical_DCF for each step of the sensitivity sweep,
    incrementing `variable` by args.s at each step.

    returns:
        (cond dict, dcfs dict)
    """
    dcfs = {}
    cond = {args.v: []}

    for increment in range(1, int(args.steps) + 1):
        var  = vars(args)[variable] * (1 + (args.s * increment))
        step = '{}: {}'.format(args.v, str(var)[0:4])

        cond[args.v].append(step)
        vars(args)[variable] = var

        dcfs[step] = historical_DCF(
            args.t, args.y, args.p, args.d,
            args.eg, args.cg, args.pg, args.i,
        )

    return cond, dcfs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Discounted Cash Flow analysis for Indian NSE/BSE stocks.'
    )

    parser.add_argument('--t',  '--ticker',
                        help='NSE/BSE ticker (e.g. DMART.NS, RELIANCE.NS)',
                        type=str, default='DMART.NS')
    parser.add_argument('--y',  '--years',
                        help='Number of historical years to compute DCF for',
                        type=int, default=1)
    parser.add_argument('--p',  '--period',
                        help='Years to forecast FCF into the future',
                        type=int, default=5)
    parser.add_argument('--i',  '--interval',
                        help='Statement interval: "annual" (default) or "quarter"',
                        default='annual')
    parser.add_argument('--d',  '--discount_rate',
                        help='Discount rate / WACC (e.g. 0.10 for 10%%)',
                        type=float, default=0.10)
    parser.add_argument('--eg', '--earnings_growth_rate',
                        help='YoY EBIT growth assumption (e.g. 0.12 for 12%%)',
                        type=float, default=0.12)
    parser.add_argument('--cg', '--cap_ex_growth_rate',
                        help='YoY CapEx growth assumption',
                        type=float, default=0.045)
    parser.add_argument('--pg', '--perpetual_growth_rate',
                        help='Terminal / perpetual growth rate (e.g. 0.06 for 6%%)',
                        type=float, default=0.06)
    parser.add_argument('--s',  '--step_increase',
                        help='Step size for sensitivity sweep (0 = no sweep)',
                        type=float, default=0)
    parser.add_argument('--steps',
                        help='Number of steps in the sensitivity sweep',
                        type=int, default=5)
    parser.add_argument('--v',  '--variable',
                        help='Variable to sweep: eg | cg | pg | discount_rate',
                        default=None)

    args = parser.parse_args()
    main(args)
