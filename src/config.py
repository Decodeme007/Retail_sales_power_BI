"""
Configuration module for Retail Sales Data Engineering & BI Platform.
Supports dual database engines:
- Local SQLite (zero configuration, works immediately out of the box)
- MySQL Server (for production deployment when configured)
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
DATA_REJECTED_DIR = BASE_DIR / "data" / "rejected"
LOGS_DIR = BASE_DIR / "logs"
SQL_DIR = BASE_DIR / "sql"
POWERBI_DIR = BASE_DIR / "powerbi"

# Database Configuration
# Default to SQLite for immediate local execution without external server requirement
DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "retail_sales_dw")

SQLITE_DB_PATH = BASE_DIR / "retail_sales_dw.db"

def get_db_url(db_type=None):
    selected_type = (db_type or DB_TYPE).lower()
    if selected_type == "mysql":
        auth = f"{MYSQL_USER}:{MYSQL_PASSWORD}@" if MYSQL_PASSWORD else f"{MYSQL_USER}@"
        return f"mysql+pymysql://{auth}{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    else:
        # SQLite connection
        return f"sqlite:///{SQLITE_DB_PATH}"

# Pipeline thresholds
MAX_REJECT_PERCENTAGE = 5.0 # Quality gate fails if rejection rate > 5%
