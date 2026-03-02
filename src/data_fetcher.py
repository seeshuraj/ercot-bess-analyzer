"""Data fetcher module for ERCOT market data."""
import pandas as pd
import os
from datetime import datetime, timedelta


def fetch_spp(date="30 days ago", end="today", location="HB_NORTH"):
    """
    Fetch Real-Time Settlement Point Prices (SPP) for a given location.
    Uses synthetic data when ERCOT API is unavailable.
    """
    print(f"Fetching SPP for {location}...")
    from src.synthetic_data import get_spp_or_generate
    
    # Calculate days
    if isinstance(date, str):
        if "days ago" in date:
            days = int(date.split()[0])
        else:
            days = 30
    else:
        days = 30
    
    spp = get_spp_or_generate(days=days, location=location)
    print(f"  Retrieved {len(spp)} records")
    return spp


def fetch_as_prices(date="30 days ago", end="today"):
    """Fetch Ancillary Services clearing prices. Uses synthetic data when unavailable."""
    print("Fetching AS prices...")
    from src.synthetic_data import get_as_prices_or_generate
    
    if isinstance(date, str):
        if "days ago" in date:
            days = int(date.split()[0])
        else:
            days = 30
    else:
        days = 30
    
    as_prices = get_as_prices_or_generate(days=days)
    print(f"  Retrieved {len(as_prices)} records")
    return as_prices


def load_or_fetch_data(days=30, location="HB_NORTH", force_refresh=False):
    """
    Load cached data or fetch fresh data from ERCOT (or generate realistic synthetic).
    """
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    
    spp_path = os.path.join(data_dir, f"spp_{location}_{days}days.csv")
    as_path = os.path.join(data_dir, f"as_prices_{days}days.csv")
    
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
