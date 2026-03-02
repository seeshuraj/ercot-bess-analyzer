"""Revenue stacking calculator for ERCOT BESS."""
import pandas as pd
import numpy as np
from typing import Tuple, Dict


def calculate_revenue_stack(
    spp: pd.DataFrame,
    as_prices: pd.DataFrame,
    capacity_mw: float,
    duration_hrs: float,
    rte: float = 0.85,
    as_reserved_frac: float = 0.0,
    dispatch_method: str = "threshold"
) -> Tuple[pd.DataFrame, Dict]:
    """
    Calculate complete revenue stack for a BESS asset.
    
    Args:
        spp: Settlement Point Prices DataFrame
        as_prices: Ancillary Services prices DataFrame
        capacity_mw: Battery power capacity (MW)
        duration_hrs: Battery duration (hours)
        rte: Round-trip efficiency
        as_reserved_frac: Fraction of capacity reserved for AS
        dispatch_method: "threshold" or "advanced"
    
    Returns:
        Tuple of (daily_revenue_df, summary_metrics)
    """
    from src.dispatch_model import simulate_dispatch, simulate_dispatch_advanced, calc_as_revenue
    
    # Extract price series from SPP data
    if 'SPP' in spp.columns:
        prices = spp.set_index('Time')['SPP']
    elif 'Price' in spp.columns:
        prices = spp.set_index('Time')['Price']
    elif 'LMP' in spp.columns:
        prices = spp.set_index('Time')['LMP']
    else:
        # Try to find the price column
        price_cols = [c for c in spp.columns if 'price' in c.lower() or 'spp' in c.lower() or 'lmp' in c.lower()]
        if price_cols:
            prices = spp.set_index('Time')[price_cols[0]]
        else:
            # Use numeric columns
            numeric_cols = spp.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                prices = spp.set_index('Time')[numeric_cols[0]]
            else:
                raise ValueError(f"Cannot find price column in SPP data. Columns: {spp.columns.tolist()}")
    
    # Calculate energy arbitrage revenue
    if dispatch_method == "advanced":
        arbitrage_df = simulate_dispatch_advanced(prices, capacity_mw, duration_hrs, rte, as_reserved_frac)
    else:
        arbitrage_df = simulate_dispatch(prices, capacity_mw, duration_hrs, rte, as_reserved_frac)
    
    # Calculate AS revenue
    as_df = calc_as_revenue(as_prices, capacity_mw, as_reserved_frac)
    
    # Merge results
    if arbitrage_df.empty:
        return pd.DataFrame(), {}
    
    arbitrage_df = arbitrage_df.rename(columns={'arbitrage_revenue': 'energy_arbitrage'})
    
    if not as_df.empty:
        as_df = as_df.rename(columns={'Time': 'date'})
        merged = arbitrage_df.merge(as_df, on='date', how='left')
        merged['total_as_revenue'] = merged['total_as_revenue'].fillna(0)
    else:
        merged = arbitrage_df
        merged['total_as_revenue'] = 0
    
    # Calculate total revenue
    merged['total_revenue'] = merged['energy_arbitrage'] + merged['total_as_revenue']
    
    # Calculate $/kW-month metrics
    # Normalize to $/kW-month: (total_revenue / (capacity_mw * 1000)) * 1000 = $/kW
    # But typically expressed as monthly rate
    total_kw = capacity_mw * 1000  # kW
    merged['revenue_per_kw'] = merged['total_revenue'] / total_kw
    
    # Calculate summary metrics
    n_days = len(merged)
    total_energy = merged['energy_arbitrage'].sum()
    total_as = merged['total_as_revenue'].sum()
    total_rev = total_energy + total_as
    
    summary = {
        'total_revenue_30d': total_rev,
        'energy_arbitrage_30d': total_energy,
        'as_revenue_30d': total_as,
        'revenue_per_kw_month': (total_rev / total_kw) * (30 / n_days),  # Normalized to monthly rate
        'n_days': n_days,
        'pct_energy': (total_energy / total_rev * 100) if total_rev > 0 else 0,
        'pct_as': (total_as / total_rev * 100) if total_rev > 0 else 0,
        'peak_arbitrage_day': merged.loc[merged['energy_arbitrage'].idxmax(), 'date'] if not merged.empty else None,
        'avg_daily_revenue': merged['total_revenue'].mean(),
        'max_daily_revenue': merged['total_revenue'].max(),
        'min_daily_revenue': merged['total_revenue'].min()
    }
    
    return merged, summary


def format_currency(value: float) -> str:
    """Format value as currency."""
    return f"${value:,.2f}"


def calculate_npv(revenue_series: pd.Series, discount_rate: float = 0.08, years: int = 10) -> float:
    """
    Calculate NPV of revenue stream.
    
    Args:
        revenue_series: Daily revenue series
        discount_rate: Annual discount rate
        years: Projection years
    
    Returns:
        NPV value
    """
    # Assume revenue repeats (simplified)
    daily_rate = (1 + discount_rate) ** (1/365) - 1
    
    npv = 0
    for i in range(years * 365):
        npv += revenue_series.mean() / (1 + daily_rate) ** i
    
    return npv


if __name__ == "__main__":
    # Test with sample data
    import numpy as np
    
    # Create synthetic SPP
    dates = pd.date_range("2026-02-01", periods=96*30, freq="15min")
    np.random.seed(42)
    prices = 30 + np.random.randn(len(dates)) * 10
    
    spp = pd.DataFrame({
        'Time': dates,
        'SPP': prices
    })
    
    # Create synthetic AS prices
    as_dates = pd.date_range("2026-02-01", periods=30, freq="D")
    as_prices = pd.DataFrame({
        'Time': as_dates,
        'Regulation Up': np.random.uniform(5, 20, 30),
        'Regulation Down': np.random.uniform(3, 15, 30),
        'Non-Spinning Reserves': np.random.uniform(2, 10, 30),
        'Responsive Reserves': np.random.uniform(1, 8, 30)
    })
    
    # Calculate revenue
    result, summary = calculate_revenue_stack(
        spp, as_prices,
        capacity_mw=100,
        duration_hrs=4,
        rte=0.85,
        as_reserved_frac=0.2
    )
    
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
