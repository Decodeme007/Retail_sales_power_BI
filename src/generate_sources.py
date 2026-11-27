"""
Generate modular enterprise raw CSV files from the downloaded retail dataset.
Adds realistic dirty edge cases (duplicates, nulls, inconsistent date formats,
negative quantities) to prove the robustness of the data quality & validation engine.
"""

import pandas as pd
import numpy as np
import os

RAW_PATH = os.path.join("data", "raw")
SOURCE_FILE = os.path.join(RAW_PATH, "sample_superstore.csv")

def generate_enterprise_sources():
    print(f"Reading master dataset from {SOURCE_FILE}...")
    df = pd.read_csv(SOURCE_FILE, encoding="latin1")

    # 1. Customers Table
    customers = df[["Customer ID", "Customer Name", "Segment"]].drop_duplicates().copy()
    customers.columns = ["customer_id", "customer_name", "segment"]
    
    # Inject deliberate dirty records to test data quality engine
    dirty_cust = pd.DataFrame([
        {"customer_id": "CUST-DIRTY-01", "customer_name": "  Corrupted Lead LLC  ", "segment": None}, # Null segment & leading whitespace
        {"customer_id": "CG-12520", "customer_name": "Claire Gute Duplicate", "segment": "Consumer"}, # Duplicate existing ID
        {"customer_id": None, "customer_name": "Ghost User", "segment": "Corporate"} # Null primary key
    ])
    customers_raw = pd.concat([customers, dirty_cust], ignore_index=True)
    customers_raw.to_csv(os.path.join(RAW_PATH, "raw_customers.csv"), index=False)
    print(f"Saved raw_customers.csv: {len(customers_raw)} rows")

    # 2. Products Table
    products = df[["Product ID", "Category", "Sub-Category", "Product Name"]].drop_duplicates(subset=["Product ID"]).copy()
    products.columns = ["product_id", "category", "sub_category", "product_name"]
    dirty_prod = pd.DataFrame([
        {"product_id": "PROD-DIRTY-01", "category": None, "sub_category": "Chairs", "product_name": "Broken Chair SKU"}, # Null category
        {"product_id": None, "category": "Technology", "sub_category": "Phones", "product_name": "Unregistered Phone"}, # Null primary key
    ])
    products_raw = pd.concat([products, dirty_prod], ignore_index=True)
    products_raw.to_csv(os.path.join(RAW_PATH, "raw_products.csv"), index=False)
    print(f"Saved raw_products.csv: {len(products_raw)} rows")

    # 3. Geography / Store Locations
    geography = df[["Country", "City", "State", "Postal Code", "Region"]].drop_duplicates().copy()
    geography.columns = ["country", "city", "state", "postal_code", "region"]
    geography["postal_code"] = geography["postal_code"].fillna(0).astype(int).astype(str).str.zfill(5)
    geography.to_csv(os.path.join(RAW_PATH, "raw_geography.csv"), index=False)
    print(f"Saved raw_geography.csv: {len(geography)} rows")

    # 4. Orders Header Table
    orders = df[["Order ID", "Order Date", "Ship Date", "Ship Mode", "Customer ID", "Postal Code"]].drop_duplicates(subset=["Order ID"]).copy()
    orders.columns = ["order_id", "order_date", "ship_date", "ship_mode", "customer_id", "postal_code"]
    orders["postal_code"] = orders["postal_code"].fillna(0).astype(int).astype(str).str.zfill(5)
    
    # Introduce messy date formatting (some MM/DD/YYYY, some YYYY-MM-DD, some string noise)
    orders.loc[orders.index % 7 == 0, "order_date"] = pd.to_datetime(orders.loc[orders.index % 7 == 0, "order_date"]).dt.strftime("%Y-%m-%d")
    
    # Add dirty orders
    dirty_orders = pd.DataFrame([
        {"order_id": "ORD-INVALID-DATE", "order_date": "not-a-date", "ship_date": "2023-01-01", "ship_mode": "Standard Class", "customer_id": "CG-12520", "postal_code": "42420"},
        {"order_id": "ORD-GHOST-CUST", "order_date": "2023-05-10", "ship_date": "2023-05-15", "ship_mode": "First Class", "customer_id": "NON-EXISTENT-999", "postal_code": "90036"}
    ])
    orders_raw = pd.concat([orders, dirty_orders], ignore_index=True)
    orders_raw.to_csv(os.path.join(RAW_PATH, "raw_orders.csv"), index=False)
    print(f"Saved raw_orders.csv: {len(orders_raw)} rows")

    # 5. Order Items / Sales Transactions Table
    items = df[["Order ID", "Product ID", "Sales", "Quantity", "Discount", "Profit"]].copy()
    items.columns = ["order_id", "product_id", "sales", "quantity", "discount", "profit"]
    
    # Add dirty transaction records (negative quantity, negative sales, corrupted formats)
    dirty_items = pd.DataFrame([
        {"order_id": "CA-2016-152156", "product_id": "FUR-BO-10001798", "sales": -50.00, "quantity": 1, "discount": 0.0, "profit": -10.0}, # Negative sales
        {"order_id": "CA-2016-152156", "product_id": "FUR-BO-10001798", "sales": 120.00, "quantity": -3, "discount": 0.1, "profit": 20.0}, # Negative quantity
        {"order_id": "CA-2016-152156", "product_id": "FUR-BO-10001798", "sales": "invalid_num", "quantity": 1, "discount": 0.0, "profit": 0.0} # String in numeric field
    ])
    items_raw = pd.concat([items, dirty_items], ignore_index=True)
    items_raw.to_csv(os.path.join(RAW_PATH, "raw_order_items.csv"), index=False)
    print(f"Saved raw_order_items.csv: {len(items_raw)} rows")

if __name__ == "__main__":
    generate_enterprise_sources()
