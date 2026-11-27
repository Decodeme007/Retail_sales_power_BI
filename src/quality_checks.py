"""
Quality checks and data validation engine.
Ensures no bad data corrupts the data warehouse.
Rejections are logged with failure reasons into data/rejected/.
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime
from pathlib import Path
from config import DATA_REJECTED_DIR

logger = logging.getLogger("ETL_QualityEngine")

def log_rejections(df_rejected: pd.DataFrame, source_name: str, reason: str) -> None:
    """Saves rejected records to data/rejected/ with reason annotation."""
    if df_rejected.empty:
        return
    
    df_out = df_rejected.copy()
    df_out["rejection_reason"] = reason
    df_out["rejected_at"] = datetime.utcnow().isoformat()
    
    out_file = DATA_REJECTED_DIR / f"{source_name}_rejected.csv"
    mode = "a" if out_file.exists() else "w"
    header = not out_file.exists()
    
    df_out.to_csv(out_file, mode=mode, header=header, index=False)
    logger.warning(f"[{source_name}] Rejected {len(df_rejected)} records. Reason: {reason}. Saved to {out_file.name}")

def validate_customers(df: pd.DataFrame) -> pd.DataFrame:
    """Validates raw customer records."""
    logger.info("Validating Customers...")
    df = df.copy()
    initial_count = len(df)
    
    # 1. Null Primary Key check
    null_pk_mask = df["customer_id"].isna() | (df["customer_id"].astype(str).str.strip() == "")
    if null_pk_mask.any():
        log_rejections(df[null_pk_mask], "customers", "NULL_OR_EMPTY_CUSTOMER_ID")
        df = df[~null_pk_mask].copy()

    # 2. Duplicate Primary Key check
    dup_mask = df.duplicated(subset=["customer_id"], keep="first")
    if dup_mask.any():
        log_rejections(df[dup_mask], "customers", "DUPLICATE_CUSTOMER_ID")
        df = df[~dup_mask].copy()

    # Clean text columns
    df["customer_name"] = df["customer_name"].astype(str).str.strip().str.title()
    df["segment"] = df["segment"].fillna("Consumer").astype(str).str.strip().str.title()
    
    logger.info(f"Customers validation complete. Kept {len(df)} of {initial_count} records.")
    return df

def validate_products(df: pd.DataFrame) -> pd.DataFrame:
    """Validates raw product records."""
    logger.info("Validating Products...")
    df = df.copy()
    initial_count = len(df)

    # 1. Null Primary Key check
    null_pk_mask = df["product_id"].isna() | (df["product_id"].astype(str).str.strip() == "")
    if null_pk_mask.any():
        log_rejections(df[null_pk_mask], "products", "NULL_OR_EMPTY_PRODUCT_ID")
        df = df[~null_pk_mask].copy()

    # 2. Duplicate Primary Key check
    dup_mask = df.duplicated(subset=["product_id"], keep="first")
    if dup_mask.any():
        log_rejections(df[dup_mask], "products", "DUPLICATE_PRODUCT_ID")
        df = df[~dup_mask].copy()

    # Impute missing category/subcategory
    df["category"] = df["category"].fillna("General Merchandise").astype(str).str.strip()
    df["sub_category"] = df["sub_category"].fillna("Other").astype(str).str.strip()
    df["product_name"] = df["product_name"].astype(str).str.strip()

    logger.info(f"Products validation complete. Kept {len(df)} of {initial_count} records.")
    return df

def validate_geography(df: pd.DataFrame) -> pd.DataFrame:
    """Validates geography records."""
    logger.info("Validating Geography...")
    df = df.copy()
    df["country"] = df["country"].fillna("United States").astype(str).str.strip()
    df["city"] = df["city"].fillna("Unknown").astype(str).str.strip().str.title()
    df["state"] = df["state"].fillna("Unknown").astype(str).str.strip().str.title()
    df["region"] = df["region"].fillna("Central").astype(str).str.strip().str.title()
    df["postal_code"] = df["postal_code"].fillna("00000").astype(str).str.replace(".0", "", regex=False).str.strip().str.zfill(5)
    
    df = df.drop_duplicates(subset=["postal_code", "city", "state"]).copy()
    return df

def validate_orders(df: pd.DataFrame, valid_customer_ids: set) -> pd.DataFrame:
    """Validates order headers and verifies referential integrity with customers."""
    logger.info("Validating Orders Header...")
    df = df.copy()
    initial_count = len(df)

    # Clean postal_code
    df["postal_code"] = df["postal_code"].fillna("00000").astype(str).str.replace(".0", "", regex=False).str.strip().str.zfill(5)

    # 1. Check order_id
    null_pk_mask = df["order_id"].isna() | (df["order_id"].astype(str).str.strip() == "")
    if null_pk_mask.any():
        log_rejections(df[null_pk_mask], "orders", "NULL_OR_EMPTY_ORDER_ID")
        df = df[~null_pk_mask].copy()

    # 2. Date parsing validation with format='mixed'
    order_dates = pd.to_datetime(df["order_date"], format="mixed", errors="coerce")
    ship_dates = pd.to_datetime(df["ship_date"], format="mixed", errors="coerce")
    
    invalid_dates_mask = order_dates.isna() | ship_dates.isna()
    if invalid_dates_mask.any():
        log_rejections(df[invalid_dates_mask], "orders", "INVALID_DATE_FORMAT")
        df = df[~invalid_dates_mask].copy()
        order_dates = order_dates[~invalid_dates_mask]
        ship_dates = ship_dates[~invalid_dates_mask]

    # 3. Ship date should be >= order date
    date_logic_mask = ship_dates < order_dates
    if date_logic_mask.any():
        log_rejections(df[date_logic_mask], "orders", "SHIP_DATE_BEFORE_ORDER_DATE")
        df = df[~date_logic_mask].copy()
        order_dates = order_dates[~date_logic_mask]
        ship_dates = ship_dates[~date_logic_mask]

    df["order_date"] = order_dates
    df["ship_date"] = ship_dates

    # 4. Foreign Key Referential Integrity (Customer ID)
    orphan_cust_mask = ~df["customer_id"].isin(valid_customer_ids)
    if orphan_cust_mask.any():
        log_rejections(df[orphan_cust_mask], "orders", "ORPHAN_CUSTOMER_ID_FK_VIOLATION")
        df = df[~orphan_cust_mask].copy()

    df = df.drop_duplicates(subset=["order_id"]).copy()
    logger.info(f"Orders validation complete. Kept {len(df)} of {initial_count} records.")
    return df

def validate_order_items(df: pd.DataFrame, valid_order_ids: set, valid_product_ids: set) -> pd.DataFrame:
    """Validates transaction item rows and numeric constraints."""
    logger.info("Validating Order Items (Transactions)...")
    df = df.copy()
    initial_count = len(df)

    # 1. Numeric coercion
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["discount"] = pd.to_numeric(df["discount"], errors="coerce")
    df["profit"] = pd.to_numeric(df["profit"], errors="coerce")

    # 2. Non-numeric or NaN values
    nan_mask = df["sales"].isna() | df["quantity"].isna() | df["discount"].isna() | df["profit"].isna()
    if nan_mask.any():
        log_rejections(df[nan_mask], "order_items", "NON_NUMERIC_FINANCIAL_VALUE")
        df = df[~nan_mask].copy()

    # 3. Business rule: Sales > 0 and Quantity > 0
    negative_val_mask = (df["sales"] <= 0) | (df["quantity"] <= 0) | (df["discount"] < 0) | (df["discount"] > 1.0)
    if negative_val_mask.any():
        log_rejections(df[negative_val_mask], "order_items", "OUT_OF_BOUNDS_FINANCIAL_METRIC")
        df = df[~negative_val_mask].copy()

    # 4. Foreign Key checks
    orphan_order_mask = ~df["order_id"].isin(valid_order_ids)
    if orphan_order_mask.any():
        log_rejections(df[orphan_order_mask], "order_items", "ORPHAN_ORDER_ID_FK_VIOLATION")
        df = df[~orphan_order_mask].copy()

    orphan_prod_mask = ~df["product_id"].isin(valid_product_ids)
    if orphan_prod_mask.any():
        log_rejections(df[orphan_prod_mask], "order_items", "ORPHAN_PRODUCT_ID_FK_VIOLATION")
        df = df[~orphan_prod_mask].copy()

    logger.info(f"Order Items validation complete. Kept {len(df)} of {initial_count} records.")
    return df
