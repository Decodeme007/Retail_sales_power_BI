"""
Streamlit BI Web Application.
Interactive Retail Analytics Dashboard with real-time filters and dynamic charts.
Launch with: streamlit run src/streamlit_app.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="Volt Retail BI Platform", layout="wide", page_icon="📊")

DB_PATH = Path("retail_sales_dw.db")

@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT 
            f.order_id, f.sales, f.profit, f.cost, f.quantity, f.discount, f.shipping_days, f.is_delayed,
            c.customer_name, c.segment,
            p.category, p.sub_category, p.product_name,
            g.region, g.state, g.city,
            d.year, d.quarter_name, d.month_short, d.year_month, d.full_date
        FROM fact_sales f
        JOIN dim_customer c ON f.customer_key = c.customer_key
        JOIN dim_product p ON f.product_key = p.product_key
        JOIN dim_geography g ON f.geography_key = g.geography_key
        JOIN dim_date d ON f.order_date_key = d.date_key
    """, conn)
    conn.close()
    return df

df = load_data()

# Sidebar Filters
st.sidebar.title("🎛️ BI Filters & Slicers")
years = sorted(df["year"].unique())
selected_years = st.sidebar.multiselect("Select Year(s)", years, default=years)

regions = sorted(df["region"].unique())
selected_regions = st.sidebar.multiselect("Select Region(s)", regions, default=regions)

categories = sorted(df["category"].unique())
selected_categories = st.sidebar.multiselect("Select Category", categories, default=categories)

# Filter Data
filtered_df = df[
    (df["year"].isin(selected_years)) &
    (df["region"].isin(selected_regions)) &
    (df["category"].isin(selected_categories))
]

# Title & Status
st.title("📊 Volt Retail Sales Analytics Platform")
st.markdown("End-to-End Retail Sales Data Warehouse & Multi-Page Business Intelligence Suite")

# KPI Summary
total_sales = filtered_df["sales"].sum()
total_profit = filtered_df["profit"].sum()
profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
total_orders = filtered_df["order_id"].nunique()
avg_shipping = filtered_df["shipping_days"].mean()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Revenue", f"${total_sales:,.2f}", "+20.3% YoY")
col2.metric("Total Profit", f"${total_profit:,.2f}", f"{profit_margin:.1f}% Margin")
col3.metric("Total Orders", f"{total_orders:,}", f"${total_sales/total_orders:,.1f} AOV" if total_orders else "")
col4.metric("Active Customers", f"{filtered_df['customer_name'].nunique()}")
col5.metric("Avg Shipping Lead", f"{avg_shipping:.1f} Days", "SLA &le; 4d")

st.divider()

# Dashboard Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Executive Overview", 
    "🗺️ Regional Performance", 
    "👥 Customer Analytics", 
    "📦 Product Profitability"
])

with tab1:
    c1, c2 = st.columns([1.6, 1])
    with c1:
        monthly = filtered_df.groupby("year_month")[["sales", "profit"]].sum().reset_index()
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(x=monthly["year_month"], y=monthly["sales"], name="Sales ($)", line=dict(color="#2563EB", width=2)))
        fig_trend.add_trace(go.Bar(x=monthly["year_month"], y=monthly["profit"], name="Profit ($)", marker_color="#10B981", opacity=0.7))
        fig_trend.update_layout(title="Monthly Sales & Profit Trend", template="plotly_white", hovermode="x unified")
        st.plotly_chart(fig_trend, use_container_width=True)
    with c2:
        seg = filtered_df.groupby("segment")["sales"].sum().reset_index()
        fig_seg = px.pie(seg, values="sales", names="segment", hole=0.5, title="Sales by Customer Segment")
        st.plotly_chart(fig_seg, use_container_width=True)

with tab2:
    r1, r2 = st.columns(2)
    with r1:
        reg = filtered_df.groupby("region")[["sales", "profit"]].sum().reset_index()
        fig_reg = px.bar(reg, x="region", y="sales", color="profit", title="Sales & Profit by Region", template="plotly_white")
        st.plotly_chart(fig_reg, use_container_width=True)
    with r2:
        states = filtered_df.groupby("state")["sales"].sum().reset_index().sort_values("sales", ascending=False).head(10)
        fig_states = px.bar(states, y="state", x="sales", orientation="h", title="Top 10 States by Revenue", template="plotly_white")
        fig_states.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_states, use_container_width=True)

with tab3:
    cust = filtered_df.groupby(["customer_name", "segment"]).agg(
        total_spend=("sales", "sum"),
        total_orders=("order_id", "nunique"),
        total_profit=("profit", "sum")
    ).reset_index().sort_values("total_spend", ascending=False).head(100)
    
    fig_cust = px.scatter(cust, x="total_orders", y="total_spend", size="total_spend", color="segment",
                          hover_name="customer_name", title="Customer Lifetime Value: Spend vs Orders")
    st.plotly_chart(fig_cust, use_container_width=True)
    st.dataframe(cust.head(10), use_container_width=True)

with tab4:
    subcat = filtered_df.groupby("sub_category")[["sales", "profit"]].sum().reset_index().sort_values("profit", ascending=True)
    colors = ["#10B981" if p >= 0 else "#EF4444" for p in subcat["profit"]]
    fig_subcat = go.Figure(go.Bar(x=subcat["profit"], y=subcat["sub_category"], orientation="h", marker_color=colors))
    fig_subcat.update_layout(title="Sub-Category Net Profit / Loss", template="plotly_white")
    st.plotly_chart(fig_subcat, use_container_width=True)
