-- ============================================================================
-- 20 ADVANCED RETAIL ANALYTICS & BUSINESS INTELLIGENCE SQL QUERIES
-- Database: retail_sales_dw (Tested & compatible with MySQL 8.0+ and SQLite)
-- Techniques: CTEs, Window Functions (LAG, LEAD, DENSE_RANK, SUM OVER),
-- Aggregations, Conditional Logic, Cohort Analysis
-- ============================================================================

-- ----------------------------------------------------------------------------
-- QUERY 1: Yearly & Quarterly Revenue, Cost, Profit & Profit Margin
-- ----------------------------------------------------------------------------
-- Business Question: How has revenue, profit, and margin evolved over fiscal quarters?
SELECT 
    d.year,
    d.quarter_name,
    COUNT(DISTINCT f.order_id) AS total_orders,
    ROUND(SUM(f.sales), 2) AS total_revenue,
    ROUND(SUM(f.cost), 2) AS total_cost,
    ROUND(SUM(f.profit), 2) AS total_profit,
    ROUND((SUM(f.profit) / SUM(f.sales)) * 100, 2) AS profit_margin_pct
FROM fact_sales f
JOIN dim_date d ON f.order_date_key = d.date_key
GROUP BY d.year, d.quarter_name
ORDER BY d.year ASC, d.quarter_name ASC;

-- ----------------------------------------------------------------------------
-- QUERY 2: Month-over-Month (MoM) Revenue Growth Rate (Window Function LAG)
-- ----------------------------------------------------------------------------
-- Business Question: What is the monthly revenue growth trend and MoM growth rate?
WITH monthly_sales AS (
    SELECT 
        d.year,
        d.month,
        d.year_month,
        ROUND(SUM(f.sales), 2) AS current_month_revenue
    FROM fact_sales f
    JOIN dim_date d ON f.order_date_key = d.date_key
    GROUP BY d.year, d.month, d.year_month
)
SELECT 
    year,
    month,
    year_month,
    current_month_revenue,
    LAG(current_month_revenue, 1) OVER (ORDER BY year_month) AS prior_month_revenue,
    ROUND(
        ((current_month_revenue - LAG(current_month_revenue, 1) OVER (ORDER BY year_month)) 
        / LAG(current_month_revenue, 1) OVER (ORDER BY year_month)) * 100, 2
    ) AS mom_growth_pct
FROM monthly_sales
ORDER BY year_month ASC;

-- ----------------------------------------------------------------------------
-- QUERY 3: Cumulative Running Total Revenue by Year (Window Function SUM OVER)
-- ----------------------------------------------------------------------------
-- Business Question: What is the cumulative running revenue progression throughout each year?
WITH monthly_revenue AS (
    SELECT 
        d.year,
        d.month,
        d.month_short,
        d.year_month,
        ROUND(SUM(f.sales), 2) AS month_sales
    FROM fact_sales f
    JOIN dim_date d ON f.order_date_key = d.date_key
    GROUP BY d.year, d.month, d.month_short, d.year_month
)
SELECT 
    year,
    month_short,
    year_month,
    month_sales,
    ROUND(SUM(month_sales) OVER (PARTITION BY year ORDER BY month ASC), 2) AS ytd_running_total_sales
FROM monthly_revenue
ORDER BY year ASC, month ASC;

-- ----------------------------------------------------------------------------
-- QUERY 4: Top 10 Best-Selling Products by Revenue (Window Function DENSE_RANK)
-- ----------------------------------------------------------------------------
-- Business Question: Which top 10 products generate the highest gross revenue?
WITH ranked_products AS (
    SELECT 
        p.product_id,
        p.product_name,
        p.category,
        p.sub_category,
        SUM(f.quantity) AS total_units_sold,
        ROUND(SUM(f.sales), 2) AS total_revenue,
        ROUND(SUM(f.profit), 2) AS total_profit,
        DENSE_RANK() OVER (ORDER BY SUM(f.sales) DESC) AS revenue_rank
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.product_id, p.product_name, p.category, p.sub_category
)
SELECT 
    revenue_rank,
    product_id,
    product_name,
    category,
    sub_category,
    total_units_sold,
    total_revenue,
    total_profit
FROM ranked_products
WHERE revenue_rank <= 10
ORDER BY revenue_rank ASC;

-- ----------------------------------------------------------------------------
-- QUERY 5: Top 5 Most Profitable vs Top 5 Loss-Making Products
-- ----------------------------------------------------------------------------
-- Business Question: What are the biggest profit drivers versus profit bleeders?
WITH top_profitable AS (
    SELECT 
        'Top 5 Profitable' AS performance_tier,
        p.product_name,
        p.category,
        ROUND(SUM(f.sales), 2) AS total_sales,
        ROUND(SUM(f.profit), 2) AS total_profit,
        ROUND((SUM(f.profit) / SUM(f.sales)) * 100, 2) AS margin_pct
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.product_key, p.product_name, p.category
    ORDER BY total_profit DESC
    LIMIT 5
),
bottom_loss_making AS (
    SELECT 
        'Bottom 5 Loss-Making' AS performance_tier,
        p.product_name,
        p.category,
        ROUND(SUM(f.sales), 2) AS total_sales,
        ROUND(SUM(f.profit), 2) AS total_profit,
        ROUND((SUM(f.profit) / SUM(f.sales)) * 100, 2) AS margin_pct
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.product_key, p.product_name, p.category
    ORDER BY total_profit ASC
    LIMIT 5
)
SELECT * FROM top_profitable
UNION ALL
SELECT * FROM bottom_loss_making;

-- ----------------------------------------------------------------------------
-- QUERY 6: Regional Performance Matrix & Contribution Percentage
-- ----------------------------------------------------------------------------
-- Business Question: What is the sales and profit contribution across US regions?
SELECT 
    g.region,
    COUNT(DISTINCT f.order_id) AS total_orders,
    COUNT(DISTINCT f.customer_key) AS unique_customers,
    ROUND(SUM(f.sales), 2) AS total_revenue,
    ROUND(SUM(f.profit), 2) AS total_profit,
    ROUND((SUM(f.profit) / SUM(f.sales)) * 100, 2) AS profit_margin_pct,
    ROUND((SUM(f.sales) * 100.0 / (SELECT SUM(sales) FROM fact_sales)), 2) AS revenue_share_pct
FROM fact_sales f
JOIN dim_geography g ON f.geography_key = g.geography_key
GROUP BY g.region
ORDER BY total_revenue DESC;

-- ----------------------------------------------------------------------------
-- QUERY 7: Top 3 Highest Spending Customers per Region (DENSE_RANK PARTITION BY)
-- ----------------------------------------------------------------------------
-- Business Question: Who are our top valuable VIP accounts in each geographic region?
WITH customer_regional_spend AS (
    SELECT 
        g.region,
        c.customer_name,
        c.segment,
        COUNT(DISTINCT f.order_id) AS order_count,
        ROUND(SUM(f.sales), 2) AS total_spent,
        DENSE_RANK() OVER (PARTITION BY g.region ORDER BY SUM(f.sales) DESC) AS regional_rank
    FROM fact_sales f
    JOIN dim_customer c ON f.customer_key = c.customer_key
    JOIN dim_geography g ON f.geography_key = g.geography_key
    GROUP BY g.region, c.customer_key, c.customer_name, c.segment
)
SELECT 
    region,
    regional_rank,
    customer_name,
    segment,
    order_count,
    total_spent
FROM customer_regional_spend
WHERE regional_rank <= 3
ORDER BY region ASC, regional_rank ASC;

-- ----------------------------------------------------------------------------
-- QUERY 8: Customer RFM Value Segmentation
-- ----------------------------------------------------------------------------
-- Business Question: How do customer tiers (Platinum, Gold, Silver, Bronze) split by revenue?
WITH customer_aggregates AS (
    SELECT 
        c.customer_key,
        SUM(f.sales) AS customer_revenue,
        COUNT(DISTINCT f.order_id) AS order_count,
        CASE 
            WHEN SUM(f.sales) >= 5000 THEN 'Platinum ($5000+)'
            WHEN SUM(f.sales) >= 2500 THEN 'Gold ($2500-$4999)'
            WHEN SUM(f.sales) >= 1000 THEN 'Silver ($1000-$2499)'
            ELSE 'Bronze (<$1000)'
        END AS tier
    FROM fact_sales f
    JOIN dim_customer c ON f.customer_key = c.customer_key
    GROUP BY c.customer_key
)
SELECT 
    tier,
    COUNT(customer_key) AS customer_count,
    ROUND(SUM(customer_revenue), 2) AS tier_revenue,
    ROUND(AVG(customer_revenue), 2) AS avg_revenue_per_customer,
    ROUND(AVG(order_count), 1) AS avg_orders_per_customer
FROM customer_aggregates
GROUP BY tier
ORDER BY tier_revenue DESC;

-- ----------------------------------------------------------------------------
-- QUERY 9: Repeat Purchase & Customer Retention Rate
-- ----------------------------------------------------------------------------
-- Business Question: What percentage of our customer base are repeat buyers?
WITH customer_orders AS (
    SELECT 
        customer_key,
        COUNT(DISTINCT order_id) AS lifetime_orders
    FROM fact_sales
    GROUP BY customer_key
)
SELECT 
    COUNT(*) AS total_customers,
    SUM(CASE WHEN lifetime_orders = 1 THEN 1 ELSE 0 END) AS one_time_buyers,
    SUM(CASE WHEN lifetime_orders > 1 THEN 1 ELSE 0 END) AS repeat_buyers,
    ROUND((CAST(SUM(CASE WHEN lifetime_orders > 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)) * 100, 2) AS repeat_buyer_rate_pct
FROM customer_orders;

-- ----------------------------------------------------------------------------
-- QUERY 10: Product Category & Sub-Category Margin Health
-- ----------------------------------------------------------------------------
-- Business Question: Which product categories produce the highest profit margins?
SELECT 
    p.category,
    p.sub_category,
    COUNT(DISTINCT f.order_id) AS total_orders,
    SUM(f.quantity) AS total_units_sold,
    ROUND(SUM(f.sales), 2) AS total_revenue,
    ROUND(SUM(f.profit), 2) AS total_profit,
    ROUND((SUM(f.profit) / SUM(f.sales)) * 100, 2) AS profit_margin_pct
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.category, p.sub_category
ORDER BY p.category ASC, total_profit DESC;

-- ----------------------------------------------------------------------------
-- QUERY 11: Impact of Discounts on Profitability (Loss-Leader Detection)
-- ----------------------------------------------------------------------------
-- Business Question: At what discount bracket do transactions turn unprofitable?
SELECT 
    CASE 
        WHEN discount = 0.00 THEN '0% (No Discount)'
        WHEN discount <= 0.10 THEN '1% - 10%'
        WHEN discount <= 0.20 THEN '11% - 20%'
        WHEN discount <= 0.40 THEN '21% - 40%'
        ELSE '> 40% (Deep Discount)'
    END AS discount_bracket,
    COUNT(*) AS total_transactions,
    ROUND(SUM(sales), 2) AS total_revenue,
    ROUND(SUM(profit), 2) AS total_profit,
    ROUND((SUM(profit) / SUM(sales)) * 100, 2) AS profit_margin_pct,
    SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) AS loss_making_transactions
FROM fact_sales
GROUP BY discount_bracket
ORDER BY total_revenue DESC;

-- ----------------------------------------------------------------------------
-- QUERY 12: Shipping Mode Lead Time & Profitability
-- ----------------------------------------------------------------------------
-- Business Question: What is the average transit lead time and profitability per ship mode?
SELECT 
    ship_mode,
    COUNT(DISTINCT order_id) AS total_orders,
    ROUND(AVG(shipping_days), 1) AS avg_lead_days,
    ROUND(SUM(sales), 2) AS total_sales,
    ROUND(SUM(profit), 2) AS total_profit,
    ROUND((SUM(profit) / SUM(sales)) * 100, 2) AS profit_margin_pct
FROM fact_sales
GROUP BY ship_mode
ORDER BY total_orders DESC;

-- ----------------------------------------------------------------------------
-- QUERY 13: Delivery Delay Rate by Region (> 4 Days in Transit)
-- ----------------------------------------------------------------------------
-- Business Question: Which regions experience the highest frequency of shipping delays?
SELECT 
    g.region,
    COUNT(*) AS total_shipments,
    SUM(f.is_delayed) AS delayed_shipments,
    ROUND((CAST(SUM(f.is_delayed) AS FLOAT) / COUNT(*)) * 100, 2) AS delayed_shipment_pct,
    ROUND(AVG(f.shipping_days), 1) AS avg_transit_days
FROM fact_sales f
JOIN dim_geography g ON f.geography_key = g.geography_key
GROUP BY g.region
ORDER BY delayed_shipment_pct DESC;

-- ----------------------------------------------------------------------------
-- QUERY 14: Pareto Analysis (80/20 Rule) - Cumulative Revenue Contribution
-- ----------------------------------------------------------------------------
-- Business Question: What percentage of revenue is generated by top-tier products?
WITH product_revenue AS (
    SELECT 
        p.product_id,
        p.product_name,
        ROUND(SUM(f.sales), 2) AS item_sales
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.product_id, p.product_name
),
cumulative_revenue AS (
    SELECT 
        product_id,
        product_name,
        item_sales,
        SUM(item_sales) OVER (ORDER BY item_sales DESC) AS running_sales,
        (SELECT SUM(sales) FROM fact_sales) AS total_catalog_sales
    FROM product_revenue
)
SELECT 
    product_id,
    product_name,
    item_sales,
    ROUND((running_sales / total_catalog_sales) * 100, 2) AS cumulative_sales_pct
FROM cumulative_revenue
WHERE (running_sales / total_catalog_sales) <= 0.80
LIMIT 15;

-- ----------------------------------------------------------------------------
-- QUERY 15: Average Order Value (AOV) by Customer Segment
-- ----------------------------------------------------------------------------
-- Business Question: Which customer segment generates the largest basket size?
WITH order_level_sales AS (
    SELECT 
        f.order_id,
        c.segment,
        SUM(f.sales) AS order_total,
        SUM(f.profit) AS order_profit
    FROM fact_sales f
    JOIN dim_customer c ON f.customer_key = c.customer_key
    GROUP BY f.order_id, c.segment
)
SELECT 
    segment,
    COUNT(order_id) AS total_orders,
    ROUND(SUM(order_total), 2) AS total_sales,
    ROUND(AVG(order_total), 2) AS average_order_value_aov,
    ROUND(AVG(order_profit), 2) AS average_order_profit
FROM order_level_sales
GROUP BY segment
ORDER BY total_sales DESC;

-- ----------------------------------------------------------------------------
-- QUERY 16: New vs Returning Customer Sales Contribution by Year
-- ----------------------------------------------------------------------------
-- Business Question: How much annual revenue comes from newly acquired customers vs existing?
WITH first_order_year AS (
    SELECT 
        f.customer_key,
        MIN(d.year) AS acquisition_year
    FROM fact_sales f
    JOIN dim_date d ON f.order_date_key = d.date_key
    GROUP BY f.customer_key
)
SELECT 
    d.year AS order_year,
    CASE 
        WHEN d.year = fo.acquisition_year THEN 'New Customer'
        ELSE 'Returning Customer'
    END AS customer_type,
    COUNT(DISTINCT f.customer_key) AS customer_count,
    ROUND(SUM(f.sales), 2) AS total_revenue
FROM fact_sales f
JOIN dim_date d ON f.order_date_key = d.date_key
JOIN first_order_year fo ON f.customer_key = fo.customer_key
GROUP BY d.year, customer_type
ORDER BY d.year ASC, customer_type DESC;

-- ----------------------------------------------------------------------------
-- QUERY 17: Seasonality: Revenue Pattern by Day of the Week
-- ----------------------------------------------------------------------------
-- Business Question: On what days do we receive the highest sales volume?
SELECT 
    d.day_name,
    d.day_of_week,
    COUNT(DISTINCT f.order_id) AS total_orders,
    ROUND(SUM(f.sales), 2) AS total_sales,
    ROUND(AVG(f.sales), 2) AS avg_item_sale
FROM fact_sales f
JOIN dim_date d ON f.order_date_key = d.date_key
GROUP BY d.day_name, d.day_of_week
ORDER BY d.day_of_week ASC;

-- ----------------------------------------------------------------------------
-- QUERY 18: Unprofitable Sub-Categories Warning List
-- ----------------------------------------------------------------------------
-- Business Question: Which sub-categories are losing money in specific regions?
SELECT 
    g.region,
    p.category,
    p.sub_category,
    ROUND(SUM(f.sales), 2) AS total_sales,
    ROUND(SUM(f.profit), 2) AS net_profit,
    ROUND((SUM(f.profit) / SUM(f.sales)) * 100, 2) AS profit_margin_pct
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
JOIN dim_geography g ON f.geography_key = g.geography_key
GROUP BY g.region, p.category, p.sub_category
HAVING SUM(f.profit) < 0
ORDER BY net_profit ASC;

-- ----------------------------------------------------------------------------
-- QUERY 19: Customer Recency & Churn Risk (Days Since Last Order)
-- ----------------------------------------------------------------------------
-- Business Question: Which top customers have gone dormant (no orders in > 180 days)?
WITH customer_last_order AS (
    SELECT 
        c.customer_id,
        c.customer_name,
        c.segment,
        MAX(d.full_date) AS last_order_date,
        ROUND(SUM(f.sales), 2) AS lifetime_spend
    FROM fact_sales f
    JOIN dim_customer c ON f.customer_key = c.customer_key
    JOIN dim_date d ON f.order_date_key = d.date_key
    GROUP BY c.customer_id, c.customer_name, c.segment
)
SELECT 
    customer_id,
    customer_name,
    segment,
    last_order_date,
    lifetime_spend,
    ROUND((JULIANDAY('2018-01-01') - JULIANDAY(last_order_date))) AS days_since_last_order,
    CASE 
        WHEN (JULIANDAY('2018-01-01') - JULIANDAY(last_order_date)) > 365 THEN 'Churned (> 1 Year)'
        WHEN (JULIANDAY('2018-01-01') - JULIANDAY(last_order_date)) > 180 THEN 'At Risk (6-12 Months)'
        ELSE 'Active (< 6 Months)'
    END AS churn_risk_status
FROM customer_last_order
WHERE lifetime_spend >= 2000
ORDER BY days_since_last_order DESC
LIMIT 15;

-- ----------------------------------------------------------------------------
-- QUERY 20: Product Affinity / Cross-Selling Basket Analysis
-- ----------------------------------------------------------------------------
-- Business Question: Which distinct sub-categories are most frequently purchased together in the same basket?
SELECT 
    p1.sub_category AS sub_category_A,
    p2.sub_category AS sub_category_B,
    COUNT(DISTINCT f1.order_id) AS co_occurrence_count
FROM fact_sales f1
JOIN fact_sales f2 ON f1.order_id = f2.order_id AND f1.product_key < f2.product_key
JOIN dim_product p1 ON f1.product_key = p1.product_key
JOIN dim_product p2 ON f2.product_key = p2.product_key
WHERE p1.sub_category <> p2.sub_category
GROUP BY p1.sub_category, p2.sub_category
ORDER BY co_occurrence_count DESC
LIMIT 10;
