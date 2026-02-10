-- Seed schema and sample data for local development
CREATE SCHEMA IF NOT EXISTS opendata_nodata;

CREATE TABLE IF NOT EXISTS opendata_nodata.model_for_all_domain (
    order_date date NOT NULL,
    buyer_np varchar,
    seller_np varchar,
    category varchar,
    domain varchar,
    np_type varchar,
    orders int4
);

CREATE TABLE IF NOT EXISTS opendata_nodata.model_for_all_domain_pincode (
    order_date date NOT NULL,
    domain varchar,
    delivery_city varchar,
    seller_city varchar,
    orders int8
);

-- Sample data
INSERT INTO opendata_nodata.model_for_all_domain (order_date, buyer_np, seller_np, category, domain, np_type, orders) VALUES
('2025-01-01', 'BuyerApp1', 'SellerApp1', 'Grocery', 'Retail B2C', 'Inter NP', 1500),
('2025-01-01', 'BuyerApp1', 'SellerApp1', 'Fashion', 'Retail B2C', 'Inter NP', 800),
('2025-01-01', 'BuyerApp2', 'SellerApp2', 'Grocery', 'Retail B2C', 'Intra NP', 1200),
('2025-01-01', 'BuyerApp1', 'SellerApp3', 'Mutual Fund', 'Finance', 'Inter NP', 300),
('2025-01-01', 'BuyerApp3', 'SellerApp1', 'Cabs/Auto', 'Ride Hailing', NULL, 2000),
('2025-01-02', 'BuyerApp1', 'SellerApp1', 'Grocery', 'Retail B2C', 'Inter NP', 1600),
('2025-01-02', 'BuyerApp2', 'SellerApp2', 'Electronics', 'Retail B2C', 'Intra NP', 950),
('2025-01-02', 'BuyerApp1', 'SellerApp4', 'Bus', 'Public Transport', 'Inter NP', 500),
('2025-01-02', 'BuyerApp3', 'SellerApp2', 'B2B', 'Retail B2B', 'Inter NP', 400),
('2025-01-02', 'BuyerApp1', 'SellerApp5', 'Gift Card', 'Retail Voucher', NULL, 150);

INSERT INTO opendata_nodata.model_for_all_domain_pincode (order_date, domain, delivery_city, seller_city, orders) VALUES
('2025-01-01', 'Retail B2C', 'Bangalore', 'Bangalore', 3500),
('2025-01-01', 'Retail B2C', 'Delhi', 'Mumbai', 2100),
('2025-01-01', 'Finance', 'Mumbai', 'Mumbai', 300),
('2025-01-01', 'Ride Hailing', 'Hyderabad', 'Hyderabad', 2000),
('2025-01-01', 'Logistics', 'Chennai', 'Bangalore', 800),
('2025-01-02', 'Retail B2C', 'Bangalore', 'Delhi', 2550),
('2025-01-02', 'Retail B2C', 'Mumbai', 'Mumbai', 1800),
('2025-01-02', 'Public Transport', 'Delhi', 'Delhi', 500),
('2025-01-02', 'Retail B2B', 'Pune', 'Mumbai', 400),
('2025-01-02', 'Retail Voucher', 'Kolkata', 'Bangalore', 150);
