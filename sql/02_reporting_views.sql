-- ============================================================================
-- RETAIL SALES ENTERPRISE DATA WAREHOUSE - REPORTING VIEWS
-- Compatible with MySQL 8.0+ and SQLite
-- ============================================================================

-- ----------------------------------------------------------------------------
-- VIEW 1: Executive Monthly Performance View
-- Powers the Executive Overview Dashboard Page
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_executive_monthly_summary;
CREATE VIEW vw_executive_monthly_summary AS
SELECT 
    d.year,
    d.quarter_name,
    d.month,
    d.month_short,
    d.year_month,
    COUNT(DISTINCT f.order_id) AS total_orders,
    COUNT(DISTINCT f.customer_key) AS active_customers,
    SUM(f.quantity) AS total_units_sold,
    ROUND(SUM(f.sales), 2) AS total_revenue,
    ROUND(SUM(f.cost), 2) AS total_cost,
    ROUND(SUM(f.profit), 2) AS total_profit,
    ROUND((SUM(f.profit) / SUM(f.sales)) * 100, 2) AS profit_margin_pct,
    ROUND(AVG(f.discount) * 100, 2) AS avg_discount_pct,
    ROUND(AVG(f.shipping_days), 1) AS avg_shipping_days,
    ROUND((CAST(SUM(f.is_delayed) AS FLOAT) / COUNT(*)) * 100, 2) AS delayed_delivery_rate_pct
FROM fact_sales f
JOIN dim_date d ON f.order_date_key = d.date_key
GROUP BY d.year, d.quarter_name, d.month, d.month_short, d.year_month;

-- ----------------------------------------------------------------------------
-- VIEW 2: Regional Sales & Profitability View
-- Powers the Regional & Geospatial Dashboard Page
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_regional_performance;
CREATE VIEW vw_regional_performance AS
SELECT 
    g.region,
    g.state,
    g.city,
    COUNT(DISTINCT f.order_id) AS total_orders,
    COUNT(DISTINCT f.customer_key) AS customer_count,
    ROUND(SUM(f.sales), 2) AS total_revenue,
    ROUND(SUM(f.profit), 2) AS total_profit,
    ROUND((SUM(f.profit) / SUM(f.sales)) * 100, 2) AS profit_margin_pct,
    ROUND(AVG(f.discount) * 100, 2) AS avg_discount_pct,
    SUM(f.quantity) AS units_sold
FROM fact_sales f
JOIN dim_geography g ON f.geography_key = g.geography_key
GROUP BY g.region, g.state, g.city;

-- ----------------------------------------------------------------------------
-- VIEW 3: Customer Value & RFM Segmentation View
-- Powers the Customer Analytics Dashboard Page
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_customer_segmentation;
CREATE VIEW vw_customer_segmentation AS
SELECT 
    c.customer_key,
    c.customer_id,
    c.customer_name,
    c.segment,
    COUNT(DISTINCT f.order_id) AS lifetime_orders,
    ROUND(SUM(f.sales), 2) AS lifetime_revenue,
    ROUND(SUM(f.profit), 2) AS lifetime_profit,
    ROUND(AVG(f.sales), 2) AS avg_order_item_value,
    MIN(d.full_date) AS first_purchase_date,
    MAX(d.full_date) AS latest_purchase_date,
    CASE 
        WHEN SUM(f.sales) >= 5000 THEN 'Platinum VIP'
        WHEN SUM(f.sales) >= 2500 THEN 'Gold Tier'
        WHEN SUM(f.sales) >= 1000 THEN 'Silver Tier'
        ELSE 'Bronze / Regular'
    END AS customer_tier
FROM fact_sales f
JOIN dim_customer c ON f.customer_key = c.customer_key
JOIN dim_date d ON f.order_date_key = d.date_key
GROUP BY c.customer_key, c.customer_id, c.customer_name, c.segment;

-- ----------------------------------------------------------------------------
-- VIEW 4: Product Category & Margin Performance View
-- Powers the Product Analytics Dashboard Page
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_product_profitability;
CREATE VIEW vw_product_profitability AS
SELECT 
    p.category,
    p.sub_category,
    p.product_id,
    p.product_name,
    COUNT(DISTINCT f.order_id) AS order_appearances,
    SUM(f.quantity) AS total_quantity_sold,
    ROUND(SUM(f.sales), 2) AS total_revenue,
    ROUND(SUM(f.profit), 2) AS total_profit,
    ROUND((SUM(f.profit) / SUM(f.sales)) * 100, 2) AS profit_margin_pct,
    ROUND(AVG(f.discount) * 100, 2) AS avg_discount_pct,
    SUM(CASE WHEN f.profit < 0 THEN 1 ELSE 0 END) AS unprofitable_sales_count
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.category, p.sub_category, p.product_id, p.product_name;
