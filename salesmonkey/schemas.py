from flask import session

import satchless.item
import satchless.cart

from salesmonkey import ma


class Item(satchless.item.Item):
    def __init__(self, code, name, price=0):
        self.code = code
        self.name = name
        self.price = float(price)

    def __eq__(self, otherItem):
        return self.code == otherItem.code

    def get_price(self):
        return self.price


class ItemSchema(ma.Schema):
    code = ma.String()
    name = ma.String()
    price = ma.Float()


class CartLineSchema(ma.Schema):
    product = ma.Nested(ItemSchema)
    quantity = ma.Integer()
    line_price = ma.Method("get_line_price", deserialize="load_line_price")

    def get_line_price(self, obj):
        return obj.get_total()

    def load_line_price(self, value):
        return float(value)


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
    grand_total = ma.Method('get_grand_total', deserialize='load_grand_total')

    def get_grand_total(self, obj):
        return obj.get_total()

    def load_grand_total(self, value):
        return float(value)
