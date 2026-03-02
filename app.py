"""
ERCOT BESS Revenue Stack Analyzer
Streamlit Dashboard

A tool for battery asset owners to simulate historical revenue across
energy arbitrage and ancillary services in ERCOT.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data_fetcher import load_or_fetch_data
from src.revenue_calculator import calculate_revenue_stack

# Page config
st.set_page_config(
    page_title="ERCOT BESS Revenue Analyzer",
    page_icon="🔋",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #1f77b4;
    }
    .metric-label {
        font-size: 14px;
        color: #666;
    }
    .insight-box {
        background-color: #e8f4f8;
        border-left: 4px solid #1f77b4;
        padding: 15px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Title and description
st.title("🔋 ERCOT BESS Revenue Stack Analyzer")
st.markdown("""
**Problem:** Battery asset owners in ERCOT face a shifting revenue landscape — ancillary service 
revenues have fallen ~90% since 2023, while real-time energy arbitrage now dominates. This tool 
helps owners understand their historical revenue stack and optimize capacity allocation between revenue streams.
""")

# Sidebar inputs
st.sidebar.header("⚙️ Battery Configuration")

capacity_mw = st.sidebar.slider("Capacity (MW)", min_value=10, max_value=500, value=100, step=10)
duration_hrs = st.sidebar.slider("Duration (hours)", min_value=1, max_value=8, value=4, step=1)
rte = st.sidebar.slider("Round-Trip Efficiency", min_value=0.70, max_value=0.95, value=0.85, step=0.01)
as_reserved_frac = st.sidebar.slider("AS Capacity Reserve (%)", min_value=0, max_value=100, value=20, step=5) / 100
location = st.sidebar.selectbox(
    "ERCOT Zone",
    ["HB_NORTH", "HB_HOUSTON", "HB_WEST", "HB_SOUTH"],
    index=0
)
dispatch_method = st.sidebar.radio("Dispatch Method", ["threshold", "advanced"], index=0)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Data Range")
days_option = st.sidebar.select_slider(
    "History",
    options=[7, 14, 30],
    value=30
)
force_refresh = st.sidebar.checkbox("Force refresh data", value=False)

# Main content
try:
    # Load data
    with st.spinner(f'Fetching {days_option} days of ERCOT market data...'):
        spp, as_prices = load_or_fetch_data(
            days=days_option,
            location=location,
            force_refresh=force_refresh
        )
    
    if spp.empty:
        st.error("⚠️ No SPP data available. Please try a different location or date range.")
        st.stop()
    
    # Calculate revenue
    revenue_df, summary = calculate_revenue_stack(
        spp, as_prices,
        capacity_mw=capacity_mw,
        duration_hrs=duration_hrs,
        rte=rte,
        as_reserved_frac=as_reserved_frac,
        dispatch_method=dispatch_method
    )
    
    if revenue_df.empty:
        st.error("⚠️ Could not calculate revenue. Please check data availability.")
        st.stop()
    
    # Key metrics
    st.markdown("### 📈 Revenue Summary (Last 30 Days)")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">${summary['total_revenue_30d']:,.0f}</div>
            <div class="metric-label">Total Revenue</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">${summary['revenue_per_kw_month']:,.2f}</div>
            <div class="metric-label">$/kW-month</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        pct_energy = summary['pct_energy']
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #2ca02c">{pct_energy:.1f}%</div>
            <div class="metric-label">Energy Arbitrage</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        pct_as = summary['pct_as']
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #ff7f0e">{pct_as:.1f}%</div>
            <div class="metric-label">Ancillary Services</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Revenue breakdown chart
    st.markdown("### 💰 Daily Revenue Stack")
    
    # Prepare data for stacking
    chart_data = revenue_df[['date', 'energy_arbitrage', 'total_as_revenue']].copy()
    chart_data = chart_data.rename(columns={
        'energy_arbitrage': 'Energy Arbitrage',
        'total_as_revenue': 'Ancillary Services'
    })
    
    fig = px.bar(
        chart_data,
        x='date',
        y=['Energy Arbitrage', 'Ancillary Services'],
        title=f'Daily Revenue by Stream - {capacity_mw}MW/{duration_hrs}hr Battery @ {location}',
        labels={'value': 'Revenue ($)', 'date': 'Date'},
        color_discrete_map={
            'Energy Arbitrage': '#2ca02c',
            'Ancillary Services': '#ff7f0e'
        },
        barmode='stack'
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    
    # Price duration curve
    st.markdown("### 📊 Price Duration Curve")
    
    # Extract prices
    if 'SPP' in spp.columns:
        prices = spp.set_index('Time')['SPP'].dropna()
    elif 'Price' in spp.columns:
        prices = spp.set_index('Time')['Price'].dropna()
    else:
        price_cols = [c for c in spp.columns if 'price' in c.lower()]
        if price_cols:
            prices = spp.set_index('Time')[price_cols[0]].dropna()
        else:
            prices = spp.select_dtypes(include=[np.number]).iloc[:, 0]
    
    # Calculate duration curve
    prices_sorted = prices.sort_values(ascending=False).reset_index(drop=True)
    prices_sorted.index = prices_sorted.index / len(prices_sorted) * 100
    
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(
        x=prices_sorted.index,
        y=prices_sorted.values,
        mode='lines',
        fill='tozeroy',
        line=dict(color='#1f77b4'),
        name='SPP'
    ))
    fig_price.update_layout(
        title='Real-Time SPP Duration Curve',
        xaxis_title='Percentile (%)',
        yaxis_title='Price ($/MWh)',
        hovermode="closest"
    )
    st.plotly_chart(fig_price, use_container_width=True)
    
    # Insights
    st.markdown("### 💡 Key Insights")
    
    avg_daily = summary['avg_daily_revenue']
    max_daily = summary['max_daily_revenue']
    min_daily = summary['min_daily_revenue']
    
    st.markdown(f"""
    <div class="insight-box">
    <ul>
        <li><strong>Average daily revenue:</strong> ${avg_daily:,.2f}</li>
        <li><strong>Best day:</strong> ${max_daily:,.2f} ({summary['peak_arbitrage_day'].strftime('%Y-%m-%d') if summary['peak_arbitrage_day'] else 'N/A'})</li>
        <li><strong>Toughest day:</strong> ${min_daily:,.2f}</li>
        <li><strong>Revenue mix:</strong> {pct_energy:.1f}% energy + {pct_as:.1f}% AS</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Methodology note
    st.markdown("---")
    st.markdown("""
    ### 📝 Methodology
    
    **Energy Arbitrage:** Perfect-foresight dispatch simulation using {method} approach.
    Charge during lowest {charge_pct}% of prices, discharge during highest {discharge_pct}%.
    
    **Ancillary Services:** Capacity payment model assuming {as_pct:.0%} of capacity reserved.
    Revenue = AS clearing price × MW committed × 24 hours × 85% availability factor.
    
    **Note:** This is an upper-bound benchmark. Real operators use day-ahead price forecasts,
    not actual prices. Modo's Benchmarking Pro uses similar methodology for historical analysis.
    """.format(
        method=dispatch_method,
        charge_pct=25,
        discharge_pct=75,
        as_pct=as_reserved_frac
    ))
    
    # Data table
    with st.expander("📋 View Daily Revenue Data"):
        st.dataframe(
            revenue_df[['date', 'energy_arbitrage', 'total_as_revenue', 'total_revenue']].rename(columns={
                'date': 'Date',
                'energy_arbitrage': 'Energy ($)',
                'total_as_revenue': 'AS ($)',
                'total_revenue': 'Total ($)'
            }),
            use_container_width=True
        )

except Exception as e:
    st.error(f"Error: {str(e)}")
    st.markdown("""
    ### Troubleshooting
    - Try a different date range or location
    - Force refresh data to get latest prices
    - Check ERCOT data availability
    """)
    import traceback
    st.code(traceback.format_exc())

# Footer
st.markdown("---")
st.markdown("*Built for Modo Energy Take-Home Task | ERCOT BESS Revenue Analyzer*")
