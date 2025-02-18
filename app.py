import json
import requests
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
        customer = Customer.create(
            full_name=request.form.get("full_name"),
            address=request.form.get("address")
        )
        return redirect("/customers")
    return render_template("list-customer.html", customers=Customer.select())

@app.route("/new-invoice")
def create_invoice_form():
    return render_template("create-invoice.html", customers=Customer.select())

@app.route("/invoices", methods=["GET", "POST"])
def invoices():
    if request.method == "POST":
        data = request.form
        items = json.loads(data.get("invoice_items"))
        invoice = Invoice.create(
            customer=data.get("customer"),
            date=data.get("date"),
            total_amount=float(data.get("total_amount")),
            tax_percent=float(data.get("tax_percent")),
            payable_amount=float(data.get("total_amount")) + (float(data.get("total_amount")) * float(data.get("tax_percent"))) / 100
        )
        for item in items:
            InvoiceItem.create(
                invoice=invoice,
                item_name=item.get("item_name"),
                qty=int(item.get("qty")),
                rate=float(item.get("price")),
                amount=int(item.get("qty")) * float(item.get("price"))
            )
        invoice.gov_arn = generate_arn(invoice.customer.full_name, invoice.invoice_id, invoice.payable_amount)
        invoice.save()
        return redirect("/invoices")
    return render_template("list-invoice.html", invoices=Invoice.select())

@app.route("/download/<int:invoice_id>")
def download_pdf(invoice_id):
    invoice = Invoice.get_by_id(invoice_id)
    html = HTML(string=render_template("print/invoice.html", invoice=invoice))
    response = make_response(html.write_pdf())
    response.headers["Content-Type"] = "application/pdf"
    return response

@app.route('/customers/<int:customer_id>/delete', methods=['POST'])
def delete_customer(customer_id):
    invoices = Invoice.select().where(Invoice.customer == customer_id)
    for invoice in invoices:
        InvoiceItem.delete().where(InvoiceItem.invoice == invoice).execute()
    Invoice.delete().where(Invoice.customer == customer_id).execute()
    Customer.delete().where(Customer.id == customer_id).execute()
    return redirect(url_for('customers'))

@app.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = Customer.get_by_id(customer_id)
    if request.method == 'POST':
        customer.full_name = request.form['full_name']
        customer.address = request.form['address']
        customer.save()
        return redirect(url_for('customers'))
    return render_template('edit-customer.html', customer=customer)

@app.route('/invoices/<int:invoice_id>/delete', methods=['POST'])
def delete_invoice(invoice_id):
    InvoiceItem.delete().where(InvoiceItem.invoice == invoice_id).execute()
    Invoice.delete().where(Invoice.invoice_id == invoice_id).execute()
    return redirect(url_for('invoices'))

@app.route('/invoices/<int:invoice_id>/edit', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    invoice = Invoice.get_by_id(invoice_id)
    invoice_items = InvoiceItem.select().where(InvoiceItem.invoice == invoice)
    if request.method == 'POST':
        invoice.date = request.form['date']
        invoice.tax_percent = float(request.form['tax_percent'])
        updated_items = json.loads(request.form['invoice_items'])
        deleted_items = json.loads(request.form['deleted_items'])
        for item_id in deleted_items:
            InvoiceItem.delete().where(InvoiceItem.id == item_id).execute()
        for item in updated_items:
            if item['item_id'] == "new":
                InvoiceItem.create(
                    invoice=invoice,
                    item_name=item['item_name'],
                    qty=int(item['qty']),
                    rate=float(item['price']),
                    amount=int(item['qty']) * float(item['price'])
                )
            else:
                invoice_item = InvoiceItem.get(InvoiceItem.id == int(item['item_id']))
                invoice_item.item_name = item['item_name']
                invoice_item.qty = int(item['qty'])
                invoice_item.rate = float(item['price'])
                invoice_item.amount = int(item['qty']) * float(item['price'])
                invoice_item.save()
        invoice.payable_amount = sum(item.amount for item in InvoiceItem.select().where(InvoiceItem.invoice == invoice)) * (1 + invoice.tax_percent / 100)
        invoice.save()
        return redirect('/invoices')
    return render_template('edit-invoice.html', invoice=invoice, invoice_items=invoice_items)

def generate_arn(customer_name, invoice_id, payable_amount):
    url = "https://frappe.school/api/method/generate-pro-einvoice-id"
    data = {"customer_name": customer_name, "invoice_id": invoice_id, "payable_amount": payable_amount}
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json().get("arn")
    except requests.RequestException as e:
        print(f"Error generating ARN: {e}")
        return None
