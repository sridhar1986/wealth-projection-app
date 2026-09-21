# 4-Bucket Wealth & Retirement Projection Application

An interactive, multi-bucket financial planning dashboard built with Python, Streamlit, Pandas, and Plotly.

## Portfolio Buckets

The application models 4 distinct financial buckets with their specific tax, growth, and contribution profiles:

1. **Investment Accounts (Taxable Brokerage)**
   - Pre-loaded balance: **$2,000,000**
   - High liquidity, models annual dividend/tax drag and capital gains tax on liquidation.
2. **Pre-Tax Retirement (Traditional 401k / Traditional IRA)**
   - Pre-loaded balance: **$1,000,000**
   - Tax-deferred compounding, taxed as ordinary income upon retirement withdrawal.
3. **Post-Tax Retirement (Roth IRA / Roth 401k)**
   - Pre-loaded balance: **$100,000**
   - Tax-free compounding and 100% tax-free qualified withdrawals.
4. **529 Tax-Advantaged (Education Savings)**
   - Pre-loaded balance: **$20,000**
   - Tax-free compounding for qualified educational expenses.

**Total Starting Portfolio**: **$3,120,000**

---

## Quick Start

### 1. Launch the Application
Run the one-click startup script:
```bash
./run.sh
```
Or activate the virtual environment and run Streamlit directly:
```bash
source .venv/bin/activate
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`.

---

## Features

- **Interactive Sliders & Inputs**: Adjust starting balances, annual contributions, expected returns, and fee drags in real time.
- **Inflation Adjustment**: Instantly toggle between **Nominal Future Dollars** and **Real Inflation-Adjusted Purchasing Power**.
- **Net After-Tax Wealth View**: Estimates usable net worth after accounting for ordinary income taxes on Pre-Tax accounts and capital gains taxes on taxable investments.
- **Plotly Visualizations**:
  - Stacked area growth chart displaying bucket accumulation year by year.
  - Inflation impact line chart.
  - Side-by-side asset allocation donut charts (Today vs. Year $X$).
- **CSV Data Management**:
  - One-click export of current configurations to `my_portfolio_buckets.csv`.
  - Upload your own custom CSV files to quickly model different scenarios.
  - Full year-by-year amortization schedule CSV export.

---

## CSV Schema Reference

If you create your own CSV file, use this format:

```csv
bucket,account_name,current_balance,annual_contribution,expected_return_pct,drag_pct
Investment Accounts,Taxable Brokerage,2000000,20000,7.5,0.2
Pre-Tax Retirement,Traditional 401(k) / IRA,1000000,23000,7.0,0.1
Post-Tax Retirement,Roth IRA / Roth 401(k),100000,7000,8.0,0.05
529 Tax-Advantaged,College 529 Plan,20000,6000,6.0,0.1
```
# wealth-projector
