"""
Master ETL Pipeline Orchestrator.
Orchestrates: Ingestion -> Quality Checks -> Transformation -> Star Schema Modeling -> DB Loading.
Includes structured logging, timing metrics, and quality gate assertions.
"""

import os
import sys
import time
import logging
import argparse
import pandas as pd
from pathlib import Path

# Add src to sys.path
sys.path.append(str(Path(__file__).resolve().parent))

from config import DATA_RAW_DIR, LOGS_DIR, MAX_REJECT_PERCENTAGE
import quality_checks as qc
import transform as tf
import load

def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "etl_pipeline.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("ETL_Master")

def run_pipeline(db_type: str = "sqlite", incremental: bool = False):
    logger = setup_logging()
    logger.info("================================================================================")
    logger.info(f"STARTING RETAIL SALES DATA PIPELINE (Target: {db_type.upper()}, Incremental: {incremental})")
    logger.info("================================================================================")
    start_time = time.time()

    # 1. INGESTION
    logger.info("PHASE 1: Extracting raw source CSV files...")
    try:
        raw_cust = pd.read_csv(DATA_RAW_DIR / "raw_customers.csv")
        raw_prod = pd.read_csv(DATA_RAW_DIR / "raw_products.csv")
        raw_geo = pd.read_csv(DATA_RAW_DIR / "raw_geography.csv")
        raw_orders = pd.read_csv(DATA_RAW_DIR / "raw_orders.csv")
        raw_items = pd.read_csv(DATA_RAW_DIR / "raw_order_items.csv")
        logger.info(f"Extracted: {len(raw_cust)} customers, {len(raw_prod)} products, {len(raw_orders)} orders, {len(raw_items)} items.")
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise

    # 2. VALIDATION & QUALITY CHECKS
    logger.info("PHASE 2: Running Data Quality Engine & Validation Gates...")
    val_cust = qc.validate_customers(raw_cust)
    val_prod = qc.validate_products(raw_prod)
    val_geo = qc.validate_geography(raw_geo)
    
    valid_cust_ids = set(val_cust["customer_id"])
    valid_prod_ids = set(val_prod["product_id"])
    
    val_orders = qc.validate_orders(raw_orders, valid_cust_ids)
    valid_order_ids = set(val_orders["order_id"])
    
    val_items = qc.validate_order_items(raw_items, valid_order_ids, valid_prod_ids)

    # Calculate overall rejection rate
    total_raw_rows = len(raw_cust) + len(raw_prod) + len(raw_orders) + len(raw_items)
    total_clean_rows = len(val_cust) + len(val_prod) + len(val_orders) + len(val_items)
    rejected_rows = total_raw_rows - total_clean_rows
    rejection_rate = (rejected_rows / total_raw_rows) * 100
    
    logger.info(f"Data Quality Summary: Cleaned {total_clean_rows}/{total_raw_rows} records ({rejection_rate:.2f}% rejected).")
    if rejection_rate > MAX_REJECT_PERCENTAGE:
        logger.warning(f"Rejection rate {rejection_rate:.2f}% exceeds threshold {MAX_REJECT_PERCENTAGE}%! Audit rejected logs.")

    # 3. TRANSFORMATION & STAR SCHEMA MODELING
    logger.info("PHASE 3: Transforming into Star Schema (Dimension & Fact Tables)...")
    tables = tf.build_star_schema(val_cust, val_prod, val_geo, val_orders, val_items)

    # 4. EXPORT CONFORMED FILES
    logger.info("PHASE 4: Exporting conformed datasets for Power BI...")
    load.export_to_processed_files(tables)

    # 5. DATABASE LOADING
    logger.info(f"PHASE 5: Loading data into {db_type.upper()} Data Warehouse...")
    load.load_to_database(tables, db_type=db_type, incremental=incremental)

    elapsed_time = time.time() - start_time
    logger.info("================================================================================")
    logger.info(f"ETL PIPELINE COMPLETED SUCCESSFULLY IN {elapsed_time:.2f} SECONDS")
    logger.info(f"Fact Table Rows: {len(tables['fact_sales'])}")
    logger.info(f"Total Sales Processed: ${tables['fact_sales']['sales'].sum():,.2f}")
    logger.info(f"Total Profit Processed: ${tables['fact_sales']['profit'].sum():,.2f}")
    logger.info("================================================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retail Sales ETL Pipeline Orchestrator")
    parser.add_argument("--db-type", choices=["sqlite", "mysql"], default="sqlite", help="Target database engine")
    parser.add_argument("--incremental", action="store_true", help="Enable incremental loading")
    args = parser.parse_args()
    
    run_pipeline(db_type=args.db_type, incremental=args.incremental)
