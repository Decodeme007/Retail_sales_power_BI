"""
Transformation and Star Schema Dimensional Modeling Module.
Constructs conformed dimension tables and the central fact table.
Generates surrogate keys, date dimension, and key business metrics.
"""

import pandas as pd
import numpy as np
import hashlib
import logging
from datetime import datetime

logger = logging.getLogger("ETL_Transform")

def generate_dim_date(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    """Generates an exhaustive enterprise Calendar Dimension table."""
    logger.info(f"Generating Date Dimension from {start_date.date()} to {end_date.date()}...")
    date_range = pd.date_range(start=start_date, end=end_date, freq="D")
    
    df_date = pd.DataFrame({"full_date": date_range})
    df_date["date_key"] = df_date["full_date"].dt.strftime("%Y%m%d").astype(int)
    df_date["year"] = df_date["full_date"].dt.year
    df_date["quarter"] = df_date["full_date"].dt.quarter
    df_date["quarter_name"] = "Q" + df_date["quarter"].astype(str)
    df_date["month"] = df_date["full_date"].dt.month
    df_date["month_name"] = df_date["full_date"].dt.strftime("%B")
    df_date["month_short"] = df_date["full_date"].dt.strftime("%b")
    df_date["year_month"] = df_date["full_date"].dt.strftime("%Y-%m")
    df_date["day_of_month"] = df_date["full_date"].dt.day
    df_date["day_of_week"] = df_date["full_date"].dt.dayofweek + 1 # 1=Mon, 7=Sun
    df_date["day_name"] = df_date["full_date"].dt.strftime("%A")
    df_date["is_weekend"] = df_date["day_of_week"].isin([6, 7]).astype(int)
    
    # Fiscal calendar (assuming July 1 fiscal start)
    df_date["fiscal_year"] = np.where(df_date["month"] >= 7, df_date["year"] + 1, df_date["year"])
    df_date["fiscal_quarter"] = ((df_date["month"] - 7) % 12 // 3) + 1
    
    return df_date

def build_star_schema(customers: pd.DataFrame, 
                      products: pd.DataFrame, 
                      geography: pd.DataFrame, 
                      orders: pd.DataFrame, 
                      order_items: pd.DataFrame):
    """
    Transforms raw entities into a conformed Star Schema:
    - dim_customer
    - dim_product
    - dim_geography
    - dim_date
    - fact_sales
    """
    logger.info("Transforming into Star Schema Dimensional Model...")

    # 1. dim_customer
    dim_customer = customers[["customer_id", "customer_name", "segment"]].drop_duplicates().copy()
    dim_customer.sort_values(by="customer_id", inplace=True)
    dim_customer.reset_index(drop=True, inplace=True)
    dim_customer.insert(0, "customer_key", dim_customer.index + 1)

    # 2. dim_product
    dim_product = products[["product_id", "product_name", "category", "sub_category"]].drop_duplicates().copy()
    dim_product.sort_values(by="product_id", inplace=True)
    dim_product.reset_index(drop=True, inplace=True)
    dim_product.insert(0, "product_key", dim_product.index + 1)

    # 3. dim_geography
    dim_geography = geography[["postal_code", "city", "state", "region", "country"]].drop_duplicates().copy()
    dim_geography["postal_code"] = dim_geography["postal_code"].astype(str).str.strip().str.zfill(5)
    dim_geography.sort_values(by=["state", "city", "postal_code"], inplace=True)
    dim_geography.reset_index(drop=True, inplace=True)
    dim_geography.insert(0, "geography_key", dim_geography.index + 1)

    # 4. dim_date
    min_date = min(orders["order_date"].min(), orders["ship_date"].min())
    max_date = max(orders["order_date"].max(), orders["ship_date"].max())
    dim_date = generate_dim_date(min_date, max_date)

    # 5. fact_sales construction
    # Merge order items with orders header
    merged = pd.merge(order_items, orders, on="order_id", how="inner")
    merged["postal_code"] = merged["postal_code"].astype(str).str.strip().str.zfill(5)
    
    # Merge surrogate keys
    merged = pd.merge(merged, dim_customer[["customer_id", "customer_key"]], on="customer_id", how="inner")
    merged = pd.merge(merged, dim_product[["product_id", "product_key"]], on="product_id", how="inner")
    merged = pd.merge(merged, dim_geography[["postal_code", "geography_key"]], on="postal_code", how="inner")

    # Metrics and derived calculations
    merged["order_date_key"] = merged["order_date"].dt.strftime("%Y%m%d").astype(int)
    merged["ship_date_key"] = merged["ship_date"].dt.strftime("%Y%m%d").astype(int)
    merged["sales"] = merged["sales"].round(2)
    merged["quantity"] = merged["quantity"].astype(int)
    merged["discount"] = merged["discount"].round(4)
    merged["profit"] = merged["profit"].round(2)
    
    # Financial metrics
    merged["cost"] = (merged["sales"] - merged["profit"]).round(2)
    merged["profit_margin_pct"] = np.where(merged["sales"] > 0, ((merged["profit"] / merged["sales"]) * 100).round(2), 0.0)
    merged["unit_price"] = (merged["sales"] / merged["quantity"]).round(2)
    merged["shipping_days"] = (merged["ship_date"] - merged["order_date"]).dt.days
    merged["is_delayed"] = (merged["shipping_days"] > 4).astype(int)
    merged["is_profitable"] = (merged["profit"] > 0).astype(int)

    # Select final fact columns
    fact_sales = merged[[
        "order_id",
        "order_date_key",
        "ship_date_key",
        "customer_key",
        "product_key",
        "geography_key",
        "ship_mode",
        "sales",
        "quantity",
        "discount",
        "profit",
        "cost",
        "profit_margin_pct",
        "unit_price",
        "shipping_days",
        "is_delayed",
        "is_profitable"
    ]].copy()

    fact_sales.reset_index(drop=True, inplace=True)
    fact_sales.insert(0, "sales_id", fact_sales.index + 1)
    
    # Incremental / CDC row hash
    def compute_row_hash(row):
        unique_str = f"{row['order_id']}_{row['product_key']}_{row['sales']}_{row['profit']}"
        return hashlib.md5(unique_str.encode()).hexdigest()

    fact_sales["row_hash"] = fact_sales.apply(compute_row_hash, axis=1)
    fact_sales["etl_loaded_at"] = datetime.utcnow().isoformat()

    logger.info(f"Star schema assembled successfully: fact_sales has {len(fact_sales)} rows.")
    return {
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_geography": dim_geography,
        "dim_date": dim_date,
        "fact_sales": fact_sales
    }
