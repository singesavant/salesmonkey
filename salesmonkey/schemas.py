from flask import session

import satchless.item
import satchless.cart

from salesmonkey import ma


class ERPDocument(ma.Schema):
    name = ma.String(attribute='name')


class ERPItemSchema(ERPDocument):
    code = ma.String(attribute="item_code")
    description = ma.String(attribute='web_long_description')
    price = ma.Float(attribute='standard_rate')
    thumbnail = ma.String(attribute='thumbnail')


class ERPSalesOrderItemSchema(ERPDocument):
    item_code = ma.String()
    item_name = ma.String()
    description = ma.String()
    quantity = ma.Int(attribute="qty")
    rate = ma.Float()
    amount = ma.Float(attribute="net_amount")


class ERPSalesOrderSchema(ERPDocument):
    name = ma.String(attribute="name")
    date = ma.DateTime(attribute="transaction_date")
    title = ma.String(attribute="title")
    customer = ma.String()
    amount_total = ma.Float(attribute="grand_total")
    items = ma.Nested(ERPSalesOrderItemSchema, many=True)

class Item(satchless.item.Item):
    def __init__(self, code, name):
        self.code = code
        self.name = name

class ItemSchema(ma.Schema):
    code = ma.String()
    name = ma.String()

class CartLineSchema(ma.Schema):
    product = ma.Nested(ItemSchema)
    quantity = ma.String()

class Cart(satchless.cart.Cart):
    @staticmethod
    def from_session():
        cart = session.get('cart', None)
        if cart is None:
            session['cart'] = Cart()

        return session.get('cart')

    @property
    def items(self):
        return list(self)

class CartSchema(ma.Schema):
    items = ma.Nested(CartLineSchema,
                      many=True)
