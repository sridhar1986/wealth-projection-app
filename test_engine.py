import unittest
import pandas as pd
from engine import AccountConfig, ProjectionParameters, ProjectionEngine


class TestProjectionEngine(unittest.TestCase):
    def test_pure_compounding_no_contributions(self):
        acc = AccountConfig(
            bucket="Investment Accounts",
            account_name="Brokerage",
            current_balance=100000.0,
            annual_contribution=0.0,
            expected_return_pct=10.0,
            drag_pct=0.0,
        )
        params = ProjectionParameters(
            years=3,
            inflation_rate_pct=0.0,
            contribution_growth_rate_pct=0.0,
        )
        df = ProjectionEngine.run_projection([acc], params)
        
        # Check Year 0
        self.assertEqual(df.loc[0, "total_nominal_balance"], 100000.0)
        # Year 1: 100,000 * 1.10 = 110,000
        self.assertAlmostEqual(df.loc[1, "total_nominal_balance"], 110000.0)
        # Year 2: 110,000 * 1.10 = 121,000
        self.assertAlmostEqual(df.loc[2, "total_nominal_balance"], 121000.0)
        # Year 3: 121,000 * 1.10 = 133,100
        self.assertAlmostEqual(df.loc[3, "total_nominal_balance"], 133100.0)

    def test_inflation_discounting(self):
        acc = AccountConfig(
            bucket="Investment Accounts",
            account_name="Brokerage",
            current_balance=100000.0,
            annual_contribution=0.0,
            expected_return_pct=0.0,
            drag_pct=0.0,
        )
        params = ProjectionParameters(
            years=2,
            inflation_rate_pct=5.0,
        )
        df = ProjectionEngine.run_projection([acc], params)
        # Nominal balance remains 100,000
        self.assertEqual(df.loc[2, "total_nominal_balance"], 100000.0)
        # Real balance: 100000 / (1.05^2) = 100000 / 1.1025 = 90702.9478
        expected_real = 100000.0 / (1.05 ** 2)
        self.assertAlmostEqual(df.loc[2, "total_real_balance"], expected_real, places=2)

    def test_csv_load_and_run(self):
        csv_path = "sample_accounts.csv"
        accounts = ProjectionEngine.load_accounts_from_csv(csv_path)
        self.assertEqual(len(accounts), 4)

        total_start = sum(a.current_balance for a in accounts)
        self.assertEqual(total_start, 3120000.0)

        params = ProjectionParameters(years=10)
        df = ProjectionEngine.run_projection(accounts, params)
        self.assertEqual(len(df), 11)  # Year 0 to 10
        self.assertEqual(df.loc[0, "total_nominal_balance"], 3120000.0)
        self.assertGreater(df.loc[10, "total_nominal_balance"], 3120000.0)

    def test_tax_adjusted_balances(self):
        accounts = [
            AccountConfig(bucket="Pre-Tax Retirement", account_name="401k", current_balance=1000000.0),
            AccountConfig(bucket="Post-Tax Retirement", account_name="Roth", current_balance=100000.0),
        ]
        ending_balances = {
            "Pre-Tax Retirement": 1000000.0,
            "Post-Tax Retirement": 100000.0,
        }
        params = ProjectionParameters(pre_tax_retirement_tax_rate_pct=20.0)
        net = ProjectionEngine.calculate_tax_adjusted_balances(accounts, ending_balances, params)
        self.assertAlmostEqual(net["Pre-Tax Retirement"], 800000.0)
        self.assertAlmostEqual(net["Post-Tax Retirement"], 100000.0)

    def test_cash_burn_phases_and_waterfall(self):
        from engine import SpendingPhase
        acc_inv = AccountConfig(bucket="Investment Accounts", account_name="Brokerage", current_balance=100000.0, expected_return_pct=0.0)
        acc_529 = AccountConfig(bucket="529 Tax-Advantaged", account_name="529", current_balance=20000.0, expected_return_pct=0.0)
        
        # Phase 1: Year 1-2 with 10k 529 draw and 20k total burn (10k from 529, 10k from Investment)
        # Phase 2: Year 3 with 30k total burn (from Investment)
        phases = [
            SpendingPhase(name="School Phase", start_year=1, end_year=2, annual_burn=20000.0, education_from_529=10000.0),
            SpendingPhase(name="Post-School Phase", start_year=3, end_year=3, annual_burn=30000.0, education_from_529=0.0),
        ]
        params = ProjectionParameters(
            years=3,
            inflation_rate_pct=0.0,
            enable_cash_burn=True,
            inflate_spending=False,
            spending_phases=phases,
        )
        df = ProjectionEngine.run_projection([acc_inv, acc_529], params)
        
        # Year 1: 529 has 20k - 10k = 10k. Investment has 100k - 10k = 90k. Total = 100k
        self.assertAlmostEqual(df.loc[1, "529 Tax-Advantaged_nominal"], 10000.0)
        self.assertAlmostEqual(df.loc[1, "Investment Accounts_nominal"], 90000.0)
        self.assertAlmostEqual(df.loc[1, "total_nominal_balance"], 100000.0)
        self.assertAlmostEqual(df.loc[1, "annual_burn"], 20000.0)
        
        # Year 2: 529 has 10k - 10k = 0k. Investment has 90k - 10k = 80k. Total = 80k
        self.assertAlmostEqual(df.loc[2, "529 Tax-Advantaged_nominal"], 0.0)
        self.assertAlmostEqual(df.loc[2, "Investment Accounts_nominal"], 80000.0)
        self.assertAlmostEqual(df.loc[2, "total_nominal_balance"], 80000.0)
        
        # Year 3: 529 has 0k. Investment has 80k - 30k = 50k. Total = 50k
        self.assertAlmostEqual(df.loc[3, "529 Tax-Advantaged_nominal"], 0.0)
        self.assertAlmostEqual(df.loc[3, "Investment Accounts_nominal"], 50000.0)
        self.assertAlmostEqual(df.loc[3, "total_nominal_balance"], 50000.0)
        self.assertAlmostEqual(df.loc[3, "cumulative_burn"], 70000.0)


if __name__ == "__main__":
    unittest.main()

