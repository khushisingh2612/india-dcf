"""
Visualization toolkit for the India DCF model.

Plots DCF-implied share prices against actual historical NSE/BSE prices
fetched via yfinance.
"""

import sys
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.append('..')
from modeling.data import get_historical_share_prices

sns.set()
sns.set_context('paper')


def visualize_bulk_historicals(dcfs, ticker, condition):
    """
    Plot historical DCF-implied share prices under different growth assumptions
    alongside the actual stock price over the same period.

    All values are in INR (₹).

    args:
        dcfs:      nested dict — {condition_label: {date: dcf_result_dict}}
        ticker:    NSE/BSE ticker symbol (e.g. 'DMART.NS')
        condition: dict of format {'variable_name': [label1, label2, ...]}
                   or {'Ticker': [ticker]} for single-ticker runs
    """
    dcf_share_prices = {}

    try:
        conditions = [str(c) for c in list(condition.values())[0]]
    except IndexError:
        conditions = [condition['Ticker']]

    for cond in conditions:
        dcf_share_prices[cond] = {
            year: dcfs[cond][year]['share_price']
            for year in dcfs[cond].keys()
        }

    # Plot each DCF scenario
    for cond in conditions:
        plt.plot(
            list(dcf_share_prices[cond].keys())[::-1],
            list(dcf_share_prices[cond].values())[::-1],
            label=cond,
        )

    # Overlay actual historical stock prices
    dates = list(dcf_share_prices[list(dcf_share_prices.keys())[0]].keys())[::-1]
    historical_stock_prices = get_historical_share_prices(ticker=ticker, dates=dates)

    plt.plot(
        list(historical_stock_prices.keys()),
        list(historical_stock_prices.values()),
        label=f'₹{ticker} actual price',
        linewidth=2,
        linestyle='--',
    )

    plt.xlabel('Fiscal Year End Date')
    plt.ylabel('Share Price (₹)')
    plt.legend(loc='upper right')
    plt.title(f'{ticker} — DCF Intrinsic Value vs. Market Price')
    plt.tight_layout()
    plt.savefig('imgs/{}_{}.png'.format(ticker, list(condition.keys())[0]))
    plt.show()
