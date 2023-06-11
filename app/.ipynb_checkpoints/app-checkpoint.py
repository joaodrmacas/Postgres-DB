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

@app.route("/clients/create_client", methods=("GET",))
@app.route("/clients/<client_number>/update", methods=("GET",))
def client_update(client_number=-1):
    """View, or delete an account."""
    
    if client_number == -1:
        return render_template("client/create_client.html")
    

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


@app.route("/accounts/<client_number>/delete", methods=("POST",))
def client_delete(client_number):
    """Delete the account."""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                DELETE FROM customer
                WHERE cust_no = %(account_number)s;
                """,
                {"account_number": client_number},
            )
        conn.commit()
    return redirect(url_for("client_index"))








@app.route("/", methods=("GET",))
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
                SELECT account_number, branch_name, balance
                FROM account
                ORDER BY account_number DESC
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

    return render_template("product/index.html", clients=products, page_number=page_number)


@app.route("/supplies", methods=("GET",))
def supply_index(page_number=1):
    return render_template("supply/index.html", clients=products, page_number=page_number)

@app.route("/deliveries", methods=("GET",))
def delivery_index(page_number=1):
    return render_template("delivery/index.html", clients=products, page_number=page_number)






















@app.route("/ping", methods=("GET",))
def ping():
    log.debug("ping!")
    return jsonify({"message": "pong!", "status": "success"})


if __name__ == "__main__":
    app.run()
