#!/usr/bin/python3
import os
from logging.config import dictConfig

import psycopg
import json
from flask import flash
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from psycopg.rows import namedtuple_row
from psycopg_pool import ConnectionPool

import re


# postgres://{user}:{password}@{hostname}:{port}/{database-name}
#DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://p3:p3@postgres/p3")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://db:db@postgres/db")


pool = ConnectionPool(conninfo=DATABASE_URL)
# the pool starts connecting immediately.


dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s:%(lineno)s - %(funcName)20s(): %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

app = Flask(__name__)
log = app.logger
app.secret_key = "secret_key"


@app.route("/", methods=("GET",))
@app.route("/clients", methods=("GET",))
@app.route("/clients/<int:page_number>", methods=("GET",))
def client_index(page_number=1):
    """Show all the accounts, most recent first."""

    if page_number < 1:
        return redirect("/clients/1")

    query = request.args.get('query')
    isSearch=False
    limit = 5  # Set the limit to the desired number of items per page
    offset = (page_number - 1) * limit  # Calculate the offset based on the current page number
     
    if not query: 
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                clients = cur.execute(
                    """
                    SELECT cust_no, name, address, phone
                    FROM customer
                    ORDER BY cust_no
                    LIMIT %s OFFSET %s;
                    """,
                    (limit, offset),
                ).fetchall()
                log.debug(f"Found {cur.rowcount} rows.")
    else: 
        isSearch=True
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                clients = cur.execute("SELECT cust_no, name, address, phone FROM customer WHERE LOWER(name) LIKE LOWER(%s) OR phone LIKE %s OR cust_no::text LIKE %s",  ('%' + query + '%', '%' + query + '%', '%' + query + '%')
                ).fetchall()
                log.debug(f"Found {cur.rowcount} rows.")

    # API-like response is returned to clients that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(clients)
    numberSearch = len(clients)
    return render_template("client/index.html", clients=clients, page_number=page_number,isSearch=isSearch,query=query,numberSearch=numberSearch)

@app.route("/clients/<client_number>/update", methods=("GET",))
def client_update(client_number=-1):
    """View, or delete, or create an account."""
    
    if client_number == -1:
        return redirect(client_index)
    

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            client = cur.execute(
                """
                SELECT cust_no, name, address, phone, email
                FROM customer
                WHERE cust_no = %(account_number)s;
                """,
                {"account_number": client_number},
            ).fetchone()
            log.debug(f"Found {cur.rowcount} rows.")

    return render_template("client/update.html", client=client)

@app.route("/clients/create_client", methods=("GET","POST"))
def client_create():
    """Create a new account."""

    if request.method == "POST":
        name = request.form["name"]
        addressS = request.form["addressS"]
        addressZ = request.form["addressZ"]
        addressC = request.form["addressC"]
        phone = request.form["phone"]
        email = request.form["email"]
        error = None

        #se estao todos preenchidos ou se faltam preencher alguns ou se estao todos vazios
        if all([addressS,addressZ,addressC]):
            address = addressS + " " + addressZ + " " + addressC
        elif all([add == "" for add in [addressS,addressZ,addressC]]): 
            address = None
        else:
            error = "Address is incomplete!"

        if not name:
            error = "Name is required!"
        if not email:
            error = "Email is required!"
        if "@" not in email or "." not in email:
            error = "Email is invalid!"
            
        if phone:
            if phone.isnumeric() == False:
                error = "Phone must be a number!"

        

        if error is not None:
            flash(error)
        else:
            try:
                with pool.connection() as conn:
                    with conn.cursor(row_factory=namedtuple_row) as cur:
                        conn.autocommit = False
                        cur.execute(
                            """
                            INSERT INTO customer (cust_no, name, address, phone, email)
                            SELECT COALESCE(MAX(cust_no), 0) + 1, %(name)s, %(address)s, %(phone)s, %(email)s FROM customer;
                            """,
                            {"name": name, "address": address, "phone": phone, "email": email},
                        )
                    conn.commit()
                return redirect(url_for("client_index"))
            except psycopg.DatabaseError as error:
                error_message = str(error)
                if re.search(r'Key \(email\)=\((.*?)\) already exists', error_message):
                    email = re.search(r'Key \(email\)=\((.*?)\) already exists', error_message).group(1)
                    error = f"Email '{email}' is already in use!"
                    flash(error)

    return render_template("client/create_client.html")

@app.route("/accounts/<client_number>/delete", methods=("POST",))
def client_delete(client_number):
    """Delete the account."""
    num = int(client_number)
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                DELETE FROM contains WHERE order_no IN
                (SELECT order_no FROM orders WHERE  cust_no = %s);
                """,
                (num,)
            )
            cur.execute(
                """
                DELETE FROM process pr WHERE order_no IN 
                (SELECT order_no FROM orders WHERE cust_no = %s);
                """,
                (num,)
            )
            cur.execute(
                """
                DELETE FROM pay p WHERE p.cust_no = %s;
                """,
                (num,)
            )
            cur.execute(
                """
                DELETE FROM orders o WHERE o.cust_no=%s;
                """,
                (num,)
            )
            cur.execute(
                """
                DELETE FROM customer c WHERE c.cust_no=%s;
                """,
                (num,)
            )
        conn.commit()
    return redirect(url_for("client_index"))

@app.route("/products", methods=("GET",))
@app.route("/products/<int:page_number>", methods=("GET",))
def product_index(page_number=1):
    """Show all the products, most recent first."""

    if page_number < 1:
        return redirect("/products/1")
    query = request.args.get('query')
    isSearch= False
    limit = 5  # Set the limit to the desired number of items per page
    offset = (page_number - 1) * limit  # Calculate the offset based on the current page number
    if not query or query == " ":
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                products = cur.execute(
                    """
                    SELECT SKU, name, description, price, ean
                    FROM product
                    ORDER BY name
                    LIMIT %s OFFSET %s;
                    """,
                    (limit, offset),
                ).fetchall()
                log.debug(f"Found {cur.rowcount} rows.")
    else:
        isSearch=True
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                products = cur.execute("SELECT sku, name, description, price, ean FROM product WHERE LOWER(name) LIKE LOWER(%s) OR price::text LIKE %s OR LOWER(sku) LIKE LOWER(%s) OR ean::text LIKE %s",  ('%' + query + '%', '%' + query + '%', '%' + query + '%','%' + query + '%')
                ).fetchall()
                log.debug(f"Found {cur.rowcount} rows.")
                
    # API-like response is returned to clients that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(products)
    numberSearch = len(products)
    return render_template("product/index.html", products=products, page_number=page_number,isSearch=isSearch,query=query,numberSearch=numberSearch)


@app.route("/product/<string:product_sku>/update",methods =("GET", "POST"))
def product_update(product_sku):
    """View, or delete, or edit a product."""
    
    if request.method == "GET":
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                product = cur.execute(
                    """
                    SELECT SKU, name, description, price, ean
                    FROM product
                    WHERE SKU = %(sku)s;
                    """,
                    {"sku": product_sku},
                ).fetchone()
                log.debug(f"Found {cur.rowcount} rows.")
    
    if request.method == "POST":
        price = request.form["price"]
        description = request.form["description"]

        error = None

        #data check app side

        if error is not None:
            flash(error)
        else:
            with pool.connection() as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute(
                        """
                        UPDATE product
                        SET price = %(price)s,
                            description = %(description)s
                        WHERE SKU = %(product_sku)s;
                        """,
                        {"product_sku": product_sku, "price": price, "description": description},
                    )
                conn.commit()
            return redirect(url_for("product_index"))

    return render_template("product/update.html", product=product)

@app.route("/product/create_product", methods=("GET","POST"))
def product_create():
    """Create a new product."""


    if request.method == "POST":
        sku = request.form["sku"]
        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        ean = request.form["ean"]

        error = None

        if ean == "":
            ean = None

        if not name:
            error = "Name is required!"
        if not price:
            error = "Price is required!"
        try:
            price = float(price)
        except:
            error = "Price must be a float"
        if not sku:
            error = "SKU is required!"
        if not description:
            description = ""
        

        

        if error is not None:
            flash(error)
        else:
            try:
                with pool.connection() as conn:
                    with conn.cursor(row_factory=namedtuple_row) as cur:
                        cur.execute(
                            """
                            INSERT INTO product (SKU, name, description, price, ean)
                            VALUES (%(SKU)s, %(name)s, %(description)s, %(price)s, %(ean)s);
                            """,
                            {"SKU": sku, "name": name, "description": description, "price": price, "ean": ean},
                        )
                    conn.commit()
                return redirect(url_for("product_index"))
            except psycopg.DatabaseError as error:
                error_message = str(error)
                #if re.search(r'duplicate key value violates unique constraint', error_message):
                if re.search(r'Key \(sku\)=\((.*?)\) already exists', error_message):
                    sku = re.search(r'Key \(sku\)=\((.*?)\) already exists', error_message).group(1)
                    error = f"SKU '{sku}' is already used!"
                elif re.search(r'Key \(ean\)=\((.*?)\) already exists', error_message):
                    ean = re.search(r'Key \(ean\)=\((.*?)\) already exists', error_message).group(1)
                    error = f"EAN '{ean}' is already used!"
                else:
                    error = "An error occurred while creating the client."
                flash(error)

    return render_template("product/create_product.html")

@app.route("/product/<string:product_sku>/delete",methods =("POST",))
def product_delete(product_sku):
    sk = product_sku
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT order_no FROM contains WHERE sku = %s", (sk,))
            orders = cur.fetchall()

            for order in orders: 
                cur.execute("DELETE FROM contains WHERE order_no = %s", (order[0],))
                cur.execute("DELETE FROM pay WHERE order_no = %s", (order[0],))
                cur.execute("DELETE FROM process WHERE order_no = %s", (order[0],))
                cur.execute("DELETE FROM orders WHERE order_no = %s", (order[0],))

            cur.execute("""
                DELETE FROM delivery WHERE TIN IN
                (SELECT TIN FROM supplier WHERE sku = %s)
                """, (sk,))
            
            cur.execute("DELETE FROM supplier WHERE sku = %s", (sk,))
            cur.execute("DELETE FROM product WHERE sku = %s", (sk,))
        
        conn.commit()
    
    return redirect(url_for("product_index"))

@app.route("/supplier", methods=("GET","POST",))
@app.route("/supplier/<int:page_number>", methods=("GET","POST,"))
def supplier_index(page_number=1):
    error  = None
    query = request.args.get('query')
    isSearch= False
    if error is not None:
            flash(error)
    limit = 5  # Set the limit to the desired number of items per page
    offset = (page_number - 1) * limit  # Calculate the offset based on the current page number
    if not query or query==" ":
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                supliers = cur.execute(
                    """
                    SELECT sku, address, name, tin,date
                    FROM supplier
                    ORDER BY sku
                    LIMIT %s OFFSET %s;
                    """,
                    (limit, offset),
                ).fetchall()
                log.debug(f"Found {cur.rowcount} rows.")
    else:
        isSearch=True
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                supliers = cur.execute("SELECT sku, address, name, tin,date FROM supplier WHERE LOWER(name) LIKE LOWER(%s) OR tin LIKE %s OR LOWER(sku) LIKE LOWER(%s)",  ('%' + query + '%', '%' + query + '%', '%' + query + '%')
                ).fetchall()
                log.debug(f"Found {cur.rowcount} rows.")

    # API-like response is returned to supliers that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(supliers)
    numberSearch = len(supliers)
    return render_template("supply/index.html",supliers=supliers,page_number=page_number,isSearch=isSearch,query=query,numberSearch=numberSearch)

@app.route("/supplier/<tin>/update", methods=("GET",))
def supplier_update(tin=""):
    """View, or delete, or create an account."""
    
    if tin == "":
        return render_template("supply/index.html")
    
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            supplier = cur.execute(
                """
                SELECT name, address, sku, tin,date
                FROM supplier
                WHERE tin = %(tin)s;
                """,
                {"tin": tin},
            ).fetchone()
            log.debug(f"Found {cur.rowcount} rows.")

    return render_template("supply/update.html", supplier=supplier)

@app.route("/supplier/<tin>/delete", methods=("POST",))
def supplier_delete(tin=""):
    """Delete the account."""
    
    if tin == "":
         return render_template("supply/index.html")
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                DELETE FROM delivery WHERE TIN IN
                (SELECT TIN FROM supplier where tin=%s)
                """,
                (tin,)
            )
            cur.execute(
                """
                DELETE FROM supplier
                WHERE TIN = %s;
                """,
                (tin,),
            )
        conn.commit()
    return redirect(url_for("supplier_index"))

@app.route("/supplier/register", methods=("GET","POST"))
def supplier_register():
    """Create a new supplier."""



    if request.method == "POST":
        name = request.form["supplier_name"]
        tin = request.form["supplier_tin"]
        sku = request.form["supplier_sku"]
        addressS = request.form["addressS"]
        addressZ = request.form["addressZ"]
        addressC = request.form["addressC"]
        date = request.form["date"]
        date = date.replace("-","/")
        error = None

        #se estao todos preenchidos ou se faltam preencher alguns ou se estao todos vazios
        if all([add is not None for add in [addressS,addressZ,addressC]]):
            address = addressS + " " + addressZ + " " + addressC
        elif any([add is None for add in [addressS,addressZ,addressC]]): 
            error = "Address is incomplete!"
        else:
            address = None

        if name == "":
            name = None
        if sku == "":
            sku = None
        if date == "":
            date = None
        

        if error is not None:
            flash(error)
        else:
            try:
                with pool.connection() as conn:
                    with conn.cursor(row_factory=namedtuple_row) as cur:
                        cur.execute(
                            """
                            INSERT INTO supplier (sku, address, name, tin, date)
                            VALUES (%(sku)s, %(address)s, %(name)s, %(tin)s, %(date)s);
                            """,
                            {"sku": sku, "name": name, "address": address, "tin": tin, "date": date},
                        )
                    conn.commit()
                return redirect(url_for("supplier_index"))
            except psycopg.DatabaseError as error:
                error_message = str(error)
                if re.search(r'Key \(sku\)=\(\d+\) is not present in table "product"', error_message):
                        error = "SKU does not exist!"
                        flash(error)
                        error=""
                elif re.search(r'Key \(tin\)=\(\d+\) already exists', error_message):
                        error = "Tin already exists!"
                        flash(error)
                        error=""
    return render_template("supply/registerSuplier.html")

@app.route("/orders", methods=("GET",))
@app.route("/orders/<int:page_number>", methods=("GET",))
def order_index(page_number=1):
    
    limit = 5  # Set the limit to the desired number of items per page
    offset = (page_number - 1) * limit  # Calculate the offset based on the current page number
    query = request.args.get('query')
    isSearch= False
    if not query or query==" ":
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                orders = cur.execute(
                    """
                    SELECT o.order_no, o.cust_no, o.date, p.order_no AS payment_order_no
                    FROM orders o
                    LEFT JOIN pay p ON o.order_no = p.order_no
                    ORDER BY o.order_no
                    LIMIT %s OFFSET %s;
                    """,
                    (limit, offset),
                ).fetchall()
                log.debug(f"Found {cur.rowcount} rows.")
    else:
        isSearch=True
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                orders = cur.execute("SELECT o.order_no, o.cust_no, o.date, p.order_no AS payment_order_no FROM orders o LEFT JOIN pay p ON o.order_no = p.order_no WHERE p.order_no::text LIKE %s OR o.cust_no::text LIKE %s OR o.order_no::text LIKE %s OR o.date::text LIKE %s",  ('%' + query + '%', '%' + query + '%', '%' + query + '%','%' + query + '%')
                ).fetchall()
                log.debug(f"Found {cur.rowcount} rows.")
           
    # Create a list to store the orders with payment status (paid/not paid)
    modified_orders = []
    
    for order in orders:
        if order.payment_order_no is not None:
            # Order has a corresponding payment record, indicating it has been paid
            modified_order = dict(order._asdict())
            modified_order['is_paid'] = True
        else:
            # Order does not have a corresponding payment record, indicating it has not been paid
            modified_order = dict(order._asdict())
            modified_order['is_paid'] = False
        
        modified_orders.append(modified_order)

    # API-like response is returned to orders that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(modified_orders)
    numberSearch = len(orders)
    return render_template("order/index.html", orders=modified_orders, page_number=page_number,isSearch=isSearch,query=query,numberSearch=numberSearch)

@app.route("/orders/<order_no>/pay", methods=("GET","POST"))
def order_pay(order_no):
    """Pay for an order."""
    if request.method == "POST":
        cust_no = request.form["cust_no"]
        error = None
        if not cust_no:
            error = "Customer number is required!"
        if not order_no:
            error = "Order number is required!"
        
        if error is not None:
            flash(error)
        else:
            try:
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO pay (order_no, cust_no)
                            VALUES (%(order_no)s, %(cust_no)s);
                            """,
                            {"cust_no": cust_no, "order_no": order_no},
                        )
                    conn.commit()
            except psycopg.errors.DatabaseError as error:
                #flash(str(error))
                error_message = str(error)
                if re.search(r'Key \(cust_no\)=\(\d+\) is not present in table "customer"', error_message):
                    error = "Customer does not exist!"
                    flash(error)
                    return render_template("order/pay.html", order_no=order_no)
                if re.search(r'Key \(order_no\)=\(\d+\) already exists', error_message):
                    error = "Order has already been paid!"
                    flash(error)
                    error = ""
                # Handle other database errors
                if error:
                    error = "An error occurred while creating the order."
                    flash(error)
            return redirect(url_for("order_index"))

    return render_template("order/pay.html", order_no=order_no)

@app.route("/order/create_order", methods=("GET","POST"))
def order_create():
    """Create a new order."""


    if request.method == "POST":
        cust_no = request.form["cust_no"]
        date = request.form["date"]
        skus = request.form['selected_products'] 
        skus_data = json.loads(skus)
        
        error = None

        #flash(skus)
        if len(skus_data) == 0:
            error = ('Order is empty')
        if not cust_no:
            error = "Customer Number is required!"
        if not date:
            error = "Date is required!"
        if error is not None:
            flash(error)
        else:
            try:
                with pool.connection() as conn:
                    with conn.cursor(row_factory=namedtuple_row) as cur:
                        order_n = cur.execute("""SELECT COALESCE(MAX(order_no),0)+1 FROM orders""").fetchone()
                        cur.execute(
                            """
                            INSERT INTO orders (order_no, cust_no, date)
                            VALUES (%(order_n)s, %(cust_no)s, %(date)s);
                            """,
                            {"order_n":order_n[0],"cust_no": cust_no, "date": date},
                        )
                        
                        for key in skus_data.keys():
                            cur.execute("SELECT sku FROM product WHERE sku = %s", (key,))
                            if cur.rowcount == 0:
                                error = 'There is no product with the following sku: ' + key + '.'
                                conn.rollback()
                                flash(error)
                                return render_template("order/create.html")
                            cur.execute(
                                """
                                INSERT INTO contains (order_no,SKU,qty)
                                VALUES (%(order_n)s, %(sku)s, %(qt)s)
                                """,
                                {"order_n":order_n[0],"sku":key,"qt":skus_data[key]},
                            )
                    conn.commit()
                return redirect(url_for("order_index"))
            except psycopg.DatabaseError as error:
                error_message = str(error)
                if re.search(r'Key \(cust_no\)=\(\d+\) is not present in table "customer"', error_message):
                    error = "Customer does not exist!"
                    flash(error)
                else:
                    # Handle other database errors
                    flash(error)
                    error = "An error occurred while creating the order."
                    flash(error)


    return render_template("order/create.html")

@app.route("/ping", methods=("GET",))
def ping():
    log.debug("ping!")
    return jsonify({"message": "pong!", "status": "success"})

if __name__ == "__main__":
    app.run()
