-- Raw landing schema: one table per source CSV, explicit types and FKs.
-- Loaded by src/ecommerce_intel/ingest.py (idempotent: truncate + copy in one transaction).

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id              text PRIMARY KEY,
    customer_unique_id       text NOT NULL,
    customer_zip_code_prefix integer NOT NULL,
    customer_city            text NOT NULL,
    customer_state           text NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.sellers (
    seller_id              text PRIMARY KEY,
    seller_zip_code_prefix integer NOT NULL,
    seller_city            text NOT NULL,
    seller_state           text NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.products (
    product_id                 text PRIMARY KEY,
    product_category_name      text,
    product_name_lenght        integer,
    product_description_lenght integer,
    product_photos_qty         integer,
    product_weight_g           integer,
    product_length_cm          integer,
    product_height_cm          integer,
    product_width_cm           integer
);

CREATE TABLE IF NOT EXISTS raw.product_category_name_translation (
    product_category_name         text PRIMARY KEY,
    product_category_name_english text NOT NULL
);

-- No primary key: the source contains duplicate zip/city combinations.
CREATE TABLE IF NOT EXISTS raw.geolocation (
    geolocation_zip_code_prefix integer NOT NULL,
    geolocation_lat             numeric(10, 6) NOT NULL,
    geolocation_lng             numeric(10, 6) NOT NULL,
    geolocation_city            text NOT NULL,
    geolocation_state           text NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.orders (
    order_id                      text PRIMARY KEY,
    customer_id                   text NOT NULL,
    order_status                  text NOT NULL,
    order_purchase_timestamp      timestamp NOT NULL,
    order_approved_at             timestamp,
    order_delivered_carrier_date  timestamp,
    order_delivered_customer_date timestamp,
    order_estimated_delivery_date timestamp NOT NULL,
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id)
        REFERENCES raw.customers (customer_id)
);

CREATE TABLE IF NOT EXISTS raw.order_items (
    order_id            text NOT NULL,
    order_item_id       integer NOT NULL,
    product_id          text NOT NULL,
    seller_id           text NOT NULL,
    shipping_limit_date timestamp NOT NULL,
    price               numeric(12, 2) NOT NULL,
    freight_value       numeric(12, 2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id),
    CONSTRAINT fk_items_order FOREIGN KEY (order_id)
        REFERENCES raw.orders (order_id),
    CONSTRAINT fk_items_product FOREIGN KEY (product_id)
        REFERENCES raw.products (product_id),
    CONSTRAINT fk_items_seller FOREIGN KEY (seller_id)
        REFERENCES raw.sellers (seller_id)
);

CREATE TABLE IF NOT EXISTS raw.order_payments (
    order_id             text NOT NULL,
    payment_sequential   integer NOT NULL,
    payment_type         text NOT NULL,
    payment_installments integer NOT NULL,
    payment_value        numeric(12, 2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential),
    CONSTRAINT fk_payments_order FOREIGN KEY (order_id)
        REFERENCES raw.orders (order_id)
);

-- No primary key: review_id is duplicated and orders can carry several reviews.
CREATE TABLE IF NOT EXISTS raw.order_reviews (
    review_id               text NOT NULL,
    order_id                text NOT NULL,
    review_score            integer NOT NULL,
    review_comment_title    text,
    review_comment_message  text,
    review_creation_date    timestamp,
    review_answer_timestamp timestamp,
    CONSTRAINT fk_reviews_order FOREIGN KEY (order_id)
        REFERENCES raw.orders (order_id)
);
