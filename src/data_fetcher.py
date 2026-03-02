"""Data fetcher module for ERCOT market data."""
import pandas as pd
import os
from datetime import datetime, timedelta


def fetch_spp(date="30 days ago", end="today", location="HB_NORTH"):
    """
    Fetch Real-Time Settlement Point Prices (SPP) for a given location.
    
    First attempts to fetch real data from ERCOT via gridstatus.
    Falls back to synthetic data if API is unavailable.
    """
    print(f"Fetching SPP for {location}...")
    
    # Try real data first
    try:
        import gridstatus
        iso = gridstatus.Ercot()
        
        # Calculate date range
        if isinstance(date, str):
            if "days ago" in date:
                days = int(date.split()[0])
            else:
                days = 30
        else:
            days = 30
        
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        
        print(f"  Attempting to fetch real ERCOT data...")
        spp = iso.get_spp(date=start_dt, end=end_dt, market="REAL_TIME_15_MIN")
        
        if spp is not None and len(spp) > 0:
            # Filter to requested location
            if 'Location' in spp.columns and location != "HB_NORTH":
                spp = spp[spp['Location'] == location]
            
            # Select relevant columns
            if 'SPP' in spp.columns:
                spp = spp[['Time', 'SPP']].copy()
            elif 'Price' in spp.columns:
                spp = spp[['Time', 'Price']].rename(columns={'Price': 'SPP'})
            
            print(f"  ✅ Real ERCOT data fetched: {len(spp)} records")
            return spp
            
    except Exception as e:
        print(f"  ⚠️ gridstatus fetch failed ({type(e).__name__}), using synthetic data")
    
    # Fallback to synthetic data
    from src.synthetic_data import generate_realistic_spp
    
    if isinstance(date, str):
        if "days ago" in date:
            days = int(date.split()[0])
        else:
            days = 30
    else:
        days = 30
    
    spp = generate_realistic_spp(days=days, location=location)
    print(f"  Generated synthetic data: {len(spp)} records")
    return spp


def fetch_as_prices(date="30 days ago", end="today"):
    """Fetch Ancillary Services clearing prices. Tries gridstatus first, then synthetic."""
    print("Fetching AS prices...")
    
    # Try real data first
    try:
        import gridstatus
        iso = gridstatus.Ercot()
        
        # Calculate date range
        if isinstance(date, str):
            if "days ago" in date:
                days = int(date.split()[0])
            else:
                days = 30
        else:
            days = 30
        
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        
        print(f"  Attempting to fetch real AS prices...")
        as_prices = iso.get_as_prices(date=start_dt, end=end_dt)
        
        if as_prices is not None and len(as_prices) > 0:
            print(f"  ✅ Real AS data fetched: {len(as_prices)} records")
            return as_prices
            
    except Exception as e:
        print(f"  ⚠️ gridstatus AS fetch failed ({type(e).__name__}), using synthetic data")
    
    # Fallback to synthetic
    from src.synthetic_data import generate_realistic_as_prices
    
    if isinstance(date, str):
        if "days ago" in date:
            days = int(date.split()[0])
        else:
            days = 30
    else:
        days = 30
    
    as_prices = generate_realistic_as_prices(days=days)
    print(f"  Generated synthetic AS data: {len(as_prices)} records")
    return as_prices


def load_or_fetch_data(days=30, location="HB_NORTH", force_refresh=False):
    """
    Load cached data or fetch fresh data from ERCOT (or generate realistic synthetic).
    Uses date-stamped cache files to ensure fresh data.
    """
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    
    # Date-stamped cache to avoid stale data
    today = datetime.now().strftime("%Y%m%d")
    spp_path = os.path.join(data_dir, f"spp_{location}_{days}days_{today}.csv")
    as_path = os.path.join(data_dir, f"as_prices_{days}days_{today}.csv")
    
    # Try loading from cache first
    if not force_refresh:
        if os.path.exists(spp_path) and os.path.exists(as_path):
            print("Loading from cache...")
            spp = pd.read_csv(spp_path, parse_dates=['Time'])
            as_prices = pd.read_csv(as_path, parse_dates=['Time'])
            return spp, as_prices
    
    # Fetch fresh data (or generate synthetic)
    spp = fetch_spp(date=f"{days} days ago", end="today", location=location)
    as_prices = fetch_as_prices(date=f"{days} days ago", end="today")
    
    # Cache to disk
    if not spp.empty:
        spp.to_csv(spp_path, index=False)
        print(f"  Cached SPP to {spp_path}")
    
    if not as_prices.empty:
        as_prices.to_csv(as_path, index=False)
        print(f"  Cached AS to {as_path}")
    
    return spp, as_prices


if __name__ == "__main__":
    # Test fetching
    spp, as_prices = load_or_fetch_data(days=7)
    print(f"\nSPP shape: {spp.shape}")
    print(f"AS prices shape: {as_prices.shape}")
    print("\nSPP columns:", spp.columns.tolist())
    print("\nAS columns:", as_prices.columns.tolist())
