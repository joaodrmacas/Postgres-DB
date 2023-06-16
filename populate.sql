-- populate

CREATE TABLE IF NOT EXISTS gs (
  n INTEGER
);

INSERT INTO gs(n)
SELECT generate_series
FROM generate_series(1, 50000);

-- table "customer"
INSERT INTO customer (cust_no, name, email, phone, address)
SELECT
  n AS cust_no,
  'Customer ' || n AS name,
  'customer' || n || '@example.com' AS email,
  '987654321' AS phone,
  'Rua ' || n || ', '|| n || n || n || 4444 || '-' || 444 || ' Vila ' || n  AS address
FROM gs;

-- table "orders"
INSERT INTO orders (order_no, cust_no, date)
SELECT
  n AS order_no,
  FLOOR(random() * 50000) + 1 AS cust_no,
  CURRENT_DATE - (random() * 365*10)::int AS date
FROM gs;

-- table "pay"
INSERT INTO pay (order_no, cust_no)
SELECT
  t_rands.my_order_no,
  (SELECT cust_no FROM orders o WHERE o.order_no = t_rands.my_order_no) AS cust_no
FROM (
  SELECT DISTINCT FLOOR(random() * 50000) + 1 AS my_order_no
  FROM gs
  LIMIT FLOOR(50000 / 2)
) AS t_rands;

-- table "employee"
INSERT INTO employee (ssn, TIN, bdate, name)
SELECT
  'SSN' || n AS ssn,
  'TIN' || n AS TIN,
  (date_trunc('year', current_date) - interval '18 years' - random() * interval '365 days')::date AS bdate,
  'Employee ' || n AS name
FROM gs;

-- table "process"
INSERT INTO process (ssn, order_no)
SELECT
    'SSN' || my_ssn AS ssn,
    (SELECT FLOOR(random() * 50000) + 1 FROM gs LIMIT 1) AS order_no
FROM (
  SELECT DISTINCT FLOOR(random() * 50000) + 1 AS my_ssn
  FROM gs
  LIMIT FLOOR(50000 / 2)
) AS t_rands;

-- table "department"
INSERT INTO department (name)
SELECT
  'Department ' || n
FROM gs
LIMIT FLOOR(50000/500);

-- table "workplace"
INSERT INTO workplace (address, lat, long)
SELECT
  'Rua ' || n || ', '|| n || n || n || n || '-' || n || n || n || ' Cidade ' || n  AS address,
  (my_lat_long * 180) - 90 AS lat,
  (my_lat_long * 360) - 180 AS long
FROM (
  SELECT DISTINCT n, random() AS my_lat_long
  FROM gs
  LIMIT FLOOR(50000/100)
) AS t_rands;

-- table "office"
INSERT INTO office (address)
SELECT
  address
FROM workplace
ORDER BY random()
LIMIT 50000/100/2;

-- table "warehouse"
INSERT INTO warehouse (address)
SELECT
  address
FROM workplace
WHERE address NOT IN (SELECT * FROM office);

-- table "works"
INSERT INTO works (ssn, name, address)
SELECT
      e.ssn,
      (SELECT 'Department ' || FLOOR(50000/500 * random() + 1) FROM gs LIMIT 1) AS name,
      (SELECT address FROM workplace ORDER BY random() LIMIT 1) AS address
FROM employee AS e
LIMIT 50000;

-- table "product"
INSERT INTO product (SKU, name, description, price, ean)
SELECT
  'SKU' || n AS SKU,
  'Product ' || n AS name,
  'Description for Product ' || n AS description,
  (random() * 500)::numeric(10, 2) AS price,
  n AS ean
FROM gs;

-- table "contains"
INSERT INTO contains (order_no, SKU, qty)
SELECT DISTINCT
    order_no,
    SKU,
    FLOOR(random() * 10 + 1) AS qty
FROM (SELECT DISTINCT FLOOR(50000 * random() + 1) AS order_no,
        'SKU' || FLOOR(50000 * random() + 1) AS SKU
    FROM generate_series(1, 2000*4)) AS pairs;

-- table "supplier"
INSERT INTO supplier (TIN, name, address, SKU, date)
SELECT
  'TIN' || n AS TIN,
  'Supplier ' || n AS name,
  'Rua ' || n || ', '|| n || n || n || n || '-' || n || n || n || ' Cidade ' || n  AS address,
  (SELECT 'SKU' || FLOOR(50000 * random() + 1) FROM gs LIMIT 1) AS SKU,
  CURRENT_DATE - (random() * 365 * 2)::int AS date
FROM gs;

-- table "delivery"
INSERT INTO delivery (address, TIN)
SELECT
  pairs.new_address,
  pairs.TIN
FROM (SELECT DISTINCT (SELECT address FROM warehouse ORDER BY random() LIMIT 1) AS new_address,
                              'TIN' || FLOOR(50000 * random() + 1) AS TIN FROM gs) AS pairs
LIMIT FLOOR(50000/100/2 * 10);