from flask import session

import satchless.item
import satchless.cart

from salesmonkey import ma


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
