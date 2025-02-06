## Homework

* Implement edit and delete of customers
* Implement edit and delete of invoices
    * how will you handle delete of invoice items?
* Clean up the JS code
* Fix "calculation" of total amount in backend
* Fake e-Invoicing government portal


### Snippets

Person(Model)

# create a new person in database

p = Person(full_name="John Doe") # Person.create(full_name="John Doe")
p.save()


# Read

p = Person.get_by_id(1)

# Update
p.full_name = "Jenny Doe"
p.save()


# Delete

p.delete_instance()

# List

Person.select()
