import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io

from engine import AccountConfig, ProjectionParameters, ProjectionEngine, STANDARD_BUCKETS, SpendingPhase

import hmac

st.set_page_config(
    page_title="4-Bucket Wealth & Retirement Projector",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

def check_password() -> bool:
    """Returns True if the user entered the correct password."""
    secret_password = st.secrets.get("password", None)
    if not secret_password:
        return True

    def password_entered():
        if hmac.compare_digest(st.session_state["password_input"], str(secret_password)):
            st.session_state["password_correct"] = True
            if "password_input" in st.session_state:
                del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.subheader("🔒 Wealth Planner Login")
        st.caption("Enter your password to unlock the portfolio projections.")
        st.text_input(
            "Password",
            type="password",
            key="password_input",
            on_change=password_entered,
            placeholder="Enter password and press Enter...",
        )
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("❌ Incorrect password. Please try again.")

    return False

if not check_password():
    st.stop()


# Custom Styling for polished dashboard look
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .stMetric {
        background-color: #f8fafc;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
    .bucket-card {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        background-color: #ffffff;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Default accounts setup pre-loaded with user's numbers
DEFAULT_ACCOUNTS = [
    AccountConfig(
        bucket="Investment Accounts",
        account_name="Taxable Brokerage",
        current_balance=200000.0,
        annual_contribution=6000.0,
        expected_return_pct=7.5,
        drag_pct=0.2,
    ),
    AccountConfig(
        bucket="Pre-Tax Retirement",
        account_name="Traditional 401(k) / IRA",
        current_balance=100000.0,
        annual_contribution=10000.0,
        expected_return_pct=7.0,
        drag_pct=0.1,
    ),
    AccountConfig(
        bucket="Post-Tax Retirement",
        account_name="Roth IRA / Roth 401(k)",
        current_balance=10000.0,
        annual_contribution=3500.0,
        expected_return_pct=8.0,
        drag_pct=0.05,
    ),
    AccountConfig(
        bucket="529 Tax-Advantaged",
        account_name="529 Education Savings",
        current_balance=2000.0,
        annual_contribution=1200.0,
        expected_return_pct=6.0,
        drag_pct=0.1,
    ),
]


COLOR_MAP = {
    "Investment Accounts": "#6366F1",      # Indigo
    "Pre-Tax Retirement": "#0284C7",       # Sky Blue
    "Post-Tax Retirement": "#10B981",      # Emerald Green
    "529 Tax-Advantaged": "#F59E0B",       # Amber
}

# Session state initialization
if "accounts" not in st.session_state:
    st.session_state.accounts = [AccountConfig(**a.to_dict()) for a in DEFAULT_ACCOUNTS]

# Sidebar - Global Parameters
st.sidebar.title("⚙️ Projection Controls")

years = st.sidebar.slider("Projection Horizon (Years)", min_value=1, max_value=40, value=20, step=1)
view_real = st.sidebar.toggle("Adjust for Inflation (Real Dollars)", value=False)
inflation_rate = st.sidebar.slider("Expected Annual Inflation (%)", min_value=0.0, max_value=8.0, value=2.5, step=0.1)
contribution_growth = st.sidebar.slider("Annual Contribution Growth (%)", min_value=0.0, max_value=8.0, value=2.0, step=0.5,
                                        help="Models annual increases to your contributions (e.g. salary raises).")

with st.sidebar.expander("Tax Rate Assumptions (for Net Wealth)", expanded=False):
    pre_tax_rate = st.slider("Pre-Tax Retirement Tax Rate (%)", 0.0, 45.0, 22.0, 1.0,
                             help="Estimated effective tax rate upon withdrawal in retirement.")
    cap_gains_rate = st.slider("Taxable Capital Gains Rate (%)", 0.0, 35.0, 15.0, 1.0,
                               help="Estimated capital gains tax rate on taxable investment gains.")

st.sidebar.markdown("---")
st.sidebar.subheader("📁 CSV Data Management")

# CSV Export
current_df = ProjectionEngine.accounts_to_dataframe(st.session_state.accounts)
csv_buffer = io.StringIO()
current_df.to_csv(csv_buffer, index=False)
st.sidebar.download_button(
    label="📥 Download Portfolio as CSV",
    data=csv_buffer.getvalue(),
    file_name="my_portfolio_buckets.csv",
    mime="text/csv",
    use_container_width=True,
)

# CSV Import
uploaded_file = st.sidebar.file_uploader("📤 Upload Custom CSV", type=["csv"])
if uploaded_file is not None:
    try:
        uploaded_accounts = ProjectionEngine.load_accounts_from_csv(uploaded_file)
        st.session_state.accounts = uploaded_accounts
        st.sidebar.success("Successfully imported accounts from CSV!")
    except Exception as e:
        st.sidebar.error(f"Error reading CSV: {e}")

if st.sidebar.button("🔄 Reset to Default Portfolio ($312K)", use_container_width=True):
    st.session_state.accounts = [AccountConfig(**a.to_dict()) for a in DEFAULT_ACCOUNTS]
    st.rerun()

if st.secrets.get("password", None) and st.session_state.get("password_correct", False):
    st.sidebar.markdown("---")
    if st.sidebar.button("🔒 Log Out", use_container_width=True):
        st.session_state["password_correct"] = False
        st.rerun()



# Main Page Header
st.title("📊 4-Bucket Wealth & Retirement Projection Model")
st.caption("Personalized long-term growth projection across Taxable, Pre-Tax, Roth, and 529 accounts.")

# Account Configuration Section
with st.expander("📝 Edit Account Balances, Returns & Contributions", expanded=True):
    st.write("Modify your starting balances, expected annual growth, and contributions for each bucket:")
    
    cols = st.columns(4)
    updated_accounts = []
    
    for idx, acc in enumerate(st.session_state.accounts):
        col = cols[idx % 4]
        with col:
            st.markdown(f"**{acc.bucket}**")
            account_name = st.text_input(f"Name #{idx+1}", value=acc.account_name, key=f"name_{idx}")
            balance = st.number_input(f"Current Balance ($)", value=float(acc.current_balance), step=5000.0, format="%.0f", key=f"bal_{idx}")
            contrib = st.number_input(f"Annual Contribution ($)", value=float(acc.annual_contribution), step=500.0, format="%.0f", key=f"contrib_{idx}")
            ret_pct = st.number_input(f"Expected Return (%)", value=float(acc.expected_return_pct), step=0.25, format="%.2f", key=f"ret_{idx}")
            drag_pct = st.number_input(f"Tax/Fee Drag (%)", value=float(acc.drag_pct), step=0.05, format="%.2f", key=f"drag_{idx}",
                                       help="Expense ratio or annual dividend drag.")
            
            updated_accounts.append(
                AccountConfig(
                    bucket=acc.bucket,
                    account_name=account_name,
                    current_balance=balance,
                    annual_contribution=contrib,
                    expected_return_pct=ret_pct,
                    drag_pct=drag_pct,
                )
            )

st.session_state.accounts = updated_accounts

# Cash Burn & Spending Phases Section
with st.expander("🔥 Cash Burn & Spending Phases (Optional)", expanded=True):
    st.write("Model life-stage spending (e.g., higher expenses during kids' school/college years, transitioning to lower post-school living expenses).")

    enable_burn = st.checkbox("Enable Cash Burn / Spending Drawdowns", value=False, help="When enabled, annual living expenses and education draws are deducted from your portfolio.")
    
    spending_phases = []
    inflate_spending = True
    if enable_burn:
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            inflate_spending = st.checkbox("Adjust expenses for annual inflation (%)", value=True, help="Increases annual spending with your expected inflation rate.")
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.markdown("#### Phase 1: High Burn (Kids School / Family)")
            default_p1_end = min(15, years)
            p1_end = st.slider("Phase 1 Duration (Years)", min_value=1, max_value=max(1, years), value=default_p1_end, key="p1_dur",
                               help="How many years Phase 1 lasts (e.g. until kids finish school/college).")
            p1_burn = st.number_input("Phase 1 Total Annual Spending ($)", min_value=0.0, value=30000.0, step=2500.0, format="%.0f", key="p1_burn")
            p1_529 = st.number_input("Portion Drawn from 529 for Education ($)", min_value=0.0, value=2000.0, step=500.0, format="%.0f", key="p1_529",
                                     help="Amount drawn specifically from the 529 bucket for tuition.")
            spending_phases.append(SpendingPhase(name="Phase 1 (School/Family)", start_year=1, end_year=p1_end, annual_burn=p1_burn, education_from_529=p1_529))

        with col_p2:
            st.markdown("#### Phase 2: Post-School / Retirement")
            p2_start = p1_end + 1
            if p2_start <= years:
                st.info(f"Phase 2 covers Years **{p2_start} to {years}**.")
                p2_burn = st.number_input("Phase 2 Annual Spending ($)", min_value=0.0, value=20000.0, step=2500.0, format="%.0f", key="p2_burn")
                spending_phases.append(SpendingPhase(name="Phase 2 (Post-School)", start_year=p2_start, end_year=years, annual_burn=p2_burn, education_from_529=0.0))
            else:
                st.info("Phase 1 spans the entire projection horizon.")


# Run Projections
params = ProjectionParameters(
    years=years,
    inflation_rate_pct=inflation_rate,
    contribution_growth_rate_pct=contribution_growth,
    pre_tax_retirement_tax_rate_pct=pre_tax_rate,
    capital_gains_tax_rate_pct=cap_gains_rate,
    enable_cash_burn=enable_burn,
    inflate_spending=inflate_spending,
    spending_phases=spending_phases,
)

df_proj = ProjectionEngine.run_projection(st.session_state.accounts, params)

# Extract final metrics
end_year_row = df_proj.iloc[-1]
initial_row = df_proj.iloc[0]

total_start = initial_row["total_nominal_balance"]
total_end_nominal = end_year_row["total_nominal_balance"]
total_end_real = end_year_row["total_real_balance"]
total_contributions = end_year_row["total_contributions"]
total_growth = end_year_row["total_growth"]
total_burned = end_year_row["cumulative_burn"]

display_total_end = total_end_real if view_real else total_end_nominal

# Depletion alert if applicable
depleted_years = df_proj[df_proj["total_nominal_balance"] <= 0]
if not depleted_years.empty:
    first_depleted_year = int(depleted_years.iloc[0]["year"])
    st.error(f"⚠️ **Warning**: Under this spending rate, your portfolio is projected to be fully depleted in **Year {first_depleted_year}**.")

# Tax-adjusted calculation
ending_nominal_by_bucket = {acc.bucket: end_year_row[f"{acc.bucket}_nominal"] for acc in st.session_state.accounts}
net_usable_balances = ProjectionEngine.calculate_tax_adjusted_balances(st.session_state.accounts, ending_nominal_by_bucket, params)
total_net_usable_nominal = sum(net_usable_balances.values())
deflator_end = (1.0 + inflation_rate / 100.0) ** years
total_net_usable_display = (total_net_usable_nominal / deflator_end) if view_real else total_net_usable_nominal

# Top KPI Metrics Row
st.markdown("---")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

value_prefix = "Real" if view_real else "Nominal"

with kpi1:
    gain_loss = display_total_end - total_start
    st.metric(
        label=f"Projected Wealth (Year {years}) [{value_prefix}]",
        value=f"${display_total_end:,.0f}",
        delta=f"{'+' if gain_loss >= 0 else ''}${gain_loss:,.0f} Net Change",
    )

with kpi2:
    st.metric(
        label=f"Total Contributions Added",
        value=f"${total_contributions:,.0f}",
        delta=f"Over {years} Years",
    )

with kpi3:
    if enable_burn:
        st.metric(
            label=f"Total Lifetime Cash Burned",
            value=f"${total_burned:,.0f}",
            delta=f"Funded via Portfolio",
            delta_color="inverse",
        )
    else:
        st.metric(
            label=f"Total Compound Growth",
            value=f"${total_growth:,.0f}",
            delta=f"{((total_growth / total_start) * 100.0):.1f}% Portfolio Gain",
        )

with kpi4:
    tax_discount = max(0.0, display_total_end - total_net_usable_display)
    st.metric(
        label=f"Est. Net Usable Wealth (After-Tax)",
        value=f"${total_net_usable_display:,.0f}",
        delta=f"-${tax_discount:,.0f} Est. Taxes",
        delta_color="off",
    )


# Visualization Section
tab_growth, tab_compare, tab_allocation, tab_table = st.tabs([
    "📈 Growth by Bucket (Stacked)",
    "⚖️ Nominal vs. Real Purchasing Power",
    "🍩 Asset Allocation Comparison",
    "📋 Detailed Year-by-Year Schedule",
])

with tab_growth:
    st.subheader(f"Portfolio Growth Over {years} Years ({value_prefix} Dollars)")
    suffix = "_real" if view_real else "_nominal"
    
    fig_stacked = go.Figure()
    
    for acc in st.session_state.accounts:
        col_name = f"{acc.bucket}{suffix}"
        if col_name in df_proj.columns:
            fig_stacked.add_trace(
                go.Scatter(
                    x=df_proj["year"],
                    y=df_proj[col_name],
                    name=f"{acc.bucket} ({acc.account_name})",
                    mode="lines",
                    stackgroup="one",
                    line=dict(width=1.5, color=COLOR_MAP.get(acc.bucket, None)),
                    hovertemplate=f"<b>{acc.bucket}</b><br>Year %{{x}}: $%{{y:,.0f}}<extra></extra>",
                )
            )

    fig_stacked.update_layout(
        xaxis_title="Years from Today",
        yaxis_title=f"Balance (${value_prefix})",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=40, b=20),
        height=500,
    )
    st.plotly_chart(fig_stacked, use_container_width=True)

with tab_compare:
    st.subheader("The Inflation Impact: Future Dollars vs. Today's Purchasing Power")
    fig_compare = go.Figure()

    fig_compare.add_trace(
        go.Scatter(
            x=df_proj["year"],
            y=df_proj["total_nominal_balance"],
            name="Nominal Balance (Future Face Value)",
            line=dict(color="#0284C7", width=3),
            hovertemplate="Nominal: $%{y:,.0f}<extra></extra>",
        )
    )

    fig_compare.add_trace(
        go.Scatter(
            x=df_proj["year"],
            y=df_proj["total_real_balance"],
            name=f"Real Balance (Purchasing Power @ {inflation_rate}% Inflation)",
            line=dict(color="#10B981", width=3, dash="dash"),
            hovertemplate="Real: $%{y:,.0f}<extra></extra>",
        )
    )

    fig_compare.update_layout(
        xaxis_title="Years from Today",
        yaxis_title="Total Portfolio Value ($)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=40, b=20),
        height=450,
    )
    st.plotly_chart(fig_compare, use_container_width=True)

    if enable_burn:
        st.markdown("---")
        st.subheader("Annual Inflows (Contributions) vs. Outflows (Cash Burn)")
        fig_flows = go.Figure()
        fig_flows.add_trace(
            go.Bar(
                x=df_proj["year"].iloc[1:],
                y=df_proj["annual_total_contribution"].iloc[1:],
                name="Annual Contributions (Inflow)",
                marker_color="#10B981",
                hovertemplate="Inflow: $%{y:,.0f}<extra></extra>",
            )
        )
        fig_flows.add_trace(
            go.Bar(
                x=df_proj["year"].iloc[1:],
                y=df_proj["annual_burn"].iloc[1:],
                name="Annual Cash Burn (Outflow)",
                marker_color="#EF4444",
                hovertemplate="Outflow: $%{y:,.0f}<extra></extra>",
            )
        )
        fig_flows.update_layout(
            barmode="group",
            xaxis_title="Years from Today",
            yaxis_title="Annual Amount ($)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=40, b=20),
            height=350,
        )
        st.plotly_chart(fig_flows, use_container_width=True)

with tab_allocation:
    st.subheader("Asset Allocation Breakdown: Year 0 vs. Year End")
    col_pie1, col_pie2 = st.columns(2)

    labels = [acc.bucket for acc in st.session_state.accounts]
    colors = [COLOR_MAP.get(b, "#888888") for b in labels]
    
    values_start = [initial_row[f"{b}_nominal"] for b in labels]
    values_end = [end_year_row[f"{b}_nominal"] for b in labels]

    with col_pie1:
        st.markdown("#### Starting Allocation (Today)")
        fig_donut_start = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values_start,
                    hole=0.55,
                    marker=dict(colors=colors),
                    textinfo="label+percent",
                    hovertemplate="%{label}: $%{value:,.0f} (%{percent})<extra></extra>",
                )
            ]
        )
        fig_donut_start.update_layout(showlegend=False, height=380, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_donut_start, use_container_width=True)

    with col_pie2:
        st.markdown(f"#### Projected Allocation (Year {years})")
        fig_donut_end = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values_end,
                    hole=0.55,
                    marker=dict(colors=colors),
                    textinfo="label+percent",
                    hovertemplate="%{label}: $%{value:,.0f} (%{percent})<extra></extra>",
                )
            ]
        )
        fig_donut_end.update_layout(showlegend=False, height=380, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_donut_end, use_container_width=True)

with tab_table:
    st.subheader("Year-by-Year Growth Table")
    
    # Format DataFrame for clean reading
    display_df = df_proj.copy()
    display_cols = ["year", "total_nominal_balance", "total_real_balance"]
    if enable_burn:
        display_cols.extend(["annual_burn", "net_cash_flow", "cumulative_burn"])
    display_cols.extend(["total_contributions", "total_growth"])
    for acc in st.session_state.accounts:
        display_cols.append(f"{acc.bucket}_nominal")
    
    table_subset = display_df[display_cols].copy()
    
    # Formatting numbers as currency
    format_dict = {col: "${:,.0f}".format for col in display_cols if col != "year"}
    styled_table = table_subset.style.format(format_dict)
    
    st.dataframe(styled_table, use_container_width=True, height=400)
    
    # Download projection schedule
    proj_csv = table_subset.to_csv(index=False)
    st.download_button(
        label="📥 Download Full Projections Schedule (CSV)",
        data=proj_csv,
        file_name=f"wealth_projection_{years}_years.csv",
        mime="text/csv",
    )

