-- Database initialization script for TalkToData Enterprise
-- This script sets up the necessary tables and initial data

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Create user sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_accessed TIMESTAMP DEFAULT NOW(),
    ip_address VARCHAR(45),
    user_agent TEXT
);

-- Create query history table for audit and analytics
CREATE TABLE IF NOT EXISTS query_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    generated_sql TEXT,
    execution_time FLOAT,
    result_count INTEGER,
    status VARCHAR(20) NOT NULL, -- success, error, timeout
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    correlation_id UUID DEFAULT uuid_generate_v4()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_query_history_user_id ON query_history(user_id);
CREATE INDEX IF NOT EXISTS idx_query_history_created_at ON query_history(created_at);
CREATE INDEX IF NOT EXISTS idx_query_history_status ON query_history(status);
CREATE INDEX IF NOT EXISTS idx_query_history_correlation_id ON query_history(correlation_id);

-- Create sample data tables for demonstration
CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(50),
    state VARCHAR(50),
    country VARCHAR(50),
    postal_code VARCHAR(20),
    registration_date DATE DEFAULT CURRENT_DATE,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    price DECIMAL(10,2),
    cost DECIMAL(10,2),
    stock_quantity INTEGER DEFAULT 0,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    order_date TIMESTAMP DEFAULT NOW(),
    total_amount DECIMAL(12,2),
    status VARCHAR(20) DEFAULT 'pending',
    shipping_address TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2),
    total_price DECIMAL(12,2)
);

-- Create sample data
INSERT INTO customers (customer_name, email, phone, city, state, country) VALUES
('John Doe', 'john.doe@email.com', '+1-555-0101', 'New York', 'NY', 'USA'),
('Jane Smith', 'jane.smith@email.com', '+1-555-0102', 'Los Angeles', 'CA', 'USA'),
('Bob Johnson', 'bob.johnson@email.com', '+1-555-0103', 'Chicago', 'IL', 'USA'),
('Alice Brown', 'alice.brown@email.com', '+1-555-0104', 'Houston', 'TX', 'USA'),
('Charlie Davis', 'charlie.davis@email.com', '+1-555-0105', 'Phoenix', 'AZ', 'USA')
ON CONFLICT (email) DO NOTHING;

INSERT INTO products (product_name, category, price, cost, stock_quantity, description) VALUES
('Laptop Pro 15"', 'Electronics', 1299.99, 899.99, 50, 'High-performance laptop for professionals'),
('Wireless Mouse', 'Electronics', 29.99, 15.99, 200, 'Ergonomic wireless mouse with precision tracking'),
('Office Chair', 'Furniture', 249.99, 149.99, 25, 'Comfortable ergonomic office chair'),
('Desk Lamp', 'Furniture', 79.99, 39.99, 75, 'LED desk lamp with adjustable brightness'),
('Coffee Mug', 'Kitchen', 12.99, 6.99, 150, 'Ceramic coffee mug with company logo')
ON CONFLICT DO NOTHING;

INSERT INTO orders (customer_id, total_amount, status) VALUES
(1, 1329.98, 'completed'),
(2, 79.99, 'pending'),
(3, 262.98, 'shipped'),
(4, 42.98, 'completed'),
(5, 1299.99, 'processing')
ON CONFLICT DO NOTHING;

INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price) VALUES
(1, 1, 1, 1299.99, 1299.99),
(1, 2, 1, 29.99, 29.99),
(2, 4, 1, 79.99, 79.99),
(3, 3, 1, 249.99, 249.99),
(3, 5, 1, 12.99, 12.99),
(4, 2, 1, 29.99, 29.99),
(4, 5, 1, 12.99, 12.99),
(5, 1, 1, 1299.99, 1299.99)
ON CONFLICT DO NOTHING;

-- Create indexes for sample data tables
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_city ON customers(city);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);

-- Create a view for order summaries
CREATE OR REPLACE VIEW order_summary AS
SELECT 
    o.order_id,
    c.customer_name,
    c.email,
    o.order_date,
    o.total_amount,
    o.status,
    COUNT(oi.order_item_id) as item_count
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY o.order_id, c.customer_name, c.email, o.order_date, o.total_amount, o.status
ORDER BY o.order_date DESC;

-- Grant permissions (adjust as needed)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO talktodb_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO talktodb_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO talktodb_user;

-- Development user permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dev_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dev_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO dev_user;
