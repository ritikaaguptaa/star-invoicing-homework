import json

import sqlite3

from flask import Flask, render_template, request, redirect, make_response, url_for

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
    customers = Customer.select()
    return render_template("create-invoice.html", customers=customers)


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

        # Save Invoice Items
        for item in items:
            InvoiceItem(
                invoice=invoice,
                item_name=item.get("item_name"),
                qty=item.get("qty"),
                rate=item.get("price"),
                amount=int(item.get("qty")) * float(item.get("price")),
            ).save()

        # Generate ARN
        arn = generate_arn(
            customer_name=invoice.customer.full_name,
            invoice_id=invoice.invoice_id,
            payable_amount=invoice.payable_amount,
        )

        # Save ARN to Invoice
        if arn:
            invoice.gov_arn = arn
            invoice.save()

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

#getting all customers for customer deletion functionality
@app.route('/customers', methods=['GET'])
def customer_list():
    conn = sqlite3.connect('invoices.db')  
    conn.row_factory = sqlite3.Row
    customers = conn.execute('SELECT * FROM Customer').fetchall()
    conn.close()
    return render_template('customer_list.html', customers=customers)

# Delete customer by ID
@app.route('/customers/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    # Getting invoices associated with the customer
    invoices = Invoice.select().where(Invoice.customer == customer_id)

    # Delete all invoice items associated with the customer's invoices
    for invoice in invoices:
        InvoiceItem.delete().where(InvoiceItem.invoice == invoice).execute()

    # Delete all invoices related to the customer
    Invoice.delete().where(Invoice.customer == customer_id).execute()

    # Now delete the customer
    Customer.delete().where(Customer.id == customer_id).execute()

    return redirect(url_for('customer_list'))

#edit customer functionality
@app.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
def edit_customer(customer_id):
    conn = sqlite3.connect('invoices.db')
    conn.row_factory = sqlite3.Row
    customer = conn.execute('SELECT * FROM Customer WHERE id = ?', (customer_id,)).fetchone()
    conn.close()

    if request.method == 'POST':
        # Get the updated details from the form
        full_name = request.form['full_name']
        address = request.form['address']

        # Update the customer details in the database
        conn = sqlite3.connect('invoices.db')
        conn.execute('UPDATE Customer SET full_name = ?, address = ? WHERE id = ?', 
                     (full_name, address, customer_id))
        conn.commit()
        conn.close()

        return redirect(url_for('customer_list'))

    return render_template('edit-customer.html', customer=customer)

#invoices deletion functionality
@app.route('/invoices/<int:invoice_id>/delete', methods=['POST'])
def delete_invoice(invoice_id):
    # Delete invoice items first
    InvoiceItem.delete().where(InvoiceItem.invoice == invoice_id).execute()

    # Delete the invoice itself
    Invoice.delete().where(Invoice.invoice_id == invoice_id).execute()

    return redirect(url_for('invoices'))


#edit invoices functionality
@app.route('/invoices/<int:invoice_id>/edit', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    # Fetch the invoice and its associated items
    invoice = Invoice.get(Invoice.invoice_id == invoice_id)
    invoice_items = InvoiceItem.select().where(InvoiceItem.invoice == invoice)

    if request.method == 'POST':
        # Update invoice details
        invoice.date = request.form['date']
        invoice.tax_percent = float(request.form['tax_percent'])

        # Handle items
        updated_items = json.loads(request.form['invoice_items'])
        deleted_items = json.loads(request.form['deleted_items'])

        # Delete marked items
        for item_id in deleted_items:
            InvoiceItem.delete().where(InvoiceItem.id == item_id).execute()

        # Update or add new items
        for item in updated_items:
            if item['item_id'] == "new":
                # Add new item
                InvoiceItem.create(
                    invoice=invoice,
                    item_name=item['item_name'],
                    qty=int(item['qty']),
                    rate=float(item['price']),
                    amount=int(item['qty']) * float(item['price'])
                )
            else:
                # Update existing item
                invoice_item = InvoiceItem.get(InvoiceItem.id == int(item['item_id']))
                invoice_item.item_name = item['item_name']
                invoice_item.qty = int(item['qty'])
                invoice_item.rate = float(item['price'])
                invoice_item.amount = int(item['qty']) * float(item['price'])
                invoice_item.save()

        # Fetch updated items
        updated_invoice_items = InvoiceItem.select().where(InvoiceItem.invoice == invoice)

        # Calculate subtotal
        subtotal = sum(item.amount for item in updated_invoice_items)

        # Calculate tax
        tax_amount = (subtotal * invoice.tax_percent) / 100

        # Update payable amount
        invoice.payable_amount = subtotal + tax_amount
        invoice.save()

        return redirect('/invoices')

    return render_template('edit-invoice.html', invoice=invoice, invoice_items=invoice_items)


import requests

def generate_arn(customer_name, invoice_id, payable_amount):
    url = "https://frappe.school/api/method/generate-pro-einvoice-id"
    data = {
        "customer_name": customer_name,
        "invoice_id": invoice_id,
        "payable_amount": payable_amount
    }
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  
        response_data = response.json()
        return response_data.get("arn")
    except requests.RequestException as e:
        print(f"Error generating ARN: {e}")
        return None
