import json

from flask import Flask, render_template, request, redirect, make_response

from peewee import SqliteDatabase

from models import Customer, Invoice, InvoiceItem

from weasyprint import HTML

app = Flask(__name__)

db = SqliteDatabase("invoices.db")
db.create_tables([Customer, Invoice, InvoiceItem])


@app.route("/")
def index():
    return "Home Page"


@app.route("/new-customer")
def create_customer_form():
    return render_template("create-customer.html")


@app.route("/customers", methods=["POST", "GET"])
def customers():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        address = request.form.get("address")

        customer = Customer(full_name=full_name, address=address)
        customer.save()
        return redirect("/customers")

    else:
        customers = Customer.select()
        return render_template("list-customer.html", customers=customers)


@app.route("/new-invoice")
def create_invoice_form():
    return render_template("create-invoice.html")


@app.route("/invoices", methods=["GET", "POST"])
def invoices():
    if request.method == "POST":
        data = request.form
        total_amount = float(data.get("total_amount"))
        tax_percent = float(data.get("tax_percent"))

        items_json = data.get("invoice_items")

        items = json.loads(items_json)

        invoice = Invoice(
            customer=data.get("customer"),
            date=data.get("date"),
            total_amount=total_amount,
            tax_percent=tax_percent,
            payable_amount=total_amount + (total_amount * tax_percent) / 100,
        )

        invoice.save()

        for item in items:
            InvoiceItem(
                invoice=invoice,
                item_name=item.get("item_name"),
                qty=item.get("qty"),
                rate=item.get("price"),
                amount=int(item.get("qty")) * float(item.get("price"))
            ).save()

        return redirect("/invoices")
    else:
        return render_template("list-invoice.html", invoices=Invoice.select())


@app.route("/download/<int:invoice_id>")
def download_pdf(invoice_id):
    # get the invoice
    invoice = Invoice.get_by_id(invoice_id)

    # generate the PDF
    html = HTML(string=render_template("print/invoice.html", invoice=invoice))
    response = make_response(html.write_pdf())

    response.headers["Content-Type"] = "application/pdf"

    # send it back to the user
    return response

