"""
Database Loading and Storage Engine.
Loads transformed Star Schema data into SQLite / MySQL.
Also exports conformed CSV files to data/processed/ for direct Power BI ingestion.
"""

import pandas as pd
import logging
from sqlalchemy import create_engine, text
from pathlib import Path
from config import get_db_url, DATA_PROCESSED_DIR

logger = logging.getLogger("ETL_Loader")

def export_to_processed_files(tables: dict) -> None:
    """Exports clean dimensional tables to CSV and Parquet for Power BI and backups."""
    logger.info("Exporting conformed tables to data/processed/ ...")
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    for table_name, df in tables.items():
        csv_file = DATA_PROCESSED_DIR / f"{table_name}.csv"
        parquet_file = DATA_PROCESSED_DIR / f"{table_name}.parquet"
        
        df.to_csv(csv_file, index=False)
        try:
            df.to_parquet(parquet_file, index=False)
        except Exception:
            pass # Parquet export optional if pyarrow not available
        logger.info(f"Exported {table_name}: {len(df)} records -> {csv_file.name}")

def load_to_database(tables: dict, db_type: str = "sqlite", incremental: bool = False) -> None:
    """
    Loads dimensional model into relational database (SQLite or MySQL).
    Supports full reload or incremental CDC loading based on row_hash.
    """
    db_url = get_db_url(db_type)
    logger.info(f"Connecting to database: {db_type.upper()} ({db_url.split('@')[-1] if '@' in db_url else db_url})")
    
    engine = create_engine(db_url)
    
    with engine.begin() as conn:
        for table_name in ["dim_customer", "dim_product", "dim_geography", "dim_date"]:
            df = tables[table_name]
            logger.info(f"Loading dimension table: {table_name} ({len(df)} rows)...")
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            logger.info(f"Loaded {table_name} successfully.")

        # Fact Sales loading
        fact_df = tables["fact_sales"]
        if incremental and table_exists(conn, "fact_sales", db_type):
            logger.info("Performing incremental load (CDC via row_hash)...")
            existing_hashes = pd.read_sql("SELECT row_hash FROM fact_sales", conn)["row_hash"].tolist()
            new_records = fact_df[~fact_df["row_hash"].isin(existing_hashes)]
            if not new_records.empty:
                new_records.to_sql("fact_sales", conn, if_exists="append", index=False)
                logger.info(f"Incrementally appended {len(new_records)} new rows to fact_sales.")
            else:
                logger.info("No new records to append. fact_sales is up-to-date.")
        else:
            logger.info(f"Performing full load of fact_sales ({len(fact_df)} rows)...")
            fact_df.to_sql("fact_sales", conn, if_exists="replace", index=False)
            logger.info("Loaded fact_sales successfully.")

        # Create indexes for optimal SQL query performance
        create_indexes(conn, db_type)

def table_exists(conn, table_name: str, db_type: str) -> bool:
    """Checks if a table exists in the database."""
    try:
        if db_type == "sqlite":
            query = text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        else:
            query = text(f"SHOW TABLES LIKE '{table_name}'")
        result = conn.execute(query).fetchone()
        return result is not None
    except Exception:
        return False

def create_indexes(conn, db_type: str) -> None:
    """Creates indexes on foreign keys and commonly filtered columns."""
    logger.info("Building database indexes on Star Schema keys...")
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_fact_order_date ON fact_sales(order_date_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_customer ON fact_sales(customer_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_product ON fact_sales(product_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_geography ON fact_sales(geography_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_order_id ON fact_sales(order_id);",
        "CREATE INDEX IF NOT EXISTS idx_dim_cust_segment ON dim_customer(segment);",
        "CREATE INDEX IF NOT EXISTS idx_dim_prod_category ON dim_product(category, sub_category);",
        "CREATE INDEX IF NOT EXISTS idx_dim_geo_region ON dim_geography(region, state);"
    ]
    
    for stmt in index_statements:
        try:
            conn.execute(text(stmt))
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")
    logger.info("Database indexes created successfully.")
