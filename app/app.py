#!/usr/bin/python3
import os
from logging.config import dictConfig

import psycopg
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
DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://p3:p3@postgres/p3")

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

    limit = 5  # Set the limit to the desired number of items per page
    offset = (page_number - 1) * limit  # Calculate the offset based on the current page number
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

    # API-like response is returned to clients that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(clients)

    return render_template("client/index.html", clients=clients, page_number=page_number)


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
            with pool.connection() as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    conn.autocommit = False
                    cur.execute(
                        """
                        INSERT INTO customer (cust_no, name, address, phone, email)
                        VALUES (%(cust_no)s, %(name)s, %(address)s, %(phone)s, %(email)s);
                        """,
                        {"cust_no": 15, "name": name, "address": address, "phone": phone, "email": email},
                    )
                #conn.commit()
            return redirect(url_for("client_index"))
        
    return render_template("client/create_client.html")



@app.route("/accounts/<client_number>/delete", methods=("POST",))
def client_delete(client_number):
    """Delete the account."""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                SELECT delete_cust(%s);
                """,
                (int(client_number),)
            )
        conn.commit()
    return redirect(url_for("client_index"))








@app.route("/products", methods=("GET",))
@app.route("/products/<int:page_number>", methods=("GET",))
def product_index(page_number=1):
    """Show all the products, most recent first."""

    if page_number < 1:
        return redirect("/products/1")

    limit = 5  # Set the limit to the desired number of items per page
    offset = (page_number - 1) * limit  # Calculate the offset based on the current page number
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

    # API-like response is returned to clients that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(products)

    return render_template("product/index.html", products=products, page_number=page_number)


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

        if not name:
            error = "Name is required!"
        if not price:
            error = "Price is required!"
        elif price.isnumeric() == False:
            error = "Price must be a number!"
        if not ean:
            error = "EAN is required!"
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
    pass






@app.route("/supplier", methods=("GET",))
@app.route("/supplier/<int:page_number>", methods=("GET",))
def supplier_index(page_number=1):
    
    limit = 5  # Set the limit to the desired number of items per page
    offset = (page_number - 1) * limit  # Calculate the offset based on the current page number
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            supliers = cur.execute(
                """
                SELECT sku, address, name, tin
                FROM supplier
                ORDER BY sku
                LIMIT %s OFFSET %s;
                """,
                (limit, offset),
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

    # API-like response is returned to supliers that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(supliers)
    return render_template("supply/index.html",supliers=supliers,page_number=page_number)

@app.route("/supplier/<supplier_name>/update", methods=("GET",))
@app.route("/supplier/defau/update", methods=("GET",))
def supplier_update(supplier_name=""):
    """View, or delete, or create an account."""
    
    if supplier_name == "":
        return render_template("supply/index.html")
    
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            supplier = cur.execute(
                """
                SELECT name, address, sku, tin
                FROM supplier
                WHERE name = %(supplier_name)s;
                """,
                {"supplier_name": supplier_name},
            ).fetchone()
            log.debug(f"Found {cur.rowcount} rows.")

    return render_template("supply/update.html", supplier=supplier)



@app.route("/supplier/<supplier_name>/delete", methods=("POST",))
def supplier_delete(supplier_name=""):
    """Delete the account."""
    if supplier_name == "":
         return render_template("supply/index.html")
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                DELETE FROM supplier
                WHERE name = %(supplier_name)s;
                """,
                {"supplier_name": supplier_name},
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
        error = None

        #se estao todos preenchidos ou se faltam preencher alguns ou se estao todos vazios
        if all([add is not None for add in [addressS,addressZ,addressC]]):
            address = addressS + " " + addressZ + " " + addressC
        elif any([add is None for add in [addressS,addressZ,addressC]]): 
            error = "Address is incomplete!"
        else:
            address = None

        if not name:
            error = "Name is required!"
        if not sku:
            error = "sku is required!"
        if tin.isnumeric() == False:
            error = "Tin must be a number!"
        

        

        if error is not None:
            flash(error)
        else:
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
    
    return render_template("supply/registerSuplier.html")













@app.route("/orders", methods=("GET",))
@app.route("/orders/<int:page_number>", methods=("GET",))
def order_index(page_number=1):
    
    limit = 5  # Set the limit to the desired number of items per page
    offset = (page_number - 1) * limit  # Calculate the offset based on the current page number
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
    
    return render_template("order/index.html", orders=modified_orders, page_number=page_number)


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

        error = None

        if not cust_no:
            error = "Customer Number is required!"
        if not date:
            error = "Date is required!"
        #elif date.isdate() == False:
        #    error = "Price must be a number!"


        if error is not None:
            flash(error)
        else:
            try:
                with pool.connection() as conn:
                    with conn.cursor(row_factory=namedtuple_row) as cur:
                        cur.execute(
                            """
                            INSERT INTO orders (order_no, cust_no, date)
                            SELECT COALESCE(MAX(order_no), 0) + 1, %(cust_no)s, %(date)s FROM orders;
                            """,
                            {"cust_no": cust_no, "date": date},
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
