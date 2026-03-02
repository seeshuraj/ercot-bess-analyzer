"""Generate realistic synthetic ERCOT market data when API is unavailable."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_realistic_spp(days=30, location="HB_NORTH", seed=42):
    """
    Generate realistic Settlement Point Prices based on ERCOT market patterns.
    
    ERCOT SPP typically ranges from -$50 to $500+/MWh with:
    - Daily pattern: higher during peak hours (7am-9pm)
    - Weekly pattern: lower on weekends
    - Volatility: high during scarcity events
    - Negative prices: common during high renewable generation
    """
    np.random.seed(seed)
    
    # Time index
    intervals_per_day = 96  # 15-min intervals
    total_intervals = days * intervals_per_day
    start_date = datetime.now() - timedelta(days=days)
    dates = pd.date_range(start=start_date, periods=total_intervals, freq="15min")
    
    # Base price components
    hour_of_day = dates.hour
    day_of_week = dates.dayofweek
    
    # 1. Daily pattern (higher during peak)
    peak_hours = ((hour_of_day >= 7) & (hour_of_day <= 21)).astype(float)
    daily_pattern = 25 + 20 * peak_hours
    
    # 2. Weekly pattern (weekends lower)
    weekend_factor = np.where(day_of_week >= 5, 0.85, 1.0)
    
    # 3. Random component with autocorrelation
    n = len(dates)
    base_prices = np.random.randn(n) * 12
    
    # Add some autocorrelation
    for i in range(1, n):
        base_prices[i] = 0.7 * base_prices[i-1] + 0.3 * base_prices[i]
    
    # 4. Combine components
    prices = (daily_pattern * weekend_factor + base_prices)
    
    # 5. Add occasional price spikes (scarcity events)
    spike_days = np.random.choice(range(2, days-2), size=max(1, days//10), replace=False)
    for spike_day in spike_days:
        spike_start = spike_day * intervals_per_day + np.random.randint(20, 70)
        spike_duration = np.random.randint(4, 20)
        spike_magnitude = np.random.uniform(50, 200)
        prices[spike_start:min(spike_start+spike_duration, n)] += spike_magnitude
    
    # 6. Occasional negative prices (renewable oversupply)
    negative_indices = np.random.choice(n, size=int(n * 0.02), replace=False)
    prices[negative_indices] = -np.random.uniform(5, 30, len(negative_indices))
    
    # Create DataFrame
    df = pd.DataFrame({
        'Time': dates,
        'Location': location,
        'SPP': prices,
        'Market': 'REAL_TIME_15_MIN'
    })
    
    return df


def generate_realistic_as_prices(days=30, seed=42):
    """
    Generate realistic Ancillary Services prices.
    
    Based on actual ERCOT AS market patterns:
    - Reg Up/Reg Down: $5-30/MW-hr typical, can spike higher
    - Non-Spin: $2-15/MW-hr
    - RRS: $1-10/MW-hr
    
    Note: AS revenues have declined ~90% since 2023 due to market saturation
    """
    np.random.seed(seed)
    
    dates = pd.date_range(start=datetime.now() - timedelta(days=days), periods=days, freq="D")
    
    # Base prices (reflect post-2023 depressed market)
    reg_up = np.random.uniform(3, 15, days) + np.random.randn(days) * 3
    reg_down = np.random.uniform(2, 12, days) + np.random.randn(days) * 2
    non_spin = np.random.uniform(1, 8, days) + np.random.randn(days) * 1.5
    rrs = np.random.uniform(0.5, 5, days) + np.random.randn(days) * 1
    
    # Ensure non-negative
    reg_up = np.maximum(reg_up, 0.5)
    reg_down = np.maximum(reg_down, 0.5)
    non_spin = np.maximum(non_spin, 0.25)
    rrs = np.maximum(rrs, 0.1)
    
    df = pd.DataFrame({
        'Time': dates,
        'Regulation Up': reg_up,
        'Regulation Down': reg_down,
        'Non-Spinning Reserves': non_spin,
        'Responsive Reserves': rrs
    })
    
    return df


def get_spp_or_generate(days=30, location="HB_NORTH", force_synthetic=False):
    """
    Try to fetch real data, fall back to synthetic if unavailable.
    """
    if force_synthetic:
        return generate_realistic_spp(days, location)
    
    try:
        import gridstatus
        iso = gridstatus.Ercot()
        
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=days)
        
        spp = iso.get_spp(date=start, end=end, market="REAL_TIME_15_MIN")
        
        if spp is not None and len(spp) > 0:
            return spp
    except Exception as e:
        print(f"Could not fetch real data: {e}")
    
    print("Using synthetic data (realistic simulation)")
    return generate_realistic_spp(days, location)


def get_as_prices_or_generate(days=30, force_synthetic=False):
    """Try to fetch real AS prices, fall back to synthetic."""
    if force_synthetic:
        return generate_realistic_as_prices(days)
    
    try:
        import gridstatus
        iso = gridstatus.Ercot()
        
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=days)
        
        as_prices = iso.get_as_prices(date=start, end=end)
        
        if as_prices is not None and len(as_prices) > 0:
            return as_prices
    except Exception as e:
        print(f"Could not fetch real AS prices: {e}")
    
    return generate_realistic_as_prices(days)


if __name__ == "__main__":
    # Test generation
    spp = generate_realistic_spp(7)
    as_prices = generate_realistic_as_prices(7)
    
    print("SPP Sample:")
    print(spp.head())
    print(f"\nSPP Stats:\n{spp['SPP'].describe()}")
    
    print("\n\nAS Prices Sample:")
    print(as_prices.head())
