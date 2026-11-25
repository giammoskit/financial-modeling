# Trend Filtered Multi Asset Portfolio

Streamlit app for the group assignment of 2270 Financial Modeling at Nova SBE. The app lets a user change the main assumptions of the strategy and see the resulting performance and benchmark comparison.

**Live app** *add the Streamlit URL after deployment*

## The strategy

The portfolio targets cautious retail investors who save for retirement over five to ten years. It holds four ETFs at 25% each.

| Ticker | Asset class |
|---|---|
| SPY | US equities (S&P 500) |
| EFA | Developed equities outside the US (MSCI EAFE) |
| IEF | US Treasury bonds with 7 to 10 years to maturity |
| GLD | Gold |

At the end of every month, each ETF is compared with its 10 month simple moving average. An ETF above its average keeps its 25% for the next month. An ETF below it moves to 3 month US Treasury bills for the next month. The portfolio is rebalanced monthly. Results are compared with a 60/40 portfolio (SPY and IEF), the same four ETFs without the filter, and the S&P 500.

## What the user can change

| Control | Effect |
|---|---|
| Moving average window | From 2 to 12 months (prospectus value 10) |
| Trading cost | From 0 to 100 basis points per trade (prospectus value 10) |
| Trend filter | On or off. Off gives the equal weight portfolio without the rule |
| Sample period | Any range of years between 2006 and 2025 |
| Benchmark | 60/40, equal weight or S&P 500, used for alpha, beta, tracking error and information ratio |

The button "Reset to prospectus settings" restores the values used in the prospectus. With these values the app shows exactly the numbers of Table 1 in the notebook.

## Files

| File | Content |
|---|---|
| `app.py` | Streamlit interface and charts |
| `strategy.py` | Data download, allocation rule, backtest engine and performance measures. Identical to the engine cells of the Colab notebook |
| `requirements.txt` | Python packages needed by the app |
| `.streamlit/config.toml` | Light theme and colours |
| `data/` | Optional backup of the Yahoo Finance prices (see below) |

## Run the app locally

Python 3.10 or newer is required.

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501. The first load downloads the prices from Yahoo Finance and takes a few seconds.

## Deploy on Streamlit Community Cloud

1. Create a public GitHub repository and upload every file of this folder, including the hidden `.streamlit` folder.
2. Go to https://share.streamlit.io and sign in with the same GitHub account.
3. Click Create app in the upper right corner and choose the option for an existing app. Fill in the repository, the branch `main` and the main file path `app.py`.
4. Open Advanced settings and choose Python 3.12. The Python version cannot be changed later without deleting and redeploying the app.
5. Press Deploy. The first build takes a few minutes.
6. Put the app URL in this README, in the header table and the `APP_URL` variable of the notebook, and in the prospectus. Put the repository URL in `REPO_URL` at the top of `app.py` and in the notebook.

An app that has not been used for a while can go to sleep. A visitor then sees a button to wake it up, which takes about a minute. Open the app shortly before the deadline to check that it runs.

## Data

All prices come from the Yahoo Finance API through the yfinance package. Closing prices are adjusted for splits and dividends, so returns include reinvested dividends. Daily prices are converted to month end prices. The risk free rate is the 13 week Treasury bill yield (ticker ^IRX) at the previous month end, divided by 12.

The app caches the download for 24 hours. If Yahoo Finance does not respond and the file `data/prices_snapshot.csv` exists, the app uses that saved copy of the same Yahoo Finance prices and shows a warning. To create the file, set `SAVE_SNAPSHOT = True` in the last code cell of the notebook, run it in Colab, download `data/prices_snapshot.csv` from the Files panel and upload it to the `data` folder of this repository. The notebook itself always downloads the data from the API.

## Disclaimer

Educational project. Past performance does not predict future returns. Nothing in this repository is investment advice.
