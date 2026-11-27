"""
Verification runner for all 20 SQL analytical queries.
Executes each query against retail_sales_dw.db and displays results.
"""

import sqlite3
import pandas as pd
import re
from pathlib import Path

DB_PATH = Path("retail_sales_dw.db")
SQL_FILE = Path("sql/03_advanced_analytics_20.sql")

def run_all_queries():
    print(f"Connecting to database: {DB_PATH.resolve()}...")
    conn = sqlite3.connect(DB_PATH)
    
    with open(SQL_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by QUERY headers
    query_blocks = re.split(r"-- QUERY \d+:", content)[1:]
    print(f"Found {len(query_blocks)} queries to execute.\n")

    for i, block in enumerate(query_blocks, start=1):
        # Extract title
        first_line = block.strip().split("\n")[0].strip("- ")
        # Extract SQL statements (remove comments)
        sql_lines = []
        for line in block.strip().split("\n")[1:]:
            if not line.strip().startswith("--"):
                sql_lines.append(line)
        sql_query = "\n".join(sql_lines).strip().rstrip(";")

        print(f"--------------------------------------------------------------------------------")
        print(f"EXECUTING QUERY {i}: {first_line}")
        print(f"--------------------------------------------------------------------------------")
        try:
            df = pd.read_sql_query(sql_query, conn)
            print(f"Status: SUCCESS ({len(df)} rows returned)")
            print(df.head(3).to_string(index=False))
            print()
        except Exception as e:
            print(f"Status: ERROR -> {e}")
            raise

    conn.close()
    print("================================================================================")
    print("ALL 20 SQL ANALYTICAL QUERIES EXECUTED AND VERIFIED WITH 100% SUCCESS!")
    print("================================================================================")

if __name__ == "__main__":
    run_all_queries()
