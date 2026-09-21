"""
Portfolio Projection Engine
Models multi-bucket wealth accumulation across taxable, pre-tax, Roth, and 529 accounts.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Union
import io
import pandas as pd


STANDARD_BUCKETS = [
    "Investment Accounts",
    "Pre-Tax Retirement",
    "Post-Tax Retirement",
    "529 Tax-Advantaged",
]


@dataclass
class AccountConfig:
    bucket: str
    account_name: str
    current_balance: float
    annual_contribution: float = 0.0
    expected_return_pct: float = 7.0
    drag_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SpendingPhase:
    name: str
    start_year: int
    end_year: int
    annual_burn: float
    education_from_529: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectionParameters:
    years: int = 20
    inflation_rate_pct: float = 2.5
    contribution_growth_rate_pct: float = 2.0
    pre_tax_retirement_tax_rate_pct: float = 22.0  # Estimated tax rate on pre-tax withdrawals
    capital_gains_tax_rate_pct: float = 15.0      # Long-term capital gains tax rate on taxable gains
    enable_cash_burn: bool = False
    inflate_spending: bool = True                 # Whether cash burn inflates over time
    spending_phases: List[SpendingPhase] = None

    def __post_init__(self):
        if self.spending_phases is None:
            self.spending_phases = []



class ProjectionEngine:
    """Calculates compound returns, contributions, real purchasing power, and tax-adjusted wealth."""

    @staticmethod
    def load_accounts_from_csv(file_or_buffer: Union[str, io.StringIO, io.BytesIO]) -> List[AccountConfig]:
        """Loads and validates accounts from a CSV file or buffer."""
        df = pd.read_csv(file_or_buffer)
        return ProjectionEngine.dataframe_to_accounts(df)

    @staticmethod
    def dataframe_to_accounts(df: pd.DataFrame) -> List[AccountConfig]:
        """Converts a pandas DataFrame into a list of AccountConfig instances."""
        required_cols = ["bucket", "current_balance"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column in accounts data: {col}")

        accounts = []
        for _, row in df.iterrows():
            accounts.append(
                AccountConfig(
                    bucket=str(row["bucket"]).strip(),
                    account_name=str(row.get("account_name", row["bucket"])).strip(),
                    current_balance=float(row["current_balance"]),
                    annual_contribution=float(row.get("annual_contribution", 0.0)),
                    expected_return_pct=float(row.get("expected_return_pct", 7.0)),
                    drag_pct=float(row.get("drag_pct", 0.0)),
                )
            )
        return accounts

    @staticmethod
    def accounts_to_dataframe(accounts: List[AccountConfig]) -> pd.DataFrame:
        """Converts accounts list to a pandas DataFrame."""
        return pd.DataFrame([acc.to_dict() for acc in accounts])

    @staticmethod
    def run_projection(
        accounts: List[AccountConfig],
        params: ProjectionParameters,
    ) -> pd.DataFrame:
        """
        Executes annual projection across all accounts.
        Returns a DataFrame containing year-by-year projections per bucket and aggregate totals.
        """
        records = []

        # Track per-account state
        account_states = []
        for acc in accounts:
            account_states.append({
                "config": acc,
                "balance": acc.current_balance,
                "cost_basis": acc.current_balance,
                "total_contributions": 0.0,
                "total_growth": 0.0,
            })

        # Year 0 initial state
        initial_total_balance = sum(s["balance"] for s in account_states)
        initial_record = {
            "year": 0,
            "total_nominal_balance": initial_total_balance,
            "total_real_balance": initial_total_balance,
            "total_contributions": 0.0,
            "total_growth": 0.0,
            "annual_total_contribution": 0.0,
            "annual_total_growth": 0.0,
            "annual_burn": 0.0,
            "cumulative_burn": 0.0,
            "net_cash_flow": 0.0,
        }

        # Per bucket columns for Year 0
        for s in account_states:
            b_name = s["config"].bucket
            initial_record[f"{b_name}_nominal"] = s["balance"]
            initial_record[f"{b_name}_real"] = s["balance"]
            initial_record[f"{b_name}_contributions"] = 0.0
            initial_record[f"{b_name}_growth"] = 0.0

        records.append(initial_record)

        g = params.contribution_growth_rate_pct / 100.0
        inf = params.inflation_rate_pct / 100.0
        cumulative_burn = 0.0

        for year in range(1, params.years + 1):
            deflator = (1.0 + inf) ** year
            contribution_factor = (1.0 + g) ** (year - 1)

            annual_contributions_this_year = 0.0
            annual_growth_this_year = 0.0

            year_record = {
                "year": year,
            }

            # Step 1: Growth and Contributions
            for s in account_states:
                cfg = s["config"]
                b_name = cfg.bucket

                curr_contrib = cfg.annual_contribution * contribution_factor
                net_return_rate = (cfg.expected_return_pct - cfg.drag_pct) / 100.0
                curr_growth = s["balance"] * net_return_rate

                s["balance"] = max(0.0, s["balance"] + curr_growth + curr_contrib)
                s["cost_basis"] += curr_contrib
                s["total_contributions"] += curr_contrib
                s["total_growth"] = s["balance"] - cfg.current_balance - s["total_contributions"]

                annual_contributions_this_year += curr_contrib
                annual_growth_this_year += curr_growth

            # Step 2: Calculate Cash Burn / Spending for this year
            actual_burn = 0.0
            actual_529_draw = 0.0
            if params.enable_cash_burn and params.spending_phases:
                active_phases = [
                    p for p in params.spending_phases
                    if p.start_year <= year <= p.end_year
                ]
                base_burn = sum(p.annual_burn for p in active_phases)
                base_529 = sum(p.education_from_529 for p in active_phases)

                spend_multiplier = (1.0 + inf) ** (year - 1) if params.inflate_spending else 1.0
                actual_burn = base_burn * spend_multiplier
                actual_529_draw = base_529 * spend_multiplier

            # Step 3: Execute Withdrawals (Waterfall)
            remaining_burn = actual_burn

            # 3a. Draw education portion from 529 first if specified
            if actual_529_draw > 0:
                for s in account_states:
                    if s["config"].bucket == "529 Tax-Advantaged" and s["balance"] > 0:
                        draw = min(s["balance"], actual_529_draw)
                        s["balance"] -= draw
                        remaining_burn = max(0.0, remaining_burn - draw)

            # 3b. Waterfall for remaining burn: Taxable -> Pre-Tax -> Roth -> remaining 529
            bucket_priority = ["Investment Accounts", "Pre-Tax Retirement", "Post-Tax Retirement", "529 Tax-Advantaged"]
            for target_bucket in bucket_priority:
                if remaining_burn <= 0:
                    break
                for s in account_states:
                    if s["config"].bucket == target_bucket and s["balance"] > 0:
                        draw = min(s["balance"], remaining_burn)
                        s["balance"] -= draw
                        remaining_burn -= draw

            total_withdrawn = actual_burn - remaining_burn  # amount successfully drawn
            cumulative_burn += total_withdrawn
            net_cash_flow = annual_contributions_this_year - total_withdrawn

            # Record per-bucket final balances
            for s in account_states:
                b_name = s["config"].bucket
                year_record[f"{b_name}_nominal"] = s["balance"]
                year_record[f"{b_name}_real"] = s["balance"] / deflator
                year_record[f"{b_name}_contributions"] = s["total_contributions"]
                year_record[f"{b_name}_growth"] = s["total_growth"]

            total_nominal = sum(s["balance"] for s in account_states)
            total_real = total_nominal / deflator
            total_contributions = sum(s["total_contributions"] for s in account_states)
            total_growth = sum(s["total_growth"] for s in account_states)

            year_record["total_nominal_balance"] = total_nominal
            year_record["total_real_balance"] = total_real
            year_record["total_contributions"] = total_contributions
            year_record["total_growth"] = total_growth
            year_record["annual_total_contribution"] = annual_contributions_this_year
            year_record["annual_total_growth"] = annual_growth_this_year
            year_record["annual_burn"] = total_withdrawn
            year_record["cumulative_burn"] = cumulative_burn
            year_record["net_cash_flow"] = net_cash_flow

            records.append(year_record)

        df_result = pd.DataFrame(records)
        return df_result

    @staticmethod
    def calculate_tax_adjusted_balances(
        accounts: List[AccountConfig],
        ending_nominal_balances: Dict[str, float],
        params: ProjectionParameters,
    ) -> Dict[str, float]:
        """
        Calculates estimated net usable (after-tax) wealth at the end of projection.
        - Pre-Tax Retirement: discounted by pre_tax_retirement_tax_rate_pct
        - Roth & 529: 100% tax-free
        - Investment: capital gains tax applied only on accrued gains over cost basis
        """
        net_balances = {}
        for acc in accounts:
            nominal = ending_nominal_balances.get(acc.bucket, acc.current_balance)
            if acc.bucket == "Pre-Tax Retirement":
                tax_rate = params.pre_tax_retirement_tax_rate_pct / 100.0
                net_balances[acc.bucket] = nominal * (1.0 - tax_rate)
            elif acc.bucket == "Investment Accounts":
                cap_gains_rate = params.capital_gains_tax_rate_pct / 100.0
                estimated_basis = acc.current_balance  # simplified basis
                gains = max(0.0, nominal - estimated_basis)
                net_balances[acc.bucket] = nominal - (gains * cap_gains_rate)
            else:
                # Roth and 529 qualified
                net_balances[acc.bucket] = nominal

        return net_balances
