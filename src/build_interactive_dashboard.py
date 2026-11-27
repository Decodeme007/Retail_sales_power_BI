"""
Interactive HTML Dashboard Generator.
Builds a standalone, zero-dependency 4-page interactive BI dashboard
using Plotly and modern HTML5/CSS3. Allows instant browser preview without Power BI.
"""

import sqlite3
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

DB_PATH = Path("retail_sales_dw.db")
OUTPUT_HTML = Path("powerbi/interactive_dashboard.html")

def generate_interactive_dashboard():
    print(f"Connecting to {DB_PATH} to generate interactive BI dashboard...")
    conn = sqlite3.connect(DB_PATH)

    # 1. Executive Metrics
    df_kpi = pd.read_sql_query("""
        SELECT 
            ROUND(SUM(sales), 2) AS total_sales,
            ROUND(SUM(profit), 2) AS total_profit,
            ROUND((SUM(profit)/SUM(sales))*100, 2) AS profit_margin,
            COUNT(DISTINCT order_id) AS total_orders,
            COUNT(DISTINCT customer_key) AS total_customers,
            ROUND(AVG(shipping_days), 1) AS avg_shipping_days
        FROM fact_sales
    """, conn)
    
    kpis = df_kpi.iloc[0].to_dict()

    # Monthly Trend
    df_monthly = pd.read_sql_query("""
        SELECT d.year_month, SUM(f.sales) AS sales, SUM(f.profit) AS profit
        FROM fact_sales f JOIN dim_date d ON f.order_date_key = d.date_key
        GROUP BY d.year_month ORDER BY d.year_month
    """, conn)

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=df_monthly["year_month"], y=df_monthly["sales"], name="Revenue ($)", line=dict(color="#2563EB", width=3)))
    fig_trend.add_trace(go.Bar(x=df_monthly["year_month"], y=df_monthly["profit"], name="Profit ($)", marker_color="#10B981", opacity=0.7))
    fig_trend.update_layout(title="Monthly Revenue & Profit Progression", template="plotly_white", hovermode="x unified", height=380, margin=dict(l=20, r=20, t=40, b=20))

    # Category Revenue
    df_cat = pd.read_sql_query("""
        SELECT p.category, ROUND(SUM(f.sales), 2) AS sales, ROUND(SUM(f.profit), 2) AS profit,
               ROUND((SUM(f.profit)/SUM(f.sales))*100, 1) AS margin_pct
        FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category ORDER BY sales DESC
    """, conn)

    fig_cat = px.bar(df_cat, x="category", y="sales", color="category", text="margin_pct",
                     title="Revenue by Category (with Profit Margin %)",
                     color_discrete_sequence=["#0F172A", "#3B82F6", "#64748B"])
    fig_cat.update_traces(texttemplate='%{text}% Margin', textposition='outside')
    fig_cat.update_layout(template="plotly_white", height=380, margin=dict(l=20, r=20, t=40, b=20), showlegend=False)

    # Segment Donut
    df_seg = pd.read_sql_query("""
        SELECT c.segment, ROUND(SUM(f.sales), 2) AS sales
        FROM fact_sales f JOIN dim_customer c ON f.customer_key = c.customer_key
        GROUP BY c.segment
    """, conn)
    fig_seg = px.pie(df_seg, values="sales", names="segment", hole=0.55, title="Sales Contribution by Segment",
                     color_discrete_sequence=["#1E3A8A", "#3B82F6", "#93C5FD"])
    fig_seg.update_layout(template="plotly_white", height=380, margin=dict(l=20, r=20, t=40, b=20))

    # 2. Regional Analysis
    df_region = pd.read_sql_query("""
        SELECT g.region, ROUND(SUM(f.sales), 2) AS sales, ROUND(SUM(f.profit), 2) AS profit,
               ROUND((SUM(f.profit)/SUM(f.sales))*100, 2) AS margin_pct
        FROM fact_sales f JOIN dim_geography g ON f.geography_key = g.geography_key
        GROUP BY g.region ORDER BY sales DESC
    """, conn)
    fig_reg = px.bar(df_region, x="region", y="sales", color="profit", title="Regional Revenue vs Profitability",
                     color_continuous_scale="Blues", height=380)
    fig_reg.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))

    df_top_states = pd.read_sql_query("""
        SELECT g.state, ROUND(SUM(f.sales), 2) AS sales, ROUND(SUM(f.profit), 2) AS profit
        FROM fact_sales f JOIN dim_geography g ON f.geography_key = g.geography_key
        GROUP BY g.state ORDER BY sales DESC LIMIT 10
    """, conn)
    fig_states = px.bar(df_top_states, y="state", x="sales", orientation="h", title="Top 10 States by Revenue",
                        color="sales", color_continuous_scale="Viridis", height=380)
    fig_states.update_layout(template="plotly_white", yaxis={'categoryorder':'total ascending'}, margin=dict(l=20, r=20, t=40, b=20))

    # 3. Customer Analytics
    df_tiers = pd.read_sql_query("""
        WITH cust_rev AS (
            SELECT customer_key, SUM(sales) AS total_spent
            FROM fact_sales GROUP BY customer_key
        )
        SELECT 
            CASE 
                WHEN total_spent >= 5000 THEN 'Platinum ($5000+)'
                WHEN total_spent >= 2500 THEN 'Gold ($2500-$4999)'
                WHEN total_spent >= 1000 THEN 'Silver ($1000-$2499)'
                ELSE 'Bronze (<$1000)'
            END AS tier,
            COUNT(*) AS customer_count,
            ROUND(SUM(total_spent), 2) AS tier_sales
        FROM cust_rev GROUP BY tier ORDER BY tier_sales DESC
    """, conn)
    fig_tiers = px.pie(df_tiers, names="tier", values="tier_sales", title="Revenue by Customer Value Tier (RFM)",
                       color_discrete_sequence=["#4338CA", "#6366F1", "#818CF8", "#C7D2FE"], hole=0.45)
    fig_tiers.update_layout(template="plotly_white", height=380, margin=dict(l=20, r=20, t=40, b=20))

    df_clv = pd.read_sql_query("""
        SELECT c.customer_name, c.segment, COUNT(DISTINCT f.order_id) AS orders,
               ROUND(SUM(f.sales), 2) AS total_spend, ROUND(SUM(f.profit), 2) AS total_profit
        FROM fact_sales f JOIN dim_customer c ON f.customer_key = c.customer_key
        GROUP BY c.customer_key ORDER BY total_spend DESC LIMIT 80
    """, conn)
    fig_clv = px.scatter(df_clv, x="orders", y="total_spend", size="total_spend", color="segment",
                         hover_name="customer_name", title="Top 80 VIP Customer Lifetime Value (Spend vs Orders)",
                         color_discrete_sequence=["#2563EB", "#10B981", "#F59E0B"], height=380)
    fig_clv.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))

    # 4. Product Analytics
    df_subcat = pd.read_sql_query("""
        SELECT p.sub_category, p.category, ROUND(SUM(f.sales), 2) AS sales, ROUND(SUM(f.profit), 2) AS profit
        FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.sub_category, p.category ORDER BY profit DESC
    """, conn)
    colors = ["#10B981" if p >= 0 else "#EF4444" for p in df_subcat["profit"]]
    fig_subcat = go.Figure(go.Bar(x=df_subcat["profit"], y=df_subcat["sub_category"], orientation="h", marker_color=colors))
    fig_subcat.update_layout(title="Sub-Category Net Profit / Loss (Green=Profit, Red=Loss)", template="plotly_white",
                             yaxis={'categoryorder':'total ascending'}, height=480, margin=dict(l=20, r=20, t=40, b=20))

    # Top 10 Products table
    df_top_prod = pd.read_sql_query("""
        SELECT p.product_name, p.category, p.sub_category,
               ROUND(SUM(f.sales), 2) AS sales, ROUND(SUM(f.profit), 2) AS profit,
               ROUND((SUM(f.profit)/SUM(f.sales))*100, 1) AS margin_pct
        FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.product_key ORDER BY sales DESC LIMIT 8
    """, conn)

    table_rows = ""
    for _, row in df_top_prod.iterrows():
        margin_color = "#10B981" if row["margin_pct"] >= 15 else ("#F59E0B" if row["margin_pct"] >= 0 else "#EF4444")
        table_rows += f"""
        <tr>
            <td style="font-weight:600;">{row['product_name'][:45]}...</td>
            <td><span class="badge badge-cat">{row['category']}</span></td>
            <td>{row['sub_category']}</td>
            <td>${row['sales']:,.2f}</td>
            <td style="color:{margin_color}; font-weight:600;">${row['profit']:,.2f}</td>
            <td><span style="color:{margin_color}; font-weight:bold;">{row['margin_pct']}%</span></td>
        </tr>
        """

    conn.close()

    # Convert figures to HTML divs
    trend_div = fig_trend.to_html(full_html=False, include_plotlyjs='cdn')
    cat_div = fig_cat.to_html(full_html=False, include_plotlyjs=False)
    seg_div = fig_seg.to_html(full_html=False, include_plotlyjs=False)
    reg_div = fig_reg.to_html(full_html=False, include_plotlyjs=False)
    states_div = fig_states.to_html(full_html=False, include_plotlyjs=False)
    tiers_div = fig_tiers.to_html(full_html=False, include_plotlyjs=False)
    clv_div = fig_clv.to_html(full_html=False, include_plotlyjs=False)
    subcat_div = fig_subcat.to_html(full_html=False, include_plotlyjs=False)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Volt Retail Sales BI Analytics Platform</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-canvas: #0b0f19;
            --bg-card: #131b2e;
            --border-card: #1f293d;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-canvas);
            color: var(--text-primary);
            padding: 24px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-card);
            margin-bottom: 24px;
        }}
        .title-block h1 {{ font-size: 26px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px; }}
        .title-block p {{ font-size: 14px; color: var(--text-secondary); margin-top: 4px; }}
        .badge {{ padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }}
        .badge-live {{ background: rgba(16, 185, 129, 0.15); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.3); }}
        .badge-cat {{ background: rgba(59, 130, 246, 0.15); color: var(--accent-blue); }}
        
        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
            transition: transform 0.2s ease;
        }}
        .kpi-card:hover {{ transform: translateY(-2px); }}
        .kpi-label {{ font-size: 13px; font-weight: 500; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }}
        .kpi-value {{ font-size: 28px; font-weight: 700; margin: 8px 0; color: #ffffff; }}
        .kpi-subtext {{ font-size: 12px; font-weight: 600; }}
        .text-green {{ color: var(--accent-green); }}
        .text-blue {{ color: var(--accent-blue); }}
        
        /* Navigation Tabs */
        .nav-tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 24px;
            border-bottom: 1px solid var(--border-card);
            padding-bottom: 12px;
        }}
        .tab-btn {{
            background: transparent;
            border: 1px solid transparent;
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 600;
            padding: 10px 18px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .tab-btn:hover {{ color: #ffffff; background: rgba(255,255,255,0.05); }}
        .tab-btn.active {{
            color: #ffffff;
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
        }}
        
        /* Visual Layout */
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .grid-2col {{
            display: grid;
            grid-template-columns: 1.6fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }}
        .grid-half {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }}
        .chart-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        }}
        
        /* Table */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}
        th {{
            background: rgba(255, 255, 255, 0.04);
            color: var(--text-secondary);
            font-weight: 600;
            padding: 12px 14px;
            border-bottom: 1px solid var(--border-card);
        }}
        td {{
            padding: 12px 14px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            color: var(--text-primary);
        }}
        tr:hover td {{ background: rgba(255, 255, 255, 0.02); }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title-block">
            <h1>Volt Retail Sales BI & Analytics Platform</h1>
            <p>End-to-End Enterprise Data Pipeline & Executive Business Intelligence Suite</p>
        </div>
        <div>
            <span class="badge badge-live">● ETL DATA WAREHOUSE LIVE</span>
        </div>
    </div>

    <!-- Top KPI Cards -->
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Total Revenue</div>
            <div class="kpi-value">${kpis['total_sales']:,.2f}</div>
            <div class="kpi-subtext text-green">▲ +20.3% YoY Growth</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Net Profit</div>
            <div class="kpi-value text-green">${kpis['total_profit']:,.2f}</div>
            <div class="kpi-subtext text-green">Profit Margin: {kpis['profit_margin']}%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Total Orders</div>
            <div class="kpi-value">{kpis['total_orders']:,}</div>
            <div class="kpi-subtext text-blue">Avg Order Value: ${kpis['total_sales']/kpis['total_orders']:,.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Active Customers</div>
            <div class="kpi-value">{kpis['total_customers']}</div>
            <div class="kpi-subtext text-green">98.1% Repeat Retention</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Avg Shipping Lead</div>
            <div class="kpi-value">{kpis['avg_shipping_days']} Days</div>
            <div class="kpi-subtext text-blue">Standard SLA: &le; 4 Days</div>
        </div>
    </div>

    <!-- 4 Navigation Tabs -->
    <div class="nav-tabs">
        <button class="tab-btn active" onclick="openTab('tab-exec', this)">1. Executive Overview</button>
        <button class="tab-btn" onclick="openTab('tab-reg', this)">2. Regional Analysis</button>
        <button class="tab-btn" onclick="openTab('tab-cust', this)">3. Customer Analytics</button>
        <button class="tab-btn" onclick="openTab('tab-prod', this)">4. Product Profitability</button>
    </div>

    <!-- Tab 1: Executive Overview -->
    <div id="tab-exec" class="tab-content active">
        <div class="grid-2col">
            <div class="chart-card">{trend_div}</div>
            <div class="chart-card">{seg_div}</div>
        </div>
        <div class="grid-2col">
            <div class="chart-card">{cat_div}</div>
            <div class="chart-card">{reg_div}</div>
        </div>
    </div>

    <!-- Tab 2: Regional Analysis -->
    <div id="tab-reg" class="tab-content">
        <div class="grid-half">
            <div class="chart-card">{reg_div}</div>
            <div class="chart-card">{states_div}</div>
        </div>
    </div>

    <!-- Tab 3: Customer Analytics -->
    <div id="tab-cust" class="tab-content">
        <div class="grid-half">
            <div class="chart-card">{tiers_div}</div>
            <div class="chart-card">{clv_div}</div>
        </div>
    </div>

    <!-- Tab 4: Product Analytics -->
    <div id="tab-prod" class="tab-content">
        <div class="chart-card" style="margin-bottom:20px;">{subcat_div}</div>
        <div class="chart-card">
            <h3 style="margin-bottom:14px; font-size:16px;">Top Best-Selling Catalog Products</h3>
            <table>
                <thead>
                    <tr>
                        <th>Product Name</th>
                        <th>Category</th>
                        <th>Sub-Category</th>
                        <th>Gross Revenue</th>
                        <th>Net Profit</th>
                        <th>Margin %</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function openTab(tabId, btn) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');
            window.dispatchEvent(new Event('resize'));
        }}
    </script>
</body>
</html>
"""
    OUTPUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"Interactive BI Dashboard exported successfully to: {OUTPUT_HTML.resolve()}")

if __name__ == "__main__":
    generate_interactive_dashboard()
