-- ============================================================================
-- RETAIL SALES ENTERPRISE DATA WAREHOUSE - STAR SCHEMA DDL (MySQL 8.0+)
-- Database: retail_sales_dw
-- ============================================================================

CREATE DATABASE IF NOT EXISTS retail_sales_dw
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE retail_sales_dw;

-- Disable foreign key checks during schema creation/migration
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------------------------------------------------------
-- 1. DIMENSION: Customer (dim_customer)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_customer;
CREATE TABLE dim_customer (
    customer_key INT AUTO_INCREMENT PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL UNIQUE,
    customer_name VARCHAR(150) NOT NULL,
    segment VARCHAR(50) NOT NULL DEFAULT 'Consumer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_cust_segment (segment)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------------------------
-- 2. DIMENSION: Product (dim_product)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_product;
CREATE TABLE dim_product (
    product_key INT AUTO_INCREMENT PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL UNIQUE,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    sub_category VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_prod_category (category),
    INDEX idx_prod_subcategory (sub_category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------------------------
-- 3. DIMENSION: Geography / Store Location (dim_geography)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_geography;
CREATE TABLE dim_geography (
    geography_key INT AUTO_INCREMENT PRIMARY KEY,
    postal_code VARCHAR(20) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    region VARCHAR(50) NOT NULL,
    country VARCHAR(100) NOT NULL DEFAULT 'United States',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_geo_region_state (region, state),
    INDEX idx_geo_postal (postal_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------------------------
-- 4. DIMENSION: Date (dim_date)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    date_key INT PRIMARY KEY COMMENT 'Format: YYYYMMDD',
    full_date DATE NOT NULL,
    year SMALLINT NOT NULL,
    quarter TINYINT NOT NULL,
    quarter_name VARCHAR(10) NOT NULL,
    month TINYINT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    month_short CHAR(3) NOT NULL,
    year_month CHAR(7) NOT NULL,
    day_of_month TINYINT NOT NULL,
    day_of_week TINYINT NOT NULL COMMENT '1=Monday, 7=Sunday',
    day_name VARCHAR(15) NOT NULL,
    is_weekend TINYINT(1) NOT NULL DEFAULT 0,
    fiscal_year SMALLINT NOT NULL,
    fiscal_quarter TINYINT NOT NULL,
    INDEX idx_date_year_month (year, month),
    INDEX idx_date_full_date (full_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------------------------
-- 5. FACT TABLE: Sales (fact_sales)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_sales;
CREATE TABLE fact_sales (
    sales_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    order_date_key INT NOT NULL,
    ship_date_key INT NOT NULL,
    customer_key INT NOT NULL,
    product_key INT NOT NULL,
    geography_key INT NOT NULL,
    ship_mode VARCHAR(50) NOT NULL,
    sales DECIMAL(12, 2) NOT NULL CHECK (sales > 0),
    quantity INT NOT NULL CHECK (quantity > 0),
    discount DECIMAL(6, 4) NOT NULL DEFAULT 0.0000 CHECK (discount >= 0 AND discount <= 1.0),
    profit DECIMAL(12, 2) NOT NULL,
    cost DECIMAL(12, 2) NOT NULL,
    profit_margin_pct DECIMAL(8, 2) NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    shipping_days INT NOT NULL,
    is_delayed TINYINT(1) NOT NULL DEFAULT 0,
    is_profitable TINYINT(1) NOT NULL DEFAULT 1,
    row_hash CHAR(32) NOT NULL UNIQUE COMMENT 'MD5 hash for CDC / Incremental loading',
    etl_loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Key Constraints
    CONSTRAINT fk_sales_order_date FOREIGN KEY (order_date_key) REFERENCES dim_date(date_key),
    CONSTRAINT fk_sales_ship_date FOREIGN KEY (ship_date_key) REFERENCES dim_date(date_key),
    CONSTRAINT fk_sales_customer FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
    CONSTRAINT fk_sales_product FOREIGN KEY (product_key) REFERENCES dim_product(product_key),
    CONSTRAINT fk_sales_geography FOREIGN KEY (geography_key) REFERENCES dim_geography(geography_key),
    
    -- Composite & Performance Indexes
    INDEX idx_fact_order_id (order_id),
    INDEX idx_fact_order_date_key (order_date_key),
    INDEX idx_fact_customer_key (customer_key),
    INDEX idx_fact_product_key (product_key),
    INDEX idx_fact_geography_key (geography_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- STORED PROCEDURE: Incremental Upsert Logic (CDC)
-- ============================================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_upsert_sales_record //
CREATE PROCEDURE sp_upsert_sales_record (
    IN p_order_id VARCHAR(50),
    IN p_order_date_key INT,
    IN p_ship_date_key INT,
    IN p_customer_key INT,
    IN p_product_key INT,
    IN p_geography_key INT,
    IN p_ship_mode VARCHAR(50),
    IN p_sales DECIMAL(12,2),
    IN p_quantity INT,
    IN p_discount DECIMAL(6,4),
    IN p_profit DECIMAL(12,2),
    IN p_cost DECIMAL(12,2),
    IN p_profit_margin_pct DECIMAL(8,2),
    IN p_unit_price DECIMAL(10,2),
    IN p_shipping_days INT,
    IN p_is_delayed TINYINT(1),
    IN p_is_profitable TINYINT(1),
    IN p_row_hash CHAR(32)
)
BEGIN
    INSERT INTO fact_sales (
        order_id, order_date_key, ship_date_key, customer_key, product_key, geography_key,
        ship_mode, sales, quantity, discount, profit, cost, profit_margin_pct,
        unit_price, shipping_days, is_delayed, is_profitable, row_hash, etl_loaded_at
    )
    VALUES (
        p_order_id, p_order_date_key, p_ship_date_key, p_customer_key, p_product_key, p_geography_key,
        p_ship_mode, p_sales, p_quantity, p_discount, p_profit, p_cost, p_profit_margin_pct,
        p_unit_price, p_shipping_days, p_is_delayed, p_is_profitable, p_row_hash, NOW()
    )
    ON DUPLICATE KEY UPDATE
        sales = VALUES(sales),
        quantity = VALUES(quantity),
        discount = VALUES(discount),
        profit = VALUES(profit),
        cost = VALUES(cost),
        profit_margin_pct = VALUES(profit_margin_pct),
        unit_price = VALUES(unit_price),
        shipping_days = VALUES(shipping_days),
        is_delayed = VALUES(is_delayed),
        is_profitable = VALUES(is_profitable),
        etl_loaded_at = NOW();
END //

DELIMITER ;
