"""Battery dispatch model for energy arbitrage simulation."""
import pandas as pd
import numpy as np
from typing import Tuple


def simulate_dispatch(
    prices: pd.Series,
    capacity_mw: float,
    duration_hrs: float,
    rte: float = 0.85,
    as_reserved_frac: float = 0.0,
    charge_threshold_pct: float = 25,
    discharge_threshold_pct: float = 75
) -> pd.DataFrame:
    """
    Perfect-foresight daily dispatch simulation for energy arbitrage.
    
    This uses a simple threshold-based heuristic: charge when prices are
    below the charge_threshold, discharge when above discharge_threshold.
    
    Args:
        prices: 15-minute price series with datetime index
        capacity_mw: Battery power capacity (MW)
        duration_hrs: Battery energy capacity (hours = MWh / MW)
        rte: Round-trip efficiency (0-1)
        as_reserved_frac: Fraction of capacity reserved for AS (unavailable for arbitrage)
        charge_threshold_pct: Percentile below which to charge
        discharge_threshold_pct: Percentile above which to discharge
    
    Returns:
        DataFrame with daily revenue breakdown
    """
    # Available capacity for energy arbitrage
    available_mw = capacity_mw * (1 - as_reserved_frac)
    max_energy_mwh = available_mw * duration_hrs
    
    # Energy moved per 15-min interval
    energy_per_interval = available_mw * 0.25  # MW * 0.25 hr
    
    results = []
    
    # Group by day
    for date, day_prices in prices.groupby(prices.index.date):
        prices_arr = day_prices.values
        
        if len(prices_arr) == 0:
            continue
            
        # Calculate thresholds for this day
        threshold_low = np.percentile(prices_arr, charge_threshold_pct)
        threshold_high = np.percentile(prices_arr, discharge_threshold_pct)
        
        soc = 0.0  # Start with empty battery
        daily_revenue = 0.0
        charge_amount = 0.0
        discharge_amount = 0.0
        
        for price in prices_arr:
            if price <= threshold_low and soc < max_energy_mwh:
                # Charge: buy cheap power
                can_charge = min(energy_per_interval, max_energy_mwh - soc)
                soc += can_charge
                # Cost to charge (accounting for RTE losses on discharge)
                daily_revenue -= can_charge * price
                charge_amount += can_charge
                
            elif price >= threshold_high and soc > 0:
                # Discharge: sell expensive power
                can_discharge = min(energy_per_interval, soc)
                soc -= can_discharge
                # Revenue from discharge (accounting for RTE losses)
                daily_revenue += can_discharge * price * rte
                discharge_amount += can_discharge
        
        results.append({
            'date': pd.Timestamp(date),
            'arbitrage_revenue': daily_revenue,
            'charge_mwh': charge_amount,
            'discharge_mwh': discharge_amount,
            'net_energy_mwh': discharge_amount * rte - charge_amount,
            'avg_price_charge': threshold_low,
            'avg_price_discharge': threshold_high
        })
    
    return pd.DataFrame(results)


def simulate_dispatch_advanced(
    prices: pd.Series,
    capacity_mw: float,
    duration_hrs: float,
    rte: float = 0.85,
    as_reserved_frac: float = 0.0
) -> pd.DataFrame:
    """
    Advanced dispatch: optimize charge/discharge based on daily price spread.
    
    This version finds the optimal N intervals to charge/discharge based on
    the battery's energy capacity constraints.
    
    Args:
        prices: 15-minute price series with datetime index
        capacity_mw: Battery power capacity (MW)
        duration_hrs: Battery energy capacity (hours)
        rte: Round-trip efficiency
        as_reserved_frac: Fraction reserved for AS
    
    Returns:
        DataFrame with daily revenue
    """
    available_mw = capacity_mw * (1 - as_reserved_frac)
    max_energy_mwh = available_mw * duration_hrs
    
    results = []
    
    for date, day_prices in prices.groupby(prices.index.date):
        prices_arr = day_prices.values
        n_intervals = len(prices_arr)
        
        if n_intervals == 0:
            continue
        
        # Calculate how many intervals we can fully charge/discharge
        max_intervals_charge = int(max_energy_mwh / (available_mw * 0.25))
        max_intervals_discharge = int(max_energy_mwh / (available_mw * 0.25))
        
        # Sort prices to find best intervals
        sorted_indices = np.argsort(prices_arr)
        
        # Charge during cheapest intervals
        charge_indices = sorted_indices[:max_intervals_charge]
        # Discharge during most expensive intervals
        discharge_indices = sorted_indices[-max_intervals_discharge:]
        
        # Calculate energy amounts
        charge_price = np.mean(prices_arr[charge_indices])
        discharge_price = np.mean(prices_arr[discharge_indices])
        
        charge_energy = min(max_intervals_charge * available_mw * 0.25, max_energy_mwh)
        # Can't charge and discharge same energy - need cycle
        # Assume we do a full cycle: charge then discharge
        cycle_energy = min(charge_energy, max_energy_mwh)
        
        # Revenue = discharge revenue - charge cost (accounting for RTE)
        revenue = cycle_energy * discharge_price * rte - cycle_energy * charge_price
        
        results.append({
            'date': pd.Timestamp(date),
            'arbitrage_revenue': revenue,
            'charge_mwh': charge_energy,
            'discharge_mwh': cycle_energy,
            'charge_price': charge_price,
            'discharge_price': discharge_price,
            'price_spread': discharge_price - charge_price
        })
    
    return pd.DataFrame(results)


def calc_as_revenue(
    as_prices: pd.DataFrame,
    capacity_mw: float,
    as_reserved_frac: float = 0.0,
    availability_factor: float = 0.85
) -> pd.DataFrame:
    """
    Calculate ancillary services revenue from capacity payments.
    
    Note: In ERCOT, a battery cannot be simultaneously committed to all AS products.
    This simplified model assumes the battery commits to the highest-clearing AS product
    each day. Real dispatch co-optimizes across products hourly.
    
    Args:
        as_prices: DataFrame with AS prices (Reg Up, Reg Down, Non-Spin, RRS)
        capacity_mw: Battery capacity
        as_reserved_frac: Fraction of capacity committed to AS
        availability_factor: Expected availability (default 85%)
    
    Returns:
        DataFrame with daily AS revenue breakdown
    """
    if as_prices.empty:
        return pd.DataFrame()
    
    as_mw = capacity_mw * as_reserved_frac
    
    # Find AS price columns
    as_cols = [col for col in as_prices.columns if any(
        x in col.lower() for x in ['regulation', 'reg up', 'reg down', 'non-spin', 'nonspin', 'responsive', 'rrs']
    )]
    
    if not as_cols:
        # Try common column names
        as_cols = ['Regulation Up', 'Regulation Down', 'Non-Spinning Reserves', 'Responsive Reserves']
        as_cols = [c for c in as_cols if c in as_prices.columns]
    
    if not as_cols:
        print(f"Warning: No AS columns found. Available: {as_prices.columns.tolist()}")
        return pd.DataFrame()
    
    # Set time index and resample to daily
    as_df = as_prices.set_index('Time')
    
    # Calculate daily average prices
    daily_prices = as_df[as_cols].resample('D').mean()
    
    # FIX: Pick the highest-value AS product per day (not sum of all products)
    # In ERCOT, battery capacity can only committed to ONE product at a time
    best_as_price = daily_prices.max(axis=1)
    best_product = daily_prices.idxmax(axis=1)
    
    # Calculate revenue using the best AS product
    daily_revenue = pd.DataFrame({
        'Time': best_as_price.index,
        'best_as_product': best_product.values,
        'best_as_price': best_as_price.values,
        'total_as_revenue': best_as_price.values * as_mw * 24 * availability_factor
    })
    
    # Add individual product columns for reference
    for col in as_cols:
        if col in daily_prices.columns:
            daily_revenue[f'{col}_price'] = daily_prices[col].values
    
    return daily_revenue


if __name__ == "__main__":
    # Test with sample data
    import numpy as np
    
    # Create synthetic prices
    dates = pd.date_range("2026-02-01", periods=96*7, freq="15min")
    np.random.seed(42)
    base_prices = 30 + np.random.randn(len(dates)) * 15
    # Add daily pattern
    hour_of_day = dates.hour
    base_prices += 10 * np.sin(2 * np.pi * hour_of_day / 24)
    
    prices = pd.Series(base_prices, index=dates)
    
    # Test dispatch
    result = simulate_dispatch(prices, capacity_mw=100, duration_hrs=4, rte=0.85)
    print(result.head())
