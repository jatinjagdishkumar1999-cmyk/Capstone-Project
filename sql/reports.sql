-- Part 1 / Task 3 — Reports against the RAW (uncleaned) data.
-- Run:  sqlite3 mamaearth.db < sql/schema.sql && sqlite3 mamaearth.db < sql/seed_data.sql
--       sqlite3 -header -column mamaearth.db < sql/reports.sql
-- (Report (i) alters the customers table; schema.sql drops/recreates it, so re-runs are safe.)
-- Each '-- OUTPUT:' block above a query is the real result of running it on the raw seed data
-- (decimals padded to 2 d.p. for readability).

-- (a) Order totals
-- OUTPUT:
--   total_orders  total_revenue  avg_order_value
--   ------------  -------------  ---------------
--   180           99860.20       554.78
SELECT COUNT(*) AS total_orders,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_revenue,
       ROUND(AVG(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS avg_order_value
FROM orders o
JOIN products p ON p.product_id = o.product_id;

-- (b) COUNT(*) vs COUNT(column)
-- OUTPUT:
--   all_rows  rated_rows  unrated_rows
--   --------  ----------  ------------
--   180       165         15
SELECT COUNT(*) AS all_rows,
       COUNT(rating) AS rated_rows,
       COUNT(*) - COUNT(rating) AS unrated_rows
FROM orders;

-- (c1) Customers with zero orders — LEFT JOIN
-- OUTPUT:
--   customer_id  name
--   -----------  ------
--   C045         Vihaan
SELECT c.customer_id, c.name
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

-- (c2) Independent cross-check — NOT IN
-- OUTPUT:
--   customer_id  name
--   -----------  ------
--   C045         Vihaan
SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);

-- (d) Return rate by city, only cities above 20%
-- OUTPUT:
--   city       total_orders  returned_orders  return_rate_pct
--   ---------  ------------  ---------------  ---------------
--   Jaipur     19            8                42.10
--   Lucknow    49            15               30.60
--   Bangalore  33            8                24.20
SELECT c.city,
       COUNT(*) AS total_orders,
       SUM(o.returned) AS returned_orders,
       ROUND(100.0 * SUM(o.returned) / COUNT(*), 1) AS return_rate_pct
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.city
HAVING return_rate_pct > 20
ORDER BY return_rate_pct DESC;

-- (e1) Top 5 customers by spend.
-- Tie-break on customer_id ASC so equal spend always ranks in a stable, reproducible order
-- (otherwise LIMIT/OFFSET pages could overlap or skip rows between runs).
-- OUTPUT:
--   customer_id  name     total_spend
--   -----------  -------  -----------
--   C043         Reyansh  12920.00
--   C026         Isha     8371.60
--   C008         Meera    4564.60
--   C011         Arjun    4111.00
--   C042         Sanya    3785.00
SELECT c.customer_id, c.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p  ON p.product_id  = o.product_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 5;

-- (e2) Ranks 3-5 via OFFSET (same ORDER BY, same tie-break)
-- OUTPUT:
--   customer_id  name   total_spend
--   -----------  -----  -----------
--   C008         Meera  4564.60
--   C011         Arjun  4111.00
--   C042         Sanya  3785.00
SELECT c.customer_id, c.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p  ON p.product_id  = o.product_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 3 OFFSET 2;

-- (f) Revenue by category (three-table join)
-- OUTPUT:
--   category      order_count  category_revenue
--   ------------  -----------  ----------------
--   Haircare      54           44956.10
--   Skincare      60           27346.00
--   Babycare      30           16805.00
--   PersonalCare  36           10753.10
SELECT p.category,
       COUNT(*) AS order_count,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS category_revenue
FROM orders o
JOIN products p  ON p.product_id  = o.product_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY p.category
ORDER BY category_revenue DESC;

-- (g) Customers whose name starts with 'A'
-- OUTPUT:
--   customer_id  name
--   -----------  ------
--   C001         Aarav
--   C003         Aditi
--   C004         Ananya
--   C011         Arjun
--   C021         Aryan
--   C030         Anika
--   C031         Aditya
--   C036         Aisha
--   C041         Ayaan
--   C044         Aria
SELECT customer_id, name FROM customers WHERE name LIKE 'A%' ORDER BY customer_id;

-- (h) Distinct acquisition sources
-- OUTPUT:
--   acquisition_source
--   ------------------
--   Ad
--   Organic
--   Referral
--   Social
SELECT DISTINCT acquisition_source FROM customers ORDER BY acquisition_source;

-- (i) Add loyalty_tier, populate with a single UPDATE ... CASE (no WHERE)
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);
UPDATE customers SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;
-- OUTPUT:
--   loyalty_tier  customers
--   ------------  ---------
--   Gold          28
--   Silver        17
SELECT loyalty_tier, COUNT(*) AS customers FROM customers GROUP BY loyalty_tier ORDER BY loyalty_tier;
